"""AI-ready layer.

Today this is deterministic Python (date/budget arithmetic + a templated
report) — no LLM, no API key. It is isolated here so it can later be swapped
for a real provider (OpenAI / Azure / Anthropic) behind the same interface.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict

from app.db import all_rows, loads, one
from app.schemas import AiPlanIn, AiReportIn
from app.services.graph import get_project_or_404
from app.services.metrics import calculate_metrics
from app.services.serializers import risk_level
from core.defaults import DEFAULT_PARAMETERS


def generate_plan(conn: sqlite3.Connection, payload: AiPlanIn) -> Dict[str, Any]:
    p = get_project_or_404(conn, payload.project_id)
    params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
    phases = params.get("phases", DEFAULT_PARAMETERS["phases"])
    base = date.fromisoformat(p["start_date"])
    project_end = date.fromisoformat(p["end_date"])
    horizon_days = max(30, payload.horizon_weeks * 7)
    segment = max(5, math.floor(horizon_days / max(len(phases), 1)))
    last_order = one(conn, "SELECT COALESCE(MAX(order_index), 0) AS mx FROM tasks WHERE project_id = ?", (p["id"],))["mx"]
    generated, previous_id = [], None
    for idx, phase in enumerate(phases):
        s = base + timedelta(days=idx * segment)
        e = min(base + timedelta(days=(idx + 1) * segment - 2), project_end)
        item = {
            "project_id": p["id"], "title": f"{phase}: entregable principal", "phase": phase, "task_type": "task",
            "start_date": s.isoformat(), "end_date": e.isoformat(), "progress": 0,
            "owner": p["project_manager"] or "PM", "status": "Pendiente",
            "story_points": 8 if phase.lower().startswith("ej") else 0,
            "budget": round(float(p["budget"] or 0) / max(len(phases), 1) * 0.12, 2),
            "description": f"Generado para el objetivo: {payload.objective}", "order_index": last_order + idx + 1,
        }
        generated.append(item)
        if payload.create_records:
            cur = conn.execute(
                """INSERT INTO tasks (project_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, description, order_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item["project_id"], item["title"], item["phase"], item["task_type"], item["start_date"], item["end_date"], item["progress"], item["owner"], item["status"], item["story_points"], item["budget"], item["description"], item["order_index"]),
            )
            if previous_id:
                conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", (p["id"], previous_id, cur.lastrowid))
            previous_id = cur.lastrowid
    if payload.create_records:
        conn.commit()
    return {
        "message": "Plan generado con motor IA-ready. Sustituible por OpenAI/Azure OpenAI cuando se configure la llave.",
        "generated_tasks": generated,
    }


def build_report(conn: sqlite3.Connection, payload: AiReportIn) -> Dict[str, Any]:
    p = get_project_or_404(conn, payload.project_id)
    m = calculate_metrics(conn, payload.project_id)
    risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ? AND status != 'Cerrado' ORDER BY probability * impact DESC LIMIT 5", (payload.project_id,))
    params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
    report = f"""Informe ejecutivo para {payload.audience}
Proyecto: {p['name']}
Estado: {p['status']} | Salud: {m['health']}
Avance general: {m['progress']}%
Presupuesto ejecutado estimado: {m['spent']:,.0f} de {m['budget']:,.0f} {p['currency']}
Riesgos abiertos: {m['open_risks']} | Riesgos altos: {m['high_risks']}
Ruta crítica: {m['critical_path_tasks']} tareas abiertas con dependencias.

Foco recomendado:
1. Revisar tareas atrasadas y dependencias críticas.
2. Confirmar capacidad de recursos de QA y Desarrollo.
3. Mantener gobierno PMP para hitos y cambios de alcance, permitiendo ejecución ágil en sprints.
""".strip()
    if risks:
        report += "\n\nPrincipales riesgos:\n" + "\n".join(
            [f"- {r['title']} ({risk_level(r['probability'], r['impact'], params)})" for r in risks]
        )
    return {"report": report}
