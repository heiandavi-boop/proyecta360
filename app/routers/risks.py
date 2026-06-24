import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.db import get_db, loads, one
from app.schemas import RiskIn
from app.services.graph import get_project_or_404
from app.services.serializers import serialize_risk
from core.defaults import DEFAULT_PARAMETERS

router = APIRouter(prefix="/api/risks", tags=["risks"])


@router.post("")
def create_risk(payload: RiskIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    p = get_project_or_404(conn, payload.project_id)
    params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
    cur = conn.execute(
        "INSERT INTO risks (project_id, title, probability, impact, response, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (payload.project_id, payload.title, payload.probability, payload.impact, payload.response, payload.status, payload.owner),
    )
    conn.commit()
    return serialize_risk(one(conn, "SELECT * FROM risks WHERE id = ?", (cur.lastrowid,)), params)
