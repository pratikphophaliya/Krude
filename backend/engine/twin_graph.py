"""
Krude - Component 5: Supply Chain Digital Twin graph
====================================================
Builds the map the dashboard draws: load port -> chokepoints (in transit order) -> Indian
discharge port, with each route's flow in kbd.

Flow per route = the country's 3-month trailing average imports split across its routes in
proportion to route capacity (the same split used for corridor exposure). Port coordinates are
in data/ports.csv; SPR caverns come from data/spr_facilities.csv.
"""

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

try:
    from engine.database import db
except ImportError:
    from backend.engine.database import db

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CHOKEPOINT_NAMES = {
    "hormuz": "Hormuz",
    "bab_el_mandeb": "Bab-el-Mandeb",
    "suez": "Suez",
    "malacca": "Malacca",
    "cape_of_good_hope": "Cape of Good Hope",
}

ROUTE_FLOWS_SQL = """
WITH latest_3m AS (SELECT DISTINCT month FROM imports ORDER BY month DESC LIMIT 3),
trailing AS (
    SELECT country, AVG(volume_kbd) AS avg_kbd FROM imports
    WHERE month IN (SELECT month FROM latest_3m) GROUP BY country
)
SELECT r.route_id, t.country, r.load_port, r.primary_discharge_port AS discharge_port,
       r.chokepoints_all AS chokepoints, r.transit_days,
       t.avg_kbd * r.capacity_kbd / SUM(r.capacity_kbd) OVER (PARTITION BY t.country) AS kbd
FROM trailing t
JOIN routes r ON LOWER(TRIM(t.country)) = LOWER(TRIM(COALESCE(r.source_country, r.source)))
"""


def _ports() -> Dict[str, Dict[str, Any]]:
    with open(DATA_DIR / "ports.csv", encoding="utf-8") as f:
        return {r["port"]: {"kind": r["kind"], "lat": float(r["lat"]), "lon": float(r["lon"])}
                for r in csv.DictReader(f)}


def _spr_sites() -> List[Dict[str, Any]]:
    with open(DATA_DIR / "spr_facilities.csv", encoding="utf-8") as f:
        return [{
            "id": f"spr:{r['facility_name']}",
            "name": f"{r['facility_name']} SPR",
            "type": "spr",
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
            "label": f"{float(r['capacity_mmbbl']):.1f} MMbbl",
        } for r in csv.DictReader(f) if r["status"] == "Operational"]


def build_twin_graph(min_kbd: float = 1.0) -> Dict[str, Any]:
    ports = _ports()
    flows = [r for r in db.query_duckdb(ROUTE_FLOWS_SQL) if (r["kbd"] or 0) >= min_kbd]
    total_imports = db.get_corridor_exposure()["total_import_demand_kbd"]

    nodes: Dict[str, Dict[str, Any]] = {}
    segments: Dict[tuple, Dict[str, Any]] = {}
    port_volume = defaultdict(float)

    def add_node(node_id: str, name: str, kind: str, port_key: str, country: str = None):
        if node_id not in nodes and port_key in ports:
            p = ports[port_key]
            nodes[node_id] = {"id": node_id, "name": name, "type": kind, "lat": p["lat"], "lon": p["lon"],
                              "country": country, "kbd": 0.0}
        return node_id in nodes

    routes_out, missing = [], set()
    for f in flows:
        chokes = [c for c in str(f["chokepoints"]).split("|") if c in CHOKEPOINT_NAMES]
        src, dst = f"load:{f['load_port']}", f"dest:{f['discharge_port']}"
        ok = add_node(src, f["load_port"], "origin", f["load_port"], f["country"])
        ok &= add_node(dst, f["discharge_port"], "dest", f["discharge_port"])
        for c in chokes:
            ok &= add_node(f"choke:{c}", CHOKEPOINT_NAMES[c], "choke", c)
        if not ok:
            missing.add(f["load_port"])
            continue

        kbd = float(f["kbd"])
        path = [src] + [f"choke:{c}" for c in chokes] + [dst]
        for node_id in path:
            nodes[node_id]["kbd"] += kbd
        for a, b in zip(path, path[1:]):
            seg = segments.setdefault((a, b), {"from": a, "to": b, "kbd": 0.0, "corridors": set()})
            seg["kbd"] += kbd
            seg["corridors"].update(CHOKEPOINT_NAMES[c] for c in chokes)
        port_volume[f["discharge_port"]] += kbd
        routes_out.append({
            "route_id": f["route_id"], "country": f["country"], "load_port": f["load_port"],
            "discharge_port": f["discharge_port"], "corridors": [CHOKEPOINT_NAMES[c] for c in chokes],
            "transit_days": f["transit_days"], "kbd": round(kbd, 1),
        })

    for n in nodes.values():
        n["kbd"] = round(n["kbd"], 1)
    mapped = sum(r["kbd"] for r in routes_out)
    return {
        "basis": "3-month trailing average imports (imports_wide.csv), split across each supplier's routes by capacity",
        "total_imports_kbd": total_imports,
        "mapped_kbd": round(mapped, 1),
        "unmapped_kbd": round(max(0.0, total_imports - mapped), 1),
        "nodes": list(nodes.values()) + _spr_sites(),
        "segments": [{**s, "kbd": round(s["kbd"], 1), "corridors": sorted(s["corridors"])} for s in segments.values()],
        "routes": sorted(routes_out, key=lambda r: -r["kbd"]),
        "discharge_port_kbd": {k: round(v, 1) for k, v in sorted(port_volume.items(), key=lambda x: -x[1])},
        "ports_without_coordinates": sorted(missing),
    }
