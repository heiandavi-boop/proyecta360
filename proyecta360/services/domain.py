from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from fastapi import HTTPException

from proyecta360.core.config import DEFAULT_PARAMETERS
from proyecta360.core.database import all_rows, loads, one

PROJECT_PROFILE_RESPONSE_FIELDS = ["project_code", "requesting_area", "project_type", "priority", "responsible_team"]
PROJECT_CONTEXT_RESPONSE_FIELDS = [
    "problem_statement", "current_situation", "consequence_if_not_done", "general_objective",
    "specific_objectives", "objective_indicators", "scope_included", "scope_excluded",
    "success_criteria", "assumptions", "constraints", "project_context", "political_context",
    "geographic_context", "socioeconomic_context", "cultural_context", "institutional_context",
    "stakeholders", "stakeholders_context", "external_dependencies", "regulatory_constraints",
]


def serialize_project(p: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(p)
    params = loads(out.pop("parameters_json", "{}"), DEFAULT_PARAMETERS)
    params = params if isinstance(params, dict) else {}
    out["parameters"] = params
    profile = params.get("project_profile") or {}
    strategic = params.get("strategic_framework") or {}
    for key in PROJECT_PROFILE_RESPONSE_FIELDS:
        out[key] = profile.get(key, "")
    for key in PROJECT_CONTEXT_RESPONSE_FIELDS:
        out[key] = strategic.get(key, "")
    out["ai_context"] = {
        "problem_statement": strategic.get("problem_statement") or strategic.get("main_gap", ""),
        "current_situation": strategic.get("current_situation", ""),
        "consequence_if_not_done": strategic.get("consequence_if_not_done", ""),
        "general_objective": strategic.get("general_objective", ""),
        "specific_objectives": strategic.get("specific_objectives", ""),
        "objective_indicators": strategic.get("objective_indicators", ""),
        "scope_included": strategic.get("scope_included", ""),
        "scope_excluded": strategic.get("scope_excluded", ""),
        "success_criteria": strategic.get("success_criteria", ""),
        "context": strategic.get("project_context", ""),
        "stakeholders": strategic.get("stakeholders") or strategic.get("stakeholders_context", ""),
        "constraints": strategic.get("constraints", ""),
        "external_dependencies": strategic.get("external_dependencies", ""),
        "regulatory_constraints": strategic.get("regulatory_constraints", ""),
    }
    return out


def serialize_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(evidence)
    out.pop("file_path", None)
    out.pop("stored_filename", None)
    out["download_url"] = f"/api/evidences/{out['id']}/download"
    return out


def risk_level(probability: int, impact: int, parameters: Optional[Dict[str, Any]] = None) -> str:
    params = parameters or DEFAULT_PARAMETERS
    score = probability * impact
    high = params.get("risk_matrix", {}).get("high_threshold", 15)
    medium = params.get("risk_matrix", {}).get("medium_threshold", 8)
    if score >= high:
        return "Alto"
    if score >= medium:
        return "Medio"
    return "Bajo"


def serialize_risk(r: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(r)
    out["score"] = int(out.get("probability") or 0) * int(out.get("impact") or 0)
    return out


def get_project_or_404(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    p = one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return p


def get_task_or_404(conn: sqlite3.Connection, task_id: int) -> Dict[str, Any]:
    task = one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return task


def assert_task_in_project(conn: sqlite3.Connection, task_id: int, project_id: int, label: str = "Tarea") -> Dict[str, Any]:
    task = get_task_or_404(conn, task_id)
    if task["project_id"] != project_id:
        raise HTTPException(status_code=400, detail=f"{label} no pertenece al proyecto")
    return task


def dependency_creates_cycle(conn: sqlite3.Connection, project_id: int, predecessor_id: int, successor_id: int) -> bool:
    stack = [successor_id]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if current == predecessor_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        rows = all_rows(conn, "SELECT successor_id FROM dependencies WHERE project_id = ? AND predecessor_id = ?", (project_id, current))
        stack.extend(int(r["successor_id"]) for r in rows)
    return False


def validate_dependency(conn: sqlite3.Connection, project_id: int, predecessor_id: int, successor_id: int) -> None:
    if predecessor_id == successor_id:
        raise HTTPException(status_code=400, detail="Una tarea no puede depender de si misma")
    assert_task_in_project(conn, predecessor_id, project_id, "La tarea predecesora")
    assert_task_in_project(conn, successor_id, project_id, "La tarea sucesora")
    if dependency_creates_cycle(conn, project_id, predecessor_id, successor_id):
        raise HTTPException(status_code=400, detail="La dependencia genera un ciclo")


def assert_component_in_project(conn: sqlite3.Connection, component_id: int, project_id: int) -> Dict[str, Any]:
    component = one(conn, "SELECT * FROM components WHERE id = ?", (component_id,))
    if not component:
        raise HTTPException(status_code=404, detail="Componente no encontrado")
    if component["project_id"] != project_id:
        raise HTTPException(status_code=400, detail="El componente no pertenece al proyecto")
    return component


def add_history(conn: sqlite3.Connection, project_id: int, entity_type: str, entity_name: str, action: str, notes: str = "", actor: str = "Sistema") -> None:
    conn.execute(
        "INSERT INTO change_log (project_id, entity_type, entity_name, action, notes, actor) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, entity_type, entity_name, action, notes, actor),
    )


def get_thread_or_404(conn: sqlite3.Connection, thread_id: int) -> Dict[str, Any]:
    thread = one(conn, "SELECT * FROM conversation_threads WHERE id = ?", (thread_id,))
    if not thread:
        raise HTTPException(status_code=404, detail="Conversacion no encontrada")
    return thread
