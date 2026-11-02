"""
Krude - Energy Supply Chain & Geopolitical Risk Digital Twin API
=============================================================================
A lightweight FastAPI backend powering the single-page Krude dashboard with
unified DuckDB/SQLite storage, real Searoute marine distances, crude quality adjustments,
and live procurement optimization.

Honesty & Truthfulness Mapping:
- Component 1: Risk Intelligence Agent — REAL (live GDELT DOC 2.0 headlines + fine-tuned Llama 3.2 3B inference)
- Component 2: Disruption Scenario Modeller — SIMULATED (rule-of-thumb formulas, user assumptions)
- Component 3: Adaptive Procurement Orchestrator — REAL (live optimization against DuckDB/SQLite dataset with crude quality penalty)
- Component 4: Strategic Reserve Optimisation Agent — SIMULATED (9.5 days real baseline, stated assumptions)
- Component 5: Supply Chain Digital Twin — Unified state-based dashboard
"""

import os
import sys
import json
import time
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, List, Literal

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
FRONTEND_DIR = ROOT_DIR / "frontend"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

# First run (fresh clone): build the DuckDB/SQLite database from the CSVs in backend/data
from engine.database import db, DUCKDB_PATH
if not DUCKDB_PATH.exists():
    from data.db_loader import build_all
    build_all()

