from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Header
from fastapi import APIRouter

from proyecta360.schemas.api import (
    AiChatIn,
    AiPlanIn,
    AiReportIn,
    AuthLoginIn,
    ComponentIn,
    ConversationMessageIn,
    ConversationThreadIn,
    DeliverableIn,
    DependencyIn,
    ProjectIn,
    ProjectUpdate,
    ResourceIn,
    RiskIn,
    SprintIn,
    StoryIn,
    TaskIn,
    TaskUpdate,
)


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    all_rows = ctx.all_rows
    bootstrap_payload = ctx.bootstrap_payload
    calculate_metrics = ctx.calculate_metrics
    context_label = ctx.context_label
    db = ctx.db
    deep_merge = ctx.deep_merge
    DEFAULT_PARAMETERS = ctx.DEFAULT_PARAMETERS
    dumps = ctx.dumps
    get_project_or_404 = ctx.get_project_or_404
    get_task_or_404 = ctx.get_task_or_404
    get_thread_or_404 = ctx.get_thread_or_404
    hash_password = ctx.hash_password
    init_db = ctx.init_db
    iso_value = ctx.iso_value
    loads = ctx.loads
    MAX_UPLOAD_BYTES = ctx.MAX_UPLOAD_BYTES
    normalize_task_dates = ctx.normalize_task_dates
    one = ctx.one
    parse_iso = ctx.parse_iso
    portfolio_summary = ctx.portfolio_summary
    project_intelligence = ctx.project_intelligence
    public_user = ctx.public_user
    recalculate_project_schedule = ctx.recalculate_project_schedule
    refresh_outline_levels = ctx.refresh_outline_levels
    risk_level = ctx.risk_level
    safe_filename = ctx.safe_filename
    seed_database = ctx.seed_database
    serialize_project = ctx.serialize_project
    serialize_risk = ctx.serialize_risk
    task_duration_days = ctx.task_duration_days
    UPLOAD_DIR = ctx.UPLOAD_DIR
    user_from_authorization = ctx.user_from_authorization
    validate_dependency = ctx.validate_dependency
    assert_component_in_project = ctx.assert_component_in_project
    assert_task_in_project = ctx.assert_task_in_project
    @router.get("/api/portfolio")
    def get_portfolio() -> Dict[str, Any]:
        init_db()
        with db() as conn:
            return {"projects": portfolio_summary(conn)}
    
    
    @router.get("/api/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "app": "Proyecta360", "time": datetime.utcnow().isoformat()}
    
    
    @router.get("/api/bootstrap")
    def bootstrap(project_id: Optional[int] = None, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            payload = bootstrap_payload(conn, project_id)
            payload["current_user"] = public_user(user_from_authorization(conn, authorization))
            return payload
    
    
    @router.post("/api/seed")
    def seed() -> Dict[str, str]:
        init_db()
        with db() as conn:
            seed_database(conn)
        return {"message": "Datos base cargados"}

    return router


