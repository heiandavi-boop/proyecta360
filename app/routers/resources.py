import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.db import get_db, one
from app.schemas import ResourceIn
from app.services.graph import get_project_or_404

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.post("")
def create_resource(payload: ResourceIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    get_project_or_404(conn, payload.project_id)
    cur = conn.execute(
        "INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)",
        (payload.project_id, payload.name, payload.role, payload.email, payload.capacity),
    )
    conn.commit()
    return one(conn, "SELECT * FROM resources WHERE id = ?", (cur.lastrowid,))
