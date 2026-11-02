"""
Krude - Component 3: Adaptive Procurement Orchestrator
======================================================
Ranks and allocates replacement crude across every (supplier grade x shipping route) option
in the DuckDB/SQLite dataset:

- Landed cost = FOB + searoute freight + quality penalty
    quality_adj = 0.25*max(0, 32-API) + 0.30*max(0, S-2.0) + 0.10*max(0, API-38)
- Risk-adjusted cost = landed + P(route disrupted in 30d) * DISRUPTION_COST_USD_BBL,
  where P(route) = 1 - prod(1 - P(chokepoint)) over the route's chokepoints, from the live
  corridor probabilities of the Risk Intelligence Agent.
- Allocation is a linear program (PuLP/CBC): minimise risk-adjusted cost subject to
  per-country liftable caps (1.4 x peak 24-month import volume) and per-route capacity.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import pulp

try:
    from engine.database import db
except ImportError:
    from backend.engine.database import db

# Expected cost of a disrupted barrel (spot replacement premium + delay/demurrage), $/bbl.
# A stated assumption: it converts route disruption probability into $/bbl so risk and price trade off.
DISRUPTION_COST_USD_BBL = 40.0
# Penalty on unmet demand in the LP; far above any landed cost so the solver always buys if it can
UNMET_PENALTY_USD_BBL = 1000.0

CORRIDOR_TO_CHOKEPOINT = {
    "Hormuz": "hormuz",
    "Bab-el-Mandeb": "bab_el_mandeb",
    "Suez": "suez",
    "Malacca": "malacca",
    "Cape of Good Hope": "cape_of_good_hope",
}


class AdaptiveProcurementOrchestrator:
    """Component 3: risk-adjusted supplier ranking and LP allocation over real landed-cost options."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.db = db

    def _options(self, corridor_p: Dict[str, float], blocked_chokepoints: Optional[List[str]] = None,
                 allow_sanctioned: bool = False) -> List[Dict[str, Any]]:
        """Liftable landed-cost options with route disruption probability and risk-adjusted cost."""
        p_by_choke = {CORRIDOR_TO_CHOKEPOINT.get(k, k): v for k, v in corridor_p.items()}
        options = []
        for o in self.db.get_landed_procurement_options(avoid_chokepoints=blocked_chokepoints):
            if (o["sanctioned"] and not allow_sanctioned) or not o["max_liftable_kbd"]:
                continue  # zero liftable = no import history to scale from
            p_clear = 1.0
            for choke in (o["chokepoint"] or "none").split("|"):
                p_clear *= 1.0 - p_by_choke.get(choke, 0.0)
            p_route = 1.0 - p_clear
            options.append(dict(
                o,
                route_disruption_p=round(p_route, 4),
                risk_premium_usd_bbl=round(p_route * DISRUPTION_COST_USD_BBL, 2),
                risk_adjusted_cost_usd_bbl=round(o["total_landed_cost_usd_bbl"] + p_route * DISRUPTION_COST_USD_BBL, 2),
            ))
        return options

    @staticmethod
    def _route_label(chokepoint: str) -> str:
        if not chokepoint or chokepoint == "none":
            return "Direct (no chokepoint)"
        names = {v: k for k, v in CORRIDOR_TO_CHOKEPOINT.items()}
        return " + ".join(names.get(c, c) for c in chokepoint.split("|"))

    def rank_suppliers(self, corridor_p: Dict[str, float], top_n: int = 12) -> Dict[str, Any]:
        """Best route per supplier grade, ranked by risk-adjusted landed cost (lower is better)."""
        best: Dict[tuple, Dict[str, Any]] = {}
        for o in self._options(corridor_p):
            key = (o["country"], o["grade"])
            if key not in best or o["risk_adjusted_cost_usd_bbl"] < best[key]["risk_adjusted_cost_usd_bbl"]:
                best[key] = o

        ranked = sorted(best.values(), key=lambda o: o["risk_adjusted_cost_usd_bbl"])[:top_n]
        out = []
        for rank, o in enumerate(ranked, start=1):
            route = self._route_label(o["chokepoint"])
            out.append({
                "rank": rank,
                "supplier": o["country"],
                "crude_grade": o["grade"],
                "origin_terminal": o["origin_port"],
                "dest_port": o["dest_port"],
                "chokepoint_route": route,
                "searoute_days": o["transit_days"],
                "max_liftable_kbd": round(o["max_liftable_kbd"], 1),
                "landed_cost_usd": o["total_landed_cost_usd_bbl"],
                "risk_adjusted_cost_usd_bbl": o["risk_adjusted_cost_usd_bbl"],
                "route_disruption_p": o["route_disruption_p"],
                "fob_usd_bbl": o["base_fob_usd_per_bbl"],
                "freight_usd_bbl": o["freight_usd_per_bbl"],
                "quality_penalty_usd_bbl": o["quality_adj_usd_per_bbl"],
                "why": (
                    f"{o['grade']} ({o['api_gravity']}° API, {o['sulphur_pct']}% S) from {o['origin_port']} to "
                    f"{o['dest_port']} via {route}: FOB ${o['base_fob_usd_per_bbl']:.2f} + freight "
                    f"${o['freight_usd_per_bbl']:.2f} + quality ${o['quality_adj_usd_per_bbl']:.2f} = "
                    f"${o['total_landed_cost_usd_bbl']:.2f}/bbl. {o['route_disruption_p']:.1%} 30-day route "
                    f"disruption risk adds ${o['risk_premium_usd_bbl']:.2f} -> ${o['risk_adjusted_cost_usd_bbl']:.2f}/bbl. "
                    f"Up to {o['max_liftable_kbd']:,.0f} kbd liftable (1.4x peak 24-month imports)."
                ),
            })

        return {
            "component_label": "Real — ranked over DuckDB landed-cost options with live corridor risk",
            "formula": f"risk_adjusted = FOB + freight + quality_penalty + P(route disrupted 30d) x ${DISRUPTION_COST_USD_BBL:.0f}/bbl",
            "optimization_direction": "Lower risk-adjusted cost = better",
            "active_corridor_probabilities": corridor_p,
            "ranked_suppliers": out,
            "optimal_recommendation": out[0] if out else None,
        }

    def generate_procurement_plan(self, required_deficit_mbpd: float, corridor_p: Dict[str, float],
                                  blocked_chokepoints: Optional[List[str]] = None,
                                  allow_sanctioned: bool = False) -> Dict[str, Any]:
        """LP allocation of the supply deficit across options, respecting country and route capacity."""
        options = self._options(corridor_p, blocked_chokepoints, allow_sanctioned)
        deficit_kbd = required_deficit_mbpd * 1000.0

        prob = pulp.LpProblem("crude_procurement", pulp.LpMinimize)
        x = [pulp.LpVariable(f"x_{i}", lowBound=0) for i in range(len(options))]
        unmet = pulp.LpVariable("unmet", lowBound=0)
        prob += pulp.lpSum(o["risk_adjusted_cost_usd_bbl"] * x[i] for i, o in enumerate(options)) + UNMET_PENALTY_USD_BBL * unmet
        prob += pulp.lpSum(x) + unmet == deficit_kbd

        by_country, by_route = defaultdict(list), defaultdict(list)
        for i, o in enumerate(options):
            by_country[o["country"]].append(i)
            by_route[o["route_id"]].append(i)
        for country, idx in by_country.items():
            prob += pulp.lpSum(x[i] for i in idx) <= options[idx[0]]["max_liftable_kbd"], f"cap_{len(prob.constraints)}"
        for route_id, idx in by_route.items():
            prob += pulp.lpSum(x[i] for i in idx) <= options[idx[0]]["route_capacity_kbd"], f"route_{len(prob.constraints)}"

        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        status = pulp.LpStatus[prob.status]
        if status != "Optimal":
            raise RuntimeError(f"Procurement LP did not solve: {status}")

        orders = []
        for i, o in enumerate(options):
            kbd = x[i].value() or 0.0
            if kbd < 0.05:
                continue
            orders.append({
                "country": o["country"],
                "grade": o["grade"],
                "origin_port": o["origin_port"],
                "dest_port": o["dest_port"],
                "route_type": o["route_type"],
                "transit_days": o["transit_days"],
                "chokepoints": o["chokepoint"],
                "route_disruption_p": o["route_disruption_p"],
                "allocated_volume_kbd": round(kbd, 1),
                "allocated_volume_mbpd": round(kbd / 1000.0, 3),
                "base_fob_usd_bbl": o["base_fob_usd_per_bbl"],
                "freight_cost_usd_bbl": o["freight_usd_per_bbl"],
                "quality_penalty_usd_bbl": o["quality_adj_usd_per_bbl"],
                "total_landed_cost_usd_bbl": o["total_landed_cost_usd_bbl"],
                "risk_adjusted_cost_usd_bbl": o["risk_adjusted_cost_usd_bbl"],
                "total_daily_cost_usd_million": round(kbd * o["total_landed_cost_usd_bbl"] / 1000.0, 2),
            })
        orders.sort(key=lambda r: -r["allocated_volume_kbd"])

        procured_kbd = sum(r["allocated_volume_kbd"] for r in orders)
        spend = sum(r["allocated_volume_kbd"] * r["total_landed_cost_usd_bbl"] for r in orders)
        return {
            "solver": "PuLP CBC linear program",
            "solver_status": status,
            "target_deficit_mbpd": required_deficit_mbpd,
            "procured_volume_mbpd": round(procured_kbd / 1000.0, 3),
            "unmet_deficit_mbpd": round((unmet.value() or 0.0) / 1000.0, 3),
            "average_landed_cost_usd_bbl": round(spend / procured_kbd, 2) if procured_kbd else None,
            "total_allocated_daily_spend_usd_million": round(spend / 1000.0, 2),
            "allocated_orders": orders,
            "constraints_applied": {
                "blocked_chokepoints": blocked_chokepoints or [],
                "allow_sanctioned": allow_sanctioned,
                "per_country_liftable_cap": True,
                "per_route_capacity": True,
                "disruption_cost_usd_bbl": DISRUPTION_COST_USD_BBL,
            },
        }