from engine.risk_intel import RiskIntelligenceAgent, CORRIDORS
from engine.scenario_modeller import DisruptionScenarioModeller, run_scenario
from engine.procurement_orchestrator import AdaptiveProcurementOrchestrator
from engine.spr_optimiser import StrategicReserveOptimiser
from engine.fine_tuning_adapter import AIModelManager
from engine.live_poller import live_manager
from engine.validation import validate
from engine.twin_graph import build_twin_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the live SSE broadcast loop with the shared risk agent."""
    live_manager.start_live_poller(risk_agent)
    yield
    live_manager.stop_live_poller()

app = FastAPI(
    lifespan=lifespan,
    title="Krude - Energy Supply Chain Digital Twin",
    description="Unified DuckDB/SQLite energy intelligence platform with real Searoute marine graphs, fine-tuned Llama 3.2 3B + LoRA AI model, crude quality penalties, and live procurement optimization.",
    version="3.2.0"
)

# The dashboard is served from this app (same origin); only listed origins may call the API cross-site
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Initialize engines
risk_agent = RiskIntelligenceAgent(DATA_DIR, MODELS_DIR)
scenario_modeller = DisruptionScenarioModeller()
procurement_orchestrator = AdaptiveProcurementOrchestrator(DATA_DIR)
spr_optimiser = StrategicReserveOptimiser()
model_manager = AIModelManager(DATA_DIR, MODELS_DIR)

# Schemas
CorridorName = Literal["Hormuz", "Bab-el-Mandeb", "Malacca", "Cape of Good Hope", "Suez"]

class ScenarioSimRequest(BaseModel):
    corridor: CorridorName = "Hormuz"
    disruption_duration_days: int = Field(30, ge=1, le=180)
    # Optional analyst override; omitted = modelled from global supply loss and live Brent
    price_rise_usd_per_barrel: Optional[float] = Field(None, ge=0.0, le=150.0)
    disruption_severity_pct: float = Field(50.0, ge=0.0, le=100.0)

class ProcurementRankRequest(BaseModel):
    # Optional analyst override (0-10 per corridor); omitted = live corridor probabilities
    corridor_risk_scores: Optional[Dict[CorridorName, float]] = None

class ProcurementOptimizeRequest(BaseModel):
    required_deficit_mbpd: float = Field(1.5, ge=0.1, le=10.0)
    blocked_chokepoints: List[Literal["hormuz", "bab_el_mandeb", "suez", "malacca", "cape_of_good_hope"]] = Field(default_factory=list)
    allow_sanctioned: bool = Field(False)
    corridor_risk_scores: Optional[Dict[CorridorName, float]] = None

class ReserveLPOptimizeRequest(BaseModel):
    # The supply-gap forecast comes from the scenario model for these inputs
    corridor: CorridorName = "Hormuz"
    disruption_duration_days: int = Field(60, ge=1, le=180)
    disruption_severity_pct: float = Field(100.0, ge=0.0, le=100.0)
    safety_floor_days: float = Field(3.0, ge=0.0, le=9.0)
    # Optional override; omitted = live 30-day Hormuz disruption probability
    p_followon: Optional[float] = Field(None, ge=0.0, le=1.0)

class UnifiedStateRequest(BaseModel):
    selected_corridor: CorridorName = "Hormuz"
    disruption_severity_pct: float = Field(50.0, ge=0.0, le=100.0)
    disruption_duration_days: int = Field(30, ge=1, le=180)
    price_rise_usd_per_barrel: Optional[float] = Field(None, ge=0.0, le=150.0)
    safety_floor_days: float = Field(3.0, ge=0.0, le=9.0)
    custom_corridor_overrides: Optional[Dict[str, float]] = None

class HeadlineAnalysisRequest(BaseModel):
    headline: str = Field(..., min_length=5, max_length=500, description="Geopolitical or maritime news headline to evaluate")
    corridor: Optional[CorridorName] = None

def live_corridor_probabilities(override_scores: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """30-day disruption probability per corridor from the live pipeline (optionally analyst-overridden)."""
    res = risk_agent.calculate_supplier_probabilities(override_scores)
    return {c["corridor"]: c["p_disruption_30d"] for c in res["corridors"]}

# --- API Endpoints ---

@app.get("/api/overview")
def get_system_overview():
    """Returns meta-information and transparency mapping."""
    db_summary = db.get_database_summary()
    model_status = model_manager.get_status()
    return {
        "project": "Krude",
        "version": "3.2.0",
        "database": db_summary,
        "ai_model": model_status,
        "truth_table": [
            {"component": "Headline risk score", "status": f"Real — live headlines scored by {model_status['active_engine']}"},
            {"component": "Headline explanation", "status": "Rule-based — the model outputs a score only"},
            {"component": "Maritime routes & distances", "status": "Real — searoute marine network graph + geometric chokepoint detection"},
            {"component": "Crude quality penalty", "status": "Real — API/Sulphur yield and hydrotreating penalty against 32 API / 2% S Indian baseline"},
            {"component": "Procurement ranking & allocation", "status": "Real — live optimization against DuckDB/SQLite dataset"},
            {"component": "Scenario impact (price/GDP/refining)", "status": "Simulated — rule-of-thumb formulas, stated assumptions"},
            {"component": "Reserve drawdown", "status": "Simulated — simple formula, 9.5-day baseline"}
        ],
        "corridors": CORRIDORS,
        "suppliers": [
            "Iraq", "Saudi Arabia", "UAE", "Kuwait", "Qatar", "Oman", "Russia",
            "Nigeria", "Angola", "Brazil", "USA", "Libya", "Guyana", "Mexico", "Venezuela", "Iran"
        ],
        "baseline_reserve_days": 9.5
    }

# --- AI Model Endpoints (KrudeAi) ---

@app.get("/api/model/status")
def get_model_status():
    """Returns whether Ollama is up, the model is installed, and whether it is loaded on GPU or CPU."""
    return model_manager.get_status()

@app.post("/api/model/analyze")
def analyze_headline(req: HeadlineAnalysisRequest):
    """
    Scores an arbitrary headline 0-10 with the fine-tuned KrudeAi model (keyword fallback if
    Ollama is down). Returns score, engine used, rule-based explanation and latency.
    """
    return model_manager.analyze_headline(headline=req.headline, corridor=req.corridor)

@app.post("/api/model/export-dataset")
def export_training_dataset():
    """Generates fine-tuning training dataset in JSONL format."""
    return model_manager.export_fine_tuning_dataset()

# --- Database Endpoints (DuckDB / SQLite) ---

@app.get("/api/database/summary")
def get_db_summary():
    """Returns status and row counts for all 5 core tables in DuckDB."""
    return db.get_database_summary()

@app.get("/api/database/suppliers")
def get_db_suppliers(include_sanctioned: bool = Query(True, description="Include sanctioned suppliers")):
    """Returns all crude supplier grades with quality adjustments and max liftable kbd."""
    return db.get_suppliers(include_sanctioned=include_sanctioned)

@app.get("/api/database/routes")
def get_db_routes(source: Optional[str] = None, dest_port: Optional[str] = None):
    """Returns maritime routes with real Searoute distances, geometric chokepoints, and freight costs."""
    return db.get_routes(source=source, dest_port=dest_port)

@app.get("/api/database/imports")
def get_db_imports(country: Optional[str] = None):
    """Returns melted long imports historical time series (month, country, volume_kbd)."""
    return db.get_historical_imports(country=country)

@app.get("/api/database/ofac")
def get_db_ofac(country: Optional[str] = None):
    """Returns OFAC sanctions and restricted supplier records."""
    return db.get_ofac_entities(country=country)

@app.get("/api/database/landed-options")
def get_db_landed_options():
    """Returns full analytical view of landed procurement options with quality and freight breakdowns."""
    return db.get_landed_procurement_options()

@app.get("/api/database/corridor-exposure")
def get_db_corridor_exposure():
    """Returns 3-month trailing average import barrel volume sitting behind each chokepoint."""
    return db.get_corridor_exposure()

# --- Risk & Simulation Endpoints ---

@app.get("/api/risk")
@app.get("/risk")
@app.get("/api/risk/live")
@app.get("/api/risk/scores")
def get_corridor_risk_scores():
    """Returns the latest 0-10 risk scores and live headlines for the 5 corridors."""
    return risk_agent.evaluate_all_corridors()

@app.post("/api/risk/refresh")
def refresh_risk_intelligence():
    """
    Component 1: Risk Intelligence Agent (REAL)
    Re-queries GDELT DOC 2.0 API and re-runs KrudeAi model inference.
    """
    return risk_agent.evaluate_all_corridors()

@app.get("/api/risk/headlines")
def get_live_headlines():
    """Returns all current live and recent breaking maritime headlines evaluated by KrudeAi."""
    return risk_agent.get_live_ticker_headlines()

@app.get("/api/risk/feed-status")
def get_feed_status():
    """Per-provider health (NewsAPI, GNews, GDELT) and time of the last successful news refresh."""
    return risk_agent.get_feed_status()

@app.get("/api/risk/timeline")
def get_corridor_timeline(corridor: CorridorName = Query("Hormuz")):
    """
    Illustrative 18-month risk curve from the curated historical event list in risk_pipeline.py
    (hand-labelled) with real Brent overlay. Not live data; see /api/risk/empirical-validation.
    """
    from engine.risk_pipeline import RiskPipeline
    pipeline = RiskPipeline()
    ts = pipeline.compute_18_month_timeseries(corridor=corridor, step_days=2)
    return {
        "corridor": corridor,
        "pipeline_stages": ["dedupe", "time_decay (t_half=7d)", "strongest_event_plus_damped_corroboration", "momentum", "sanctions"],
        "data_basis": "Curated, hand-labelled historical events (illustrative); Brent is real (FRED)",
        "data_points_count": len(ts),
        "timeline": ts
    }

@app.get("/api/risk/threat-board")
def get_threat_board():
    """Corridor Threat Board: live index, pipeline stage values, 30-day history and import exposure."""
    return risk_agent.get_threat_board()

@app.get("/api/digital-twin/graph")
def get_digital_twin_graph():
    """Digital twin map: load ports -> chokepoints -> Indian discharge ports, with real route flows (kbd)."""
    return build_twin_graph()

@app.get("/api/risk/supply-disruption-probabilities")
def get_supply_disruption_probabilities():
    """
    Live Supply-Disruption Probability (30-day horizon · by corridor and supplier).
    Distinguishes gross chokepoint exposure from net sovereign vulnerability via pipeline bypass routing.
    """
    return risk_agent.calculate_supplier_probabilities()

@app.get("/api/risk/empirical-validation")
def get_empirical_validation(corridor: CorridorName = Query("Hormuz")):
    """
    Tests whether GDELT news intensity for the corridor led real Brent moves since 2024
    (level and lead-lag correlations, spike event study). Results are computed, not asserted.
    """
    return validate(corridor)

@app.get("/api/risk/plot")
def get_corridor_plot(corridor: CorridorName = Query("Hormuz"), format: Literal["svg", "png"] = Query("svg")):
    """
    Returns visual 18-month risk plot for the corridor.
    """
    from engine.risk_pipeline import RiskPipeline
    pipeline = RiskPipeline()
    if format.lower() == "png":
        png_path = FRONTEND_DIR / "img" / f"{corridor.lower().replace(' ', '_')}_18m_risk_plot.png"
        pipeline.generate_plot(png_path, corridor=corridor)
        return FileResponse(png_path, media_type="image/png")
    else:
        svg_path = FRONTEND_DIR / "img" / f"{corridor.lower().replace(' ', '_')}_18m_risk_plot.svg"
        pipeline.generate_svg_plot(svg_path, corridor=corridor)
        return FileResponse(svg_path, media_type="image/svg+xml")

# ==============================================================================
# BLOCK 5: FOUR CLEAN CORE ENDPOINTS (/risk, /scenario, /procure, /reserve)
# ==============================================================================

@app.post("/api/scenario")
@app.post("/scenario")
@app.post("/api/scenario/simulate")
def simulate_scenario(req: ScenarioSimRequest):
    """Clean Endpoint 2: Disruption Scenario Modeller & Macroeconomic Shock."""
    return scenario_modeller.simulate(
        corridor=req.corridor,
        disruption_duration_days=req.disruption_duration_days,
        price_rise_usd_per_barrel=req.price_rise_usd_per_barrel,
        disruption_severity_pct=req.disruption_severity_pct
    )

@app.post("/api/procurement/rank")
def rank_procurement(req: ProcurementRankRequest):
    """Component 3: Ranks supplier grades by risk-adjusted landed cost using live corridor probabilities."""
    return procurement_orchestrator.rank_suppliers(live_corridor_probabilities(req.corridor_risk_scores))

@app.post("/api/procure")
@app.post("/procure")
@app.post("/api/procurement/optimize")
def optimize_procurement(req: ProcurementOptimizeRequest):
    """Clean Endpoint 3: LP allocation of the deficit across suppliers and routes (risk-adjusted)."""
    return procurement_orchestrator.generate_procurement_plan(
        required_deficit_mbpd=req.required_deficit_mbpd,
        corridor_p=live_corridor_probabilities(req.corridor_risk_scores),
        blocked_chokepoints=req.blocked_chokepoints,
        allow_sanctioned=req.allow_sanctioned
    )

def reserve_plan(corridor: str, duration_days: int, severity_pct: float,
                 safety_floor_days: float = 3.0, p_followon: Optional[float] = None) -> Dict:
    """SPR LP against the scenario model's day-by-day supply gap."""
    scen = run_scenario(corridor, severity_pct / 100.0, duration_days)
    if p_followon is None:
        p_followon = live_corridor_probabilities()["Hormuz"]
    plan = spr_optimiser.optimize_drawdown_lp(
        scen["gap_kbd_by_day"], p_followon,
        base_supply_kbd=scen["india_crude_runs_kbd"], safety_floor_days=safety_floor_days)
    plan["scenario"] = {k: scen[k] for k in ("corridor", "phi", "duration_days", "daily_gap_kbd", "gap_days", "india_crude_runs_kbd")}
    return plan

