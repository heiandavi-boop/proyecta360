import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas import AiPlanIn, AiReportIn
from app.services.ai import build_report, generate_plan

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/generate-plan")
def ai_generate_plan(payload: AiPlanIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    return generate_plan(conn, payload)


@router.post("/report")
def ai_report(payload: AiReportIn, conn: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    return build_report(conn, payload)
