from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
import httpx

from proyecta360.schemas.api import (
    AiChatIn,
    AiAnalysisIn,
    AiPlanIn,
    AiProjectChatIn,
    AiRecommendationUpdate,
    AiReportIn,
    AiSettingsIn,
)
from proyecta360.services.internal_ai_engine import analyze_project_internal_ai


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    all_rows = ctx.all_rows
    calculate_metrics = ctx.calculate_metrics
    db = ctx.db
    DEFAULT_PARAMETERS = ctx.DEFAULT_PARAMETERS
    dumps = ctx.dumps
    get_project_or_404 = ctx.get_project_or_404
    get_task_or_404 = ctx.get_task_or_404
    init_db = ctx.init_db
    loads = ctx.loads
    normalize_task_dates = ctx.normalize_task_dates
    one = ctx.one
    project_intelligence = ctx.project_intelligence
    recalculate_project_schedule = ctx.recalculate_project_schedule
    risk_level = ctx.risk_level
    serialize_project = ctx.serialize_project
    user_from_authorization = ctx.user_from_authorization
    validate_dependency = ctx.validate_dependency

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

    AI_PROVIDERS: Dict[str, Dict[str, Any]] = {
        "openai": {
            "name": "OpenAI / ChatGPT",
            "default_model": "gpt-5.6-terra",
            "model_options": [
                {"value": "gpt-5.6-sol", "label": "GPT-5.6 Sol"},
                {"value": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
                {"value": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
                {"value": "gpt-5.6", "label": "GPT-5.6"},
                {"value": "gpt-4o", "label": "GPT-4o"},
                {"value": "gpt-4o-mini", "label": "GPT-4o mini"},
            ],
            "api_style": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
                {"name": "organization", "label": "Organization ID", "type": "text", "required": False},
                {"name": "project", "label": "Project ID", "type": "text", "required": False},
            ],
        },
        "anthropic": {
            "name": "Anthropic / Claude",
            "default_model": "claude-sonnet-5",
            "model_options": [
                {"value": "claude-fable-5", "label": "Claude Fable 5"},
                {"value": "claude-opus-5", "label": "Claude Opus 5"},
                {"value": "claude-sonnet-5", "label": "Claude Sonnet 5"},
                {"value": "claude-haiku-4-5", "label": "Claude Haiku 4.5"},
                {"value": "claude-mythos-preview", "label": "Claude Mythos Preview"},
            ],
            "api_style": "anthropic",
            "base_url": "https://api.anthropic.com",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
            ],
        },
        "gemini": {
            "name": "Google Gemini",
            "default_model": "gemini-3-pro",
            "model_options": [
                {"value": "gemini-3-pro", "label": "Gemini 3 Pro"},
                {"value": "gemini-3-flash", "label": "Gemini 3 Flash"},
                {"value": "gemini-3-flash-lite", "label": "Gemini 3 Flash Lite"},
                {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
                {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
                {"value": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
            ],
            "api_style": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
            ],
        },
        "deepseek": {
            "name": "DeepSeek",
            "default_model": "deepseek-chat",
            "model_options": [
                {"value": "deepseek-chat", "label": "DeepSeek Chat"},
                {"value": "deepseek-reasoner", "label": "DeepSeek Reasoner"},
            ],
            "api_style": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
            ],
        },
        "xai": {
            "name": "xAI / Grok",
            "default_model": "grok-4.5",
            "model_options": [
                {"value": "grok-4.5", "label": "Grok 4.5"},
                {"value": "grok-4.5-latest", "label": "Grok 4.5 latest"},
                {"value": "grok-4", "label": "Grok 4"},
                {"value": "grok-4-latest", "label": "Grok 4 latest"},
            ],
            "api_style": "openai_compatible",
            "base_url": "https://api.x.ai/v1",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
            ],
        },
        "mistral": {
            "name": "Mistral AI",
            "default_model": "mistral-large-latest",
            "model_options": [
                {"value": "mistral-large-latest", "label": "Mistral Large latest"},
                {"value": "mistral-medium-latest", "label": "Mistral Medium latest"},
                {"value": "mistral-small-latest", "label": "Mistral Small latest"},
                {"value": "ministral-8b-latest", "label": "Ministral 8B latest"},
                {"value": "ministral-3b-latest", "label": "Ministral 3B latest"},
                {"value": "codestral-latest", "label": "Codestral latest"},
            ],
            "api_style": "openai_compatible",
            "base_url": "https://api.mistral.ai/v1",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
            ],
        },
        "openrouter": {
            "name": "OpenRouter",
            "default_model": "openai/gpt-5.6-terra",
            "model_options": [
                {"value": "openai/gpt-5.6-sol", "label": "OpenAI GPT-5.6 Sol"},
                {"value": "openai/gpt-5.6-terra", "label": "OpenAI GPT-5.6 Terra"},
                {"value": "anthropic/claude-sonnet-5", "label": "Anthropic Claude Sonnet 5"},
                {"value": "anthropic/claude-opus-5", "label": "Anthropic Claude Opus 5"},
                {"value": "google/gemini-3-pro", "label": "Google Gemini 3 Pro"},
                {"value": "x-ai/grok-4.5", "label": "xAI Grok 4.5"},
                {"value": "deepseek/deepseek-chat", "label": "DeepSeek Chat"},
                {"value": "mistralai/mistral-large", "label": "Mistral Large"},
            ],
            "api_style": "openai_compatible",
            "base_url": "https://openrouter.ai/api/v1",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
                {"name": "site_url", "label": "Site URL", "type": "url", "required": False},
                {"name": "app_name", "label": "Nombre de app", "type": "text", "required": False},
            ],
        },
        "together": {
            "name": "Together AI",
            "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "model_options": [
                {"value": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "label": "Llama 3.3 70B Instruct Turbo"},
                {"value": "meta-llama/Llama-3.1-405B-Instruct-Turbo", "label": "Llama 3.1 405B Instruct Turbo"},
                {"value": "Qwen/Qwen2.5-72B-Instruct-Turbo", "label": "Qwen 2.5 72B Instruct Turbo"},
                {"value": "deepseek-ai/DeepSeek-V3", "label": "DeepSeek V3"},
                {"value": "deepseek-ai/DeepSeek-R1", "label": "DeepSeek R1"},
                {"value": "mistralai/Mixtral-8x7B-Instruct-v0.1", "label": "Mixtral 8x7B Instruct"},
            ],
            "api_style": "openai_compatible",
            "base_url": "https://api.together.xyz/v1",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "select", "required": True},
            ],
        },
        "custom_openai": {
            "name": "Compatible OpenAI / Personalizado",
            "default_model": "",
            "api_style": "openai_compatible",
            "base_url": "",
            "fields": [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "model", "label": "Modelo", "type": "text", "required": True},
                {"name": "base_url", "label": "Base URL", "type": "url", "required": True, "placeholder": "https://api.proveedor.com/v1"},
            ],
        },
    }

    def provider_definition(provider: str) -> Dict[str, Any]:
        return AI_PROVIDERS.get(provider) or AI_PROVIDERS["openai"]

    def serialize_ai_settings(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not row:
            return {
                "provider": "openai", "provider_name": AI_PROVIDERS["openai"]["name"],
                "model": "gpt-4o-mini", "api_key_masked": "", "config": {},
                "status": "No configurado", "last_test_at": "", "last_error": "",
                "providers": AI_PROVIDERS,
            }
        provider = row.get("provider") or "openai"
        config = loads(row.get("config_json") or "{}", {})
        return {
            "id": row["id"],
            "provider": provider,
            "provider_name": provider_definition(provider)["name"],
            "model": row["model"],
            "api_key_masked": mask_api_key(row["api_key_encrypted"]),
            "config": config,
            "status": row["status"],
            "last_test_at": row["last_test_at"],
            "last_error": row["last_error"],
            "updated_at": row["updated_at"],
            "providers": AI_PROVIDERS,
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
        snapshot: Dict[str, Any] = {
            "project": p,
            "project_context": p.get("ai_context", {}),
            "metrics": calculate_metrics(conn, project_id),
        }
        if includes.include_schedule:
            snapshot["tasks"] = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
            snapshot["dependencies"] = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ? ORDER BY id", (project_id,))
            snapshot["sprints"] = all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date, id", (project_id,))
            snapshot["stories"] = all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (project_id,))
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

    def internal_rules_analysis(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return analyze_project_internal_ai(snapshot)
        metrics = snapshot.get("metrics", {})
        project = snapshot.get("project", {})
        tasks = snapshot.get("tasks", [])
        risks = snapshot.get("risks", [])
        deliverables = snapshot.get("deliverables", [])
        evidences = snapshot.get("evidences", [])
        conversations = snapshot.get("conversations", [])
        today = date.today().isoformat()
        issues: List[Dict[str, Any]] = []
        recs: List[Dict[str, Any]] = []

        def add_issue(issue_type: str, severity: str, description: str, entity_type: str = "project", entity_id: Optional[int] = None) -> None:
            issues.append({
                "type": issue_type,
                "severity": severity,
                "description": description,
                "related_entity_type": entity_type,
                "related_entity_id": entity_id or project.get("id"),
            })

        def add_rec(action_type: str, target_module: str, title: str, description: str, justification: str, expected_impact: str, priority: str, payload: Dict[str, Any], target_entity_type: str = "", target_entity_id: Optional[int] = None) -> None:
            recs.append({
                "action_type": action_type,
                "target_module": target_module,
                "target_entity_type": target_entity_type,
                "target_entity_id": target_entity_id,
                "title": title,
                "description": description,
                "justification": justification,
                "expected_impact": expected_impact,
                "priority": priority,
                "proposed_payload": payload,
            })

        overdue_tasks = [t for t in tasks if t.get("end_date") and t.get("end_date") < today and int(t.get("progress") or 0) < 100]
        blocked_messages = [c for c in conversations if any(word in str(c.get("message", "")).lower() for word in ["bloque", "impedimento", "critico", "urgente"])]
        ownerless_tasks = [t for t in tasks if not str(t.get("owner") or "").strip() and t.get("task_type") != "summary"]
        open_high_risks = [r for r in risks if r.get("level") == "Alto" and r.get("status") != "Cerrado"]
        risks_without_plans = [r for r in open_high_risks if not str(r.get("mitigation_plan") or "").strip() or not str(r.get("contingency_plan") or "").strip()]
        deliverables_without_evidence = [
            d for d in deliverables
            if d.get("due_date") and d.get("due_date") <= today and not str(d.get("evidence_url") or "").strip() and d.get("status") != "Aprobado"
        ]
        task_progress = float(metrics.get("progress") or 0)
        budget = float(metrics.get("budget") or 0)
        spent = float(metrics.get("spent") or 0)
        budget_execution = (spent / budget * 100) if budget > 0 else 0

        if metrics.get("delayed_tasks", 0):
            add_issue("schedule_delay", "high", f"Hay {metrics['delayed_tasks']} actividades atrasadas o con bajo avance.")
            add_rec(
                "create_task", "gantt", "Plan de recuperacion del cronograma",
                "Crear una actividad de recuperacion para coordinar el cierre de tareas atrasadas.",
                "El atraso necesita responsable, fecha y seguimiento propio para evitar que se diluya en el plan.",
                "Reduce exposicion de fechas criticas y mejora control semanal.",
                "high",
                {"title": "Plan de recuperacion del cronograma", "duration_days": 3, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            )
        if overdue_tasks:
            first = overdue_tasks[0]
            add_issue("overdue_task", "high", f"La actividad '{first.get('title')}' esta vencida y no completada.", "task", first.get("id"))
        if open_high_risks:
            add_issue("open_high_risks", "high", f"Existen {len(open_high_risks)} riesgos altos abiertos.", "risk", open_high_risks[0].get("id"))
            add_rec(
                "create_task", "riesgos", "Revision ejecutiva de riesgos altos",
                "Agendar una revision corta para validar responsables, respuestas y fechas de tratamiento.",
                "Los riesgos altos abiertos requieren visibilidad y seguimiento periodico.",
                "Mejora el control de exposiciones criticas antes de que afecten cronograma o alcance.",
                "high",
                {"title": "Revision ejecutiva de riesgos altos", "duration_days": 1, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            )
        if risks_without_plans:
            risk = risks_without_plans[0]
            add_issue("risk_without_plan", "medium", f"El riesgo '{risk.get('title')}' no tiene mitigacion o contingencia completa.", "risk", risk.get("id"))
            add_rec(
                "add_mitigation_plan", "riesgos", "Completar plan de mitigacion",
                "Agregar o fortalecer el plan de mitigacion del riesgo prioritario.",
                "Un riesgo alto sin plan no permite controlar acciones preventivas.",
                "Aumenta trazabilidad y reduce improvisacion ante materializacion del riesgo.",
                "medium",
                {"risk_id": risk.get("id"), "mitigation_plan": "Definir acciones preventivas, responsable, fecha objetivo e indicador de seguimiento."},
                "risk", risk.get("id"),
            )
        if metrics.get("critical_path_tasks", 0):
            add_issue("critical_path_active", "medium", f"Hay {metrics['critical_path_tasks']} tareas abiertas con dependencias en ruta critica.")
            add_rec(
                "create_task", "gantt", "Revision de ruta critica",
                "Validar dependencias, fechas y responsables de actividades criticas.",
                "La ruta critica requiere control explicito antes de afectar hitos.",
                "Mejora predictibilidad del cierre del proyecto.",
                "medium",
                {"title": "Revision de ruta critica", "duration_days": 1, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            )
        if ownerless_tasks:
            task = ownerless_tasks[0]
            add_issue("task_without_owner", "medium", f"Hay {len(ownerless_tasks)} actividades sin responsable asignado.", "task", task.get("id"))
        if deliverables_without_evidence:
            deliverable = deliverables_without_evidence[0]
            add_issue("deliverable_without_evidence", "medium", f"El entregable '{deliverable.get('name')}' esta vencido o por vencer sin evidencia.", "deliverable", deliverable.get("id"))
            add_rec(
                "request_evidence", "entregables", "Solicitar evidencia de entregables pendientes",
                "Pedir soporte de cumplimiento para entregables vencidos o criticos.",
                "La evidencia permite cerrar trazabilidad y validar avance real.",
                "Reduce incertidumbre sobre avance fisico y aceptacion.",
                "medium",
                {"deliverable_id": deliverable.get("id"), "description": "Cargar evidencia de avance, aprobacion o entrega."},
                "deliverable", deliverable.get("id"),
            )
        if budget > 0 and budget_execution > task_progress + 15:
            add_issue("budget_ahead_of_progress", "medium", f"El presupuesto ejecutado estimado ({budget_execution:.1f}%) supera el avance fisico ({task_progress:.1f}%).")
            add_rec(
                "create_risk", "riesgos", "Riesgo de desviacion presupuesto-avance",
                "Registrar un riesgo para monitorear diferencia entre ejecucion financiera y avance fisico.",
                "La brecha puede indicar sobrecosto, avance no documentado o mala distribucion presupuestal.",
                "Permite activar seguimiento financiero y acciones correctivas tempranas.",
                "medium",
                {"title": "Desviacion entre presupuesto ejecutado y avance fisico", "probability": 3, "impact": 3, "response": "Mitigar", "owner": project.get("project_manager") or "PM", "status": "Abierto"},
            )
        if blocked_messages:
            add_issue("conversation_blocker", "medium", f"Hay {len(blocked_messages)} conversaciones recientes con posibles bloqueos o urgencias.", "conversation", blocked_messages[0].get("id"))
            add_rec(
                "create_task", "conversaciones", "Gestionar bloqueos reportados",
                "Crear una actividad de seguimiento para resolver bloqueos mencionados en conversaciones.",
                "Los bloqueos conversacionales pueden quedar fuera del cronograma si no se convierten en accion.",
                "Aumenta trazabilidad y cierre de impedimentos.",
                "medium",
                {"title": "Gestionar bloqueos reportados", "duration_days": 1, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            )
        if not evidences and tasks:
            add_issue("low_evidence_traceability", "low", "No se encontraron evidencias cargadas para el proyecto.")
        if not recs:
            add_rec(
                "create_task", "gantt", "Seguimiento preventivo semanal",
                "Crear una actividad ligera para revisar avance, riesgos y evidencias.",
                "Aunque no hay alertas criticas, la revision preventiva mantiene el proyecto actualizado.",
                "Sostiene trazabilidad y anticipacion de desviaciones.",
                "low",
                {"title": "Seguimiento preventivo semanal", "duration_days": 1, "owner": project.get("project_manager") or "PM", "status": "Pendiente", "progress": 0},
            )
        high_count = len([i for i in issues if i["severity"] == "high"])
        medium_count = len([i for i in issues if i["severity"] == "medium"])
        if high_count >= 3 or metrics.get("health") == "Crítico":
            health = "Critico"
        elif high_count or medium_count >= 2 or metrics.get("health") == "En riesgo":
            health = "En riesgo"
        elif medium_count or issues:
            health = "En observacion"
        else:
            health = "Saludable"
        return {
            "project_health": health,
            "summary": (
                f"Analisis generado por motor interno para {project.get('name')}: avance {metrics.get('progress', 0)}%, "
                f"{metrics.get('open_risks', 0)} riesgos abiertos, {metrics.get('high_risks', 0)} altos, "
                f"{metrics.get('delayed_tasks', 0)} actividades atrasadas y {metrics.get('critical_path_tasks', 0)} tareas en ruta critica. "
                f"Se detectaron {len(issues)} hallazgos y se generaron {len(recs)} recomendaciones pendientes de aprobacion humana."
            ),
            "detected_issues": issues,
            "recommended_actions": recs,
            "mode": "internal_rules",
            "engine_label": "Motor interno",
        }

    def settings_row(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
        return one(conn, "SELECT * FROM ai_settings ORDER BY id LIMIT 1")

    def ai_settings_ready(settings: Optional[Dict[str, Any]]) -> bool:
        return bool(settings and settings.get("api_key_encrypted") and settings.get("status") == "Conectado")

    def openai_compatible_request(settings: Dict[str, Any], messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        provider = settings.get("provider") or "openai"
        definition = provider_definition(provider)
        config = loads(settings.get("config_json") or "{}", {})
        base_url = (config.get("base_url") or definition.get("base_url") or "").rstrip("/")
        api_key = settings["api_key_encrypted"]
        model = settings["model"] or definition.get("default_model") or "gpt-4o-mini"
        payload: Dict[str, Any] = {"model": model or "gpt-4o-mini", "messages": messages, "temperature": 0.2}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if provider == "openai":
            if config.get("organization"):
                headers["OpenAI-Organization"] = config["organization"]
            if config.get("project"):
                headers["OpenAI-Project"] = config["project"]
        if provider == "openrouter":
            if config.get("site_url"):
                headers["HTTP-Referer"] = config["site_url"]
            if config.get("app_name"):
                headers["X-Title"] = config["app_name"]
        try:
            response = httpx.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=45,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise HTTPException(status_code=400, detail=f"Error de {definition['name']}: {detail}")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"No fue posible conectar con {definition['name']}: {exc}")

    def anthropic_request(settings: Dict[str, Any], messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        config = loads(settings.get("config_json") or "{}", {})
        base_url = (config.get("base_url") or AI_PROVIDERS["anthropic"]["base_url"]).rstrip("/")
        system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
        user_messages = [{"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("content", "")} for m in messages if m.get("role") != "system"]
        if json_mode:
            user_messages.append({"role": "user", "content": "Responde exclusivamente con un objeto JSON valido, sin Markdown."})
        payload: Dict[str, Any] = {"model": settings["model"] or AI_PROVIDERS["anthropic"]["default_model"], "messages": user_messages, "max_tokens": 2048, "temperature": 0.2}
        if system:
            payload["system"] = system
        try:
            response = httpx.post(
                f"{base_url}/v1/messages",
                headers={"x-api-key": settings["api_key_encrypted"], "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json=payload,
                timeout=45,
            )
            response.raise_for_status()
            data = response.json()
            return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Error de Anthropic/Claude: {exc.response.text[:500]}")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"No fue posible conectar con Anthropic/Claude: {exc}")

    def gemini_request(settings: Dict[str, Any], messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        config = loads(settings.get("config_json") or "{}", {})
        base_url = (config.get("base_url") or AI_PROVIDERS["gemini"]["base_url"]).rstrip("/")
        model = settings["model"] or AI_PROVIDERS["gemini"]["default_model"]
        prompt = "\n\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages)
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if json_mode:
            payload["generationConfig"]["response_mime_type"] = "application/json"
        try:
            response = httpx.post(
                f"{base_url}/models/{model}:generateContent",
                params={"key": settings["api_key_encrypted"]},
                json=payload,
                timeout=45,
            )
            response.raise_for_status()
            data = response.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(part.get("text", "") for part in parts)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Error de Google Gemini: {exc.response.text[:500]}")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"No fue posible conectar con Google Gemini: {exc}")

    def ai_provider_request(settings: Dict[str, Any], messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        provider = settings.get("provider") or "openai"
        style = provider_definition(provider).get("api_style")
        if style == "anthropic":
            return anthropic_request(settings, messages, json_mode)
        if style == "gemini":
            return gemini_request(settings, messages, json_mode)
        return openai_compatible_request(settings, messages, json_mode)

    def chatgpt_request(api_key: str, model: str, messages: List[Dict[str, str]], json_mode: bool = False) -> str:
        return ai_provider_request({"provider": "openai", "model": model, "api_key_encrypted": api_key, "config_json": "{}"}, messages, json_mode)

    def provider_label(settings: Dict[str, Any]) -> str:
        return provider_definition(settings.get("provider") or "openai")["name"]

    def locale_name(locale: str = "") -> str:
        code = (locale or "es").split("-")[0].lower()
        return {
            "en": "English",
            "zh": "Chinese",
            "hi": "Hindi",
            "es": "Spanish",
            "ar": "Arabic",
        }.get(code, "Spanish")

    def request_language(request: Request) -> str:
        return locale_name(request.headers.get("X-Locale", "es"))

    def configured_ai_analysis(settings: Dict[str, Any], snapshot: Dict[str, Any], language: str = "Spanish") -> Dict[str, Any]:
        system = (
            "Eres un copiloto experto en gestion de proyectos. Analiza el snapshot del proyecto y responde solo JSON valido. "
            "Nunca apliques cambios. Solo propone recomendaciones pendientes para aprobacion humana. "
            f"Todos los textos descriptivos deben estar en {language}."
        )
        user = (
            "Devuelve exactamente un objeto JSON con project_health, summary, detected_issues y recommended_actions. "
            "Las acciones permitidas son create_task, update_task, create_dependency, create_risk, update_risk, "
            "create_deliverable, request_evidence, add_mitigation_plan y add_contingency_plan.\n\n"
            f"Snapshot:\n{dumps(snapshot)}"
        )
        content = ai_provider_request(settings, [{"role": "system", "content": system}, {"role": "user", "content": user}], True)
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail=f"{provider_label(settings)} no devolvio JSON valido")
        result.setdefault("project_health", "Sin clasificar")
        result.setdefault("summary", "")
        result.setdefault("detected_issues", [])
        result.setdefault("recommended_actions", [])
        result["mode"] = "configured"
        result["provider"] = settings.get("provider") or "openai"
        return result

    def chatgpt_analysis(settings: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return configured_ai_analysis(settings, snapshot)

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

    def undo_ai_recommendation(conn: sqlite3.Connection, rec: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        if rec["status"] != "Aplicada":
            raise HTTPException(status_code=400, detail="Solo una recomendacion aplicada puede deshacerse")
        applied_event = one(
            conn,
            "SELECT * FROM ai_recommendation_history WHERE recommendation_id = ? AND event_type = 'Aplicada' ORDER BY created_at DESC, id DESC LIMIT 1",
            (rec["id"],),
        )
        if not applied_event:
            raise HTTPException(status_code=400, detail="No se encontro historial de aplicacion para deshacer")
        payload = ai_payload(rec)
        action = rec["action_type"]
        project_id = int(rec["project_id"])
        before = loads(applied_event.get("previous_json") or "{}", {})
        after = loads(applied_event.get("new_json") or "{}", {})
        undone: Any = {"action": action}
        if action == "create_task":
            task_id = int(after.get("id") or 0)
            if task_id:
                conn.execute("DELETE FROM dependencies WHERE predecessor_id = ? OR successor_id = ?", (task_id, task_id))
                conn.execute("DELETE FROM tasks WHERE id = ? AND project_id = ?", (task_id, project_id))
                recalculate_project_schedule(conn, project_id)
                undone = {"deleted_task_id": task_id}
        elif action == "update_task":
            task_id = int(before.get("id") or payload.get("task_id") or rec.get("target_entity_id") or 0)
            if task_id and before:
                fields = {k: before[k] for k in ["title", "progress", "owner", "status", "description", "duration_days", "start_date", "end_date"] if k in before}
                if fields:
                    conn.execute("UPDATE tasks SET " + ", ".join([f"{k}=?" for k in fields]) + " WHERE id = ? AND project_id = ?", tuple(fields.values()) + (task_id, project_id))
                    recalculate_project_schedule(conn, project_id)
                undone = {"restored_task_id": task_id}
        elif action == "create_dependency":
            dep_id = int(after.get("id") or 0)
            if dep_id:
                conn.execute("DELETE FROM dependencies WHERE id = ? AND project_id = ?", (dep_id, project_id))
                recalculate_project_schedule(conn, project_id)
                undone = {"deleted_dependency_id": dep_id}
        elif action == "create_risk":
            risk_id = int(after.get("id") or 0)
            if risk_id:
                conn.execute("DELETE FROM risks WHERE id = ? AND project_id = ?", (risk_id, project_id))
                undone = {"deleted_risk_id": risk_id}
        elif action in {"update_risk", "add_mitigation_plan", "add_contingency_plan"}:
            risk_id = int(before.get("id") or payload.get("risk_id") or rec.get("target_entity_id") or 0)
            if risk_id and before:
                fields = {k: before[k] for k in ["title", "response", "mitigation_plan", "contingency_plan", "status", "owner"] if k in before}
                if fields:
                    conn.execute("UPDATE risks SET " + ", ".join([f"{k}=?" for k in fields]) + " WHERE id = ? AND project_id = ?", tuple(fields.values()) + (risk_id, project_id))
                undone = {"restored_risk_id": risk_id}
        elif action == "create_deliverable":
            deliverable_id = int(after.get("id") or 0)
            if deliverable_id:
                conn.execute("DELETE FROM deliverables WHERE id = ? AND project_id = ?", (deliverable_id, project_id))
                undone = {"deleted_deliverable_id": deliverable_id}
        elif action in {"request_evidence", "create_alert", "update_project_status"}:
            undone = {"message": "Se retiro la aplicacion operativa de la recomendacion."}
        else:
            raise HTTPException(status_code=400, detail="Tipo de accion IA no soportado para deshacer")
        conn.execute("UPDATE ai_recommendations SET status = 'Aprobada', applied_at = '', error_message = '' WHERE id = ?", (rec["id"],))
        rec_history(conn, rec["id"], "Deshecha", user["id"], f"Aplicacion deshecha: {action}", after, undone)
        add_history(conn, project_id, "IA", rec["title"], "Aplicacion deshecha", f"{action} deshecho por {user['name']}", user["name"])
        return {"undone": True, "result": undone}

    @router.get("/api/ai/settings")
    def get_ai_settings() -> Dict[str, Any]:
        with db() as conn:
            return serialize_ai_settings(settings_row(conn))

    @router.post("/api/ai/settings")
    def save_ai_settings(payload: AiSettingsIn) -> Dict[str, Any]:
        with db() as conn:
            existing = settings_row(conn)
            provider = payload.provider or "openai"
            if provider not in AI_PROVIDERS:
                raise HTTPException(status_code=400, detail="Proveedor IA no soportado")
            definition = provider_definition(provider)
            config = dict(payload.config or {})
            existing_provider = (existing["provider"] if existing and "provider" in existing else "openai") if existing else ""
            keep_existing_key = existing and existing_provider == provider and (not payload.api_key or "****" in payload.api_key)
            api_key = existing["api_key_encrypted"] if keep_existing_key else (payload.api_key if payload.api_key and "****" not in payload.api_key else "")
            provider_changed = bool(existing and existing_provider != provider)
            incoming_model = payload.model or config.get("model") or ""
            other_provider_models = set()
            for key, item in AI_PROVIDERS.items():
                if key == provider:
                    continue
                if item.get("default_model"):
                    other_provider_models.add(item["default_model"])
                for option in item.get("model_options", []):
                    other_provider_models.add(option["value"])
            inherited_model = incoming_model in other_provider_models
            model = (definition.get("default_model") or "") if provider_changed or inherited_model else (incoming_model or definition.get("default_model") or "")
            config.pop("api_key", None)
            config.pop("model", None)
            for field in definition.get("fields", []):
                name = field["name"]
                if name in {"api_key", "model"}:
                    continue
                if field.get("required") and not str(config.get(name) or "").strip():
                    raise HTTPException(status_code=400, detail=f"Falta configurar: {field['label']}")
            if any(field["name"] == "api_key" and field.get("required") for field in definition.get("fields", [])) and not api_key:
                raise HTTPException(status_code=400, detail="Falta configurar: API Key")
            if any(field["name"] == "model" and field.get("required") for field in definition.get("fields", [])) and not model:
                raise HTTPException(status_code=400, detail="Falta configurar: Modelo")
            status = "Pendiente de prueba" if api_key else "No configurado"
            now = datetime.utcnow().isoformat()
            if existing:
                conn.execute(
                    "UPDATE ai_settings SET provider=?, model=?, api_key_encrypted=?, config_json=?, status=?, last_error='', updated_at=? WHERE id=?",
                    (provider, model, api_key, dumps(config), status, now, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO ai_settings (provider, model, api_key_encrypted, config_json, status, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (provider, model, api_key, dumps(config), status, now),
                )
            conn.commit()
            return serialize_ai_settings(settings_row(conn))

    @router.post("/api/ai/test-connection")
    def test_ai_connection() -> Dict[str, Any]:
        with db() as conn:
            settings = settings_row(conn)
            now = datetime.utcnow().isoformat()
            if not settings or not settings["api_key_encrypted"]:
                message = "Motor interno activo. Configure una API Key para usar IA real."
                if settings:
                    conn.execute("UPDATE ai_settings SET status='No configurado', last_test_at=?, last_error=? WHERE id=?", (now, message, settings["id"]))
                    conn.commit()
                return {"status": "No configurado", "mode": "internal_rules", "message": message, "last_test_at": now}
            try:
                ai_provider_request(settings, [{"role": "user", "content": "Responde solo: ok"}], False)
                conn.execute("UPDATE ai_settings SET status='Conectado', last_test_at=?, last_error='' WHERE id=?", (now, settings["id"]))
                conn.commit()
                return {"status": "Conectado", "mode": "configured", "provider": settings.get("provider") or "openai", "message": f"Conexion con {provider_label(settings)} verificada.", "last_test_at": now}
            except HTTPException as exc:
                conn.execute("UPDATE ai_settings SET status='Error', last_test_at=?, last_error=? WHERE id=?", (now, str(exc.detail), settings["id"]))
                conn.commit()
                raise

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
            settings = settings_row(conn)
            notice = "Motor interno activo: analisis generado con reglas de PRUNIN. Configure y pruebe una API Key para usar IA real."
            if ai_settings_ready(settings):
                try:
                    result = configured_ai_analysis(settings, snapshot, request_language(request))
                    notice = ""
                except HTTPException as exc:
                    now = datetime.utcnow().isoformat()
                    conn.execute("UPDATE ai_settings SET status='Error', last_test_at=?, last_error=? WHERE id=?", (now, str(exc.detail), settings["id"]))
                    result = internal_rules_analysis(snapshot)
                    notice = f"IA real no disponible ({exc.detail}). Se uso motor interno de PRUNIN."
            else:
                result = internal_rules_analysis(snapshot)
            persisted = persist_analysis(conn, project_id, user["id"], snapshot, result)
            conn.commit()
            return {**result, **persisted, "analysis_notice": notice, "demo_notice": notice}

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

    @router.post("/api/ai/recommendations/{recommendation_id}/undo")
    def undo_recommendation(recommendation_id: int, request: Request) -> Dict[str, Any]:
        with db() as conn:
            user = current_user(conn, request)
            row = one(conn, "SELECT * FROM ai_recommendations WHERE id = ?", (recommendation_id,))
            if not row:
                raise HTTPException(status_code=404, detail="Recomendacion IA no encontrada")
            result = undo_ai_recommendation(conn, row, user)
            conn.commit()
            return result

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
            settings = settings_row(conn)
            if payload.mode == "accion":
                snapshot = project_snapshot(conn, project_id, AiAnalysisIn())
                if ai_settings_ready(settings):
                    try:
                        result = configured_ai_analysis(settings, snapshot, request_language(request))
                    except HTTPException as exc:
                        now = datetime.utcnow().isoformat()
                        conn.execute("UPDATE ai_settings SET status='Error', last_test_at=?, last_error=? WHERE id=?", (now, str(exc.detail), settings["id"]))
                        result = internal_rules_analysis(snapshot)
                else:
                    result = internal_rules_analysis(snapshot)
                persisted = persist_analysis(conn, project_id, user["id"], snapshot, result)
                conn.commit()
                engine = "IA real" if result.get("mode") == "configured" else "motor interno"
                return {"mode": "accion", "answer": f"Se generaron recomendaciones pendientes con {engine}. Revisa y aprueba antes de aplicar.", **persisted}
            if ai_settings_ready(settings):
                snapshot = project_snapshot(conn, project_id, AiAnalysisIn())
                prompt = f"Respond in {request_language(request)}, using only this project snapshot. Question: {payload.message}\nSnapshot: {dumps(snapshot)}"
                try:
                    answer = ai_provider_request(settings, [{"role": "user", "content": prompt}], False)
                except HTTPException as exc:
                    now = datetime.utcnow().isoformat()
                    conn.execute("UPDATE ai_settings SET status='Error', last_test_at=?, last_error=? WHERE id=?", (now, str(exc.detail), settings["id"]))
                    answer = answer_project_question(conn, project_id, payload.message)
            else:
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
    Ruta cr\u00edtica: {m['critical_path_tasks']} tareas abiertas con dependencias.
    
    Foco recomendado:
    1. Revisar tareas atrasadas y dependencias cr\u00edticas.
    2. Confirmar capacidad de recursos de QA y Desarrollo.
    3. Mantener gobierno PMP para hitos y cambios de alcance, permitiendo ejecuci\u00f3n \u00e1gil en ciclos.
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
                return "No identifico actividades vencidas abiertas frente a la fecha actual. Mant\u00e9n el seguimiento semanal y registra evidencias de avance."
            return "Actividades atrasadas detectadas:\n" + "\n".join([f"- {t['title']} | Responsable: {t['owner'] or 'sin asignar'} | Fin: {t['end_date']} | Avance: {t['progress']}%" for t in delayed])
        if "riesg" in q:
            if not high:
                return f"El proyecto tiene {m['open_risks']} riesgos abiertos, pero no hay riesgos altos abiertos. Recomendaci\u00f3n: mantener actualizaci\u00f3n de probabilidad, impacto y respuesta."
            return "Riesgos altos abiertos:\n" + "\n".join([f"- {r['title']} | Responsable: {r['owner'] or 'sin asignar'} | Respuesta: {r['response'] or 'pendiente'}" for r in high])
        if "hito" in q:
            if not milestones:
                return "No hay hitos comprometidos seg\u00fan el estado actual. Revisa pr\u00f3ximos hitos y carga evidencias de cumplimiento."
            return "Hitos comprometidos:\n" + "\n".join([f"- {h['title']} | Fecha: {h['end_date']} | Avance: {h['progress']}%" for h in milestones])
        if "presupuesto" in q or "costo" in q or "fond" in q:
            return f"Presupuesto total: {m['budget']:,.0f} {p['currency']}. Ejecutado estimado: {m['spent']:,.0f}. Saldo estimado: {m['remaining_budget']:,.0f}."
        if "entreg" in q or "producto" in q or "evidencia" in q:
            deliverables = all_rows(conn, "SELECT name, deliverable_type, status, due_date, evidence_url FROM deliverables WHERE project_id = ? ORDER BY due_date LIMIT 8", (project_id,))
            evidences = one(conn, "SELECT COUNT(*) AS total FROM evidence_files WHERE project_id = ?", (project_id,))["total"]
            yes = "s\u00ed"
            return f"El proyecto tiene {len(deliverables)} entregables/productos visibles y {evidences} evidencias cargadas.\n" + "\n".join([f"- {d['name']} | {d['deliverable_type']} | {d['status']} | Evidencia: {yes if d['evidence_url'] else 'no'}" for d in deliverables])
        return f"Estado del proyecto {p['name']}: salud {m['health']}, avance {m['progress']}%, {m['open_risks']} riesgos abiertos ({m['high_risks']} altos), {m['delayed_tasks']} actividades atrasadas y {m['critical_path_tasks']} tareas en ruta cr\u00edtica. Recomendaciones: " + "; ".join(intel.get("recommendations", []))
    
    
    @router.post("/api/ai/chat")
    def ai_chat(payload: AiChatIn) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            answer = answer_project_question(conn, payload.project_id, payload.question)
            add_history(conn, payload.project_id, "IA", "Chat del proyecto", "Consulta", payload.question[:180], payload.author or "Usuario")
            conn.commit()
            return {"answer": answer, "generated_at": datetime.utcnow().isoformat()}


    return router


