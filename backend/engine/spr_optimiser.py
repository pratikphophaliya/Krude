"""
Krude - Component 4: Strategic Reserve Optimisation
===================================================
LP (PuLP/CBC) for the daily SPR release against a scenario's supply-gap forecast:

    minimise  sum_t  shortfall_t * (VoLL + small earlier-day tie-break) + d_t * opportunity_cost
    s.t.      R_{t+1} = R_t - d_t
              0 <= d_t <= max hydraulic draw
              shortfall_t >= gap_t - d_t,  shortfall_t >= 0
              R_t >= floor_days * cover_basis + P(follow-on disruption) * tail_gap   (adaptive floor)

gap_t comes from the Disruption Scenario Modeller (it already includes rerouted cargo arrival),
and P(follow-on) from the live corridor probability. "Days of cover" use one basis everywhere:
the official 9.5 days for 39.47 MMbbl implies 4,155 kbd per day of cover.

Fixed-rate policies (steady / aggressive / hold) are simulated with the same accounting.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

SPR_KB = 39470.0               # ISPRL Phase I capacity, thousand barrels (39.47 MMbbl)
OFFICIAL_COVER_DAYS = 9.5      # ISPRL's published cover for that capacity
COVER_BASIS_KBD = SPR_KB / OFFICIAL_COVER_DAYS   # ~4,155 kbd per day of cover
MAX_DRAW_KBD = 450.0           # combined cavern evacuation rate (assumption, assumptions.yaml)
TAIL_GAP_KB = 6400.0           # extra buffer held against a follow-on disruption
VOLL_USD_BBL = 200.0           # value of lost load: economic damage of an unserved barrel
OPPORTUNITY_COST_USD_BBL = 18.0  # cost of drawing (refill premium) vs keeping the barrel

POLICIES = {
    "steady": {"rate_kbd": 180.0, "label": "Steady release"},
    "aggressive": {"rate_kbd": 350.0, "label": "Aggressive early release"},
    "hold": {"rate_kbd": 65.0, "label": "Hold & conserve"},
}


def cover_days(kb: float) -> float:
    return kb / COVER_BASIS_KBD


class StrategicReserveOptimiser:
    """Component 4: SPR drawdown LP and fixed-policy simulation."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.caverns = [
            {"id": "VIZAG", "name": "Visakhapatnam SPR", "location": "Andhra Pradesh (East Coast)", "capacity_mbbl": 9.77},
            {"id": "MANGALORE", "name": "Mangalore SPR", "location": "Karnataka (West Coast)", "capacity_mbbl": 11.00},
            {"id": "PADUR", "name": "Padur SPR", "location": "Karnataka (West Coast)", "capacity_mbbl": 18.70},
        ]

    def optimize_drawdown_lp(self, net_deficit_kbd_by_day: List[float], p_followon: float,
                             base_supply_kbd: float, safety_floor_days: float = 3.0,
                             initial_spr_kb: float = SPR_KB) -> Dict[str, Any]:
        T = len(net_deficit_kbd_by_day)
        floor_kb = safety_floor_days * COVER_BASIS_KBD + p_followon * TAIL_GAP_KB
        draws, shortfalls, solver, status = self._solve(net_deficit_kbd_by_day, initial_spr_kb, floor_kb)

        timeline, reserve = [], initial_spr_kb
        for t in range(T):
            reserve -= draws[t]
            timeline.append({
                "day": t + 1,
                "net_deficit_pre_spr_kbd": round(net_deficit_kbd_by_day[t], 1),
                "spr_drawdown_kbd": round(draws[t], 1),
                "unmet_shortfall_kbd": round(shortfalls[t], 1),
                "remaining_spr_kb": round(reserve, 1),
                "remaining_spr_days": round(cover_days(reserve), 2),
                "available_supply_kbd": round(base_supply_kbd - shortfalls[t], 1),
            })

        drawing_days = [p["day"] for p in timeline if p["spr_drawdown_kbd"] > 0.5]
        at_max = sum(1 for d in draws if d >= MAX_DRAW_KBD - 0.5)
        peak_pre, peak_post = max(net_deficit_kbd_by_day, default=0.0), max(shortfalls, default=0.0)
        if drawing_days:
            strategy = (f"Release on days {drawing_days[0]}-{drawing_days[-1]} ({at_max} days at the "
                        f"{MAX_DRAW_KBD:.0f} kbd maximum); reserve ends at {cover_days(reserve):.1f} days of cover "
                        f"against a {cover_days(floor_kb):.1f}-day adaptive floor.")
        else:
            strategy = "No release needed: the scenario creates no supply gap."

        return {
            "optimization_model": "Minimise VoLL x shortfall + opportunity cost x drawdown",
            "solver": solver,
            "status": status,
            "parameters": {
                "duration_days": T,
                "p_followon_disruption": round(p_followon, 4),
                "safety_floor_days": safety_floor_days,
                "adaptive_reserve_floor_kb": round(floor_kb, 1),
                "initial_spr_kb": initial_spr_kb,
                "max_draw_kbd": MAX_DRAW_KBD,
                "cover_basis_kbd": round(COVER_BASIS_KBD, 1),
                "voll_usd_bbl": VOLL_USD_BBL,
                "opportunity_cost_usd_bbl": OPPORTUNITY_COST_USD_BBL,
            },
            "summary": {
                "total_spr_evacuated_kb": round(sum(draws), 1),
                "total_spr_evacuated_mbbl": round(sum(draws) / 1000.0, 2),
                "final_remaining_spr_kb": round(reserve, 1),
                "final_remaining_spr_days": round(cover_days(reserve), 2),
                "unmet_shortfall_total_kb": round(sum(shortfalls), 1),
                "peak_deficit_pre_spr_kbd": round(peak_pre, 1),
                "peak_deficit_post_spr_kbd": round(peak_post, 1),
                "deficit_mitigation_pct": round(100.0 * (peak_pre - peak_post) / peak_pre, 1) if peak_pre else 100.0,
                "drawdown_strategy": strategy,
            },
            "timeline": timeline,
        }

    def _solve(self, gaps: List[float], initial_kb: float, floor_kb: float):
        """PuLP/CBC; if PuLP is unavailable or fails, a greedy earliest-day-first draw (labelled)."""
        T = len(gaps)
        try:
            import pulp
            prob = pulp.LpProblem("spr_drawdown", pulp.LpMinimize)
            d = [pulp.LpVariable(f"d_{t}", lowBound=0, upBound=MAX_DRAW_KBD) for t in range(T)]
            s = [pulp.LpVariable(f"s_{t}", lowBound=0) for t in range(T)]
            R = [pulp.LpVariable(f"R_{t}", lowBound=floor_kb) for t in range(T + 1)]
            # Small decreasing term breaks ties toward covering earlier days first
            prob += pulp.lpSum(s[t] * (VOLL_USD_BBL + 0.05 * (T - t)) + d[t] * OPPORTUNITY_COST_USD_BBL for t in range(T))
            prob += R[0] == initial_kb
            for t in range(T):
                prob += R[t + 1] == R[t] - d[t]
                prob += s[t] >= gaps[t] - d[t]
            prob.solve(pulp.PULP_CBC_CMD(msg=False))
            status = pulp.LpStatus[prob.status]
            if status == "Optimal":
                return [d[t].value() or 0.0 for t in range(T)], [s[t].value() or 0.0 for t in range(T)], "PuLP CBC linear program", status
        except Exception:
            pass

        draws, shortfalls, reserve = [], [], initial_kb
        for gap in gaps:
            draw = max(0.0, min(gap, MAX_DRAW_KBD, reserve - floor_kb))
            reserve -= draw
            draws.append(draw)
            shortfalls.append(gap - draw)
        return draws, shortfalls, "Greedy earliest-day-first (PuLP unavailable)", "HEURISTIC"

    def simulate_policies(self, horizon_days: int = 90, safety_floor_days: float = 3.0,
                          initial_spr_kb: float = SPR_KB) -> Dict[str, Any]:
        """Days of cover over time for fixed release rates, stopping at the safety floor."""
        floor_kb = safety_floor_days * COVER_BASIS_KBD
        out = {}
        for key, p in POLICIES.items():
            reserve, curve, exhausted_day = initial_spr_kb, [], None
            for day in range(1, horizon_days + 1):
                reserve = max(floor_kb, reserve - p["rate_kbd"])
                if exhausted_day is None and reserve <= floor_kb:
                    exhausted_day = day
                curve.append(round(cover_days(reserve), 2))
            days_to_floor = (initial_spr_kb - floor_kb) / p["rate_kbd"]
            out[key] = {
                **p,
                "days_to_floor": round(days_to_floor, 1),
                "floor_reached_within_horizon": exhausted_day is not None,
                "cover_days_curve": curve,
                "verdict": (f"Releasing {p['rate_kbd']:.0f} kbd draws the reserve from {OFFICIAL_COVER_DAYS} to the "
                            f"{safety_floor_days:.1f}-day floor in {days_to_floor:.0f} days."),
            }
        return {
            "initial_cover_days": round(cover_days(initial_spr_kb), 2),
            "safety_floor_days": safety_floor_days,
            "cover_basis_kbd": round(COVER_BASIS_KBD, 1),
            "horizon_days": horizon_days,
            "policies": out,
        }
