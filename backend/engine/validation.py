"""
Krude - Empirical Check: Does Corridor News Intensity Lead Brent?
=================================================================
- News intensity: GDELT DOC 2.0 `timelinevolraw` for the corridor query since 2024-01-01, as the
  share of all GDELT-monitored articles (per million). Cached for a week; GDELT rate-limits.
- Price: daily Brent spot (FRED DCOILBRENTEU) via engine.market_data.
- Tests, on trading days:
    1. Level: Pearson r between 7-day mean intensity and the Brent price.
    2. Lead-lag: r between the 5-day change in intensity and Brent's log return over the next
       k trading days (k = 0..15). Forward windows overlap, so the p-values are optimistic.
    3. Event study: Brent's move in the 7 trading days after the largest intensity spikes,
       versus the average absolute 7-day move.
The verdict is computed from these numbers; nothing is asserted in advance.
"""

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

try:
    from engine.market_data import get_brent_history
except ImportError:
    from backend.engine.market_data import get_brent_history

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600
START = "20240101000000"

CORRIDOR_QUERIES = {
    "Hormuz": '("Strait of Hormuz" OR "Persian Gulf") (tanker OR oil OR crude)',
    "Bab-el-Mandeb": '("Red Sea" OR "Bab-el-Mandeb" OR Houthi) (tanker OR ship OR oil)',
    "Suez": '"Suez Canal" (tanker OR ship OR oil)',
    "Malacca": '("Strait of Malacca" OR "Malacca Strait") (tanker OR ship OR oil)',
    "Cape of Good Hope": '"Cape of Good Hope" (tanker OR ship OR reroute)',
}


def get_news_intensity(corridor: str) -> Optional[Dict[str, Any]]:
    """{"fetched_at", "series": {YYYY-MM-DD: articles per million}}, or None if never fetched."""
    path = DATA_DIR / f"gdelt_volume_{corridor.lower().replace(' ', '_').replace('-', '_')}.json"
    cached = None
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - cached["fetched_epoch"] < CACHE_MAX_AGE_SECONDS:
            return cached
    try:
        resp = requests.get(GDELT_URL, params={
            "query": CORRIDOR_QUERIES[corridor], "mode": "timelinevolraw", "format": "json",
            "startdatetime": START, "enddatetime": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        }, headers={"User-Agent": "KrudeEnergySecurityAgent/2.0"}, timeout=60)
        resp.raise_for_status()
        series = {}
        for point in resp.json()["timeline"][0]["data"]:
            day = f"{point['date'][0:4]}-{point['date'][4:6]}-{point['date'][6:8]}"
            norm = point.get("norm") or 0
            series[day] = point["value"] / norm * 1e6 if norm else float(point["value"])
        cached = {"fetched_epoch": time.time(),
                  "fetched_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                  "query": CORRIDOR_QUERIES[corridor], "series": series}
        path.write_text(json.dumps(cached), encoding="utf-8")
    except Exception:
        pass  # keep a stale cache if we have one
    return cached


def _pearson(x: List[float], y: List[float]) -> Optional[float]:
    n = len(x)
    if n < 10:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


def _p_value(r: float, n: int) -> float:
    """Two-sided p-value for Pearson r (normal approximation to the t statistic)."""
    if abs(r) >= 1.0:
        return 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return math.erfc(abs(t) / math.sqrt(2))


def validate(corridor: str) -> Dict[str, Any]:
    news = get_news_intensity(corridor)
    brent = get_brent_history()
    if not news or not brent:
        return {
            "corridor": corridor,
            "status": "UNAVAILABLE",
            "reason": "GDELT coverage timeline not fetched yet (GDELT rate-limits; retried on the next request)"
                      if not news else "Brent history unavailable",
        }

    vol = news["series"]
    days = sorted(vol)
    smoothed = {}
    for i, d in enumerate(days):
        window = [vol[x] for x in days[max(0, i - 6):i + 1]]
        smoothed[d] = sum(window) / len(window)

    trading = [d for d in sorted(brent) if d in smoothed]
    price = [brent[d] for d in trading]
    intensity = [smoothed[d] for d in trading]
    n = len(trading)

    r_level = _pearson(intensity, price)

    lead_lag = []
    for k in range(0, 16):
        xs, ys = [], []
        for t in range(5, n - k):
            xs.append(intensity[t] - intensity[t - 5])
            ys.append(math.log(price[t + k] / price[t]) if k else math.log(price[t] / price[t - 1]))
        r = _pearson(xs, ys)
        if r is not None:
            lead_lag.append({"lag_days": k, "r": round(r, 3), "p_value": round(_p_value(r, len(xs)), 4), "n": len(xs)})
    best = max(lead_lag, key=lambda x: x["r"], default=None)

    # Event study: largest spikes at least 14 trading days apart
    spikes = []
    for t in sorted(range(n - 7), key=lambda t: -intensity[t]):
        if all(abs(t - s) >= 14 for s in spikes):
            spikes.append(t)
        if len(spikes) == 6:
            break
    events = [{
        "date": trading[t],
        "news_intensity": round(intensity[t], 1),
        "brent_usd": price[t],
        "brent_7d_later_usd": price[t + 7],
        "brent_7d_change_pct": round(100 * (price[t + 7] / price[t] - 1), 2),
    } for t in sorted(spikes)]
    avg_abs_move = sum(abs(price[t + 7] / price[t] - 1) for t in range(n - 7)) / max(1, n - 7) * 100
    avg_event_move = sum(e["brent_7d_change_pct"] for e in events) / len(events) if events else None

    if best and best["r"] > 0 and best["p_value"] < 0.05:
        verdict = (f"Rising {corridor} coverage was followed by higher Brent: strongest at {best['lag_days']} trading "
                   f"days (r = {best['r']}, p = {best['p_value']}, overlapping windows make p optimistic).")
    else:
        verdict = (f"No statistically significant lead of {corridor} news intensity over Brent returns at 0-15 "
                   f"trading days (best r = {best['r'] if best else 'n/a'}).")

    return {
        "corridor": corridor,
        "status": "COMPUTED",
        "news_source": f"GDELT DOC 2.0 timelinevolraw, fetched {news['fetched_at']}",
        "news_query": news["query"],
        "price_source": "FRED DCOILBRENTEU (Europe Brent spot)",
        "period": {"start": trading[0], "end": trading[-1], "trading_days": n} if n else None,
        "level_correlation": {"r": round(r_level, 3), "p_value": round(_p_value(r_level, n), 4)} if r_level is not None else None,
        "lead_lag": lead_lag,
        "best_lead": best,
        "spike_events": events,
        "avg_7d_abs_move_pct": round(avg_abs_move, 2),
        "avg_7d_move_after_spikes_pct": round(avg_event_move, 2) if avg_event_move is not None else None,
        "verdict": verdict,
        "timeline": [{"date": trading[t], "news_intensity": round(intensity[t], 2), "brent_usd": price[t]}
                     for t in range(0, n, 5)],
    }
