"""Project KPIs / health computation.

``level`` is derived on the fly from each risk's probability*impact against the
project's thresholds (not read from a stored column), so metrics stay correct
even if thresholds change.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Dict

from app.db import all_rows, loads
from app.services.graph import get_project_or_404
from app.services.serializers import risk_level
from core.defaults import DEFAULT_PARAMETERS


def calculate_metrics(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    p = get_project_or_404(conn, project_id)
    params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
    tasks = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ?", (project_id,))
    risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ?", (project_id,))
    stories = all_rows(conn, "SELECT * FROM stories WHERE project_id = ?", (project_id,))
    deps = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (project_id,))
    work_tasks = [t for t in tasks if t["task_type"] != "summary"]
    progress = round(sum(int(t["progress"] or 0) for t in work_tasks) / len(work_tasks), 1) if work_tasks else 0
    spent = round(sum(float(t["budget"] or 0) * int(t["progress"] or 0) / 100 for t in work_tasks), 2)
    high_risks = len([
        r for r in risks
        if risk_level(r["probability"], r["impact"], params) == "Alto" and r["status"] != "Cerrado"
    ])
    open_risks = len([r for r in risks if r["status"] != "Cerrado"])
    completed_points = sum(int(s["points"] or 0) for s in stories if s["status"] == "Hecho")
    total_points = sum(int(s["points"] or 0) for s in stories) or 1
    today = date.today().isoformat()
    delayed_tasks = [t for t in work_tasks if t["end_date"] < today and int(t["progress"] or 0) < 100 and t["task_type"] != "milestone"]
    critical_ids = set()
    for d in deps:
        critical_ids.add(d["predecessor_id"])
        critical_ids.add(d["successor_id"])
    critical_open = [t for t in work_tasks if t["id"] in critical_ids and int(t["progress"] or 0) < 100]
    health = "Saludable"
    if high_risks >= 2 or len(delayed_tasks) >= 3:
        health = "En riesgo"
    if high_risks >= 4 or len(delayed_tasks) >= 6:
        health = "Crítico"
    return {
        "progress": progress,
        "budget": float(p["budget"] or 0),
        "spent": spent,
        "remaining_budget": max(float(p["budget"] or 0) - spent, 0),
        "open_risks": open_risks,
        "high_risks": high_risks,
        "critical_path_tasks": len(critical_open),
        "delayed_tasks": len(delayed_tasks),
        "story_completion": round(completed_points / total_points * 100, 1),
        "health": health,
    }
