"""
Krude - Brent Crude Market Data
===============================
- Daily history: FRED series DCOILBRENTEU (Europe Brent spot FOB, source EIA). Keyless CSV,
  refreshed at most once a day and cached in data/brent_history.csv.
- Latest price: ICE Brent front-month futures (Yahoo Finance BZ=F), falling back to the
  latest FRED close. Every value carries its source and as-of date.
"""

import csv
import io
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "brent_history.csv"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
HISTORY_MAX_AGE_SECONDS = 24 * 3600
SPOT_MAX_AGE_SECONDS = 15 * 60

_history: Dict[str, Any] = {"mtime": 0.0, "prices": {}}
_spot: Dict[str, Any] = {"at": 0.0, "value": None}


def get_brent_history() -> Dict[str, float]:
    """Daily Brent spot {YYYY-MM-DD: $/bbl}. Uses the cached file if FRED is unreachable."""
    stale = not HISTORY_FILE.exists() or time.time() - HISTORY_FILE.stat().st_mtime > HISTORY_MAX_AGE_SECONDS
    if stale:
        try:
            resp = requests.get(FRED_URL, params={"id": "DCOILBRENTEU", "cosd": "2023-01-01"}, timeout=20)
            resp.raise_for_status()
            HISTORY_FILE.write_text(resp.text, encoding="utf-8")
        except Exception:
            pass
    if not HISTORY_FILE.exists():
        return {}

    mtime = HISTORY_FILE.stat().st_mtime
    if mtime != _history["mtime"]:
        prices = {}
        for row in csv.reader(io.StringIO(HISTORY_FILE.read_text(encoding="utf-8"))):
            try:
                prices[row[0]] = float(row[1])
            except (ValueError, IndexError):
                continue  # header row and "." placeholders on market holidays
        _history.update(mtime=mtime, prices=prices)
    return _history["prices"]


def brent_on(date_str: str) -> Optional[float]:
    """Brent spot on a date, or the last trading day before it (None before the series starts)."""
    prices = get_brent_history()
    earlier = [d for d in prices if d <= date_str]
    return prices[max(earlier)] if earlier else None


def get_brent_spot() -> Dict[str, Any]:
    """Latest Brent price with its source; futures from Yahoo, else the latest FRED spot close."""
    if _spot["value"] and time.time() - _spot["at"] < SPOT_MAX_AGE_SECONDS:
        return _spot["value"]
    value = None
    try:
        resp = requests.get(YAHOO_URL, params={"range": "5d", "interval": "1d"},
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        value = {
            "price_usd": round(float(meta["regularMarketPrice"]), 2),
            "as_of": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).isoformat(timespec="minutes"),
            "source": "ICE Brent front-month futures (Yahoo Finance BZ=F)",
        }
    except Exception:
        prices = get_brent_history()
        if prices:
            last = max(prices)
            value = {"price_usd": prices[last], "as_of": last, "source": "Europe Brent spot (FRED DCOILBRENTEU)"}
    if value:
        _spot.update(at=time.time(), value=value)
    return value or {"price_usd": None, "as_of": None, "source": "unavailable"}
