/**
 * Krude - Main Application Controller
 * Ultra-responsive UI, native fast scrolling, rich Indian maritime map canvas,
 * multi-stage waterfall impact cards, prediction vs reality intelligence, and interactive twin reset.
 */

document.addEventListener("DOMContentLoaded", () => {
  initNativeSmoothScroll();
  initPreloader();
  initHeroStats();
  initSupplyDisruptionStrip();
  initProblemCoastalMap();
  initRiskBoard();
  initHeadlineTicker();
  initRiskVsBrentChart();
  initScenarioSimulator();
  initProcurementList();
  initReserveChart();
  initDigitalTwinMap();
  initModelSandbox();
  initLegalModals();
  initScrollAnimations();
});

function initSupplyDisruptionStrip() {
  const clockEl = document.getElementById("sp-live-clock");
  const searchInput = document.getElementById("sp-supplier-search");
  const tabs = document.querySelectorAll("#sp-filter-tabs .sp-tab");
  const tableContainer = document.getElementById("sp-suppliers-table");

  // 1. Live Ticking Clock (Updates genuinely in Indian Standard Time IST every 1s)
  function updateLiveClock() {
    if (!clockEl) return;
    const now = new Date();
    try {
      const istTimeStr = now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
      clockEl.textContent = `${istTimeStr} IST`;
    } catch (e) {
      // Fallback manual offset (+5h 30m)
      const istMs = now.getTime() + (5.5 * 60 * 60 * 1000);
      const istDate = new Date(istMs);
      const h = String(istDate.getUTCHours()).padStart(2, '0');
      const m = String(istDate.getUTCMinutes()).padStart(2, '0');
      const s = String(istDate.getUTCSeconds()).padStart(2, '0');
      clockEl.textContent = `${h}:${m}:${s} IST`;
    }
  }
  updateLiveClock();
  setInterval(updateLiveClock, 1000);

  // 2. Filled from /api/risk/supply-disruption-probabilities (no hardcoded fallback values)
  let allSuppliers = [];
  let probabilitiesLoaded = false;
  const corridorList = document.getElementById("sp-corridors-list");
  const coveredBadge = document.getElementById("sp-covered-badge");

  function probColor(p) {
    // Calibrated 30-day probabilities top out near 11%
    return p >= 0.07 ? "red" : (p >= 0.04 ? "amber" : "green");
  }

  function renderCorridors(corridors) {
    if (!corridorList) return;
    corridorList.innerHTML = "";
    corridors.forEach(c => {
      const item = document.createElement("div");
      item.className = "sp-corridor-item";
      if (c.top_event) item.title = `Strongest recent event: ${c.top_event}`;

      const name = document.createElement("div");
      name.className = "sp-c-name";
      name.textContent = c.corridor;

      const val = document.createElement("div");
      val.className = `sp-c-val text-${probColor(c.p_disruption_30d)}`;
      val.textContent = `${c.p_display} `;
      const mom = document.createElement("span");
      const momColor = c.trend === "up" ? "text-red" : (c.trend === "down" ? "text-green" : "text-dim");
      mom.className = `sp-momentum ${momColor}`;
      const arrow = c.trend === "up" ? "↗ " : (c.trend === "down" ? "↘ " : "");
      mom.textContent = `${arrow}${c.momentum}`;
      val.appendChild(mom);

      const sub = document.createElement("div");
      sub.className = "sp-c-sub";
      sub.textContent = `${c.inflow_desc} · ${c.active_events_count} live event${c.active_events_count === 1 ? "" : "s"} in window`;

      item.append(name, val, sub);
      corridorList.appendChild(item);
    });
  }

  let currentRegion = "all";
  let currentSearch = "";

  function renderSuppliers() {
    if (!tableContainer) return;
    const filtered = allSuppliers.filter(item => {
      const matchRegion = currentRegion === "all" || item.region.toLowerCase() === currentRegion.toLowerCase();
      const matchSearch = !currentSearch || item.supplier.toLowerCase().includes(currentSearch.toLowerCase()) || (item.best_route && item.best_route.toLowerCase().includes(currentSearch.toLowerCase()));
      return matchRegion && matchSearch;
    });

    if (filtered.length === 0) {
      const msg = probabilitiesLoaded ? "No suppliers match your search query." : "Loading live probabilities…";
      tableContainer.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-dim); font-size: 0.85rem;">${msg}</div>`;
      return;
    }

    tableContainer.innerHTML = filtered.map(s => {
      const pColor = `text-${probColor(s.p_supply_disruption)}`;
      const bColor = `bg-${probColor(s.p_supply_disruption)}`;
      const riskColor = s.at_risk_kbd > 0 ? (s.at_risk_kbd > 20 ? "text-red" : "text-amber") : "text-green";
      const hasOfac = s.sanctions_friction_multiplier > 1.0 || s.ofac_records_count > 0;
      
      return `
        <div class="sp-sup-row" title="Route-weighted live corridor risk${hasOfac ? ' × 1.15 OFAC sanctions friction' : ''}">
          <div class="sp-sup-info">
            <div class="sp-sup-name-row">
              <span class="sp-sup-name">${s.supplier}</span>
              <span class="sp-sup-region">${s.region}</span>
              ${hasOfac ? '<span class="sp-sup-tag-ofac">OFAC Scrutiny</span>' : ''}
              <span style="font-size:0.72rem; color:var(--text-dim); font-family:var(--font-mono); margin-left:auto; padding-right:8px;">${s.baseline_flow_kbd} kbd</span>
            </div>
            <div class="sp-sup-meta-row">
              <span class="sp-sup-note">${s.best_route}</span>
              <span class="sp-sup-shipping" title="${s.vulnerability_reason}"><i class="fa-solid fa-ship"></i> ${s.vulnerability_reason}</span>
            </div>
          </div>
          <div class="sp-sup-prob ${pColor}">${s.p_display}</div>
          <div class="sp-sup-bar-wrap">
            <div class="sp-sup-bar ${bColor}" style="width: ${Math.max(3, s.bar_pct)}%;"></div>
          </div>
          <div class="sp-sup-risk font-mono ${riskColor}">${s.at_risk_kbd} kbd</div>
        </div>
      `;
    }).join("");
  }

  // Bind tabs
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentRegion = tab.getAttribute("data-region");
      renderSuppliers();
    });
  });

  // Bind search input
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      currentSearch = e.target.value.trim();
      renderSuppliers();
    });
  }

  renderSuppliers();

  // 3. Live Polling Sync
  function fetchLiveProbabilities() {
    if (typeof fetch !== "undefined") {
      fetch("/api/risk/supply-disruption-probabilities")
        .then(res => res.ok ? res.json() : null)
        .then(data => {
          if (!data || !data.suppliers) return;
          probabilitiesLoaded = true;
          allSuppliers = data.suppliers;
          renderSuppliers();
          renderCorridors(data.corridors || []);
          if (coveredBadge) {
            coveredBadge.textContent = `${data.suppliers.length} Nations · ${Math.round(data.total_import_covered_kbd).toLocaleString()} kbd`;
          }
        })
        .catch(() => {});
    }
  }

  fetchLiveProbabilities();
  setInterval(fetchLiveProbabilities, 30000); // 30s auto sync
}

/* ==============================================================================
   1. INSTANT NATIVE SCROLL & HEADER COLOR REACTION (Zero Lag)
   ============================================================================== */
function initNativeSmoothScroll() {
  const header = document.getElementById("site-header");

  // Instant scroll listener with passive flag for 60fps performance
  window.addEventListener("scroll", () => {
    if (window.scrollY > 60) {
      header.classList.add("scrolled");
    } else {
      header.classList.remove("scrolled");
    }
  }, { passive: true });

  // Fast Native Anchor Scrolling
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.getAttribute("href");
      if (targetId === "#") return;
      const targetEl = document.querySelector(targetId);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
}

/* ==============================================================================
   2. PRELOADER
   ============================================================================== */
function initPreloader() {
  const preloader = document.getElementById("loading-screen");
  if (!preloader) return;

  setTimeout(() => {
    preloader.classList.add("loaded");
  }, 400);
}

/* ==============================================================================
   3. HERO STATS COUNT-UP ANIMATION
   ============================================================================== */
function initHeroStats() {
  const statElements = document.querySelectorAll(".stat-num");

  setTimeout(() => {
    statElements.forEach(el => {
      const target = parseFloat(el.getAttribute("data-target") || 0);
      const suffix = el.getAttribute("data-suffix") || "";
      const decimals = parseInt(el.getAttribute("data-decimals") || 0);
      const isScary = el.classList.contains("stat-scary");

      const duration = isScary ? 1400 : 1000;
      const startTime = performance.now();

      function updateNumber(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
        const current = target * ease;

        el.textContent = current.toFixed(decimals) + suffix;

        if (progress < 1) {
          requestAnimationFrame(updateNumber);
        } else {
          el.textContent = target.toFixed(decimals) + suffix;
        }
      }

      requestAnimationFrame(updateNumber);
    });
  }, 250);
}

/* ==============================================================================
   4. THE PROBLEM (Rich Coastal Map of India & Maritime Inflows - Static Basemap)
   ============================================================================== */
// Mercator Projection bounds matching basemap.svg
const LON_MIN = 15.0, LON_MAX = 112.0;
const Y_MIN = -41.137682, Y_MAX = 41.137682; // mercator y of lat -38 / +38

