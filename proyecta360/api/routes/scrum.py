from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
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
    @router.post("/api/sprints")
    def create_sprint(payload: SprintIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (payload.project_id, payload.name, payload.goal, iso_value(payload.start_date), iso_value(payload.end_date), payload.status, payload.velocity))
            conn.commit()
            return one(conn, "SELECT * FROM sprints WHERE id = ?", (cur.lastrowid,))
    
    
    @router.post("/api/stories")
    def create_story(payload: StoryIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            if payload.sprint_id:
                sprint = one(conn, "SELECT project_id FROM sprints WHERE id = ?", (payload.sprint_id,))
                if not sprint:
                    raise HTTPException(status_code=404, detail="Sprint no encontrado")
                if sprint["project_id"] != payload.project_id:
                    raise HTTPException(status_code=400, detail="El sprint no pertenece al proyecto")
            cur = conn.execute("INSERT INTO stories (project_id, sprint_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?)", (payload.project_id, payload.sprint_id, payload.title, payload.status, payload.points, payload.assignee, payload.priority))
            conn.commit()
            return one(conn, "SELECT * FROM stories WHERE id = ?", (cur.lastrowid,))
    
    
    @router.put("/api/stories/{story_id}")
    def update_story(story_id: int, payload: StoryIn) -> Dict[str, Any]:
        with db() as conn:
            if not one(conn, "SELECT id FROM stories WHERE id = ?", (story_id,)):
                raise HTTPException(status_code=404, detail="Historia no encontrada")
            get_project_or_404(conn, payload.project_id)
            if payload.sprint_id:
                sprint = one(conn, "SELECT project_id FROM sprints WHERE id = ?", (payload.sprint_id,))
                if not sprint:
                    raise HTTPException(status_code=404, detail="Sprint no encontrado")
                if sprint["project_id"] != payload.project_id:
                    raise HTTPException(status_code=400, detail="El sprint no pertenece al proyecto")
            conn.execute("UPDATE stories SET project_id=?, sprint_id=?, title=?, status=?, points=?, assignee=?, priority=? WHERE id=?", (payload.project_id, payload.sprint_id, payload.title, payload.status, payload.points, payload.assignee, payload.priority, story_id))
            conn.commit()
            return one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))
    

    return router


