"""Default per-project configuration stored in projects.parameters_json.

Lives in its own module so it is no longer a global of the request-handling
module and can be imported by schemas, serializers, seed data and the AI layer
without pulling in the whole app.
"""
from __future__ import annotations

from typing import Any, Dict

DEFAULT_PARAMETERS: Dict[str, Any] = {
    "control_model": "PMP para gobierno y control + Scrum para desarrollo",
    "execution_methodologies": ["Scrum", "Kanban", "Tradicional", "Híbrida", "XP", "Lean"],
    "selected_execution_methodology": "Scrum",
    "calendar": {
        "working_days": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
        "workday_start": "08:00",
        "workday_end": "17:00",
        "timezone": "America/Bogota",
    },
    "phases": ["Inicio", "Planeación", "Ejecución", "Pruebas", "Cierre"],
    "task_statuses": ["Pendiente", "En progreso", "Bloqueada", "Completada"],
    "story_statuses": ["Por hacer", "En progreso", "Hecho"],
    "sprint": {"duration_days": 14, "story_point_scale": [1, 2, 3, 5, 8, 13]},
    "risk_matrix": {
        "probability_scale": [1, 2, 3, 4, 5],
        "impact_scale": [1, 2, 3, 4, 5],
        "high_threshold": 15,
        "medium_threshold": 8,
    },
    "governance": {
        "critical_path_enabled": True,
        "budget_control_enabled": True,
        "weekly_status_report": True,
        "stage_gate_approval": True,
    },
    "ai": {
        "enabled": False,
        "provider": "OpenAI / Azure OpenAI",
        "model": "configurable",
        "use_project_documents": True,
        "allow_create_tasks": True,
        "allow_create_risks": True,
    },
}