const mercY = lat => (180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI / 180) / 2));

function projectGeo(lon, lat) {
  return {
    left: ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * 100, // %
    top: ((Y_MAX - mercY(lat)) / (Y_MAX - Y_MIN)) * 100  // %
  };
}

// Zero-Size Anchor Marker Builder (Dots Only)
function createMarkerElement(node, isDimmed, projectionFn = projectGeo) {
  const pos = projectionFn(node.lon, node.lat);

  const el = document.createElement("div");
  el.className = "mk";
  el.style.left = `${pos.left.toFixed(2)}%`;
  el.style.top = `${pos.top.toFixed(2)}%`;
  if (isDimmed) el.style.opacity = "0.25";
  if (node.name) {
    el.setAttribute("title", `${node.name}${node.sub ? ' (' + node.sub + ')' : ''}`);
  }

  const color = node.color || "#e6e9ef";

  el.innerHTML = `
    <span class="mk-dot" style="background: ${color};"></span>
    ${(node.isIndia || node.isChoke) ? `<span class="mk-pulse" style="color: ${color};"></span>` : ''}
  `;
  return el;
}

function initProblemCoastalMap() {
  const routesSvg = document.getElementById("problem-routes-svg");
  const markersLayer = document.getElementById("problem-markers-layer");
  if (!markersLayer || !routesSvg) return;

  const mapNodes = {
    // Chokepoints & Foreign Hubs (Split name & sub, custom edge flipX/flipY)
    hormuz: { lon: 56.25, lat: 26.56, name: "Strait of Hormuz", sub: "", color: "#EF4444", isChoke: true, flipX: true, nudgeY: -6 },
    babelmandeb: { lon: 43.33, lat: 12.58, name: "Bab-el-Mandeb", sub: "", color: "#F59E0B", isChoke: true, flipX: true, nudgeY: 4 },
    malacca: { lon: 102.89, lat: 1.43, name: "Malacca Strait", sub: "", color: "#10B981", isChoke: true, flipX: true, nudgeY: -4 },
    cape: { lon: 18.47, lat: -34.35, name: "Cape of Good Hope", sub: "", color: "#38BDF8", isChoke: true, flipY: true, nudgeY: -8 },
    
    // Indian Coastal Hubs & Refineries (fine-tuned cartographic vertical nudges)
    jamnagar: { lon: 70.06, lat: 22.47, name: "Jamnagar / Vadinar", sub: "", color: "#FFFFFF", isIndia: true, nudgeY: -14 },
    mumbai: { lon: 72.84, lat: 18.94, name: "Mumbai Hub", sub: "Refining hub", color: "#FFFFFF", isIndia: true, nudgeY: 8 },
    mangalore: { lon: 74.85, lat: 12.91, name: "Mangalore", sub: "MRPL + ISPRL", color: "#E11D48", isIndia: true, isSPR: true, nudgeY: 4 },
    kochi: { lon: 76.26, lat: 9.93, name: "Kochi", sub: "", color: "#FFFFFF", isIndia: true, nudgeY: 8 },
    vizag: { lon: 83.21, lat: 17.68, name: "Visakhapatnam", sub: "HPCL + ISPRL", color: "#E11D48", isIndia: true, isSPR: true, nudgeY: -12 },
    paradip: { lon: 86.67, lat: 20.26, name: "Paradip", sub: "", color: "#FFFFFF", isIndia: true, nudgeY: 10 }
  };

  // Line width = the corridor's share of imports (filled from /api/database/corridor-exposure)
  const supplyRoutes = [
    { from: "hormuz", to: "jamnagar", key: "hormuz", share: 0, color: "#EF4444", name: "Hormuz", curveOffset: -35 },
    { from: "babelmandeb", to: "jamnagar", key: "bab_el_mandeb", share: 0, color: "#F59E0B", name: "Bab-el-Mandeb", curveOffset: -40 },
    { from: "malacca", to: "paradip", key: "malacca", share: 0, color: "#10B981", name: "Malacca", curveOffset: 25 },
    { from: "cape", to: "jamnagar", key: "cape_of_good_hope", share: 0, color: "#38BDF8", name: "Cape of Good Hope", curveOffset: -60 }
  ];
  const nodeKey = { hormuz: "hormuz", babelmandeb: "bab_el_mandeb", malacca: "malacca", cape: "cape_of_good_hope" };
  const NAMES = { hormuz: "the Strait of Hormuz", bab_el_mandeb: "Bab-el-Mandeb", suez: "the Suez Canal", malacca: "the Malacca Strait", cape_of_good_hope: "the Cape of Good Hope" };
  const DOMESTIC_KBD = 580;  // India's own crude output, assumptions.yaml (scenario_model.india_domestic_crude_kbd)
  let focusKey = "hormuz";
  let badgeText = {};

  async function loadStoryNumbers() {
    try {
      const [eRes, gRes] = await Promise.all([fetch("/api/database/corridor-exposure"), fetch("/api/digital-twin/graph")]);
      const exp = await eRes.json();
      const total = exp.total_import_demand_kbd;
      const c = exp.corridors;
      const fmt = k => `${Math.round(k).toLocaleString()} kbd`;

      Object.entries(nodeKey).forEach(([node, key]) => { mapNodes[node].sub = fmt(c[key].volume_at_risk_kbd); });
      supplyRoutes.forEach(r => { r.share = c[r.key].share_of_india_imports_pct / 100; });
      if (gRes.ok) {
        const ports = (await gRes.json()).discharge_port_kbd || {};
        mapNodes.jamnagar.sub = fmt((ports.Jamnagar || 0) + (ports.Vadinar || 0) + (ports.Mundra || 0));
        mapNodes.kochi.sub = fmt(ports.Kochi || 0);
        mapNodes.paradip.sub = fmt(ports.Paradip || 0);
      }

      const importShare = 100 * total / (total + DOMESTIC_KBD);
      setText("story-import-share", `${importShare.toFixed(1)}%`);
      setText("story-import-mbpd", (total / 1000).toFixed(2));
      setText("story-import-kbd", fmt(total));

      // Bab-el-Mandeb also carries the Suez barrels, so rank the four map corridors by their own volume
      const ranked = ["hormuz", "bab_el_mandeb", "malacca", "cape_of_good_hope"].sort((a, b) => c[b].volume_at_risk_kbd - c[a].volume_at_risk_kbd);
      focusKey = ranked[0];
      setText("story-top-share", `${c[focusKey].share_of_india_imports_pct.toFixed(1)}%`);
      setText("story-top-name", NAMES[focusKey]);
      setText("story-hormuz-kbd", fmt(c.hormuz.volume_at_risk_kbd));
      setText("story-redsea-kbd", fmt(c.bab_el_mandeb.volume_at_risk_kbd));
      setText("story-concentration-body",
        `Hormuz carries ${c.hormuz.share_of_india_imports_pct.toFixed(1)}% (${fmt(c.hormuz.volume_at_risk_kbd)}), ` +
        `Bab-el-Mandeb ${c.bab_el_mandeb.share_of_india_imports_pct.toFixed(1)}%, the Cape ${c.cape_of_good_hope.share_of_india_imports_pct.toFixed(1)}% ` +
        `and Malacca ${c.malacca.share_of_india_imports_pct.toFixed(1)}%, from the latest three months of imports.`);
      badgeText = {
        dependency: `Total Maritime Inflow Map (${importShare.toFixed(1)}% imported)`,
        concentration: `${NAMES[focusKey].replace(/^the /, "")} Concentration (${c[focusKey].share_of_india_imports_pct.toFixed(1)}% of Imports)`,
      };
      renderMap();
    } catch (e) { /* story keeps its placeholders */ }
  }

  let currentBeat = "dependency";

  function renderMap() {
    // 1. Render Markers with zero-size anchor
    markersLayer.innerHTML = "";
    Object.keys(mapNodes).forEach(k => {
      const node = mapNodes[k];
      const isDimmed = (currentBeat === "concentration" && !node.isIndia && nodeKey[k] !== focusKey);
      const el = createMarkerElement(node, isDimmed);
      markersLayer.appendChild(el);
    });

    // 2. Render Route Curves into SVG overlay (viewBox 0 0 1000 848.2)
    routesSvg.innerHTML = "";
    supplyRoutes.forEach(r => {
      const src = mapNodes[r.from];
      const dst = mapNodes[r.to];
      if (!src || !dst) return;

      const p1 = projectGeo(src.lon, src.lat);
      const p2 = projectGeo(dst.lon, dst.lat);

      const x1 = p1.left * 10;
      const y1 = p1.top * 8.482;
      const x2 = p2.left * 10;
      const y2 = p2.top * 8.482;

      const dx = x2 - x1;
      const dy = y2 - y1;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2;

      // Perpendicular control point
      const nx = -dy / dist;
      const ny = dx / dist;
      const curve = r.curveOffset || (dist * 0.15);
      const cx = midX + nx * curve;
      const cy = midY + ny * curve;

      let opacity = 0.85;
      let strokeWidth = Math.max(1.5, r.share * 18);

      if (currentBeat === "concentration") {
        if (r.key !== focusKey) {
          opacity = 0.15;
          strokeWidth = 1.2;
        } else {
          opacity = 1.0;
          strokeWidth = 9.0;
        }
      } else if (currentBeat === "buffer") {
        opacity = 0.30;
        strokeWidth = 1.8;
      }

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`);
      path.setAttribute("class", "route-arc");
      path.setAttribute("stroke", r.color);
      path.setAttribute("stroke-width", strokeWidth);
      path.setAttribute("stroke-opacity", opacity);
      routesSvg.appendChild(path);
    });
  }

  renderMap();
  loadStoryNumbers();

  // Scroll Synchronization for the 3 Beats
  const beats = document.querySelectorAll(".narrative-beat");
  const stateBadge = document.getElementById("map-state-badge");

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        beats.forEach(b => b.classList.remove("active-beat"));
        entry.target.classList.add("active-beat");
        currentBeat = entry.target.getAttribute("data-beat") || "dependency";

        if (stateBadge) {
          if (currentBeat === "dependency") stateBadge.querySelector(".state-text").textContent = badgeText.dependency || "Total Maritime Inflow Map";
          else if (currentBeat === "concentration") stateBadge.querySelector(".state-text").textContent = badgeText.concentration || "Chokepoint Concentration";
          else if (currentBeat === "buffer") stateBadge.querySelector(".state-text").textContent = "Strategic Reserve Buffer (9.5 Days Sovereign Cover)";
        }
        renderMap();
      }
    });
  }, { threshold: 0.55 });

  beats.forEach(b => observer.observe(b));
}


/* ==============================================================================
   5. LIVE RISK BOARD (from /api/risk/threat-board)
   ============================================================================== */
// Filled from the API. score = live index x 10; stages are the pipeline's real intermediate values.
const CHOKEPOINTS_DATA = {};
const LIVE_BOARD = {};   // untouched copy of the API values, for "Reset corridor"
let activeSelectedCorridor = "Hormuz";

// Same formulas as backend/engine/risk_pipeline.py, so the what-if sliders reproduce the live index
function computeIndex(st) {
  const clamp = v => Math.max(0.05, Math.min(0.98, v));
  const s = st.strongest_event, c = st.corroboration;
  const index = s > 0 ? clamp(s + (1 - s) * (c > 0 ? c / (1 + c) : 0)) : 0.05;
  const index7 = Math.max(0.05, index - st.change_7d);
  const delta = index - index7;
  const afterMomentum = clamp(delta > 0 ? index * (1 + Math.min(0.35, 0.4 * delta)) : index);
  const final = clamp(afterMomentum * st.sanctions_multiplier);
  return { index, afterMomentum, final, score: Math.round(final * 100) / 10, p30: 0.0022 + 0.108 * final };
}

function getThreatInfo(score) {
  if (score >= 7.0) {
    return { text: "CRITICAL", stateClass: "state-red", ringClass: "ring-red", pillClass: "threat-red", color: "var(--accent-red)", strokeHex: "#EF4444" };
  } else if (score >= 4.0) {
    return { text: "ELEVATED", stateClass: "state-amber", ringClass: "ring-amber", pillClass: "threat-amber", color: "var(--accent-amber)", strokeHex: "#F59E0B" };
  }
  return { text: "LOW", stateClass: "state-green", ringClass: "ring-green", pillClass: "threat-green", color: "var(--accent-green)", strokeHex: "#10B981" };
}

function updateAllCorridorCards() {
  Object.keys(CHOKEPOINTS_DATA).forEach(ck => {
    const data = CHOKEPOINTS_DATA[ck];
    const cardEl = document.querySelector(`.chokepoint-card[data-corridor="${ck}"]`);
    if (!cardEl) return;

    const isActive = (ck === activeSelectedCorridor);
    const threat = getThreatInfo(data.score);
    cardEl.classList.remove("active-card", "state-red", "state-amber", "state-green");

    const bigNum = cardEl.querySelector(".gauge-big-num");
    if (bigNum) bigNum.textContent = data.score.toFixed(1);

    const ring = cardEl.querySelector(".gauge-bar-ring");
    if (ring) {
      ring.style.strokeDashoffset = 264 - (264 * (data.score / 10));
      ring.classList.remove("ring-white", "ring-red", "ring-amber", "ring-green");
    }

    const exposureEl = cardEl.querySelector(".card-footer-stats span:first-child");
    if (exposureEl) exposureEl.textContent = `${Math.round(data.exposure_kbd).toLocaleString()} kbd · P30 ${(data.p30 * 100).toFixed(1)}%`;

    const pill = cardEl.querySelector(".threat-pill");
    if (pill) {
      pill.classList.remove("threat-neutral", "threat-red", "threat-amber", "threat-green");
      pill.textContent = data.overridden ? `${threat.text} · WHAT-IF` : threat.text;
    }

    if (isActive) {
      cardEl.classList.add("active-card", threat.stateClass);
      if (ring) ring.classList.add(threat.ringClass);
      if (pill) pill.classList.add(threat.pillClass);
      if (bigNum) bigNum.style.color = threat.color;
    } else {
      if (ring) ring.classList.add("ring-white");
      if (pill) pill.classList.add("threat-neutral");
      if (bigNum) bigNum.style.color = "var(--text-pure)";
    }
  });

  drawAllSparklines();
}

const SLIDERS = {
  news: { key: "strongest_event", toSlider: v => v * 10, fromSlider: v => v / 10, fmt: v => `${(v * 10).toFixed(1)} / 10` },
  price: { key: "corroboration", toSlider: v => v, fromSlider: v => v, fmt: v => v.toFixed(2) },
  vessel: { key: "change_7d", toSlider: v => v, fromSlider: v => v, fmt: v => `${v >= 0 ? "+" : ""}${v.toFixed(2)}` },
  sanctions: { key: "sanctions_multiplier", toSlider: v => v, fromSlider: v => v, fmt: v => `×${v.toFixed(2)}` },
};

function initRiskBoard() {
  const cards = document.querySelectorAll(".chokepoint-card");

  function syncSlidersToActiveCorridor() {
    const data = CHOKEPOINTS_DATA[activeSelectedCorridor];
    if (!data) return;
    setText("weights-panel-title", `${activeSelectedCorridor}: What-if on the live pipeline`);
    Object.entries(SLIDERS).forEach(([id, cfg]) => {
      const el = document.getElementById(`slider-${id}`);
      if (el) el.value = cfg.toSlider(data.stages[cfg.key]);
      setText(`val-weight-${id}`, cfg.fmt(data.stages[cfg.key]));
    });
    updateSignalBreakdownTable();
  }

  cards.forEach(card => {
    card.addEventListener("click", () => {
      activeSelectedCorridor = card.getAttribute("data-corridor") || "Hormuz";
      syncSlidersToActiveCorridor();
      updateAllCorridorCards();
    });
  });

  function onSliderChange() {
    const data = CHOKEPOINTS_DATA[activeSelectedCorridor];
    if (!data) return;
    Object.entries(SLIDERS).forEach(([id, cfg]) => {
      const el = document.getElementById(`slider-${id}`);
      if (el) data.stages[cfg.key] = cfg.fromSlider(parseFloat(el.value));
      setText(`val-weight-${id}`, cfg.fmt(data.stages[cfg.key]));
    });
    const r = computeIndex(data.stages);
    data.score = r.score;
    data.p30 = r.p30;
    data.overridden = true;
    updateAllCorridorCards();
    updateSignalBreakdownTable();
    if (activeProcurementMode === "sim") refreshProcurementOrchestrator();
  }

  Object.keys(SLIDERS).forEach(id => {
    const el = document.getElementById(`slider-${id}`);
    if (el) el.addEventListener("input", onSliderChange);
  });

  const resetBtn = document.getElementById("reset-weights-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", (e) => {
      if (e) e.preventDefault();
      const live = LIVE_BOARD[activeSelectedCorridor];
      if (!live) return;
      CHOKEPOINTS_DATA[activeSelectedCorridor] = JSON.parse(JSON.stringify(live));
      syncSlidersToActiveCorridor();
      updateAllCorridorCards();
      if (activeProcurementMode === "sim") refreshProcurementOrchestrator();
    });
  }

  async function loadBoard() {
    try {
      const res = await fetch("/api/risk/threat-board");
      if (!res.ok) return;
      const board = await res.json();
      board.corridors.forEach(c => {
        const entry = {
          score: c.risk_score,
          p30: c.p_disruption_30d,
          exposure_kbd: c.exposure_kbd,
          headlines_in_window: c.headlines_in_window,
          top_events: c.top_events,
          history: c.history.map(h => h.risk_score),
          stages: {
            strongest_event: c.strongest_event,
            corroboration: c.corroboration,
            change_7d: Math.round((c.news_index - c.news_index_7d_ago) * 1000) / 1000,
            sanctions_multiplier: c.sanctions_multiplier,
          },
        };
        LIVE_BOARD[c.corridor] = JSON.parse(JSON.stringify(entry));
        // Keep an analyst's what-if across refreshes
        if (!(CHOKEPOINTS_DATA[c.corridor] && CHOKEPOINTS_DATA[c.corridor].overridden)) {
          CHOKEPOINTS_DATA[c.corridor] = entry;
        }
      });
      setText("threat-board-basis", `Live: ${board.history_headlines} stored headlines · as of ${board.as_of}`);
      syncSlidersToActiveCorridor();
      updateAllCorridorCards();
    } catch (e) {
      setText("threat-board-basis", "Threat board unavailable: backend not reachable");
    }
  }

  loadBoard();
  setInterval(loadBoard, 5 * 60 * 1000);
}

function updateSignalBreakdownTable() {
  const data = CHOKEPOINTS_DATA[activeSelectedCorridor];
  if (!data) return;
  setText("breakdown-corridor-title", `${activeSelectedCorridor}: How the index is built`);

  const st = data.stages;
  const r = computeIndex(st);
  const rows = {
    news: [`${(st.strongest_event * 10).toFixed(1)} / 10`, "strongest event today", st.strongest_event > 0 ? st.strongest_event : 0.05],
    price: [st.corroboration.toFixed(2), "damped corroboration", r.index],
    vessel: [`${st.change_7d >= 0 ? "+" : ""}${st.change_7d.toFixed(2)}`, `×${(r.afterMomentum / r.index).toFixed(3)} momentum`, r.afterMomentum],
    sanctions: [`×${st.sanctions_multiplier.toFixed(2)}`, "sanctions factor", r.final],
  };
  Object.entries(rows).forEach(([id, [input, effect, after]]) => {
    setText(`raw-sig-${id}`, input);
    setText(`wt-sig-${id}`, effect);
    setText(`contrib-sig-${id}`, (after * 10).toFixed(2));
  });
  setText("breakdown-result", `Index ${r.score.toFixed(1)} / 10 → P(disruption, 30 days) ${(r.p30 * 100).toFixed(1)}% · ${data.headlines_in_window} headline${data.headlines_in_window === 1 ? "" : "s"} in the 45-day window`);

  const evEl = document.getElementById("breakdown-top-events");
  if (evEl) {
    evEl.innerHTML = "";
    (data.top_events || []).forEach(e => {
      const li = document.createElement("li");
      li.textContent = `${e.date} · scored ${e.raw_score.toFixed(1)}/10, weight today ${e.weight_now.toFixed(2)} · ${e.title}${e.source ? ` (${e.source})` : ""}`;
      evEl.appendChild(li);
    });
    if (!evEl.children.length) {
      const li = document.createElement("li");
      li.textContent = "No live headlines for this corridor in the last 45 days.";
      evEl.appendChild(li);
    }
  }
}

function drawAllSparklines() {
  const canvasIds = {
    "Hormuz": "sparkline-hormuz",
    "Bab-el-Mandeb": "sparkline-babelmandeb",
    "Suez": "sparkline-suez",
    "Malacca": "sparkline-malacca",
    "Cape of Good Hope": "sparkline-cape"
  };

  Object.entries(canvasIds).forEach(([ck, id]) => {
    const canvas = document.getElementById(id);
    const data = CHOKEPOINTS_DATA[ck];
    if (!canvas || !data || !data.history || data.history.length < 2) return;
    const ctx = canvas.getContext("2d");
    const vals = data.history;
    const w = canvas.width, h = canvas.height;
    const isActive = (ck === activeSelectedCorridor);

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = isActive ? getThreatInfo(data.score).strokeHex : "rgba(255, 255, 255, 0.4)";
    ctx.lineWidth = isActive ? 2.5 : 1.5;
    ctx.beginPath();
    // Fixed 0-10 scale so corridors are comparable
    vals.forEach((v, idx) => {
      const x = (idx / (vals.length - 1)) * (w - 10) + 5;
      const y = h - 6 - (v / 10) * (h - 12);
      if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}
/* ==============================================================================
   6. LIVE GDELT HEADLINE TICKER & HERO MODEL SCORE SYNC
   ============================================================================== */
let cachedTickerArticles = [];
let tickerRefreshInterval = null;

async function initHeadlineTicker() {
  const row1 = document.getElementById("marquee-row-1");
  const row2 = document.getElementById("marquee-row-2");
  if (!row1 || !row2) return;

  function createPill(item) {
    const pill = document.createElement("div");
    pill.className = "headline-pill";
    const scoreVal = typeof item.pred === "number" ? item.pred : (typeof item.risk_score === "number" ? item.risk_score : 5.0);
    const scoreColor = scoreVal >= 7.0 ? "threat-red" : (scoreVal >= 4.0 ? "threat-amber" : "threat-green");

    // Headlines come from third-party news APIs, so build with textContent (never innerHTML)
    const parts = [
      ["pill-tag", item.corridor || ""],
      ["pill-text", item.headline || item.title || ""],
      ["pill-source", item.source || item.provider || ""],
      [`pill-score ${scoreColor}`, scoreVal.toFixed(1)]
    ];
    parts.forEach(([cls, text]) => {
      if (!text) return;
      const span = document.createElement("span");
      span.className = cls;
      span.textContent = text;
      pill.appendChild(span);
    });

    pill.addEventListener("click", () => openHeadlineModal(item));
    return pill;
  }

  function renderMarqueeItems(articles) {
    if (!articles || articles.length === 0) return;
    row1.innerHTML = "";
    row2.innerHTML = "";

    // Duplicate dataset so marquee loops seamlessly without visual breaks
    const doubled = articles.length < 12 ? [...articles, ...articles, ...articles] : [...articles, ...articles];
    doubled.forEach((item, idx) => {
      if (idx % 2 === 0) row1.appendChild(createPill(item));
      else row2.appendChild(createPill(item));
    });
  }

  function renderFeedStatus(status) {
    const el = document.getElementById("ticker-feed-status");
    if (!el || !status) return;
    const providers = Object.entries(status.providers || {})
      .filter(([, p]) => p.configured)
      .map(([name, p]) => p.ok ? `${name} ${p.count}` : `${name} unavailable (${p.error})`);
    let updated = "no live headlines yet";
    if (status.last_updated) {
      const mins = Math.round((Date.now() - new Date(status.last_updated).getTime()) / 60000);
      updated = mins < 1 ? "updated just now" : `updated ${mins} min ago`;
    }
    const backfill = status.backfill_weeks_done < status.backfill_weeks_total
      ? [`history backfill ${status.backfill_weeks_done}/${status.backfill_weeks_total} weeks`] : [];
    el.textContent = [updated, ...providers, ...backfill].join(" · ");
  }

  async function fetchFeedStatus() {
    try {
      const res = await fetch("/api/risk/feed-status");
      if (res.ok) renderFeedStatus(await res.json());
    } catch (e) {
      // Status line is informational only
    }
  }

  async function fetchLatestStreamArticles() {
    fetchFeedStatus();
    let liveArticles = [];
    try {
      const res = await fetch("/api/risk/headlines");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          liveArticles = data;
        }
      }
    } catch (e) {
      // Fallback to /api/risk
      try {
        const res = await fetch("/api/risk");
        if (res.ok) {
          const data = await res.json();
          syncHeroCardFromRisk(data);
          if (data.corridors) {
            data.corridors.forEach(c => {
              if (c.recent_headlines) {
                c.recent_headlines.forEach(h => {
                  liveArticles.push({
                    headline: h.headline || h.title,
                    corridor: c.corridor,
                    pred: typeof h.risk_score === "number" ? h.risk_score : (c.risk_score || 5.0),
                    source: h.source || "",
                    provider: h.provider || "",
                    url: h.url || "",
                    published_at: h.published_at || "",
                    engine: h.model_used || "",
                    reason: h.reason || c.reason || "Model-calibrated maritime supply chain threat evaluation."
                  });
                });
              }
            });
          }
        }
      } catch (err) {
        console.warn("Unable to fetch live ticker:", err);
      }
    }

    if (liveArticles.length > 0) {
      cachedTickerArticles = liveArticles;
      renderMarqueeItems(cachedTickerArticles);
    }
  }

  // Initial load
  await fetchLatestStreamArticles();

  // Real-Time SSE Stream Subscription
  try {
    const eventSource = new EventSource("/api/stream/live");
    eventSource.addEventListener("live_update", (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.headlines && payload.headlines.length > 0) {
          cachedTickerArticles = payload.headlines;
          renderMarqueeItems(cachedTickerArticles);
        }
        if (payload.feed_status) renderFeedStatus(payload.feed_status);
        if (payload.corridors) {
          const hormuz = payload.corridors.find(c => c.corridor === "Hormuz");
          if (hormuz) syncHeroCardFromRisk({ corridors: payload.corridors });
        }
      } catch (err) {
        console.warn("SSE parse error:", err);
      }
    });
    eventSource.onerror = () => {
      // Handled silently by fallback interval poller
    };
  } catch (err) {
    console.warn("SSE not supported, using active polling.");
  }

  // Periodic active poller every 30 seconds
  if (tickerRefreshInterval) clearInterval(tickerRefreshInterval);
  tickerRefreshInterval = setInterval(fetchLatestStreamArticles, 30000);

  const modal = document.getElementById("headline-modal");
  const closeBtn = document.getElementById("modal-close-btn");
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.remove("active");
    });
  }
}

function syncHeroCardFromRisk(data) {
  if (!data || !data.corridors) return;
  const hormuz = data.corridors.find(c => c.corridor === "Hormuz");
  if (!hormuz) return;

  const heroScoreEl = document.getElementById("hero-live-score");
  const heroTimeEl = document.getElementById("hero-live-time");
  const heroPulseEl = document.querySelector("#hero-live-card .pulse-indicator");

  if (heroScoreEl) {
    heroScoreEl.textContent = hormuz.risk_score.toFixed(1);
    heroScoreEl.style.color = hormuz.risk_score >= 7.0 ? "var(--accent-red)" : (hormuz.risk_score >= 4.0 ? "var(--accent-amber)" : "var(--accent-green)");
  }

  if (heroPulseEl) {
    heroPulseEl.className = `pulse-indicator ${hormuz.risk_score >= 7.0 ? 'pulse-red' : (hormuz.risk_score >= 4.0 ? 'pulse-amber' : 'pulse-green')}`;
  }

  if (heroTimeEl) {
    heroTimeEl.textContent = "live GDELT · KrudeAi";
  }
}

function openHeadlineModal(item) {
  const modal = document.getElementById("headline-modal");
  if (!modal) return;

  const scoreVal = typeof item.pred === "number" ? item.pred : (typeof item.risk_score === "number" ? item.risk_score : 5.0);
  const corridorName = (item.corridor || "HORMUZ").toUpperCase();
  const headlineText = item.headline || item.title || "Maritime Security Intelligence Update";

  const corridorTag = document.getElementById("modal-corridor-tag");
  if (corridorTag) {
    corridorTag.innerHTML = `<i class="fa-solid fa-location-dot"></i> `;
    corridorTag.appendChild(document.createTextNode(corridorName));
  }

  const headlineTitle = document.getElementById("modal-headline-title");
  if (headlineTitle) headlineTitle.textContent = headlineText;

  const scoreEl = document.getElementById("modal-pred-score");
  if (scoreEl) {
    scoreEl.textContent = scoreVal.toFixed(1);
    scoreEl.style.color = scoreVal >= 7.0 ? "#EF4444" : (scoreVal >= 4.0 ? "#F59E0B" : "#10B981");
  }

  const sevEl = document.getElementById("modal-severity-level");
  if (sevEl) {
    if (scoreVal >= 7.0) {
      sevEl.textContent = "CRITICAL";
      sevEl.className = "modal-threat-pill threat-red";
    } else if (scoreVal >= 4.0) {
      sevEl.textContent = "ELEVATED";
      sevEl.className = "modal-threat-pill threat-amber";
    } else {
      sevEl.textContent = "LOW / STABLE";
      sevEl.className = "modal-threat-pill threat-green";
    }
  }

  const sourceEl = document.getElementById("modal-source-name");
  if (sourceEl) {
    sourceEl.textContent = item.source || item.headline_source || "Unknown source";
  }

  const metaEl = document.getElementById("modal-source-meta");
  if (metaEl) {
    const published = item.published_at ? new Date(item.published_at) : null;
    const when = published && !isNaN(published) ? published.toLocaleString() : "";
    metaEl.textContent = [item.provider ? `via ${item.provider}` : "", when].filter(Boolean).join(" · ");
  }

  const linkEl = document.getElementById("modal-source-link");
  if (linkEl) {
    const safeUrl = /^https?:\/\//i.test(item.url || "") ? item.url : "";
    linkEl.href = safeUrl || "#";
    linkEl.style.display = safeUrl ? "" : "none";
  }

  const reasonEl = document.getElementById("modal-reason-text");
  if (reasonEl) {
    reasonEl.textContent = item.reason || "";
  }

  const engineEl = document.getElementById("modal-engine-text");
  if (engineEl) {
    engineEl.textContent = item.engine ? `Score by ${item.engine} · explanation is rule-based` : "";
  }

  modal.classList.add("active");
}

/* ==============================================================================
   7. RISK VS BRENT DUAL-AXIS CHART (With Historical Event Annotations)
   ============================================================================== */
let riskVsBrentChartInst = null;

async function initRiskVsBrentChart() {
  const canvas = document.getElementById("risk-brent-chart");
  const verdictEl = document.getElementById("validation-verdict");
  const statsEl = document.getElementById("validation-stats");
  const eventsEl = document.getElementById("validation-events");
  if (!canvas || typeof Chart === "undefined") return;

  let data;
  try {
    const res = await fetch("/api/risk/empirical-validation?corridor=Hormuz");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    if (verdictEl) verdictEl.textContent = `Validation unavailable (${err.message}).`;
    return;
  }
  if (data.status !== "COMPUTED") {
    if (verdictEl) verdictEl.textContent = `Validation pending: ${data.reason}.`;
    return;
  }

  if (verdictEl) verdictEl.textContent = data.verdict;
  if (statsEl && data.level_correlation) {
    statsEl.textContent = `${data.period.start} to ${data.period.end} (${data.period.trading_days} trading days). ` +
      `Level correlation r = ${data.level_correlation.r}. Brent moved ${data.avg_7d_move_after_spikes_pct}% on average in the 7 days ` +
      `after the largest spikes vs a typical absolute 7-day move of ${data.avg_7d_abs_move_pct}%. ${data.news_source}.`;
  }
  if (eventsEl) {
    eventsEl.innerHTML = "";
    data.spike_events.forEach(e => {
      const card = document.createElement("div");
      card.className = "et-card";
      const up = e.brent_7d_change_pct >= 0;
      card.innerHTML = `
        <div class="et-header">
          <span class="et-date">${e.date}</span>
          <span class="threat-pill ${up ? "threat-red" : "threat-green"}">Brent ${up ? "+" : ""}${e.brent_7d_change_pct}% in 7d</span>
        </div>
        <div class="et-comparison">
          <div class="etc-item"><span class="etc-lbl">News intensity:</span><span class="etc-val text-amber font-mono">${e.news_intensity} per M articles</span></div>
          <div class="etc-item"><span class="etc-lbl">Brent:</span><span class="etc-val text-white font-mono">$${e.brent_usd} &rarr; $${e.brent_7d_later_usd}</span></div>
        </div>`;
      eventsEl.appendChild(card);
    });
  }

  const spikeDates = new Set(data.spike_events.map(e => e.date));
  const labels = data.timeline.map(p => p.date);
  const intensity = data.timeline.map(p => p.news_intensity);
  const brent = data.timeline.map(p => p.brent_usd);

  if (riskVsBrentChartInst) riskVsBrentChartInst.destroy();
  riskVsBrentChartInst = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Hormuz news intensity (per M articles, 7d mean)",
          data: intensity,
          borderColor: "#F59E0B",
          backgroundColor: "rgba(245, 158, 11, 0.12)",
          fill: true,
          tension: 0.3,
          yAxisID: "yRisk",
          borderWidth: 2,
          pointRadius: labels.map(d => spikeDates.has(d) ? 6 : 0),
          pointBackgroundColor: "#EF4444"
        },
        {
          label: "Brent spot ($/bbl)",
          data: brent,
          borderColor: "#FFFFFF",
          borderWidth: 2,
          tension: 0.25,
          yAxisID: "yBrent",
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: "#151A23", titleColor: "#FFFFFF", bodyColor: "#E2E8F0", padding: 12 }
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94A3B8", maxTicksLimit: 12 } },
        yRisk: { type: "linear", position: "left", ticks: { color: "#F59E0B" }, grid: { color: "rgba(245, 158, 11, 0.08)" } },
        yBrent: { type: "linear", position: "right", ticks: { color: "#FFFFFF" }, grid: { drawOnChartArea: false } }
      }
    }
  });
}

/* ==============================================================================
   8. SCENARIO SIMULATOR (Scaled Waterfall Cards & 90-Day Forecast)
   ============================================================================== */
let supplyGapChartInst = null;

function initScenarioSimulator() {
  const btnRun = document.getElementById("run-scenario-btn");
  const sDuration = document.getElementById("sim-slider-duration");
  const sSeverity = document.getElementById("sim-slider-severity");
  const selChokepoint = document.getElementById("sim-chokepoint-select");
  const presetBtns = document.querySelectorAll(".preset-btn");

  presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      presetBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const preset = btn.getAttribute("data-preset");

      if (preset === "hormuz_closure") {
        selChokepoint.value = "Hormuz";
        sDuration.value = 30;
        sSeverity.value = 100;
      } else if (preset === "red_sea") {
        selChokepoint.value = "Bab-el-Mandeb";
        sDuration.value = 45;
        sSeverity.value = 80;
      } else if (preset === "combined") {
        selChokepoint.value = "Hormuz";
        sDuration.value = 60;
        sSeverity.value = 90;
      }
      updateSimLabels();
      executeScenario();
    });
  });

  function updateSimLabels() {
    document.getElementById("sim-val-duration").textContent = `${sDuration.value} days`;
    document.getElementById("sim-val-severity").textContent = `${sSeverity.value}% (${sSeverity.value >= 75 ? 'Full' : 'Partial'})`;
  }

  [sDuration, sSeverity].forEach(sl => {
    if (sl) sl.addEventListener("input", updateSimLabels);
  });

  if (btnRun) {
    btnRun.addEventListener("click", executeScenario);
  }

  executeScenario();
}

async function executeScenario() {
  const duration = parseInt(document.getElementById("sim-slider-duration").value);
  const severityPct = parseInt(document.getElementById("sim-slider-severity").value);
  const corridor = document.getElementById("sim-chokepoint-select").value;
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };

  let res;
  try {
    res = await API.simulateScenario({
      corridor,
      disruption_duration_days: duration,
      disruption_severity_pct: severityPct
    });
  } catch (err) {
    set("res-peak-gap", "unavailable");
    set("res-import-cost", "unavailable");
    console.warn("Scenario simulation failed:", err);
    return;
  }

  const i = res.impacts;
  const gapKbd = Math.round(res.scenario_inputs.blocked_supply_kbd);
  set("res-peak-gap", `${gapKbd.toLocaleString()} kbd`);
  set("res-import-cost", `+$${i.estimated_additional_cost_usd_billion.toFixed(2)} B`);
  set("wf-val-lost", `${gapKbd.toLocaleString()} kbd × ${i.gap_days}d`);
  set("wf-val-cost", `+$${i.estimated_additional_cost_usd_billion.toFixed(2)} B`);
  set("wf-val-pump", `+₹${i.retail_fuel_rs_per_litre.toFixed(2)} /L`);
  set("wf-val-refinery", `-${i.refining_utilization_drop_peak_pct}% peak`);
  set("wf-val-gdp", `${i.gdp_impact_pp.toFixed(3)} pp`);
  set("sim-explanation", res.explanation);

  renderSupplyGapChart(corridor, duration, severityPct);
}

async function renderSupplyGapChart(corridor, days, severityPct) {
  const canvas = document.getElementById("supply-gap-chart");
  if (!canvas || typeof Chart === "undefined") return;

  // The reserve LP runs against the scenario model's day-by-day gap (no browser-side fallback)
  let data;
  try {
    const res = await fetch("/api/reserve/optimize-lp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corridor,
        disruption_duration_days: days,
        disruption_severity_pct: severityPct
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    console.warn("Reserve LP unavailable:", err);
    return;
  }

  if (supplyGapChartInst) supplyGapChartInst.destroy();
  const T = data.timeline.length;
  const labels = data.timeline.map(p => `Day ${p.day}`);
  const baseSupply = data.scenario.india_crude_runs_kbd;
  const baseDemand = Array(T).fill(baseSupply);
  const available = data.timeline.map(p => p.available_supply_kbd);
  const sprDrawdown = data.timeline.map(p => p.spr_drawdown_kbd);
  const remainingSprDays = data.timeline.map(p => p.remaining_spr_days);
  const lowest = Math.min(...available);

  const cover = document.getElementById("res-days-cover");
  if (cover) cover.textContent = `${remainingSprDays[T - 1].toFixed(1)} days`;
  const strategyEl = document.getElementById("spr-lp-strategy");
  if (strategyEl) strategyEl.textContent = `${data.summary.drawdown_strategy} (${data.solver})`;

  supplyGapChartInst = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: `Normal crude runs (${Math.round(baseSupply).toLocaleString()} kbd)`,
          data: baseDemand,
          borderColor: "rgba(255, 255, 255, 0.4)",
          borderDash: [4, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          yAxisID: "ySupply"
        },
        {
          label: "Available supply after SPR release",
          data: available,
          borderColor: "#10B981",
          backgroundColor: "rgba(239, 68, 68, 0.20)",
          fill: "-1",
          borderWidth: 2.5,
          tension: 0.2,
          pointRadius: 0,
          yAxisID: "ySupply"
        },
        {
          label: "Optimized SPR Drawdown d(t) [kbd]",
          data: sprDrawdown,
          borderColor: "#F59E0B",
          backgroundColor: "rgba(245, 158, 11, 0.15)",
          borderWidth: 2,
          fill: true,
          pointRadius: 0,
          yAxisID: "yDraw"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: { color: "#c9d1d9", boxWidth: 12, font: { size: 10 } }
        },
        tooltip: {
          backgroundColor: "#151A23",
          titleColor: "#FFFFFF",
          bodyColor: "#E2E8F0",
          borderColor: "rgba(255,255,255,0.15)",
          borderWidth: 1,
          padding: 10,
          callbacks: {
            footer: (items) => `SPR cover left: ${remainingSprDays[items[0].dataIndex].toFixed(1)} days`
          }
        }
      },
      scales: {
        x: { ticks: { color: "#94A3B8", maxTicksLimit: 12 }, grid: { color: "rgba(255,255,255,0.03)" } },
        ySupply: {
          type: "linear",
          position: "left",
          min: Math.floor((lowest - 300) / 500) * 500,
          max: Math.ceil((baseSupply + 200) / 500) * 500,
          ticks: { color: "#10B981" },
          grid: { color: "rgba(255,255,255,0.05)" },
          title: {
            display: true,
            text: "Net Inflow & Demand (kbd) [Left Axis]",
            color: "#10B981",
            font: { size: 11, weight: "bold" }
          }
        },
        yDraw: {
          type: "linear",
          position: "right",
          min: 0,
          max: 1000,
          ticks: { color: "#F59E0B" },
          grid: { drawOnChartArea: false },
          title: {
            display: true,
            text: "Optimized SPR Drawdown d(t) (kbd) [Right Axis]",
            color: "#F59E0B",
            font: { size: 11, weight: "bold" }
          }
        }
      }
    }
  });
}

/* ==============================================================================
   9. PROCUREMENT ORCHESTRATOR (Live vs Geopolitical Board Modes)
   ============================================================================== */
let activeProcurementMode = "live"; // "live" or "sim"

async function refreshProcurementOrchestrator() {
  const container = document.getElementById("procurement-list-deck");
  if (!container) return;

  const badgeEl = document.getElementById("proc-source-badge");
  const labelEl = document.getElementById("proc-source-label");

  // Live mode: backend uses the live corridor probabilities. Sim mode: analyst scores from the Threat Board.
  let corridorScores = null;
  if (activeProcurementMode === "sim") {
    corridorScores = {};
    Object.keys(CHOKEPOINTS_DATA).forEach(k => {
      corridorScores[k] = CHOKEPOINTS_DATA[k].score;
    });
    if (labelEl) labelEl.textContent = "Corridor Threat Board Overrides Active";
    if (badgeEl) badgeEl.style.borderColor = "rgba(245, 158, 11, 0.4)";
  } else {
    if (labelEl) labelEl.textContent = "Live Corridor Probabilities";
    if (badgeEl) badgeEl.style.borderColor = "rgba(16, 185, 129, 0.3)";
  }

  try {
    const resp = await fetch("/api/procurement/rank", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corridor_risk_scores: corridorScores })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    renderProcurementCards(data.ranked_suppliers || []);
  } catch (err) {
    container.textContent = `Procurement ranking unavailable (${err.message}). Is the backend running?`;
  }
}

function renderProcurementCards(ranking) {
  const container = document.getElementById("procurement-list-deck");
  if (!container) return;

  container.innerHTML = "";
  if (!ranking.length) {
    container.textContent = "No liftable supplier options in the dataset.";
    return;
  }
  ranking.forEach((item, idx) => {
    const card = document.createElement("div");
    card.className = `procurement-card ${idx === 0 ? 'expanded' : ''}`;
    const routeRisk = item.route_disruption_p;
    const riskClass = routeRisk >= 0.07 ? "threat-red" : (routeRisk >= 0.02 ? "threat-amber" : "threat-green");

    card.innerHTML = `
      <div class="pc-top-row">
        <span class="pc-rank ${idx === 0 ? 'rank-top' : ''}">#${item.rank}</span>
        <div class="pc-supplier-info">
          <span class="pc-supplier-name">${item.supplier} (${item.crude_grade})</span>
        </div>
        <div class="pc-metric">
          <span class="pcm-label">Landed / Risk-Adj.</span>
          <span class="pcm-val font-mono">$${item.landed_cost_usd.toFixed(2)} / $${item.risk_adjusted_cost_usd_bbl.toFixed(2)}</span>
        </div>
        <div class="pc-metric">
          <span class="pcm-label">Searoute Transit</span>
          <span class="pcm-val font-mono">${item.searoute_days} days</span>
        </div>
        <div class="pc-metric">
          <span class="pcm-label">Max Liftable</span>
          <span class="pcm-val font-mono text-green">${Math.round(item.max_liftable_kbd).toLocaleString()} kbd</span>
        </div>
        <div class="pc-metric">
          <span class="pcm-label">Route (30d risk)</span>
          <span class="threat-pill ${riskClass}">${item.chokepoint_route} · ${(routeRisk * 100).toFixed(1)}%</span>
        </div>
      </div>
      <div class="pc-expander">
        <p><strong>Why this rank:</strong> ${item.why}</p>
      </div>
    `;

    card.addEventListener("click", () => {
      card.classList.toggle("expanded");
    });

    container.appendChild(card);
  });
}

function initProcurementList() {
  const btnLive = document.getElementById("proc-mode-live");
  const btnSim = document.getElementById("proc-mode-sim");

  if (btnLive && btnSim) {
    btnLive.addEventListener("click", () => {
      btnLive.classList.add("active");
      btnSim.classList.remove("active");
      activeProcurementMode = "live";
      refreshProcurementOrchestrator();
    });

    btnSim.addEventListener("click", () => {
      btnSim.classList.add("active");
      btnLive.classList.remove("active");
      activeProcurementMode = "sim";
      refreshProcurementOrchestrator();
    });
  }

  refreshProcurementOrchestrator();
}

/* ==============================================================================
   10. STRATEGIC RESERVE OPTIMISATION (Interactive Policies & Live Risk Sync)
   ============================================================================== */
let reserveChartInst = null;
let activeReserveStrategy = "steady";

let reservePolicies = null;  // from /api/reserve/policies
let reserveLpCurve = null;   // days-of-cover curve from the LP, when synced

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function updateReserveUI(stratKey) {
  if (!reservePolicies) return;
  const p = reservePolicies.policies[stratKey];
  setText("spr-stat-rate", `${p.rate_kbd} kbd`);
  setText("spr-stat-rate-sub", p.label);
  setText("spr-stat-days", `${reservePolicies.initial_cover_days.toFixed(1)} Days`);
  setText("spr-stat-exhaust", `${Math.round(p.days_to_floor)} Days`);
  setText("spr-stat-exhaust-sub", `Until ${reservePolicies.safety_floor_days.toFixed(1)}-day floor reached`);
  setText("reserve-verdict-text", p.verdict);
  renderReserveChart(stratKey);
}

function renderReserveChart(activeKey) {
  const canvas = document.getElementById("reserve-chart");
  if (!canvas || typeof Chart === "undefined" || !reservePolicies) return;
  if (reserveChartInst) reserveChartInst.destroy();

  const H = reservePolicies.horizon_days;
  const labels = Array.from({ length: H }, (_, i) => `Day ${i + 1}`);
  const style = { steady: "#10B981", aggressive: "#EF4444", hold: "#38BDF8" };
  const datasets = Object.entries(reservePolicies.policies).map(([key, p]) => ({
    label: `${p.label} (${p.rate_kbd} kbd)`,
    data: p.cover_days_curve,
    borderColor: style[key],
    backgroundColor: key === activeKey ? `${style[key]}26` : "transparent",
    borderWidth: key === activeKey ? 3.5 : 1.5,
    borderDash: key === activeKey ? [] : [4, 4],
    fill: key === activeKey,
    pointRadius: 0
  }));
  if (reserveLpCurve) {
    datasets.push({
      label: "LP-optimal for current scenario",
      data: reserveLpCurve,
      borderColor: "#F59E0B",
      borderWidth: activeKey === "lp" ? 3.5 : 2,
      pointRadius: 0,
      fill: false
    });
  }
  datasets.push({
    label: `Safety floor (${reservePolicies.safety_floor_days.toFixed(1)} days)`,
    data: Array(H).fill(reservePolicies.safety_floor_days),
    borderColor: "rgba(255, 255, 255, 0.4)",
    borderDash: [6, 6],
    borderWidth: 1.5,
    pointRadius: 0,
    fill: false
  });

  reserveChartInst = new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, position: "top", labels: { color: "#c9d1d9", boxWidth: 12, font: { size: 10 } } }
      },
      scales: {
        x: { ticks: { color: "#94A3B8", maxTicksLimit: 12 }, grid: { display: false } },
        y: {
          min: 0,
          max: Math.ceil(reservePolicies.initial_cover_days + 1),
          ticks: { color: "#94A3B8" },
          grid: { color: "rgba(255,255,255,0.05)" },
          title: { display: true, text: "SPR Cover (Days)", color: "#E2E8F0", font: { size: 11, weight: "bold" } }
        }
      }
    }
  });
}

async function syncReserveWithScenario() {
  // LP against the scenario currently set in the simulator, with live follow-on risk
  const body = {
    corridor: document.getElementById("sim-chokepoint-select").value,
    disruption_duration_days: parseInt(document.getElementById("sim-slider-duration").value),
    disruption_severity_pct: parseInt(document.getElementById("sim-slider-severity").value)
  };
  const res = await fetch("/api/reserve/optimize-lp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const lp = await res.json();

  const H = reservePolicies.horizon_days;
  const curve = lp.timeline.map(p => p.remaining_spr_days).slice(0, H);
  while (curve.length < H) curve.push(curve.length ? curve[curve.length - 1] : reservePolicies.initial_cover_days);
  reserveLpCurve = curve;

  const drawDays = lp.timeline.filter(p => p.spr_drawdown_kbd > 0.5);
  const avgRate = drawDays.length ? drawDays.reduce((a, p) => a + p.spr_drawdown_kbd, 0) / drawDays.length : 0;
  setText("spr-stat-rate", `${Math.round(avgRate)} kbd`);
  setText("spr-stat-rate-sub", `LP average over ${drawDays.length} release days`);
  setText("spr-stat-exhaust", `${lp.summary.final_remaining_spr_days.toFixed(1)} Days`);
  setText("spr-stat-exhaust-sub", `Cover left after ${body.disruption_duration_days}-day ${body.corridor} scenario`);
  setText("reserve-verdict-text",
    `${lp.summary.drawdown_strategy} Follow-on risk P = ${(lp.parameters.p_followon_disruption * 100).toFixed(1)}% (live Hormuz, 30-day). ${lp.solver}.`);
  renderReserveChart("lp");
}

async function initReserveChart() {
  const stratBtns = document.querySelectorAll(".strat-btn[data-strategy]");
  const syncBtn = document.getElementById("spr-sync-live-btn");

  try {
    const res = await fetch("/api/reserve/policies");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    reservePolicies = await res.json();
  } catch (err) {
    setText("reserve-verdict-text", `Reserve policies unavailable (${err.message}).`);
    return;
  }

  stratBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      stratBtns.forEach(b => b.classList.remove("active"));
      if (syncBtn) syncBtn.classList.remove("active");
      btn.classList.add("active");
      activeReserveStrategy = btn.getAttribute("data-strategy");
      updateReserveUI(activeReserveStrategy);
    });
  });

  if (syncBtn) {
    syncBtn.addEventListener("click", async () => {
      stratBtns.forEach(b => b.classList.remove("active"));
      syncBtn.classList.add("active");
      try {
        await syncReserveWithScenario();
      } catch (err) {
        setText("reserve-verdict-text", `Reserve LP unavailable (${err.message}).`);
      }
    });
  }

  updateReserveUI("steady");
}

/* ==============================================================================
   11. DIGITAL TWIN (from /api/digital-twin/graph and /api/digital-twin/state)
   ============================================================================== */
// World Mercator Bounds (Houston through Malacca) - dedicated to Digital Twin Map
const WORLD_LON_MIN = -130.0, WORLD_LON_MAX = 150.0;
const WORLD_Y_MIN = -54.858810, WORLD_Y_MAX = 93.846974;

const mercYWorld = lat => (180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI / 180) / 2));

function projectWorld(lon, lat) {
  return {
    left: ((lon - WORLD_LON_MIN) / (WORLD_LON_MAX - WORLD_LON_MIN)) * 100,
    top:  ((WORLD_Y_MAX - mercYWorld(lat)) / (WORLD_Y_MAX - WORLD_Y_MIN)) * 100
  };
}

function initDigitalTwinMap() {
  const routesSvg = document.getElementById("twin-routes-svg");
  const markersLayer = document.getElementById("twin-markers-layer");
  const statusText = document.getElementById("twin-status-text");
  if (!markersLayer || !routesSvg) return;

  let graph = null;
  let corridorP = {};          // live P(disruption, 30d) per corridor
  let hit = null;              // { corridor, nodes: Set, stage }

  function twinStatus(text, cls) {
    if (!statusText) return;
    statusText.textContent = text;
    statusText.className = cls || "";
  }

  function nodeColor(n) {
    if (hit && hit.nodes.has(n.id) && hit.stage >= (n.type === "choke" ? 1 : n.type === "origin" ? 1 : 2)) return "#EF4444";
    if (n.type === "origin") return "#38BDF8";
    if (n.type === "choke") {
      const p = corridorP[n.name] || 0;
      return p >= 0.07 ? "#EF4444" : (p >= 0.04 ? "#F59E0B" : "#10B981");
    }
    if (n.type === "spr") return "#E11D48";
    return "#10B981";
  }

  function nodeLabel(n) {
    if (n.type === "choke") return `${Math.round(n.kbd).toLocaleString()} kbd · live P30 ${((corridorP[n.name] || 0) * 100).toFixed(1)}%`;
    if (n.type === "spr") return n.label;
    if (n.type === "origin") return `${n.country} · ${Math.round(n.kbd).toLocaleString()} kbd`;
    return `${Math.round(n.kbd).toLocaleString()} kbd received`;
  }

  function curvePath(a, b) {
    const dx = b.left - a.left, dy = b.top - a.top;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist === 0) return `M ${a.left} ${a.top}`;
    const bend = Math.min(6, dist * 0.12);
    const cx = (a.left + b.left) / 2 - (dy / dist) * bend;
    const cy = (a.top + b.top) / 2 + (dx / dist) * bend;
    return `M ${a.left.toFixed(2)} ${a.top.toFixed(2)} Q ${cx.toFixed(2)} ${cy.toFixed(2)} ${b.left.toFixed(2)} ${b.top.toFixed(2)}`;
  }

  function render() {
    if (!graph) return;
    const byId = Object.fromEntries(graph.nodes.map(n => [n.id, n]));

    markersLayer.innerHTML = "";
    graph.nodes.forEach(n => {
      const color = nodeColor(n);
      const el = createMarkerElement({ ...n, sub: nodeLabel(n), color, isChoke: n.type === "choke" || color === "#EF4444" }, false, projectWorld);
      markersLayer.appendChild(el);
    });

    routesSvg.innerHTML = "";
    const maxKbd = Math.max(...graph.segments.map(s => s.kbd), 1);
    graph.segments.forEach(seg => {
      const u = byId[seg.from], v = byId[seg.to];
      if (!u || !v) return;
      const cut = hit && hit.stage >= 1 && seg.corridors.includes(hit.corridor);
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", curvePath(projectWorld(u.lon, u.lat), projectWorld(v.lon, v.lat)));
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", cut ? "#EF4444" : "#64748B");
      // Width scales with the barrels on the segment
      path.setAttribute("stroke-width", (0.6 + 3.4 * Math.sqrt(seg.kbd / maxKbd)).toFixed(2));
      path.setAttribute("stroke-opacity", cut ? "0.95" : "0.5");
      path.setAttribute("vector-effect", "non-scaling-stroke");
      if (cut) path.setAttribute("stroke-dasharray", "4 3");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${u.name} → ${v.name}: ${Math.round(seg.kbd).toLocaleString()} kbd`;
      path.appendChild(title);
      routesSvg.appendChild(path);
    });
  }

  function readyText() {
    if (!graph) return;
    twinStatus(`Live graph: ${Math.round(graph.mapped_kbd).toLocaleString()} of ${Math.round(graph.total_imports_kbd).toLocaleString()} kbd mapped on ${graph.routes.length} routes ` +
      `(3-month average imports; ${Math.round(graph.unmapped_kbd).toLocaleString()} kbd from suppliers without route data). Line width = barrels per day.`);
  }

  async function load() {
    try {
      const [gRes, pRes] = await Promise.all([fetch("/api/digital-twin/graph"), fetch("/api/risk/supply-disruption-probabilities")]);
      if (gRes.ok) graph = await gRes.json();
      if (pRes.ok) {
        const p = await pRes.json();
        corridorP = Object.fromEntries((p.corridors || []).map(c => [c.corridor, c.p_disruption_30d]));
      }
      render();
      if (!hit) readyText();
    } catch (e) {
      twinStatus("Digital twin unavailable: backend not reachable");
    }
  }

  async function triggerCascade() {
    if (!graph) return;
    const corridor = document.getElementById("twin-chokepoint-select").value;
    const sev = parseFloat((document.getElementById("sim-slider-severity") || {}).value || "100");
    const days = parseInt((document.getElementById("sim-slider-duration") || {}).value || "30", 10);

    // Which routes, origins and ports lose barrels
    const affected = graph.routes.filter(r => r.corridors.includes(corridor));
    const nodes = new Set([`choke:${{ "Hormuz": "hormuz", "Bab-el-Mandeb": "bab_el_mandeb", "Suez": "suez", "Malacca": "malacca", "Cape of Good Hope": "cape_of_good_hope" }[corridor]}`]);
    const portLoss = {};
    affected.forEach(r => {
      nodes.add(`load:${r.load_port}`);
      nodes.add(`dest:${r.discharge_port}`);
      portLoss[r.discharge_port] = (portLoss[r.discharge_port] || 0) + r.kbd * sev / 100;
    });

    hit = { corridor, nodes, stage: 1 };
    render();
    twinStatus(`Disrupting ${corridor} at ${sev}% for ${days} days: running scenario, procurement and reserve models…`, "text-red font-bold");
    setTimeout(() => { if (hit) { hit.stage = 2; render(); } }, 300);

    try {
      const res = await fetch("/api/digital-twin/state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_corridor: corridor, disruption_severity_pct: sev, disruption_duration_days: days })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const state = await res.json();
      const imp = state.scenario_impact.impacts;
      const ports = Object.entries(portLoss).sort((a, b) => b[1] - a[1]).slice(0, 4)
        .map(([p, k]) => `${p} −${Math.round(k).toLocaleString()}`).join(", ");
      twinStatus(
        `${corridor} ${sev}% for ${days}d: ${Math.round(state.scenario_impact.scenario_inputs.blocked_supply_kbd).toLocaleString()} kbd blocked ` +
        `for ${imp.gap_days} days (${ports || "no mapped port"} kbd). Brent → $${imp.new_brent_usd.toFixed(0)}, ` +
        `import bill +$${imp.estimated_additional_cost_usd_billion.toFixed(1)}B. Action: ${state.latest_log.action}`,
        "text-red font-bold");
    } catch (e) {
      twinStatus(`Cascade shown from the route graph only; the models did not respond (${e.message}).`, "text-amber font-bold");
    }
  }

  const btnCascade = document.getElementById("twin-propagate-btn");
  if (btnCascade) btnCascade.addEventListener("click", triggerCascade);

  const btnReset = document.getElementById("twin-reset-btn");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      hit = null;
      render();
      readyText();
    });
  }

  load();
  setInterval(load, 5 * 60 * 1000);
}
/* ==============================================================================
   12. AI MODEL SANDBOX
   ============================================================================== */
