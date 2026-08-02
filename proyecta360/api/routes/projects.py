from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from typing import Any, Dict

from fastapi import HTTPException
from fastapi.responses import Response
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
    serialize_evidence = ctx.serialize_evidence
    serialize_project = ctx.serialize_project
    serialize_risk = ctx.serialize_risk
    task_duration_days = ctx.task_duration_days
    UPLOAD_DIR = ctx.UPLOAD_DIR
    user_from_authorization = ctx.user_from_authorization
    validate_dependency = ctx.validate_dependency
    assert_component_in_project = ctx.assert_component_in_project
    assert_task_in_project = ctx.assert_task_in_project
    @router.post("/api/projects")
    def create_project(payload: ProjectIn) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            parameters = deep_merge(DEFAULT_PARAMETERS, payload.parameters)
            calculated_end = payload.end_date or payload.start_date
            cur = conn.execute(
                """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, contractual_end_date, methodology, status, budget, currency, parameters_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload.name, payload.description, payload.sponsor, payload.project_manager, iso_value(payload.start_date), iso_value(calculated_end), iso_value(payload.contractual_end_date) if payload.contractual_end_date else "", payload.methodology, payload.status, payload.budget, payload.currency, dumps(parameters)),
            )
            add_history(conn, cur.lastrowid, "Proyecto", payload.name, "Creado", "Proyecto creado con fecha fin calculada por cronograma.")
            conn.commit()
            return serialize_project(get_project_or_404(conn, cur.lastrowid))
    
    
    @router.put("/api/projects/{project_id}")
    def update_project(project_id: int, payload: ProjectUpdate) -> Dict[str, Any]:
        with db() as conn:
            current = get_project_or_404(conn, project_id)
            data = payload.model_dump(exclude_unset=True)
            start_date = iso_value(data.get("start_date", current["start_date"]))
            end_date = iso_value(data.get("end_date", current["end_date"]))
            if end_date and start_date and end_date < start_date:
                raise HTTPException(status_code=400, detail="La fecha fin no puede ser menor a la fecha inicio")
            if "parameters" in data and data["parameters"] is not None:
                existing_parameters = loads(current["parameters_json"], DEFAULT_PARAMETERS)
                data["parameters_json"] = dumps(deep_merge(existing_parameters, data.pop("parameters")))
            fields = []
            args = []
            for k, v in data.items():
                fields.append(f"{k} = ?")
                args.append(iso_value(v))
            if fields:
                args.append(project_id)
                conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", tuple(args))
                conn.commit()
            return serialize_project(get_project_or_404(conn, project_id))
    

    @router.get("/api/projects/{project_id}/metrics")
    def metrics(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            return calculate_metrics(conn, project_id)
    
    
    @router.get("/api/projects/{project_id}/intelligence")
    def intelligence(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, project_id)
            return project_intelligence(conn, project_id)
    

    def export_project_data(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
        project = serialize_project(get_project_or_404(conn, project_id))
        return {
            "project": project,
            "components": all_rows(conn, "SELECT * FROM components WHERE project_id = ? ORDER BY id", (project_id,)),
            "resources": all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (project_id,)),
            "tasks": all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,)),
            "dependencies": all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ? ORDER BY id", (project_id,)),
            "sprints": all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date, id", (project_id,)),
            "stories": all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (project_id,)),
            "risks": [serialize_risk(r) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY id", (project_id,))],
            "deliverables": all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ? ORDER BY due_date, id", (project_id,)),
            "evidences": [serialize_evidence(r) for r in all_rows(conn, "SELECT * FROM evidence_files WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,))],
            "history": all_rows(conn, "SELECT * FROM change_log WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,)),
            "conversation_threads": all_rows(conn, "SELECT * FROM conversation_threads WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,)),
            "conversation_messages": all_rows(conn, "SELECT * FROM conversation_messages WHERE project_id = ? ORDER BY created_at, id", (project_id,)),
            "metrics": calculate_metrics(conn, project_id),
            "intelligence": project_intelligence(conn, project_id),
            "exported_at": datetime.utcnow().isoformat(),
        }
    
    
    @router.get("/api/projects/{project_id}/export/json")
    def export_project_json(project_id: int) -> Response:
        init_db()
        with db() as conn:
            data = export_project_data(conn, project_id)
            add_history(conn, project_id, "Exportación", data["project"]["name"], "JSON generado", "Descarga completa del proyecto")
            conn.commit()
        filename = f"proyecta360_proyecto_{project_id}.json"
        return Response(
            content=dumps(data),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    
    
    @router.get("/api/projects/{project_id}/export/html")
    def export_project_html(project_id: int) -> Response:
        init_db()
        with db() as conn:
            data = export_project_data(conn, project_id)
            p, m, intel = data["project"], data["metrics"], data["intelligence"]
            risks = data["risks"][:6]
            tasks = data["tasks"][:12]
            deliverables = data["deliverables"][:8]
            add_history(conn, project_id, "Exportación", p["name"], "HTML generado", "Reporte ejecutivo descargado")
            conn.commit()
        def esc(x: Any) -> str:
            return html.escape(str(x if x is not None else ""))
        html_doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Reporte {esc(p['name'])}</title>
        <style>body{{font-family:Arial,sans-serif;margin:32px;color:#0f172a}}.card{{border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin:12px 0}}h1{{color:#2563eb}}table{{border-collapse:collapse;width:100%;margin-top:10px}}td,th{{border-bottom:1px solid #e2e8f0;padding:8px;text-align:left}}.pill{{display:inline-block;padding:5px 10px;border-radius:999px;background:#eff6ff;color:#2563eb;font-weight:700}}</style></head><body>
        <h1>Reporte ejecutivo Proyecta360</h1><h2>{esc(p['name'])}</h2><p>{esc(p.get('description',''))}</p>
        <div class='card'><span class='pill'>{esc(m['health'])}</span><p><b>Avance:</b> {esc(m['progress'])}% | <b>Presupuesto ejecutado:</b> {esc(m['spent'])} de {esc(m['budget'])} {esc(p['currency'])} | <b>Riesgos altos:</b> {esc(m['high_risks'])}</p></div>
        <div class='card'><h3>Recomendaciones</h3><ul>{''.join(f'<li>{esc(x)}</li>' for x in intel.get('recommendations', []))}</ul></div>
        <div class='card'><h3>Actividades principales</h3><table><tr><th>Actividad</th><th>Responsable</th><th>Avance</th><th>Fecha fin</th></tr>{''.join(f'<tr><td>{esc(t["title"])}</td><td>{esc(t["owner"])}</td><td>{esc(t["progress"])}%</td><td>{esc(t["end_date"])}</td></tr>' for t in tasks)}</table></div>
        <div class='card'><h3>Riesgos</h3><table><tr><th>Riesgo</th><th>Nivel</th><th>Responsable</th><th>Respuesta</th></tr>{''.join(f'<tr><td>{esc(r["title"])}</td><td>{esc(r["level"])}</td><td>{esc(r["owner"])}</td><td>{esc(r["response"])}</td></tr>' for r in risks)}</table></div>
        <div class='card'><h3>Entregables y productos</h3><table><tr><th>Nombre</th><th>Tipo</th><th>Estado</th><th>Fecha</th></tr>{''.join(f'<tr><td>{esc(d["name"])}</td><td>{esc(d["deliverable_type"])}</td><td>{esc(d["status"])}</td><td>{esc(d["due_date"])}</td></tr>' for d in deliverables)}</table></div>
        <p><small>Generado automáticamente por Proyecta360 · {esc(datetime.utcnow().isoformat())}</small></p></body></html>"""
        filename = f"proyecta360_reporte_{project_id}.html"
        return Response(
            content=html_doc,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    

    return router


