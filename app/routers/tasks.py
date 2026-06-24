import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db, iso_value, one
from app.schemas import TASK_UPDATE_COLUMNS, TaskIn, TaskUpdate
from app.services.graph import assert_task_in_project, get_project_or_404, get_task_or_404

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
def create_task(payload: TaskIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    get_project_or_404(conn, payload.project_id)
    if payload.parent_id:
        parent = assert_task_in_project(conn, payload.parent_id, payload.project_id, "La tarea padre")
        if parent["id"] == payload.parent_id and parent["id"] == payload.predecessor_id:
            raise HTTPException(status_code=400, detail="La tarea padre no puede ser también dependencia inicial")
    if payload.predecessor_id:
        assert_task_in_project(conn, payload.predecessor_id, payload.project_id, "La tarea predecesora")
    cur = conn.execute(
        """INSERT INTO tasks (project_id, parent_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, description, order_index)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (payload.project_id, payload.parent_id, payload.title, payload.phase, payload.task_type, iso_value(payload.start_date), iso_value(payload.end_date), payload.progress, payload.owner, payload.status, payload.story_points, payload.budget, payload.description, payload.order_index),
    )
    if payload.predecessor_id:
        conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", (payload.project_id, payload.predecessor_id, cur.lastrowid))
    conn.commit()
    return one(conn, "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,))


@router.put("/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    get_task_or_404(conn, task_id)
    data = payload.model_dump(exclude_unset=True)
    fields, args = [], []
    for k, v in data.items():
        if k not in TASK_UPDATE_COLUMNS:
            raise HTTPException(status_code=400, detail=f"Campo no actualizable: {k}")
        fields.append(f"{k} = ?")
        args.append(iso_value(v))
    if fields:
        args.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", tuple(args))
        t = one(conn, "SELECT start_date, end_date FROM tasks WHERE id = ?", (task_id,))
        if t and t["end_date"] < t["start_date"]:
            raise HTTPException(status_code=400, detail="La fecha fin no puede ser menor a la fecha inicio")
        conn.commit()
    return one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))


@router.delete("/{task_id}")
def delete_task(task_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, str]:
    get_task_or_404(conn, task_id)
    conn.execute("DELETE FROM dependencies WHERE predecessor_id = ? OR successor_id = ?", (task_id, task_id))
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return {"message": "Tarea eliminada"}