function initModelSandbox() {
  const btnRun = document.getElementById("run-custom-inference-btn");
  const input = document.getElementById("custom-headline-input");
  const outScore = document.getElementById("term-out-score");
  const outLatency = document.getElementById("term-out-latency");
  const outReason = document.getElementById("term-out-reason");

  const sampleBtns = document.querySelectorAll(".quick-sample-btn");
  sampleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      input.value = btn.getAttribute("data-text");
      runInference();
    });
  });

  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runInference();
      }
    });
  }

  if (btnRun) btnRun.addEventListener("click", runInference);

  async function runInference() {
    const text = input.value.trim();
    if (!text) return;

    outScore.textContent = "...";
    outScore.className = "term-res-score text-amber";
    outReason.textContent = "Scoring headline...";

    try {
      const res = await API.analyzeHeadline(text, null);
      const scoreVal = res.risk_score;
      outScore.textContent = `${scoreVal.toFixed(1)} / 10.0`;
      outScore.className = `term-res-score ${scoreVal >= 7.0 ? 'text-red' : (scoreVal >= 4.0 ? 'text-amber' : 'text-green')}`;
      outLatency.textContent = `Latency: ${res.latency_ms} ms · Scored by: ${res.engine}`;
      outReason.textContent = `Why (${res.reason_engine}): ${res.reason}`;
    } catch (e) {
      outScore.textContent = "—";
      outScore.className = "term-res-score";
      outLatency.textContent = "";
      outReason.textContent = `Scoring failed: ${e.message}. Is the backend running?`;
    }
  }
}

