"""
Krude - Component 2: Disruption Scenario Modeller
=================================================
Simulates a disruption of one corridor (severity phi, duration T days) and its cascade:

1. India's physical gap: phi x India's barrels behind the chokepoint (3-month trailing imports
   split across each supplier's routes, from the DuckDB corridor_exposure table). If ships can
   divert, the gap lasts only the extra voyage days; Hormuz has no sea reroute.
2. Global supply lost: phi x (corridor global flow - pipeline bypass), or for reroutable
   corridors the in-transit gap averaged over the episode.
3. Brent: dP = live Brent x (lost share of global supply) / short-run elasticity.
4. India: import bill, retail fuel (Rs/L), refinery utilisation, and GDP/CAD rules of thumb
   scaled by duration/365 (they are quoted per +$10/bbl sustained for a year).

All constants and their sources are in data/assumptions.yaml (scenario_model).
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

try:
    from engine.database import db
    from engine.market_data import get_brent_spot, get_usd_inr
except ImportError:
    from backend.engine.database import db
    from backend.engine.market_data import get_brent_spot, get_usd_inr

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CHOKEPOINT_KEY = {
    "Hormuz": "hormuz",
    "Bab-el-Mandeb": "bab_el_mandeb",
    "Suez": "suez",
    "Malacca": "malacca",
    "Cape of Good Hope": "cape_of_good_hope",
}


@lru_cache(maxsize=1)
def _assumptions() -> Dict[str, Any]:
    return yaml.safe_load((DATA_DIR / "assumptions.yaml").read_text(encoding="utf-8"))


def _market_baseline() -> Dict[str, Any]:
    """Live Brent and USD/INR, falling back to the stated baseline in assumptions.yaml."""
    a = _assumptions()
    brent = get_brent_spot()
    fx = get_usd_inr()
    return {
        "brent_usd": brent["price_usd"] or a["national_energy_baseline"]["baseline_brent_price_usd"],
        "brent_source": brent["source"] if brent["price_usd"] else "assumptions.yaml baseline (market data unavailable)",
        "brent_as_of": brent["as_of"],
        "inr_per_usd": fx["inr_per_usd"] or a["macro_simulation_constants"]["USD_INR"],
        "inr_source": fx["source"] if fx["inr_per_usd"] else "assumptions.yaml baseline (market data unavailable)",
    }


def run_scenario(corridor: str, phi: float, duration_days: int,
                 price_rise_override: Optional[float] = None) -> Dict[str, Any]:
    """Core scenario calculation; see the module docstring for the method."""
    a = _assumptions()["scenario_model"]
    cfg = a["corridors"][corridor]
    phi = max(0.0, min(1.0, float(phi)))
    duration = max(1, int(duration_days))
    market = _market_baseline()

    # 1. India's physical gap
    exposure = db.get_corridor_exposure()
    india_imports_kbd = exposure["total_import_demand_kbd"]
    india_exposed_kbd = exposure["corridors"][CHOKEPOINT_KEY[corridor]]["volume_at_risk_kbd"]
    blocked_kbd = india_exposed_kbd * phi
    extra_days = cfg["reroute_extra_days"]
    gap_days = duration if extra_days is None else min(duration, extra_days)
    gap_kbd_by_day = [round(blocked_kbd, 1) if d < gap_days else 0.0 for d in range(duration)]

    # 2. Global supply lost
    if extra_days is None:
        global_loss_mbpd = phi * max(0.0, cfg["global_flow_mbpd"] - cfg["bypass_mbpd"])
    else:
        global_loss_mbpd = phi * cfg["global_flow_mbpd"] * gap_days / duration
    lost_share = global_loss_mbpd / a["global_liquids_supply_mbpd"]

    # 3. Brent
    modelled_rise = market["brent_usd"] * lost_share / a["price_elasticity_short_run"]
    price_rise = modelled_rise if price_rise_override is None else float(price_rise_override)
    freight_premium = 0.0 if extra_days is None else extra_days * a["freight_premium_usd_per_bbl_per_extra_day"]

    # 4. India macro transmission
    import_bill_usd_b = (price_rise * india_imports_kbd + freight_premium * blocked_kbd) * duration / 1e6
    refinery_runs_kbd = india_imports_kbd + a["india_domestic_crude_kbd"]
    avg_gap_kbd = sum(gap_kbd_by_day) / duration
    year_share = duration / 365.0

    return {
        "corridor": corridor,
        "phi": phi,
        "duration_days": duration,
        "market_baseline": market,
        "india_imports_kbd": round(india_imports_kbd, 1),
        "india_crude_runs_kbd": round(refinery_runs_kbd, 1),
        "india_exposed_kbd": round(india_exposed_kbd, 1),
        "india_exposed_share_pct": round(100.0 * india_exposed_kbd / india_imports_kbd, 1) if india_imports_kbd else 0.0,
        "daily_gap_kbd": round(blocked_kbd, 1),
        "daily_gap_mbpd": round(blocked_kbd / 1000.0, 3),
        "gap_days": gap_days,
        "reroute_extra_days": extra_days,
        "gap_kbd_by_day": gap_kbd_by_day,
        "global_supply_loss_mbpd": round(global_loss_mbpd, 2),
        "global_supply_loss_pct": round(100.0 * lost_share, 2),
        "modelled_price_rise_usd": round(modelled_rise, 2),
        "price_rise_usd": round(price_rise, 2),
        "price_rise_is_override": price_rise_override is not None,
        "new_brent_usd": round(market["brent_usd"] + price_rise, 2),
        "freight_premium_usd_bbl": round(freight_premium, 2),
        "import_bill_delta_usd_billion": round(import_bill_usd_b, 2),
        "import_bill_delta_inr_crore": round(import_bill_usd_b * 1e9 * market["inr_per_usd"] / 1e7, 0),
        "retail_fuel_rs_per_litre": round(price_rise * market["inr_per_usd"] / a["litres_per_barrel"] * a["retail_pass_through"], 2),
        "refinery_utilization_drop_avg_pct": round(100.0 * avg_gap_kbd / refinery_runs_kbd, 1),
        "refinery_utilization_drop_peak_pct": round(100.0 * blocked_kbd / refinery_runs_kbd, 1) if gap_days else 0.0,
        "gdp_impact_pp": round(price_rise / 10.0 * a["gdp_pp_per_10usd_year"] * year_share, 3),
        "cad_impact_bps": round(price_rise / 10.0 * a["cad_bps_per_10usd_year"] * year_share, 1),
    }


class DisruptionScenarioModeller:
    """Component 2: wraps run_scenario with the response shape used by the API and dashboard."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.db = db

    def simulate(self, corridor: str = "Hormuz", disruption_duration_days: int = 30,
                 disruption_severity_pct: float = 50.0,
                 price_rise_usd_per_barrel: Optional[float] = None) -> Dict[str, Any]:
        r = run_scenario(corridor, disruption_severity_pct / 100.0, disruption_duration_days, price_rise_usd_per_barrel)
        reroute = (f"ships divert (+{r['reroute_extra_days']} days), so India's gap lasts {r['gap_days']} days"
                   if r["reroute_extra_days"] is not None else "no sea reroute exists, so the gap lasts the whole disruption")
        return {
            "component_label": "Simulated — rule-of-thumb model fed by real import exposure and live Brent/USD-INR",
            "scenario_inputs": {
                "corridor": corridor,
                "disruption_duration_days": r["duration_days"],
                "disruption_severity_pct": disruption_severity_pct,
                "price_rise_usd_per_barrel": r["price_rise_usd"],
                "price_rise_is_override": r["price_rise_is_override"],
                "corridor_baseline_exposure_kbd": r["india_exposed_kbd"],
                "corridor_baseline_exposure_mbpd": round(r["india_exposed_kbd"] / 1000.0, 3),
                "blocked_supply_kbd": r["daily_gap_kbd"],
                "blocked_supply_mbpd": r["daily_gap_mbpd"],
            },
            "market_baseline": r["market_baseline"],
            "impacts": {
                "global_supply_loss_mbpd": r["global_supply_loss_mbpd"],
                "global_supply_loss_pct": r["global_supply_loss_pct"],
                "new_brent_usd": r["new_brent_usd"],
                "freight_premium_usd_bbl": r["freight_premium_usd_bbl"],
                "estimated_additional_cost_usd_billion": r["import_bill_delta_usd_billion"],
                "estimated_additional_cost_inr_crore": r["import_bill_delta_inr_crore"],
                "retail_fuel_rs_per_litre": r["retail_fuel_rs_per_litre"],
                "refining_utilization_drop_pct": r["refinery_utilization_drop_avg_pct"],
                "refining_utilization_drop_peak_pct": r["refinery_utilization_drop_peak_pct"],
                "gdp_impact_pp": r["gdp_impact_pp"],
                "cad_impact_bps": r["cad_impact_bps"],
                "blocked_supply_volume_mbpd": r["daily_gap_mbpd"],
                "gap_days": r["gap_days"],
            },
            "india_imports_kbd": r["india_imports_kbd"],
            "india_exposed_share_pct": r["india_exposed_share_pct"],
            "gap_kbd_by_day": r["gap_kbd_by_day"],
            "explanation": (
                f"{r['india_exposed_kbd']:,.0f} kbd of India's {r['india_imports_kbd']:,.0f} kbd imports "
                f"({r['india_exposed_share_pct']}%) pass {corridor}. At {disruption_severity_pct:.0f}% severity "
                f"{r['daily_gap_kbd']:,.0f} kbd is blocked; {reroute}. Globally {r['global_supply_loss_mbpd']} MBPD "
                f"({r['global_supply_loss_pct']}% of supply) is lost, moving Brent from ${r['market_baseline']['brent_usd']:.2f} "
                f"by +${r['price_rise_usd']:.2f}/bbl. Over {r['duration_days']} days India's import bill rises "
                f"${r['import_bill_delta_usd_billion']:.2f}B (GDP {r['gdp_impact_pp']:+.3f} pp, CAD +{r['cad_impact_bps']:.0f} bps)."
            ),
        }


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Disruption scenario engine")
    parser.add_argument("--corridor", default="Hormuz", choices=list(CHOKEPOINT_KEY))
    parser.add_argument("--phi", type=float, default=0.5, help="Severity fraction 0-1")
    parser.add_argument("--duration", type=int, default=30, help="Days")
    args = parser.parse_args()
    print(json.dumps(DisruptionScenarioModeller().simulate(args.corridor, args.duration, args.phi * 100), indent=2))
