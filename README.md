# Krude: India Crude Supply Chain Risk Digital Twin

Krude watches the five sea corridors India's crude imports pass through, turns live news into a
30-day disruption probability per corridor and per supplier, and lets an analyst play out a
disruption: what it does to India's supply, Brent, the import bill, which suppliers to switch to,
and how to release the Strategic Petroleum Reserve.

Built for the hackathon brief *Supply Chain Intelligence, Energy Security & Geopolitical Risk*.

---

## What is live, what is modelled

| Part | Data | Status |
|---|---|---|
| Headlines | NewsAPI, GNews, GDELT DOC 2.0, refreshed every 15 min | Live |
| Headline score (0-10) | Fine-tuned Llama 3.2 3B (`Krude-risk`) on Ollama; keyword fallback if Ollama is down | Live, each score names its engine |
| Corridor probability | Stored headlines → dedupe → 7-day half-life decay → strongest event + damped corroboration → momentum → sanctions → calibrated P(30 days) | Computed |
| Brent, USD/INR | FRED (`DCOILBRENTEU`, `DEXINUS`), Yahoo `BZ=F` for the latest Brent | Live |
| India's imports by supplier | `imports_wide.csv`, monthly Apr-2024 to Jul-2026 | Static file, see Data sources |
| Routes, distances, freight | `routes_expanded.csv` (59 routes, searoute distances) | Static file |
| Sanctions | `ofac.csv`, OFAC SDN snapshot | Static file |
| Scenario, procurement, reserve | Rule-of-thumb macro model and two linear programs (PuLP/CBC) | Modelled; constants in `assumptions.yaml` |

Not included: AIS ship tracking and live freight or war-risk rates.

---

## Modules

**1. Supply-disruption probability** (`/api/risk/supply-disruption-probabilities`)
- Per corridor: P(disruption within 30 days) from the stored live headlines, plus 7-day momentum.
- Per supplier: the supplier's 3-month imports are split across its routes by capacity. Each route's risk is `1 − Π(1 − P(chokepoint))`, and the supplier's risk is the volume-weighted average. Russia and Venezuela get ×1.15 for OFAC sanctions programmes.

**2. Corridor Threat Board** (`/api/risk/threat-board`)
- Shows the live index (0-10) per corridor with a 30-day history, and each pipeline stage's value.
- The sliders run a what-if on those stages, using the same formulas as the backend.

**3. Disruption Scenario Modeller** (`/api/scenario/simulate`)
- India's gap = severity × barrels behind the chokepoint. Reroutable corridors (Red Sea, Suez, Malacca) only lose the extra voyage days; Hormuz has no sea reroute.
- Brent rise = live Brent × (global supply lost / 102.8 MBPD) / short-run elasticity 0.2.
- Outputs: import bill, ₹/litre, refinery run cut, GDP and current-account deficit (CAD) effects scaled by duration.

**4. Adaptive Procurement Orchestrator** (`/api/procurement/rank`, `/api/procurement/optimize`)
- Risk-adjusted cost = landed cost + P(route disrupted) × $40/bbl.
- A linear program allocates a supply gap across suppliers, with per-country and per-route caps and blocked chokepoints.

**5. Strategic Reserve Optimiser** (`/api/reserve/optimize-lp`, `/api/reserve/policies`)
- A linear program schedules the daily release against the scenario's gap forecast. It minimises unserved barrels (valued at $200/bbl) plus the cost of drawing ($18/bbl).
- It keeps an adaptive floor: floor days + P(follow-on disruption) × 6.4 MMbbl.
- Reserve: ISPRL Phase I, 5.33 MMT ≈ 39.47 MMbbl ≈ 9.5 days (Visakhapatnam 9.77, Mangalore 11.00, Padur 18.70 MMbbl).

**6. Supply Chain Digital Twin** (`/api/digital-twin/graph`, `/api/digital-twin/state`)
- The map draws load ports → chokepoints → Indian discharge ports. Line width is the 3-month average flow.
- Trigger Cascade runs the scenario, procurement and reserve models for the chosen corridor, and reports the barrels lost per port and the recommended action.

**7. Empirical check** (`/api/risk/empirical-validation`)
- Tests whether GDELT coverage of a corridor led Brent moves since 2024. It reports level and lead-lag correlations and an event study around coverage spikes.
- The verdict is computed from the data, not written in advance.

---

## Data sources

