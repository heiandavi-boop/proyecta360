import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.db import get_db, iso_value, one
from app.schemas import SprintIn
from app.services.graph import get_project_or_404

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


@router.post("")
def create_sprint(payload: SprintIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    get_project_or_404(conn, payload.project_id)
    cur = conn.execute(
        "INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (payload.project_id, payload.name, payload.goal, iso_value(payload.start_date), iso_value(payload.end_date), payload.status, payload.velocity),
    )
    conn.commit()
    return one(conn, "SELECT * FROM sprints WHERE id = ?", (cur.lastrowid,))
