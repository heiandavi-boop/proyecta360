from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from fastapi import APIRouter

from proyecta360.schemas.api import (
    ComponentIn,
    ConversationMessageIn,
    ConversationThreadIn,
    DeliverableIn,
    ResourceIn,
    RiskIn,
)


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    context_label = ctx.context_label
    db = ctx.db
    DEFAULT_PARAMETERS = ctx.DEFAULT_PARAMETERS
    get_project_or_404 = ctx.get_project_or_404
    get_thread_or_404 = ctx.get_thread_or_404
    iso_value = ctx.iso_value
    loads = ctx.loads
    one = ctx.one
    risk_level = ctx.risk_level
    serialize_risk = ctx.serialize_risk
    assert_component_in_project = ctx.assert_component_in_project
    @router.post("/api/risks")
    def create_risk(payload: RiskIn) -> Dict[str, Any]:
        with db() as conn:
            p = get_project_or_404(conn, payload.project_id)
            params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
            level = risk_level(payload.probability, payload.impact, params)
            cur = conn.execute(
                """INSERT INTO risks (project_id, title, probability, impact, level, response, mitigation_plan, contingency_plan, status, owner, materialized_date, actual_impact, observations)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    payload.project_id, payload.title, payload.probability, payload.impact, level, payload.response,
                    payload.mitigation_plan, payload.contingency_plan, payload.status, payload.owner,
                    iso_value(payload.materialized_date) if payload.materialized_date else "", payload.actual_impact, payload.observations,
                ),
            )
            add_history(conn, payload.project_id, "Riesgo", payload.title, "Creado", f"Nivel: {level}. Mitigacion y contingencia registradas.")
            conn.commit()
            return serialize_risk(one(conn, "SELECT * FROM risks WHERE id = ?", (cur.lastrowid,)))
    
    
    @router.post("/api/resources")
    def create_resource(payload: ResourceIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            cur = conn.execute("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", (payload.project_id, payload.name, payload.role, payload.email, payload.capacity))
            add_history(conn, payload.project_id, "Recurso", payload.name, "Creado", payload.role)
            conn.commit()
            return one(conn, "SELECT * FROM resources WHERE id = ?", (cur.lastrowid,))
    
    
    @router.post("/api/components")
    def create_component(payload: ComponentIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            cur = conn.execute(
                "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
                (payload.project_id, payload.name, payload.methodology, payload.owner, payload.objective, payload.progress),
            )
            add_history(conn, payload.project_id, "Componente", payload.name, "Creado", payload.methodology)
            conn.commit()
            return one(conn, "SELECT * FROM components WHERE id = ?", (cur.lastrowid,))
    
    
    @router.post("/api/deliverables")
    def create_deliverable(payload: DeliverableIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            if payload.component_id:
                assert_component_in_project(conn, payload.component_id, payload.project_id)
            cur = conn.execute(
                """INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, owner, due_date, evidence_url, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload.project_id, payload.component_id, payload.name, payload.deliverable_type, payload.status, payload.owner, iso_value(payload.due_date) if payload.due_date else "", payload.evidence_url, payload.description),
            )
            add_history(conn, payload.project_id, payload.deliverable_type, payload.name, "Creado", payload.description)
            conn.commit()
            return one(conn, "SELECT * FROM deliverables WHERE id = ?", (cur.lastrowid,))
    
    
    @router.post("/api/conversations")
    def create_conversation(payload: ConversationThreadIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            label = context_label(conn, payload.context_type, payload.context_id)
            cur = conn.execute(
                """INSERT INTO conversation_threads (project_id, title, context_type, context_id, category, status, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload.project_id, payload.title, payload.context_type, payload.context_id, payload.category, payload.status, payload.created_by),
            )
            add_history(conn, payload.project_id, "Conversacion", payload.title, "Creada", f"{payload.category} en {label}", payload.created_by or "Sistema")
            conn.commit()
            return one(conn, "SELECT * FROM conversation_threads WHERE id = ?", (cur.lastrowid,))
    
    
    @router.post("/api/conversations/{thread_id}/messages")
    def create_conversation_message(thread_id: int, payload: ConversationMessageIn) -> Dict[str, Any]:
        with db() as conn:
            thread = get_thread_or_404(conn, thread_id)
            if payload.thread_id != thread_id:
                raise HTTPException(status_code=400, detail="El hilo de la ruta no coincide con el mensaje")
            if thread["project_id"] != payload.project_id:
                raise HTTPException(status_code=400, detail="La conversacion no pertenece al proyecto")
            cur = conn.execute(
                """INSERT INTO conversation_messages (thread_id, project_id, author, message, mentions, evidence_url, message_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (thread_id, payload.project_id, payload.author, payload.message, payload.mentions, payload.evidence_url, payload.message_type),
            )
            if payload.message_type in {"Decision", "Bloqueo", "Acuerdo"}:
                add_history(conn, payload.project_id, "Conversacion", thread["title"], payload.message_type, payload.message[:180], payload.author or "Equipo")
            conn.commit()
            return one(conn, "SELECT * FROM conversation_messages WHERE id = ?", (cur.lastrowid,))
    

    return router


