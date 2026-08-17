from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[2]
APP_ENV = os.getenv("APP_ENV", "local")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-local-only")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
# Inactivity timeout (minutes) after which the session requires password re-entry
INACTIVITY_TIMEOUT_MINUTES = int(os.getenv("INACTIVITY_TIMEOUT_MINUTES", "10"))
_legacy_db_path = BASE_DIR / ("proyecta" + "360.db")
_default_db_path = _legacy_db_path if _legacy_db_path.exists() else BASE_DIR / "prunin.db"
DB_PATH = Path(os.getenv("PRUNIN_DB", os.getenv("PROYECTA" + "360_DB", _default_db_path)))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", os.getenv("PRUNIN_UPLOADS", os.getenv("PROYECTA" + "360_UPLOADS", BASE_DIR / "uploads"))))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = int(os.getenv("PRUNIN_MAX_UPLOAD_BYTES", os.getenv("PROYECTA" + "360_MAX_UPLOAD_BYTES", str(MAX_UPLOAD_MB * 1024 * 1024))))

DEFAULT_PARAMETERS: Dict[str, Any] = {
    "control_model": "PMP para gobierno y control + Trabajo \u00c1gil para ejecuci\u00f3n",
    "execution_methodologies": ["Scrum", "Kanban", "Tradicional", "H\u00edbrida", "XP", "Lean"],
    "selected_execution_methodology": "H\u00edbrida",
    "agile_mode": "H\u00edbrido",
    "calendar": {
        "working_days": ["Lunes", "Martes", "Mi\u00e9rcoles", "Jueves", "Viernes"],
        "workday_start": "08:00",
        "workday_end": "17:00",
        "timezone": "America/Bogota",
    },
    "phases": ["Inicio", "Planeaci\u00f3n", "Ejecuci\u00f3n", "Pruebas", "Cierre"],
    "task_statuses": ["Pendiente", "En progreso", "Bloqueada", "Completada"],
    "story_statuses": ["Lista", "Por hacer", "En progreso", "En revision", "Bloqueado", "Hecho"],
    "sprint": {"duration_days": 14, "story_point_scale": [1, 2, 3, 5, 8, 13]},
    "agile": {"cycle_duration_days": 14, "work_item_types": ["Historia", "Tarea", "Bug", "Mejora", "Solicitud", "Entregable", "Otro"]},
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
