from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[2]
APP_ENV = os.getenv("APP_ENV", "local")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-local-only")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
DB_PATH = Path(os.getenv("PROYECTA360_DB", BASE_DIR / "proyecta360.db"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", os.getenv("PROYECTA360_UPLOADS", BASE_DIR / "uploads")))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = int(os.getenv("PROYECTA360_MAX_UPLOAD_BYTES", str(MAX_UPLOAD_MB * 1024 * 1024)))

DEFAULT_PARAMETERS: Dict[str, Any] = {
    "control_model": "PMP para gobierno y control + Scrum para desarrollo",
    "execution_methodologies": ["Scrum", "Kanban", "Tradicional", "Híbrida", "XP", "Lean"],
    "selected_execution_methodology": "Scrum",
    "calendar": {
        "working_days": ["Lunes", "Martes", "Mi?rcoles", "Jueves", "Viernes"],
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
        "model": "configurable",
        "use_project_documents": True,
        "allow_create_tasks": True,
        "allow_create_risks": True,
    },
    "strategic_framework": {
        "problem_statement": "",
        "current_situation": "",
        "main_gap": "",
        "consequence_if_not_done": "",
        "general_objective": "",
        "specific_objectives": "",
        "objective_indicators": "",
        "scope_included": "",
        "scope_excluded": "",
        "expected_results": "",
        "success_criteria": "",
        "project_context": "",
        "political_context": "",
        "geographic_context": "",
        "socioeconomic_context": "",
        "cultural_context": "",
        "stakeholders_context": "",
        "stakeholders": "",
        "institutional_context": "",
        "external_dependencies": "",
        "regulatory_constraints": "",
        "target_population": "",
        "direct_beneficiaries": "",
        "indirect_beneficiaries": "",
        "assumptions": "",
        "constraints": "",
    },
    "project_profile": {
        "project_code": "",
        "requesting_area": "",
        "project_type": "",
        "priority": "Media",
        "responsible_team": "",
    },
}

SUPPORTED_CURRENCIES = ["COP", "USD", "EUR", "MXN", "PEN", "CLP", "BRL"]
DEPENDENCY_TYPES = {"FS", "SS", "FF", "SF"}
