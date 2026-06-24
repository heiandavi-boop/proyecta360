import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db, one
from app.schemas import DependencyIn
from app.services.graph import get_project_or_404, validate_dependency

router = APIRouter(prefix="/api/dependencies", tags=["dependencies"])


@router.post("")
def create_dependency(payload: DependencyIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    get_project_or_404(conn, payload.project_id)
    validate_dependency(conn, payload.project_id, payload.predecessor_id, payload.successor_id)
    existing = one(conn, "SELECT * FROM dependencies WHERE project_id = ? AND predecessor_id = ? AND successor_id = ?", (payload.project_id, payload.predecessor_id, payload.successor_id))
    if existing:
        return existing
    cur = conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, ?)", (payload.project_id, payload.predecessor_id, payload.successor_id, payload.dependency_type))
    conn.commit()
    return one(conn, "SELECT * FROM dependencies WHERE id = ?", (cur.lastrowid,))


@router.delete("/{dependency_id}")
def delete_dependency(dependency_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, str]:
    cur = conn.execute("DELETE FROM dependencies WHERE id = ?", (dependency_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Dependencia no encontrada")
    conn.commit()
    return {"message": "Dependencia eliminada"}