/* ==============================================================================
   13. LEGAL MODALS (Terms & Conditions / Privacy Policy)
   ============================================================================== */
function initLegalModals() {
  const termsBtn = document.getElementById("footer-terms-btn");
  const privacyBtn = document.getElementById("footer-privacy-btn");
  const termsModal = document.getElementById("terms-modal");
  const privacyModal = document.getElementById("privacy-modal");
  const termsClose = document.getElementById("terms-close-btn");
  const privacyClose = document.getElementById("privacy-close-btn");

  if (termsBtn && termsModal) {
    termsBtn.addEventListener("click", (e) => {
      e.preventDefault();
      termsModal.classList.add("active");
    });
  }
  if (privacyBtn && privacyModal) {
    privacyBtn.addEventListener("click", (e) => {
      e.preventDefault();
      privacyModal.classList.add("active");
    });
  }
  if (termsClose && termsModal) {
    termsClose.addEventListener("click", () => {
      termsModal.classList.remove("active");
    });
  }
  if (privacyClose && privacyModal) {
    privacyClose.addEventListener("click", () => {
      privacyModal.classList.remove("active");
    });
  }

  [termsModal, privacyModal].forEach(m => {
    if (m) {
      m.addEventListener("click", (e) => {
        if (e.target === m) {
          m.classList.remove("active");
        }
      });
    }
  });
}

