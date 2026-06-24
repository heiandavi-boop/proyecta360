"""Entity lookups (404 helpers) and dependency-graph validation.

These raise HTTPException directly so routers stay thin. Cycle detection runs
in application code (the DB does not enforce it).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict

from fastapi import HTTPException

from app.db import all_rows, one


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
        raise HTTPException(status_code=400, detail="Una tarea no puede depender de sí misma")
    assert_task_in_project(conn, predecessor_id, project_id, "La tarea predecesora")
    assert_task_in_project(conn, successor_id, project_id, "La tarea sucesora")
    if dependency_creates_cycle(conn, project_id, predecessor_id, successor_id):
        raise HTTPException(status_code=400, detail="La dependencia genera un ciclo")
