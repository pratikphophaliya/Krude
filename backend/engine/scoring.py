"""
Krude - Headline Risk Scoring
=============================
Scores a news headline 0-10 for crude supply disruption risk.

1. KrudeAi: the fine-tuned Llama 3.2 3B model served by Ollama (OLLAMA_MODEL, default
   `Krude-risk`). Its Modelfile template ends in "Risk score:", so it returns only a number.
2. Keyword fallback, used when Ollama is unreachable or returns no score.

The short explanation is always rule-based (the model was trained to output a score only).
Every result carries `engine` so the UI never presents a fallback score as model output.
"""

import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ENGINE_LLM = "KrudeAi fine-tuned model"
ENGINE_KEYWORD = "Keyword fallback"

# After a failed call, skip the LLM for this long so a down/slow Ollama doesn't stall refreshes
LLM_RETRY_AFTER_SECONDS = 60
_llm_unavailable_until = 0.0

# (keywords, score bump over corridor baseline, explanation)
KEYWORD_RULES = [
    (["missile", "drone", "strike", "attack", "explosion", "exploded", "mine", "torpedo", "war"], 2.4,
     "Kinetic attack or weapons activity near the corridor raises tanker interdiction risk."),
    (["seize", "seizure", "piracy", "boarding", "boarded", "hijack"], 2.0,
     "Vessel seizure or boarding activity threatens commercial tanker transit."),
    (["blockade", "closure", "closed", "suspend", "halt"], 2.2,
     "Reported closure or suspension of traffic directly blocks crude flows."),
    (["sanction", "ofac", "shadow fleet", "price cap", "embargo"], 1.5,
     "Sanctions enforcement tightens which cargoes and vessels can move."),
    (["military", "navy", "naval", "patrol", "drill", "warship", "fleet", "irgc"], 1.3,
     "Naval or military posture in the corridor adds operational friction."),
    (["insurance", "war-risk", "war risk", "premium", "freight"], 1.2,
     "Rising war-risk insurance or freight costs raise landed crude prices."),
    (["reroute", "rerouting", "divert", "bypass", "delay", "congestion"], 1.1,
     "Voyage diversions lengthen transit times for India-bound cargoes."),
    (["talks", "ceasefire", "peace", "agreement", "reopen", "resume", "calm", "eases", "easing"], -1.5,
     "De-escalation signals lower near-term disruption risk."),
]


def _keyword_score(headline: str, baseline: float) -> Tuple[float, str]:
    text = headline.lower()
    for words, bump, explanation in KEYWORD_RULES:
        if any(w in text for w in words):
            return max(0.5, min(9.8, round(baseline + bump, 1))), explanation
    return round(baseline, 1), "No specific threat or de-escalation keywords in the headline."


def _llm_score(headline: str) -> Optional[float]:
    """Returns the model's 0-10 score, or None if the model is unavailable or gave no number."""
    global _llm_unavailable_until
    if time.time() < _llm_unavailable_until:
        return None
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "Krude-risk")
    try:
        # No option overrides: the Modelfile's template, stop tokens and num_predict define the output
        resp = requests.post(f"{host}/api/generate", json={
            "model": model, "prompt": headline, "stream": False, "keep_alive": "24h"
        }, timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30")))
        resp.raise_for_status()
        match = re.search(r"\b(10|\d(?:\.\d+)?)\b", resp.json().get("response", "").strip().split("\n")[0])
        if match:
            return max(0.0, min(10.0, float(match.group(1))))
    except Exception:
        _llm_unavailable_until = time.time() + LLM_RETRY_AFTER_SECONDS
    return None


def score_headline(headline: str, baseline: float = 5.0) -> Dict[str, Any]:
    """Scores one headline. `baseline` is the corridor's resting risk, used by the keyword fallback."""
    t0 = time.time()
    keyword_score, explanation = _keyword_score(headline, baseline)
    llm_score = _llm_score(headline)
    return {
        "risk_score": llm_score if llm_score is not None else keyword_score,
        "engine": ENGINE_LLM if llm_score is not None else ENGINE_KEYWORD,
        "reason": explanation,
        "reason_engine": "rule-based",
        "latency_ms": round((time.time() - t0) * 1000, 1),
    }


def llm_status() -> Dict[str, Any]:
    """Whether Ollama is reachable and the configured model is installed."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "Krude-risk")
    try:
        resp = requests.get(f"{host}/api/tags", timeout=2)
        resp.raise_for_status()
        installed = [m.get("name", "") for m in resp.json().get("models", [])]
        return {"ollama_online": True, "model": model,
                "model_installed": any(n.split(":")[0] == model.split(":")[0] for n in installed)}
    except Exception:
        return {"ollama_online": False, "model": model, "model_installed": False}