@app.post("/api/reserve")
@app.post("/reserve")
@app.post("/api/reserve/optimize-lp")
def optimize_reserve_lp(req: ReserveLPOptimizeRequest):
    """
    Clean Endpoint 4: SPR drawdown LP against the scenario's supply-gap forecast.
    min sum(shortfall_t * VoLL + d_t * opportunity_cost)
    s.t. R_{t+1} = R_t - d_t, 0 <= d_t <= max draw, R_t >= floor_days * basis + P(follow-on) * tail_gap
    """
    return reserve_plan(req.corridor, req.disruption_duration_days, req.disruption_severity_pct,
                        req.safety_floor_days, req.p_followon)

@app.get("/api/reserve/policies")
def get_reserve_policies(safety_floor_days: float = Query(3.0, ge=0.0, le=9.0), horizon_days: int = Query(90, ge=10, le=365)):
    """Days of cover over time for fixed release policies (steady 180, aggressive 350, hold 65 kbd)."""
    return spr_optimiser.simulate_policies(horizon_days=horizon_days, safety_floor_days=safety_floor_days)

# ==============================================================================
# BLOCK 5: LIVE STREAM & 60x REPLAY SIMULATION ENDPOINTS
# ==============================================================================

@app.get("/api/stream/live")
@app.get("/api/stream/events")
async def stream_live_events():
    """
    Server-Sent Events (SSE) live streaming endpoint.
    Emits continuous real-time updates from the background poller and 60x replay engine.
    """
    q = live_manager.subscribe()

    async def event_generator():
        try:
            # Initial handshake
            init_msg = json.dumps({"status": "STREAM_CONNECTED", "timestamp": time.time()})
            yield f"event: connected\ndata: {init_msg}\n\n"
            while True:
                msg = await q.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            live_manager.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/digital-twin/state")
