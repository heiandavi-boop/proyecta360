from __future__ import annotations

import csv
import html
import io
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

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

    def clean_row(row: Dict[str, Any]) -> Dict[str, str]:
        return {str(k or "").strip(): str(v or "").strip() for k, v in row.items() if str(k or "").strip()}

    def pick(row: Dict[str, str], key: str, default: Any = "") -> Any:
        value = row.get(key)
        return default if value is None or value == "" else value

    def as_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return default

    def as_float(value: Any, default: float = 0) -> float:
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def nullable_id(value: Any, refs: Dict[str, int]) -> Optional[int]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw in refs:
            return refs[raw]
        return as_int(raw, 0) or None

    def strategic_from_project_row(row: Dict[str, str]) -> Dict[str, str]:
        keys = [
            "problem_statement", "current_situation", "main_gap", "general_objective", "specific_objectives",
            "objective_indicators", "expected_results", "success_criteria", "political_context", "geographic_context",
            "socioeconomic_context", "cultural_context", "stakeholders_context", "institutional_context",
            "target_population", "direct_beneficiaries", "indirect_beneficiaries", "assumptions", "constraints",
        ]
        return {key: row[key] for key in keys if row.get(key)}

    def import_project_from_rows(conn: sqlite3.Connection, rows: List[Dict[str, str]]) -> Dict[str, Any]:
        by_entity: Dict[str, List[Dict[str, str]]] = {}
        for row in rows:
            entity = (row.get("entity") or row.get("tipo") or "").strip().lower()
            if entity:
                by_entity.setdefault(entity, []).append(row)
        project_rows = by_entity.get("project") or by_entity.get("proyecto") or []
        project_row = project_rows[0] if project_rows else {}
        if not project_row.get("name") and not project_row.get("nombre"):
            raise HTTPException(status_code=400, detail="El CSV debe incluir una fila entity=project con el campo name")

        params = deep_merge(DEFAULT_PARAMETERS, loads(project_row.get("parameters_json"), {}) or {})
        strategic = strategic_from_project_row(project_row)
        if strategic:
            params["strategic_framework"] = deep_merge(params.get("strategic_framework", {}), strategic)
        start = pick(project_row, "start_date", date.today().isoformat())
        end = pick(project_row, "end_date", start)
        cur = conn.execute(
            """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, contractual_end_date, methodology, status, budget, currency, parameters_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pick(project_row, "name", project_row.get("nombre", "Proyecto importado")),
                pick(project_row, "description", ""),
                pick(project_row, "sponsor", ""),
                pick(project_row, "project_manager", ""),
                start,
                end,
                pick(project_row, "contractual_end_date", ""),
                pick(project_row, "methodology", "Hibrida PMP + Scrum"),
                pick(project_row, "status", "Planeado"),
                as_float(pick(project_row, "budget", 0)),
                pick(project_row, "currency", "COP").upper(),
                dumps(params),
            ),
        )
        project_id = int(cur.lastrowid)
        refs: Dict[str, Dict[str, int]] = {"component": {}, "task": {}, "sprint": {}, "conversation_thread": {}}
        counts: Dict[str, int] = {"projects": 1, "components": 0, "resources": 0, "tasks": 0, "dependencies": 0, "sprints": 0, "stories": 0, "risks": 0, "deliverables": 0, "conversation_threads": 0, "conversation_messages": 0}

        for row in by_entity.get("component", []) + by_entity.get("components", []):
            cur = conn.execute(
                "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, pick(row, "name", "Componente importado"), pick(row, "methodology", "Hibrida"), pick(row, "owner", ""), pick(row, "objective", ""), as_int(pick(row, "progress", 0))),
            )
            if row.get("import_id"):
                refs["component"][row["import_id"]] = int(cur.lastrowid)
            counts["components"] += 1
        for row in by_entity.get("resource", []) + by_entity.get("resources", []):
            conn.execute("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", (project_id, pick(row, "name", "Recurso importado"), pick(row, "role", ""), pick(row, "email", ""), as_int(pick(row, "capacity", 100), 100)))
            counts["resources"] += 1

        task_rows = by_entity.get("task", []) + by_entity.get("tasks", [])
        pending_task_updates: List[tuple[int, Dict[str, str]]] = []
        for index, row in enumerate(task_rows, start=1):
            start_s, end_s, duration = normalize_task_dates(pick(row, "start_date", start), pick(row, "end_date", "") or None, as_int(pick(row, "duration_days", 1), 1), pick(row, "task_type", "task"))
            parent_id = nullable_id(pick(row, "parent_id", ""), refs["task"])
            component_id = nullable_id(pick(row, "component_ref", pick(row, "component_id", "")), refs["component"])
            cur = conn.execute(
                """INSERT INTO tasks (project_id, parent_id, component_id, title, phase, task_type, start_date, end_date, duration_days, progress, owner, status, story_points, budget, description, order_index, outline_level, is_expanded)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, parent_id, component_id, pick(row, "title", pick(row, "name", "Tarea importada")), pick(row, "phase", ""), pick(row, "task_type", "task"), start_s, end_s, duration, as_int(pick(row, "progress", 0)), pick(row, "owner", ""), pick(row, "status", "Pendiente"), as_int(pick(row, "story_points", 0)), as_float(pick(row, "budget", 0)), pick(row, "description", ""), as_int(pick(row, "order_index", index), index), as_int(pick(row, "outline_level", 0)), as_int(pick(row, "is_expanded", 1), 1)),
            )
            new_id = int(cur.lastrowid)
            if row.get("import_id"):
                refs["task"][row["import_id"]] = new_id
            pending_task_updates.append((new_id, row))
            counts["tasks"] += 1
        for task_id, row in pending_task_updates:
            parent_id = nullable_id(pick(row, "parent_ref", ""), refs["task"])
            if parent_id:
                conn.execute("UPDATE tasks SET parent_id = ? WHERE id = ?", (parent_id, task_id))

        for row in by_entity.get("dependency", []) + by_entity.get("dependencies", []):
            pred = nullable_id(pick(row, "predecessor_ref", pick(row, "predecessor_id", "")), refs["task"])
            succ = nullable_id(pick(row, "successor_ref", pick(row, "successor_id", "")), refs["task"])
            if pred and succ:
                validate_dependency(conn, project_id, pred, succ)
                conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type, lag_days) VALUES (?, ?, ?, ?, ?)", (project_id, pred, succ, pick(row, "dependency_type", "FS").upper(), as_int(pick(row, "lag_days", 0))))
                counts["dependencies"] += 1
        for row in by_entity.get("sprint", []) + by_entity.get("sprints", []):
            cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, pick(row, "name", "Sprint importado"), pick(row, "goal", ""), pick(row, "start_date", start), pick(row, "end_date", start), pick(row, "status", "Planeado"), as_int(pick(row, "velocity", 0))))
            if row.get("import_id"):
                refs["sprint"][row["import_id"]] = int(cur.lastrowid)
            counts["sprints"] += 1
        for row in by_entity.get("story", []) + by_entity.get("stories", []):
            sprint_id = nullable_id(pick(row, "sprint_ref", pick(row, "sprint_id", "")), refs["sprint"])
            conn.execute("INSERT INTO stories (project_id, sprint_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, sprint_id, pick(row, "title", "Historia importada"), pick(row, "status", "Por hacer"), as_int(pick(row, "points", 0)), pick(row, "assignee", ""), pick(row, "priority", "Media")))
            counts["stories"] += 1
        for row in by_entity.get("risk", []) + by_entity.get("risks", []):
            probability, impact = as_int(pick(row, "probability", 1), 1), as_int(pick(row, "impact", 1), 1)
            conn.execute("INSERT INTO risks (project_id, title, probability, impact, level, response, mitigation_plan, contingency_plan, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (project_id, pick(row, "title", pick(row, "name", "Riesgo importado")), probability, impact, pick(row, "level", risk_level(probability, impact, params)), pick(row, "response", ""), pick(row, "mitigation_plan", ""), pick(row, "contingency_plan", ""), pick(row, "status", "Abierto"), pick(row, "owner", "")))
            counts["risks"] += 1
        for row in by_entity.get("deliverable", []) + by_entity.get("deliverables", []):
            component_id = nullable_id(pick(row, "component_ref", pick(row, "component_id", "")), refs["component"])
            conn.execute("""INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, owner, due_date, evidence_url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (project_id, component_id, pick(row, "name", "Entregable importado"), pick(row, "deliverable_type", "Entregable"), pick(row, "status", "Planeado"), pick(row, "owner", ""), pick(row, "due_date", ""), pick(row, "evidence_url", ""), pick(row, "description", "")))
            counts["deliverables"] += 1
        for row in by_entity.get("conversation_thread", []) + by_entity.get("conversation_threads", []):
            cur = conn.execute("INSERT INTO conversation_threads (project_id, title, context_type, context_id, category, status, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, pick(row, "title", "Conversacion importada"), pick(row, "context_type", "Proyecto"), as_int(pick(row, "context_id", 0)) or None, pick(row, "category", "Seguimiento"), pick(row, "status", "Abierta"), pick(row, "created_by", "")))
            if row.get("import_id"):
                refs["conversation_thread"][row["import_id"]] = int(cur.lastrowid)
            counts["conversation_threads"] += 1
        for row in by_entity.get("conversation_message", []) + by_entity.get("conversation_messages", []):
            thread_id = nullable_id(pick(row, "thread_ref", pick(row, "thread_id", "")), refs["conversation_thread"])
            if thread_id:
                conn.execute("INSERT INTO conversation_messages (thread_id, project_id, author, message, mentions, evidence_url, message_type) VALUES (?, ?, ?, ?, ?, ?, ?)", (thread_id, project_id, pick(row, "author", ""), pick(row, "message", ""), pick(row, "mentions", ""), pick(row, "evidence_url", ""), pick(row, "message_type", "Comentario")))
                counts["conversation_messages"] += 1

        refresh_outline_levels(conn, project_id)
        if counts["tasks"]:
            recalculate_project_schedule(conn, project_id)
        add_history(conn, project_id, "Importacion", pick(project_row, "name", "Proyecto importado"), "CSV importado", f"Filas procesadas: {len(rows)}")
        return {"project_id": project_id, "counts": counts}

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

    @router.post("/api/projects/import/csv")
    async def import_project_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
        init_db()
        filename = file.filename or ""
        if not filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos CSV")
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="El archivo supera el tamano permitido")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        fields = {str(name or "").strip() for name in (reader.fieldnames or [])}
        if "entity" not in fields:
            raise HTTPException(status_code=400, detail="El CSV debe incluir la columna entity")
        rows = [clean_row(row) for row in reader]
        if not rows:
            raise HTTPException(status_code=400, detail="El CSV no contiene filas para importar")
        with db() as conn:
            result = import_project_from_rows(conn, rows)
            project = serialize_project(get_project_or_404(conn, result["project_id"]))
            conn.commit()
            return {"message": "Proyecto importado", "project": project, **result}
    
    
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


