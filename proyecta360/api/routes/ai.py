from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict
from fastapi import APIRouter

from proyecta360.schemas.api import (
    AiChatIn,
    AiPlanIn,
    AiReportIn,
    AuthLoginIn,
    ComponentIn,
    ConversationMessageIn,
    ConversationThreadIn,
    DeliverableIn,
    DependencyIn,
    ProjectIn,
    ProjectUpdate,
    ResourceIn,
    RiskIn,
    SprintIn,
    StoryIn,
    TaskIn,
    TaskUpdate,
)


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    all_rows = ctx.all_rows
    bootstrap_payload = ctx.bootstrap_payload
    calculate_metrics = ctx.calculate_metrics
    context_label = ctx.context_label
    db = ctx.db
    deep_merge = ctx.deep_merge
    DEFAULT_PARAMETERS = ctx.DEFAULT_PARAMETERS
    dumps = ctx.dumps
    get_project_or_404 = ctx.get_project_or_404
    get_task_or_404 = ctx.get_task_or_404
    get_thread_or_404 = ctx.get_thread_or_404
    hash_password = ctx.hash_password
    init_db = ctx.init_db
    iso_value = ctx.iso_value
    loads = ctx.loads
    MAX_UPLOAD_BYTES = ctx.MAX_UPLOAD_BYTES
    normalize_task_dates = ctx.normalize_task_dates
    one = ctx.one
    parse_iso = ctx.parse_iso
    portfolio_summary = ctx.portfolio_summary
    project_intelligence = ctx.project_intelligence
    public_user = ctx.public_user
    recalculate_project_schedule = ctx.recalculate_project_schedule
    refresh_outline_levels = ctx.refresh_outline_levels
    risk_level = ctx.risk_level
    safe_filename = ctx.safe_filename
    seed_database = ctx.seed_database
    serialize_project = ctx.serialize_project
    serialize_risk = ctx.serialize_risk
    task_duration_days = ctx.task_duration_days
    UPLOAD_DIR = ctx.UPLOAD_DIR
    user_from_authorization = ctx.user_from_authorization
    validate_dependency = ctx.validate_dependency
    assert_component_in_project = ctx.assert_component_in_project
    assert_task_in_project = ctx.assert_task_in_project
    @router.post("/api/ai/generate-plan")
    def ai_generate_plan(payload: AiPlanIn) -> Dict[str, Any]:
        with db() as conn:
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
                title = f"{phase}: entregable principal"
                item = {
                    "project_id": p["id"], "title": title, "phase": phase, "task_type": "task", "start_date": s.isoformat(), "end_date": e.isoformat(), "progress": 0,
                    "owner": p["project_manager"] or "PM", "status": "Pendiente", "story_points": 8 if phase.lower().startswith("ej") else 0,
                    "budget": round(float(p["budget"] or 0) / max(len(phases), 1) * 0.12, 2), "description": f"Generado para el objetivo: {payload.objective}", "order_index": last_order + idx + 1,
                }
                generated.append(item)
                if payload.create_records:
                    cur = conn.execute("""INSERT INTO tasks (project_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, description, order_index)
                                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (item["project_id"], item["title"], item["phase"], item["task_type"], item["start_date"], item["end_date"], item["progress"], item["owner"], item["status"], item["story_points"], item["budget"], item["description"], item["order_index"]))
                    if previous_id:
                        conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", (p["id"], previous_id, cur.lastrowid))
                    previous_id = cur.lastrowid
            if payload.create_records:
                conn.commit()
            return {"message": "Plan generado con motor IA-ready. Sustituible por OpenAI/Azure OpenAI cuando se configure la llave.", "generated_tasks": generated}
    
    
    @router.post("/api/ai/report")
    def ai_report(payload: AiReportIn) -> Dict[str, Any]:
        with db() as conn:
            p = get_project_or_404(conn, payload.project_id)
            m = calculate_metrics(conn, payload.project_id)
            intel = project_intelligence(conn, payload.project_id)
            risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ? AND status != 'Cerrado' ORDER BY probability * impact DESC LIMIT 5", (payload.project_id,))
            deliverables = all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ? ORDER BY due_date, id LIMIT 5", (payload.project_id,))
            report = f"""Informe ejecutivo para {payload.audience}
    Proyecto: {p['name']}
    Estado: {p['status']} | Salud: {m['health']}
    Avance general: {m['progress']}%
    Presupuesto ejecutado estimado: {m['spent']:,.0f} de {m['budget']:,.0f} {p['currency']}
    Riesgos abiertos: {m['open_risks']} | Riesgos altos: {m['high_risks']}
    Ruta cr?tica: {m['critical_path_tasks']} tareas abiertas con dependencias.
    
    Foco recomendado:
    1. Revisar tareas atrasadas y dependencias cr?ticas.
    2. Confirmar capacidad de recursos de QA y Desarrollo.
    3. Mantener gobierno PMP para hitos y cambios de alcance, permitiendo ejecuci?n ?gil en sprints.
    """.strip()
            if risks:
                report += "\n\nPrincipales riesgos:\n" + "\n".join([f"- {r['title']} ({r['level']})" for r in risks])
            if deliverables:
                report += "\n\nProductos y evidencias:\n" + "\n".join([f"- {d['name']} | {d['status']} | {d['due_date'] or 'sin fecha'}" for d in deliverables])
            report += "\n\nRecomendaciones IA-ready:\n" + "\n".join([f"- {item}" for item in intel["recommendations"]])
            return {"report": report}
    
    
    

    def answer_project_question(conn: sqlite3.Connection, project_id: int, question: str) -> str:
        p = get_project_or_404(conn, project_id)
        m = calculate_metrics(conn, project_id)
        intel = project_intelligence(conn, project_id)
        q = question.lower()
        delayed = all_rows(conn, "SELECT title, owner, end_date, progress FROM tasks WHERE project_id = ? AND end_date < ? AND progress < 100 ORDER BY end_date LIMIT 8", (project_id, date.today().isoformat()))
        high = all_rows(conn, "SELECT title, owner, level, response FROM risks WHERE project_id = ? AND level = 'Alto' AND status != 'Cerrado' ORDER BY probability * impact DESC LIMIT 6", (project_id,))
        milestones = intel.get("compromised_milestones", [])[:6]
        if any(w in q for w in ["atras", "venc", "demora", "retras"]):
            if not delayed:
                return "No identifico actividades vencidas abiertas frente a la fecha actual. Mant?n el seguimiento semanal y registra evidencias de avance."
            return "Actividades atrasadas detectadas:\n" + "\n".join([f"- {t['title']} | Responsable: {t['owner'] or 'sin asignar'} | Fin: {t['end_date']} | Avance: {t['progress']}%" for t in delayed])
        if "riesg" in q:
            if not high:
                return f"El proyecto tiene {m['open_risks']} riesgos abiertos, pero no hay riesgos altos abiertos. Recomendaci?n: mantener actualizaci?n de probabilidad, impacto y respuesta."
            return "Riesgos altos abiertos:\n" + "\n".join([f"- {r['title']} | Responsable: {r['owner'] or 'sin asignar'} | Respuesta: {r['response'] or 'pendiente'}" for r in high])
        if "hito" in q:
            if not milestones:
                return "No hay hitos comprometidos seg?n el estado actual. Revisa pr?ximos hitos y carga evidencias de cumplimiento."
            return "Hitos comprometidos:\n" + "\n".join([f"- {h['title']} | Fecha: {h['end_date']} | Avance: {h['progress']}%" for h in milestones])
        if "presupuesto" in q or "costo" in q or "fond" in q:
            return f"Presupuesto total: {m['budget']:,.0f} {p['currency']}. Ejecutado estimado: {m['spent']:,.0f}. Saldo estimado: {m['remaining_budget']:,.0f}."
        if "entreg" in q or "producto" in q or "evidencia" in q:
            deliverables = all_rows(conn, "SELECT name, deliverable_type, status, due_date, evidence_url FROM deliverables WHERE project_id = ? ORDER BY due_date LIMIT 8", (project_id,))
            evidences = one(conn, "SELECT COUNT(*) AS total FROM evidence_files WHERE project_id = ?", (project_id,))["total"]
            return f"El proyecto tiene {len(deliverables)} entregables/productos visibles y {evidences} evidencias cargadas.\n" + "\n".join([f"- {d['name']} | {d['deliverable_type']} | {d['status']} | Evidencia: {'s?' if d['evidence_url'] else 'no'}" for d in deliverables])
        return f"Estado del proyecto {p['name']}: salud {m['health']}, avance {m['progress']}%, {m['open_risks']} riesgos abiertos ({m['high_risks']} altos), {m['delayed_tasks']} actividades atrasadas y {m['critical_path_tasks']} tareas en ruta cr?tica. Recomendaciones: " + "; ".join(intel.get("recommendations", []))
    
    
    @router.post("/api/ai/chat")
    def ai_chat(payload: AiChatIn) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            answer = answer_project_question(conn, payload.project_id, payload.question)
            add_history(conn, payload.project_id, "IA", "Chat del proyecto", "Consulta", payload.question[:180], payload.author or "Usuario")
            conn.commit()
            return {"answer": answer, "generated_at": datetime.utcnow().isoformat()}


    return router


