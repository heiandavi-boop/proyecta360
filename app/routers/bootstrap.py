import sqlite3
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.db import get_db
from app.seed import seed_database
from app.services.bootstrap import bootstrap_payload

router = APIRouter(tags=["bootstrap"])


@router.get("/api/bootstrap")
def bootstrap(project_id: Optional[int] = None, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    return bootstrap_payload(conn, project_id)


@router.post("/api/seed")
def seed(conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, str]:
    seed_database(conn)
    return {"message": "Datos base cargados"}
