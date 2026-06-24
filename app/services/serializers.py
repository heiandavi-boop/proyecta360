"""Row -> API dict serializers and risk-level derivation."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.db import loads
from core.defaults import DEFAULT_PARAMETERS


def serialize_project(p: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(p)
    out["parameters"] = loads(out.pop("parameters_json", "{}"), DEFAULT_PARAMETERS)
    return out


def risk_level(probability: int, impact: int, parameters: Optional[Dict[str, Any]] = None) -> str:
    params = parameters or DEFAULT_PARAMETERS
    score = probability * impact
    high = params.get("risk_matrix", {}).get("high_threshold", 15)
    medium = params.get("risk_matrix", {}).get("medium_threshold", 8)
    if score >= high:
        return "Alto"
    if score >= medium:
        return "Medio"
    return "Bajo"


def serialize_risk(r: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Adds the derived ``score`` and, when project ``parameters`` are given,
    the derived ``level`` (computed on read from the project's risk thresholds,
    so it never goes stale)."""
    out = dict(r)
    probability = int(out.get("probability") or 0)
    impact = int(out.get("impact") or 0)
    out["score"] = probability * impact
    if parameters is not None:
        out["level"] = risk_level(probability, impact, parameters)
    return out