/* ==============================================================================
   14. GLOBAL SCROLL REVEAL ANIMATIONS (Cards & Texts)
   ============================================================================== */
function initScrollAnimations() {
  if (typeof IntersectionObserver === "undefined") return;

  const cardTargets = document.querySelectorAll(
    ".section-header-block, .card-shell, .kpi-card, .procurement-card, .spr-kpi-card, .scenario-input-card, .waterfall-card, .terminal-window, .final-cta-box, .chart-card-clean, .supplier-filter-card, .story-card, .macro-kpi-card, .sim-kpi-box, .suppliers-table-wrapper, .problem-map-wrapper, .risk-map-wrapper, .spr-cavern-strip"
  );

  const textTargets = document.querySelectorAll(
    ".section-main-heading, .section-sub, .section-tag-pill, .problem-headline, .hero-sub-statement, .hero-description, .stat-chip, .problem-summary-block p, .macro-stat-row, .kpi-desc, .story-card-desc"
  );

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in-view");
        obs.unobserve(entry.target);
      }
    });
  }, {
    root: null,
    rootMargin: "0px 0px -40px 0px",
    threshold: 0.08
  });

  cardTargets.forEach((el, idx) => {
    el.classList.add("fade-in-scroll");
    el.style.transitionDelay = `${(idx % 4) * 0.06}s`;
    observer.observe(el);
  });

  textTargets.forEach((el, idx) => {
    el.classList.add("fade-in-text");
    el.style.transitionDelay = `${(idx % 3) * 0.04}s`;
    observer.observe(el);
  });
}
