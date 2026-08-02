from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request

from proyecta360.schemas.api import (
    AiChatIn,
    AiAnalysisIn,
    AiPlanIn,
    AiProjectChatIn,
    AiRecommendationUpdate,
    AiReportIn,
    AiSettingsIn,
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

    def current_user(conn: sqlite3.Connection, request: Request) -> Dict[str, Any]:
        user = user_from_authorization(conn, request.headers.get("Authorization"))
        if not user:
            raise HTTPException(status_code=401, detail="Sesion requerida")
        return user

    def mask_api_key(value: str = "") -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "****"
        return f"{value[:3]}****{value[-4:]}"

    def serialize_ai_settings(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not row:
            return {
                "provider": "OpenAI", "model": "gpt-4o-mini", "endpoint": "", "deployment": "",
                "organization_id": "", "api_key_masked": "", "status": "No configurado",
                "last_test_at": "", "last_error": "",
            }
        return {
            "id": row["id"],
            "provider": row["provider"],
            "model": row["model"],
            "endpoint": row["endpoint"],
            "deployment": row["deployment"],
            "organization_id": row["organization_id"],
            "api_key_masked": mask_api_key(row["api_key_encrypted"]),
            "status": row["status"],
            "last_test_at": row["last_test_at"],
            "last_error": row["last_error"],
            "updated_at": row["updated_at"],
        }

    def rec_history(conn: sqlite3.Connection, recommendation_id: int, event_type: str, user_id: Optional[int], detail: str = "", previous: Any = None, new: Any = None) -> None:
        conn.execute(
            "INSERT INTO ai_recommendation_history (recommendation_id, event_type, event_detail, previous_json, new_json, user_id) VALUES (?, ?, ?, ?, ?, ?)",
            (recommendation_id, event_type, detail, dumps(previous) if previous is not None else "", dumps(new) if new is not None else "", user_id),
        )

    def ai_payload(row: Dict[str, Any]) -> Dict[str, Any]:
        return loads(row.get("edited_payload_json") or row.get("proposed_payload_json") or "{}", {})

    def serialize_recommendation(row: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(row)
        item["proposed_payload"] = loads(item.pop("proposed_payload_json", "{}"), {})
        edited_raw = item.pop("edited_payload_json", "")
        item["edited_payload"] = loads(edited_raw, {}) if edited_raw else None
        return item

    def project_snapshot(conn: sqlite3.Connection, project_id: int, includes: AiAnalysisIn) -> Dict[str, Any]:
        p = serialize_project(get_project_or_404(conn, project_id))
        snapshot: Dict[str, Any] = {"project": p, "metrics": calculate_metrics(conn, project_id)}
        if includes.include_schedule:
            snapshot["tasks"] = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
            snapshot["dependencies"] = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ? ORDER BY id", (project_id,))
        if includes.include_risks:
            snapshot["risks"] = all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY probability * impact DESC, id", (project_id,))
        if includes.include_resources:
            snapshot["resources"] = all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY name", (project_id,))
        if includes.include_deliverables:
            snapshot["deliverables"] = all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ? ORDER BY due_date, id", (project_id,))
        if includes.include_evidences:
            snapshot["evidences"] = all_rows(conn, "SELECT id, project_id, entity_type, entity_id, original_filename, content_type, size_bytes, uploaded_by, description, created_at FROM evidence_files WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        if includes.include_history:
            snapshot["history"] = all_rows(conn, "SELECT * FROM change_log WHERE project_id = ? ORDER BY created_at DESC LIMIT 30", (project_id,))
        if includes.include_conversations:
            snapshot["conversations"] = all_rows(conn, "SELECT * FROM conversation_messages WHERE project_id = ? ORDER BY created_at DESC LIMIT 30", (project_id,))
        return snapshot

    def demo_ai_analysis(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        metrics = snapshot.get("metrics", {})
        project = snapshot.get("project", {})
        issues: List[Dict[str, Any]] = []
        recs: List[Dict[str, Any]] = []
        if metrics.get("delayed_tasks", 0):
            issues.append({"type": "schedule_delay", "severity": "high", "description": f"Hay {metrics['delayed_tasks']} actividades atrasadas o con bajo avance.", "related_entity_type": "project", "related_entity_id": project.get("id")})
            recs.append({
                "action_type": "create_task", "target_module": "gantt", "title": "Plan de recuperación del cronograma",
                "description": "Crear una actividad de recuperación para destrabar tareas atrasadas.",
                "justification": "Permite asignar responsable, duración y seguimiento específico al atraso.",
                "expected_impact": "Reduce exposición de fechas críticas y mejora control semanal.",
                "priority": "high",
                "proposed_payload": {"title": "Plan de recuperación del cronograma", "duration_days": 3, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            })
        high_risks = metrics.get("high_risks", 0)
        if high_risks:
            issues.append({"type": "open_high_risks", "severity": "high", "description": f"Existen {high_risks} riesgos altos abiertos.", "related_entity_type": "risk", "related_entity_id": None})
            recs.append({
                "action_type": "create_risk", "target_module": "riesgos", "title": "Riesgo de seguimiento ejecutivo semanal",
                "description": "Registrar un riesgo de gobierno para riesgos altos sin control suficiente.",
                "justification": "Formaliza seguimiento, propietario y respuesta frente al comité.",
                "expected_impact": "Mejora visibilidad y tratamiento de riesgos críticos.",
                "priority": "high",
                "proposed_payload": {"title": "Seguimiento ejecutivo de riesgos altos", "probability": 3, "impact": 4, "response": "Mitigar", "owner": project.get("project_manager") or "PM", "status": "Abierto"},
            })
        if metrics.get("critical_path_tasks", 0):
            recs.append({
                "action_type": "create_task", "target_module": "gantt", "title": "Revisión de ruta crítica",
                "description": "Crear una tarea de revisión para validar dependencias y fechas críticas.",
                "justification": "La ruta crítica requiere control explícito antes de afectar hitos.",
                "expected_impact": "Mejora predictibilidad del cierre del proyecto.",
                "priority": "medium",
                "proposed_payload": {"title": "Revisión de ruta crítica", "duration_days": 1, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            })
        if not recs:
            recs.append({
                "action_type": "create_alert", "target_module": "ia", "title": "Mantener seguimiento preventivo",
                "description": "El proyecto no muestra alertas críticas en modo demo.",
                "justification": "Una revisión preventiva mantiene actualizada la información estratégica.",
                "expected_impact": "Sostiene trazabilidad y anticipación de desviaciones.",
                "priority": "low",
                "proposed_payload": {"message": "Mantener seguimiento preventivo semanal"},
            })
        health = "En riesgo" if issues else metrics.get("health", "Saludable")
        return {
            "project_health": health,
            "summary": f"Analisis demo de {project.get('name')}: avance {metrics.get('progress', 0)}%, {metrics.get('open_risks', 0)} riesgos abiertos y {metrics.get('critical_path_tasks', 0)} tareas en ruta critica.",
            "detected_issues": issues,
            "recommended_actions": recs,
            "mode": "demo",
        }

    def persist_analysis(conn: sqlite3.Connection, project_id: int, user_id: int, snapshot: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            """INSERT INTO ai_analysis_runs (project_id, requested_by, status, project_health, summary, input_snapshot_json, raw_output_json, started_at, finished_at)
               VALUES (?, ?, 'Completado', ?, ?, ?, ?, ?, ?)""",
            (project_id, user_id, result.get("project_health", ""), result.get("summary", ""), dumps(snapshot), dumps(result), now, now),
        )
        run_id = cur.lastrowid
        for issue in result.get("detected_issues", []):
            conn.execute(
                """INSERT INTO ai_detected_issues (analysis_run_id, project_id, type, severity, description, related_entity_type, related_entity_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, project_id, issue.get("type", ""), issue.get("severity", ""), issue.get("description", ""), issue.get("related_entity_type", ""), issue.get("related_entity_id")),
            )
        recommendation_ids = []
        for rec in result.get("recommended_actions", []):
            cur = conn.execute(
                """INSERT INTO ai_recommendations (analysis_run_id, project_id, title, description, action_type, target_module, target_entity_type, target_entity_id, justification, expected_impact, priority, proposed_payload_json, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pendiente')""",
                (run_id, project_id, rec.get("title", ""), rec.get("description", ""), rec.get("action_type", ""), rec.get("target_module", ""), rec.get("target_entity_type", ""), rec.get("target_entity_id"), rec.get("justification", ""), rec.get("expected_impact", ""), rec.get("priority", "medium"), dumps(rec.get("proposed_payload", {}))),
            )
            recommendation_ids.append(cur.lastrowid)
            rec_history(conn, cur.lastrowid, "Creada", user_id, "Recomendacion generada por analisis IA", None, rec)
        add_history(conn, project_id, "IA", "Analisis del proyecto", "Analisis IA", result.get("summary", "")[:240], "IA")
        return {"run_id": run_id, "recommendation_ids": recommendation_ids}

    def apply_ai_recommendation(conn: sqlite3.Connection, rec: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        if rec["status"] != "Aprobada":
            raise HTTPException(status_code=400, detail="Solo una recomendacion aprobada puede aplicarse")
        payload = ai_payload(rec)
        project_id = int(rec["project_id"])
        action = rec["action_type"]
        before: Any = None
        after: Any = None
        if action == "create_task":
            project = get_project_or_404(conn, project_id)
            start_date = payload.get("start_date") or project["start_date"]
            duration = int(payload.get("duration_days", 1))
            task_type = payload.get("task_type", "task")
            end_date = payload.get("end_date") or normalize_task_dates(start_date, None, duration, task_type)[1]
            order = one(conn, "SELECT COALESCE(MAX(order_index), 0) AS mx FROM tasks WHERE project_id = ?", (project_id,))["mx"] + 1
            cur = conn.execute(
                """INSERT INTO tasks (project_id, title, task_type, start_date, end_date, duration_days, progress, owner, status, description, order_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, payload.get("title") or payload.get("name") or rec["title"], task_type, start_date, end_date, duration, int(payload.get("progress", 0)), payload.get("owner") or payload.get("responsible", ""), payload.get("status", "Pendiente"), payload.get("description", rec["description"]), order),
            )
            recalculate_project_schedule(conn, project_id)
            after = one(conn, "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,))
        elif action == "update_task":
            task_id = int(payload.get("task_id") or rec.get("target_entity_id") or 0)
            before = get_task_or_404(conn, task_id)
            if int(before["project_id"]) != project_id:
                raise HTTPException(status_code=400, detail="La tarea no pertenece al proyecto")
            allowed = {k: payload[k] for k in ["title", "progress", "owner", "status", "description", "duration_days", "start_date"] if k in payload}
            if not allowed:
                raise HTTPException(status_code=400, detail="Payload sin campos actualizables")
            assignments = ", ".join([f"{k} = ?" for k in allowed])
            conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", tuple(allowed.values()) + (task_id,))
            recalculate_project_schedule(conn, project_id)
            after = one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        elif action == "create_dependency":
            pred, succ = int(payload["predecessor_id"]), int(payload["successor_id"])
            validate_dependency(conn, project_id, pred, succ)
            cur = conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type, lag_days) VALUES (?, ?, ?, ?, ?)", (project_id, pred, succ, payload.get("dependency_type", "FS"), int(payload.get("lag_days", 0))))
            recalculate_project_schedule(conn, project_id)
            after = one(conn, "SELECT * FROM dependencies WHERE id = ?", (cur.lastrowid,))
        elif action == "create_risk":
            probability, impact = int(payload.get("probability", 3)), int(payload.get("impact", 3))
            level = risk_level(probability, impact)
            cur = conn.execute(
                "INSERT INTO risks (project_id, title, probability, impact, level, response, mitigation_plan, contingency_plan, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, payload.get("title") or rec["title"], probability, impact, level, payload.get("response", ""), payload.get("mitigation_plan", ""), payload.get("contingency_plan", ""), payload.get("status", "Abierto"), payload.get("owner", "")),
            )
            after = one(conn, "SELECT * FROM risks WHERE id = ?", (cur.lastrowid,))
        elif action in {"update_risk", "add_mitigation_plan", "add_contingency_plan"}:
            risk_id = int(payload.get("risk_id") or rec.get("target_entity_id") or 0)
            before = one(conn, "SELECT * FROM risks WHERE id = ? AND project_id = ?", (risk_id, project_id))
            if not before:
                raise HTTPException(status_code=404, detail="Riesgo no encontrado")
            allowed = {}
            for key in ["title", "response", "mitigation_plan", "contingency_plan", "status", "owner"]:
                if key in payload:
                    allowed[key] = payload[key]
            if action == "add_mitigation_plan" and "mitigation_plan" not in allowed:
                allowed["mitigation_plan"] = payload.get("plan", rec["description"])
            if action == "add_contingency_plan" and "contingency_plan" not in allowed:
                allowed["contingency_plan"] = payload.get("plan", rec["description"])
            if not allowed:
                raise HTTPException(status_code=400, detail="Payload sin campos actualizables")
            conn.execute("UPDATE risks SET " + ", ".join([f"{k}=?" for k in allowed]) + " WHERE id = ?", tuple(allowed.values()) + (risk_id,))
            after = one(conn, "SELECT * FROM risks WHERE id = ?", (risk_id,))
        elif action == "create_deliverable":
            cur = conn.execute(
                "INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, owner, due_date, evidence_url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, payload.get("component_id"), payload.get("name") or rec["title"], payload.get("deliverable_type", "Entregable"), payload.get("status", "Planeado"), payload.get("owner", ""), payload.get("due_date", ""), payload.get("evidence_url", ""), payload.get("description", rec["description"])),
            )
            after = one(conn, "SELECT * FROM deliverables WHERE id = ?", (cur.lastrowid,))
        elif action in {"request_evidence", "create_alert", "update_project_status"}:
            detail = payload.get("message") or payload.get("status") or rec["description"]
            add_history(conn, project_id, "IA", rec["title"], action, detail, user["name"])
            after = {"message": detail}
        else:
            raise HTTPException(status_code=400, detail="Tipo de accion IA no soportado")
        now = datetime.utcnow().isoformat()
        conn.execute("UPDATE ai_recommendations SET status = 'Aplicada', applied_at = ?, error_message = '' WHERE id = ?", (now, rec["id"]))
        rec_history(conn, rec["id"], "Aplicada", user["id"], f"Accion aplicada: {action}", before, after)
        add_history(conn, project_id, "IA", rec["title"], "Recomendacion aplicada", f"{action} aplicado por {user['name']}", user["name"])
        return {"applied": True, "result": after}

    @router.get("/api/ai/settings")
    def get_ai_settings() -> Dict[str, Any]:
        with db() as conn:
            return serialize_ai_settings(one(conn, "SELECT * FROM ai_settings ORDER BY id LIMIT 1"))

    @router.post("/api/ai/settings")
    def save_ai_settings(payload: AiSettingsIn) -> Dict[str, Any]:
        with db() as conn:
            existing = one(conn, "SELECT * FROM ai_settings ORDER BY id LIMIT 1")
            api_key = payload.api_key if payload.api_key and "****" not in payload.api_key else (existing["api_key_encrypted"] if existing else "")
            status = "Conectado" if api_key else "No configurado"
            now = datetime.utcnow().isoformat()
            if existing:
                conn.execute(
                    """UPDATE ai_settings SET provider=?, model=?, endpoint=?, deployment=?, organization_id=?, api_key_encrypted=?, status=?, updated_at=? WHERE id=?""",
                    (payload.provider, payload.model, payload.endpoint, payload.deployment, payload.organization_id, api_key, status, now, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO ai_settings (provider, model, endpoint, deployment, organization_id, api_key_encrypted, status, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload.provider, payload.model, payload.endpoint, payload.deployment, payload.organization_id, api_key, status, now),
                )
            conn.commit()
            return serialize_ai_settings(one(conn, "SELECT * FROM ai_settings ORDER BY id LIMIT 1"))

    @router.post("/api/ai/test-connection")
    def test_ai_connection() -> Dict[str, Any]:
        with db() as conn:
            settings = one(conn, "SELECT * FROM ai_settings ORDER BY id LIMIT 1")
            now = datetime.utcnow().isoformat()
            if not settings or not settings["api_key_encrypted"]:
                message = "IA funcionando en modo demo. Configure una API Key para analisis generativo real."
                if settings:
                    conn.execute("UPDATE ai_settings SET status='No configurado', last_test_at=?, last_error=? WHERE id=?", (now, message, settings["id"]))
                    conn.commit()
                return {"status": "No configurado", "mode": "demo", "message": message, "last_test_at": now}
            conn.execute("UPDATE ai_settings SET status='Conectado', last_test_at=?, last_error='' WHERE id=?", (now, settings["id"]))
            conn.commit()
            return {"status": "Conectado", "mode": "configured", "message": "Configuracion IA registrada. La prueba remota real se habilitara al activar el servicio externo.", "last_test_at": now}

    @router.delete("/api/ai/settings")
    def clear_ai_settings() -> Dict[str, str]:
        with db() as conn:
            conn.execute("DELETE FROM ai_settings")
            conn.commit()
            return {"message": "Configuracion IA eliminada"}

    @router.post("/api/projects/{project_id}/ai/analyze")
    def analyze_project(project_id: int, payload: AiAnalysisIn, request: Request) -> Dict[str, Any]:
        with db() as conn:
            user = current_user(conn, request)
            snapshot = project_snapshot(conn, project_id, payload)
            result = demo_ai_analysis(snapshot)
            persisted = persist_analysis(conn, project_id, user["id"], snapshot, result)
            conn.commit()
            return {**result, **persisted, "demo_notice": "IA funcionando en modo demo. Configure una API Key para analisis generativo real."}

    @router.get("/api/projects/{project_id}/ai/analysis-runs")
    def list_analysis_runs(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            runs = all_rows(conn, "SELECT * FROM ai_analysis_runs WHERE project_id = ? ORDER BY started_at DESC, id DESC", (project_id,))
            return {"runs": runs}

    @router.get("/api/ai/analysis-runs/{run_id}")
    def get_analysis_run(run_id: int) -> Dict[str, Any]:
        with db() as conn:
            run = one(conn, "SELECT * FROM ai_analysis_runs WHERE id = ?", (run_id,))
            if not run:
                raise HTTPException(status_code=404, detail="Analisis IA no encontrado")
            run["input_snapshot"] = loads(run.pop("input_snapshot_json", "{}"), {})
            run["raw_output"] = loads(run.pop("raw_output_json", "{}"), {})
            run["issues"] = all_rows(conn, "SELECT * FROM ai_detected_issues WHERE analysis_run_id = ? ORDER BY id", (run_id,))
            run["recommendations"] = [serialize_recommendation(r) for r in all_rows(conn, "SELECT * FROM ai_recommendations WHERE analysis_run_id = ? ORDER BY id", (run_id,))]
            return run

    @router.get("/api/projects/{project_id}/ai/recommendations")
    def list_recommendations(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            rows = all_rows(conn, "SELECT * FROM ai_recommendations WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,))
            return {"recommendations": [serialize_recommendation(r) for r in rows]}

    @router.get("/api/ai/recommendations/{recommendation_id}")
    def get_recommendation(recommendation_id: int) -> Dict[str, Any]:
        with db() as conn:
            row = one(conn, "SELECT * FROM ai_recommendations WHERE id = ?", (recommendation_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Recomendacion IA no encontrada")
            item = serialize_recommendation(row)
            item["history"] = all_rows(conn, "SELECT * FROM ai_recommendation_history WHERE recommendation_id = ? ORDER BY created_at DESC, id DESC", (recommendation_id,))
            return item

    @router.patch("/api/ai/recommendations/{recommendation_id}")
    def update_recommendation(recommendation_id: int, payload: AiRecommendationUpdate, request: Request) -> Dict[str, Any]:
        data = payload.model_dump(exclude_unset=True)
        with db() as conn:
            user = current_user(conn, request)
            current = one(conn, "SELECT * FROM ai_recommendations WHERE id = ?", (recommendation_id,))
            if not current:
                raise HTTPException(status_code=404, detail="Recomendacion IA no encontrada")
            if current["status"] not in {"Pendiente", "Aprobada"}:
                raise HTTPException(status_code=400, detail="Esta recomendacion ya no puede editarse")
            updates: Dict[str, Any] = {}
            for field in ["title", "description", "justification", "expected_impact", "priority"]:
                if field in data:
                    updates[field] = data[field]
            if "proposed_payload" in data:
                updates["edited_payload_json"] = dumps(data["proposed_payload"])
            if "edited_payload" in data:
                updates["edited_payload_json"] = dumps(data["edited_payload"])
            if updates:
                conn.execute("UPDATE ai_recommendations SET " + ", ".join([f"{k}=?" for k in updates]) + " WHERE id = ?", tuple(updates.values()) + (recommendation_id,))
                rec_history(conn, recommendation_id, "Editada", user["id"], "Recomendacion editada por usuario", serialize_recommendation(current), data)
            conn.commit()
            return get_recommendation(recommendation_id)

    @router.post("/api/ai/recommendations/{recommendation_id}/approve")
    def approve_recommendation(recommendation_id: int, request: Request) -> Dict[str, Any]:
        with db() as conn:
            user = current_user(conn, request)
            row = one(conn, "SELECT * FROM ai_recommendations WHERE id = ?", (recommendation_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Recomendacion IA no encontrada")
            if row["status"] != "Pendiente":
                raise HTTPException(status_code=400, detail="Solo recomendaciones pendientes pueden aprobarse")
            now = datetime.utcnow().isoformat()
            conn.execute("UPDATE ai_recommendations SET status='Aprobada', decided_by=?, decided_at=? WHERE id=?", (user["id"], now, recommendation_id))
            rec_history(conn, recommendation_id, "Aprobada", user["id"], "Recomendacion aprobada")
            conn.commit()
            return get_recommendation(recommendation_id)

    @router.post("/api/ai/recommendations/{recommendation_id}/reject")
    def reject_recommendation(recommendation_id: int, request: Request) -> Dict[str, Any]:
        with db() as conn:
            user = current_user(conn, request)
            row = one(conn, "SELECT * FROM ai_recommendations WHERE id = ?", (recommendation_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Recomendacion IA no encontrada")
            if row["status"] == "Aplicada":
                raise HTTPException(status_code=400, detail="Una recomendacion aplicada no puede rechazarse")
            now = datetime.utcnow().isoformat()
            conn.execute("UPDATE ai_recommendations SET status='Rechazada', decided_by=?, decided_at=? WHERE id=?", (user["id"], now, recommendation_id))
            rec_history(conn, recommendation_id, "Rechazada", user["id"], "Recomendacion rechazada")
            conn.commit()
            return get_recommendation(recommendation_id)

    @router.post("/api/ai/recommendations/{recommendation_id}/apply")
    def apply_recommendation(recommendation_id: int, request: Request) -> Dict[str, Any]:
        with db() as conn:
            user = current_user(conn, request)
            row = one(conn, "SELECT * FROM ai_recommendations WHERE id = ?", (recommendation_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Recomendacion IA no encontrada")
            try:
                result = apply_ai_recommendation(conn, row, user)
                conn.commit()
                return result
            except HTTPException:
                raise
            except Exception as exc:
                conn.execute("UPDATE ai_recommendations SET error_message=? WHERE id=?", (str(exc), recommendation_id))
                rec_history(conn, recommendation_id, "Error al aplicar", user["id"], str(exc))
                conn.commit()
                raise HTTPException(status_code=400, detail=f"Error al aplicar recomendacion: {exc}")

    @router.get("/api/projects/{project_id}/ai/history")
    def ai_history(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            runs = all_rows(conn, """
                SELECT r.*, 
                    (SELECT COUNT(*) FROM ai_detected_issues i WHERE i.analysis_run_id = r.id) AS issues_count,
                    (SELECT COUNT(*) FROM ai_recommendations a WHERE a.analysis_run_id = r.id) AS recommendations_count,
                    (SELECT COUNT(*) FROM ai_recommendations a WHERE a.analysis_run_id = r.id AND a.status = 'Aprobada') AS approved_count,
                    (SELECT COUNT(*) FROM ai_recommendations a WHERE a.analysis_run_id = r.id AND a.status = 'Rechazada') AS rejected_count,
                    (SELECT COUNT(*) FROM ai_recommendations a WHERE a.analysis_run_id = r.id AND a.status = 'Aplicada') AS applied_count
                FROM ai_analysis_runs r WHERE r.project_id = ? ORDER BY r.started_at DESC, r.id DESC
            """, (project_id,))
            return {"history": runs}

    @router.get("/api/ai/recommendations/{recommendation_id}/history")
    def recommendation_history(recommendation_id: int) -> Dict[str, Any]:
        with db() as conn:
            return {"history": all_rows(conn, "SELECT * FROM ai_recommendation_history WHERE recommendation_id = ? ORDER BY created_at DESC, id DESC", (recommendation_id,))}

    @router.post("/api/projects/{project_id}/ai/chat")
    def project_ai_chat(project_id: int, payload: AiProjectChatIn, request: Request) -> Dict[str, Any]:
        with db() as conn:
            user = current_user(conn, request)
            if payload.mode == "accion":
                snapshot = project_snapshot(conn, project_id, AiAnalysisIn())
                result = demo_ai_analysis(snapshot)
                persisted = persist_analysis(conn, project_id, user["id"], snapshot, result)
                conn.commit()
                return {"mode": "accion", "answer": "Se generaron recomendaciones pendientes. Revisa y aprueba antes de aplicar.", **persisted}
            answer = answer_project_question(conn, project_id, payload.message)
            add_history(conn, project_id, "IA", "Chat IA del proyecto", "Consulta", payload.message[:180], user["name"])
            conn.commit()
            return {"mode": "consulta", "answer": answer, "generated_at": datetime.utcnow().isoformat()}

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
            generated = []
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
            return {"message": "Plan generado como propuesta IA. No se aplicaron cambios directos al proyecto; use Recomendaciones IA para aprobar y aplicar.", "generated_tasks": generated}
    
    
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