| File | Contents | Source |
|---|---|---|
| `backend/data/imports_wide.csv` | India's crude imports by supplier, thousand barrels/month | Matches Kpler tanker-tracking figures reported in the press (e.g. Russia 2.80 MBPD in Jul-2026; Iraq 0 in Apr-2026). The original export is not recorded. |
| `backend/data/routes_expanded.csv` | Load port, discharge port, chokepoints, distance, transit days, freight, capacity | `build_routes.py` (searoute) |
| `backend/data/suppliers.csv` | Grades, API gravity, sulphur, FOB, liftable volume | `build_suppliers.py` |
| `backend/data/ofac.csv` | OFAC SDN entities (Iran, Russia, Venezuela programmes) | `build_ofac_real.py` |
| `backend/data/ports.csv` | Port and chokepoint coordinates for the map | Public port locations |
| `backend/data/spr_facilities.csv` | ISPRL caverns | ISPRL |
| `backend/data/assumptions.yaml` | Every model constant, with its source | Hand-curated |

Downloaded at runtime and git-ignored: headline history, Brent and USD/INR history, GDELT coverage timelines.

---

## Setup

Requires Python 3.11+. Ollama is optional.

```bash
git clone https://github.com/AlooIsTasty/Krude-.git
cd Krude-
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # Linux/macOS: cp .env.example .env
python run.py
```

Open http://127.0.0.1:8000/ for the dashboard, or http://127.0.0.1:8000/docs for the API.

On first start, the server builds the DuckDB/SQLite database from the CSVs. To rebuild it by hand, run `python backend/data/db_loader.py`.

### `.env`

| Variable | Needed | Purpose |
|---|---|---|
| `NEWS_API_KEY` | Optional | NewsAPI headlines (free tier: 100 requests/day) |
| `GNEWS_API_KEY` | Optional | GNews headlines (free tier: 100 requests/day) |
| `NEWS_REFRESH_SECONDS` | Optional | Default 900; one request per provider per refresh |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | Optional | Defaults `http://localhost:11434`, `Krude-risk` |
| `CORS_ORIGINS` | Optional | Comma-separated; default `http://127.0.0.1:8000,http://localhost:8000` |

GDELT needs no key. Without NewsAPI and GNews keys, headlines come from GDELT only.

### Fine-tuned model

The headline scorer is Llama 3.2 3B with a LoRA adapter, served by Ollama as `Krude-risk`. It returns a score only; the explanation shown beside each score is rule-based. If Ollama isn't running, a keyword scorer takes over, and every score says which engine produced it.

On Windows, if Ollama's CUDA 13 backend crashes, set the environment variable `OLLAMA_LLM_LIBRARY=cuda_v12` and restart Ollama.

---

## API

| Method | Endpoint | Returns |
|---|---|---|
| GET | `/api/risk` | Corridor scores with their latest headlines |
| GET | `/api/risk/headlines` | Live headlines: source, link, time, score and engine |
| GET | `/api/risk/feed-status` | Health of each news provider and the last refresh time |
| POST | `/api/risk/refresh` | Force a news refresh |
| GET | `/api/risk/supply-disruption-probabilities` | P(30 days) per corridor and per supplier |
| GET | `/api/risk/threat-board` | Live index, pipeline stages, 30-day history, exposure |
| GET | `/api/risk/empirical-validation?corridor=` | News-intensity vs Brent test |
| GET | `/api/risk/timeline?corridor=` | Illustrative curve from a curated 2024-26 event list (not live) |
| POST | `/api/scenario/simulate` | Scenario impacts |
| POST | `/api/procurement/rank` | Suppliers ranked by risk-adjusted cost |
| POST | `/api/procurement/optimize` | LP allocation of a supply gap |
| POST | `/api/reserve/optimize-lp` | SPR release schedule for a scenario |
| GET | `/api/reserve/policies` | Fixed-rate release policies compared |
| GET | `/api/digital-twin/graph` | Route graph with flows |
| POST | `/api/digital-twin/state` | All models run together for one disruption |
| GET | `/api/model/status` | Ollama / model status |
| POST | `/api/model/analyze` | Score one headline |
| GET | `/api/stream/live` | Server-sent events with live corridor updates |
| GET | `/api/database/*` | Raw tables: suppliers, routes, imports, ofac, landed-options, corridor-exposure, summary |

---

## Tests

```bash
python -m unittest backend/tests/test_engine.py
```

These 18 tests cover:
- the database tables;
- route distances;
- quality penalties;
- corridor exposure;
- the risk pipeline, Threat Board stages and live-history probabilities;
- the scenario model;
- procurement ranking, the LP and its caps;
- the reserve LP and policies;
- the empirical check;
- the twin graph.

---

## Known limitations

- **Model accuracy:** there are no validation metrics. The labelled holdout behind earlier figures (MAE 0.72) is not in the repository.
- **Corridor probabilities:** 30-day probabilities are calibrated by hand (0.2% to 11%), not fitted to historical disruptions.
- **Headline history:** the corridor history only covers the period since live collection started. The GDELT backfill runs one week per refresh, and GDELT rate-limits.
- **Supplier routes:** each supplier's volume is split across its routes by capacity, not by the cargoes actually shipped on each route.

---

## Team

Pratik Phophaliya · Lalmuankima Colney · Mohak Chabbra
