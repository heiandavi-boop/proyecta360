import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db, one
from app.schemas import STORY_UPDATE_COLUMNS, StoryIn, StoryUpdate
from app.services.graph import get_project_or_404

router = APIRouter(prefix="/api/stories", tags=["stories"])


@router.post("")
def create_story(payload: StoryIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    get_project_or_404(conn, payload.project_id)
    if payload.sprint_id:
        sprint = one(conn, "SELECT project_id FROM sprints WHERE id = ?", (payload.sprint_id,))
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint no encontrado")
        if sprint["project_id"] != payload.project_id:
            raise HTTPException(status_code=400, detail="El sprint no pertenece al proyecto")
    cur = conn.execute(
        "INSERT INTO stories (project_id, sprint_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (payload.project_id, payload.sprint_id, payload.title, payload.status, payload.points, payload.assignee, payload.priority),
    )
    conn.commit()
    return one(conn, "SELECT * FROM stories WHERE id = ?", (cur.lastrowid,))


@router.put("/{story_id}")
def update_story(story_id: int, payload: StoryUpdate, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    story = one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))
    if not story:
        raise HTTPException(status_code=404, detail="Historia no encontrada")
    data = payload.model_dump(exclude_unset=True)
    project_id = data.get("project_id", story["project_id"])
    if "project_id" in data:
        get_project_or_404(conn, project_id)
    if data.get("sprint_id"):
        sprint = one(conn, "SELECT project_id FROM sprints WHERE id = ?", (data["sprint_id"],))
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint no encontrado")
        if sprint["project_id"] != project_id:
            raise HTTPException(status_code=400, detail="El sprint no pertenece al proyecto")
    fields, args = [], []
    for k, v in data.items():
        if k not in STORY_UPDATE_COLUMNS:
            raise HTTPException(status_code=400, detail=f"Campo no actualizable: {k}")
        fields.append(f"{k} = ?")
        args.append(v)
    if fields:
        args.append(story_id)
        conn.execute(f"UPDATE stories SET {', '.join(fields)} WHERE id = ?", tuple(args))
        conn.commit()
    return one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))