def get_unified_digital_twin_state(req: UnifiedStateRequest):
    """
    Component 5: Supply Chain Digital Twin (State-based)
    Unifies all components in one atomic state update.
    """
    overrides = req.custom_corridor_overrides or {}
    if req.selected_corridor and req.disruption_severity_pct is not None:
        overrides[req.selected_corridor] = req.disruption_severity_pct

    risk_data = risk_agent.evaluate_all_corridors(custom_disruptions=overrides)

    scenario_data = scenario_modeller.simulate(
        corridor=req.selected_corridor,
        disruption_duration_days=req.disruption_duration_days,
        price_rise_usd_per_barrel=req.price_rise_usd_per_barrel,
        disruption_severity_pct=req.disruption_severity_pct
    )

    # In the what-if, the disrupted corridor is at least as risky as the simulated severity
    corridor_p = live_corridor_probabilities()
    corridor_p[req.selected_corridor] = max(corridor_p[req.selected_corridor], req.disruption_severity_pct / 100.0)
    procurement_data = procurement_orchestrator.rank_suppliers(corridor_p)
    reserve_data = reserve_plan(req.selected_corridor, req.disruption_duration_days,
                                req.disruption_severity_pct, req.safety_floor_days)

    timestamp = time.strftime("%H:%M:%S UTC", time.gmtime())
    top = procurement_data["optimal_recommendation"]
    log_entry = {
        "timestamp": timestamp,
        "event": f"Simulated disruption in {req.selected_corridor} at {req.disruption_severity_pct:.0f}% closure",
        "action": (f"Prioritise {top['crude_grade']} from {top['supplier']} via {top['chokepoint_route']}; "
                   f"{reserve_data['summary']['drawdown_strategy']}") if top else reserve_data["summary"]["drawdown_strategy"],
    }

    return {
        "timestamp": timestamp,
        "risk_intelligence": risk_data,
        "scenario_impact": scenario_data,
        "procurement_ranking": procurement_data,
        "strategic_reserve": reserve_data,
        "database_status": db.get_database_summary(),
        "latest_log": log_entry
    }

# Serve frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Krude API running. Frontend index.html not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
