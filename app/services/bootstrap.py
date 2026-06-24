"""Assembles the full single-request snapshot consumed by the SPA."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from app.db import all_rows, loads
from app.services.graph import get_project_or_404
from app.services.metrics import calculate_metrics
from app.services.serializers import serialize_project, serialize_risk
from core.defaults import DEFAULT_PARAMETERS


def _empty_payload() -> Dict[str, Any]:
    return {
        "projects": [],
        "current_project": None,
        "tasks": [],
        "dependencies": [],
        "sprints": [],
        "stories": [],
        "risks": [],
        "resources": [],
        "metrics": {},
        "defaults": DEFAULT_PARAMETERS,
    }


def bootstrap_payload(conn: sqlite3.Connection, project_id: Optional[int] = None) -> Dict[str, Any]:
    projects = all_rows(conn, "SELECT * FROM projects ORDER BY id")
    if not projects:
        # Seeding happens once at startup (lifespan). A normal GET must never
        # write demo data; return an empty-but-valid payload instead of crashing.
        return _empty_payload()
    selected = project_id or projects[0]["id"]
    current = get_project_or_404(conn, selected)
    params = loads(current["parameters_json"], DEFAULT_PARAMETERS)
    return {
        "projects": [serialize_project(p) for p in projects],
        "current_project": serialize_project(current),
        "tasks": all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (selected,)),
        "dependencies": all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (selected,)),
        "sprints": all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date", (selected,)),
        "stories": all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (selected,)),
        "risks": [serialize_risk(r, params) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY id", (selected,))],
        "resources": all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (selected,)),
        "metrics": calculate_metrics(conn, selected),
        "defaults": DEFAULT_PARAMETERS,
    }
