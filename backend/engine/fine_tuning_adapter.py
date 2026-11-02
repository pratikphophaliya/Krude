import json
import os
import requests
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from engine.scoring import score_headline, llm_status
    from engine.risk_intel import CORRIDOR_CONFIG
except ImportError:
    from backend.engine.scoring import score_headline, llm_status
    from backend.engine.risk_intel import CORRIDOR_CONFIG


class AIModelManager:
    """
    KrudeAi model status, ad-hoc headline scoring and fine-tuning dataset export.
    Scoring itself lives in engine.scoring (fine-tuned Ollama model, keyword fallback).
    """
    def __init__(self, data_dir: Path, models_dir: Path):
        self.data_dir = data_dir
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def get_status(self) -> Dict[str, Any]:
        """Live Ollama/model status, including whether the model is currently loaded on GPU or CPU."""
        status = llm_status()
        device = "not loaded"
        if status["ollama_online"]:
            try:
                host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
                for m in requests.get(f"{host}/api/ps", timeout=2).json().get("models", []):
                    if m.get("name", "").split(":")[0] == status["model"].split(":")[0]:
                        device = "GPU" if m.get("size_vram", 0) > 0 else "CPU"
            except Exception:
                pass
        return {
            "model_name": status["model"],
            "model_architecture": "Llama 3.2 3B Instruct + LoRA (served by Ollama)",
            "ollama_online": status["ollama_online"],
            "model_installed": status["model_installed"],
            "device": device,
            "active_engine": "KrudeAi fine-tuned model" if status["model_installed"] else "Keyword fallback",
        }

    def analyze_headline(self, headline: str, corridor: Optional[str] = None) -> Dict[str, Any]:
        """Scores an arbitrary headline; the result says which engine produced the score."""
        baseline = CORRIDOR_CONFIG.get(corridor, {}).get("baseline_risk", 5.0) if corridor else 5.0
        return {"headline": headline, **score_headline(headline.strip(), baseline)}

    def _generate_heuristic_narrative(self, scenario: Dict[str, Any], procurement: Dict[str, Any]) -> str:
        """Built-in high precision strategic brief generation."""
        inputs = scenario.get("scenario_inputs", scenario.get("simulation_inputs", {}))
        impacts = scenario.get("impacts", {})
        macro = scenario.get("macro_economic_impact", {})
        orders = procurement.get("allocated_orders", [])

        corridor = inputs.get("corridor", "Hormuz")
        severity_pct = inputs.get("disruption_severity_pct", inputs.get("hormuz_closure_pct", 50))
        duration_days = inputs.get("disruption_duration_days", inputs.get("duration_days", 30))
        deficit = inputs.get("blocked_supply_mbpd", impacts.get("blocked_supply_volume_mbpd", 1.30))
        cost_b = impacts.get("estimated_additional_cost_usd_billion", macro.get("total_additional_cost_usd_billion", 2.4))
        gdp = impacts.get("gdp_impact_pp", 0.3)
        cad = impacts.get("cad_impact_bps", 50.0)

        order_summary = ", ".join([f"{o.get('volume_mbpd', 0.5)} MBPD {o.get('grade', o.get('crude_name', 'Crude'))} from {o.get('country', 'Supplier')}" for o in orders[:3]]) if orders else "West African / US Gulf alternative grades"

        narrative = (
            f"### Strategic National Energy Security Assessment\n\n"
            f"**1. Threat Assessment & Supply Shock:**\n"
            f"With {corridor} interdiction modeled at **{severity_pct}%**, "
            f"India faces an acute physical supply shortfall of **{deficit} Million Barrels/Day (MBPD)**.\n\n"
            f"**2. Economic & Fiscal Consequences:**\n"
            f"The resulting landed energy price spike and maritime rerouting surges impose an estimated **${cost_b} Billion** "
            f"additional import burden over {duration_days} days. Domestic macroeconomic headwinds include **-{gdp} pp GDP growth** and **+{cad} bps CAD widening**.\n\n"
            f"**3. Recommended Executive Actions:**\n"
            f"- **Emergency Procurement Substitution:** Immediately dispatch spot tenders for {order_summary}.\n"
            f"- **Logistics Rerouting:** Contract VLCC tonnage on the Atlantic route around the Cape of Good Hope for West African and US Gulf grades.\n"
            f"- **Strategic SPR Drawdown:** Trigger calibrated underground cavern discharge from Mangalore and Padur to safeguard coastal refiners from dry-run shutdowns."
        )
        return narrative

    def export_fine_tuning_dataset(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generates and exports an instruction-tuning dataset formatted for fine-tuning
        open-source LLMs (Llama-3, Mistral, Qwen, DeepSeek) for oil supply chain risk.
        """
        if output_path is None:
            output_path = self.models_dir / "oil_supply_chain_instruct_dataset.jsonl"

        dataset = []
        
        # Scenario variations for diverse training coverage
        scenarios = [
            {"corridor": "Hormuz", "severity_pct": 80.0, "days": 45, "name": "Severe Hormuz Strait Blockade"},
            {"corridor": "Hormuz", "severity_pct": 40.0, "days": 20, "name": "Partial Hormuz Standoff"},
            {"corridor": "Bab-el-Mandeb", "severity_pct": 95.0, "days": 60, "name": "Protracted Red Sea Denial"},
            {"corridor": "Hormuz", "severity_pct": 100.0, "days": 30, "name": "Total Persian Gulf Oil Embargo"},
            {"corridor": "Bab-el-Mandeb", "severity_pct": 60.0, "days": 15, "name": "Red Sea Maritime Flare-up"},
            {"corridor": "Suez", "severity_pct": 75.0, "days": 30, "name": "Suez Canal Tanker Blockade"}
        ]

        try:
            from engine.scenario_modeller import DisruptionScenarioModeller
            from engine.procurement_orchestrator import AdaptiveProcurementOrchestrator
        except ImportError:
            try:
                from backend.engine.scenario_modeller import DisruptionScenarioModeller
                from backend.engine.procurement_orchestrator import AdaptiveProcurementOrchestrator
            except ImportError:
                from .scenario_modeller import DisruptionScenarioModeller
                from .procurement_orchestrator import AdaptiveProcurementOrchestrator

        modeller = DisruptionScenarioModeller(self.data_dir)
        orchestrator = AdaptiveProcurementOrchestrator(self.data_dir)

        for sc in scenarios:
            sim_res = modeller.simulate(
                corridor=sc["corridor"],
                disruption_duration_days=sc["days"],
                disruption_severity_pct=sc["severity_pct"]
            )
            deficit = sim_res["scenario_inputs"]["blocked_supply_mbpd"]
            proc_res = orchestrator.generate_procurement_plan(required_deficit_mbpd=deficit)
            brief = self._generate_heuristic_narrative(sim_res, proc_res)

            sample = {
                "instruction": "You are India's Strategic Energy Security AI. Analyze the geopolitical disruption scenario, calculate supply gap metrics, and output executable procurement and SPR rerouting recommendations.",
                "input": (
                    f"Scenario: {sc['name']}\n"
                    f"Corridor: {sc['corridor']}\n"
                    f"Disruption Severity: {sc['severity_pct']}%\n"
                    f"Duration: {sc['days']} days\n"
                    f"Baseline Brent: $82.5/bbl"
                ),
                "output": brief,
                "metadata": {
                    "scenario_name": sc["name"],
                    "daily_deficit_mbpd": deficit,
                    "landed_cost_surge_b": sim_res["impacts"]["estimated_additional_cost_usd_billion"]
                }
            }
            dataset.append(sample)

        # Write to JSONL (standard fine-tuning format)
        with open(output_path, "w", encoding="utf-8") as f:
            for item in dataset:
                f.write(json.dumps(item) + "\n")

        return {
            "status": "SUCCESS",
            "samples_generated": len(dataset),
            "jsonl_path": str(output_path)
        }
