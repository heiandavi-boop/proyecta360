from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import HTTPException
from fastapi import APIRouter

from proyecta360.schemas.api import (
    AgileCycleIn,
    SprintIn,
    StoryIn,
    WorkItemIn,
)


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    all_rows = ctx.all_rows
    assert_task_in_project = ctx.assert_task_in_project
    db = ctx.db
    dumps = ctx.dumps
    add_history = ctx.add_history
    get_project_or_404 = ctx.get_project_or_404
    iso_value = ctx.iso_value
    one = ctx.one

    def validate_story_links(conn, payload: StoryIn) -> None:
        if payload.sprint_id:
            sprint = one(conn, "SELECT project_id FROM sprints WHERE id = ?", (payload.sprint_id,))
            if not sprint:
                raise HTTPException(status_code=404, detail="Sprint no encontrado")
            if sprint["project_id"] != payload.project_id:
                raise HTTPException(status_code=400, detail="El sprint no pertenece al proyecto")
        if payload.master_task_id:
            assert_task_in_project(conn, payload.master_task_id, payload.project_id, "La tarea del Plan Maestro")
        if payload.component_id:
            component = one(conn, "SELECT project_id FROM components WHERE id = ?", (payload.component_id,))
            if not component:
                raise HTTPException(status_code=404, detail="Componente no encontrado")
            if component["project_id"] != payload.project_id:
                raise HTTPException(status_code=400, detail="El componente no pertenece al proyecto")
        if payload.deliverable_id:
            deliverable = one(conn, "SELECT project_id FROM deliverables WHERE id = ?", (payload.deliverable_id,))
            if not deliverable:
                raise HTTPException(status_code=404, detail="Entregable no encontrado")
            if deliverable["project_id"] != payload.project_id:
                raise HTTPException(status_code=400, detail="El entregable no pertenece al proyecto")

    def status_timestamp(status: str, current: str = "") -> str:
        normalized = (status or "").strip().lower()
        if current:
            return current
        if normalized in {"hecho", "done", "completado", "cerrado"}:
            return datetime.utcnow().isoformat()
        return ""

    def create_cycle_record(conn, payload: SprintIn) -> Dict[str, Any]:
        get_project_or_404(conn, payload.project_id)
        cur = conn.execute(
            """INSERT INTO sprints
               (project_id, name, goal, start_date, end_date, status, velocity, cycle_type, capacity, close_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.project_id,
                payload.name,
                payload.goal,
                iso_value(payload.start_date),
                iso_value(payload.end_date),
                payload.status,
                payload.velocity,
                payload.cycle_type,
                payload.capacity,
                payload.close_summary,
            ),
        )
        conn.commit()
        cycle = one(conn, "SELECT * FROM sprints WHERE id = ?", (cur.lastrowid,))
        add_history(conn, payload.project_id, "Trabajo Agil", payload.name, "Ciclo creado", payload.goal)
        return cycle

    def create_work_item_record(conn, payload: StoryIn) -> Dict[str, Any]:
        get_project_or_404(conn, payload.project_id)
        validate_story_links(conn, payload)
        completed_at = status_timestamp(payload.status, payload.completed_at)
        cur = conn.execute(
            """INSERT INTO stories
               (project_id, sprint_id, master_task_id, component_id, deliverable_id, title, description, work_type,
                status, points, assignee, priority, blocked_reason, started_at, completed_at, labels_json, board_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.project_id,
                payload.sprint_id,
                payload.master_task_id,
                payload.component_id,
                payload.deliverable_id,
                payload.title,
                payload.description,
                payload.work_type,
                payload.status,
                payload.points,
                payload.assignee,
                payload.priority,
                payload.blocked_reason,
                payload.started_at,
                completed_at,
                dumps(payload.labels),
                payload.board_order,
            ),
        )
        conn.commit()
        item = one(conn, "SELECT * FROM stories WHERE id = ?", (cur.lastrowid,))
        add_history(conn, payload.project_id, "Trabajo Agil", payload.title, "Item creado", payload.work_type)
        return item

    def scrum_summary(conn, project_id: int, task_id: int) -> Dict[str, Any]:
        get_project_or_404(conn, project_id)
        assert_task_in_project(conn, task_id, project_id, "La tarea del Plan Maestro")
        stories = all_rows(
            conn,
            """SELECT st.*, sp.name AS sprint_name, sp.status AS sprint_status
               FROM stories st
               LEFT JOIN sprints sp ON sp.id = st.sprint_id
               WHERE st.project_id = ? AND st.master_task_id = ?
               ORDER BY st.id""",
            (project_id, task_id),
        )
        total = len(stories)
        done = [s for s in stories if str(s.get("status") or "").lower() in {"hecho", "done", "completado", "cerrado"}]
        in_progress = [s for s in stories if "progreso" in str(s.get("status") or "").lower() or str(s.get("status") or "").lower() == "in progress"]
        points_total = sum(int(s.get("points") or 0) for s in stories)
        points_done = sum(int(s.get("points") or 0) for s in done)
        if points_total:
            progress = round(points_done / points_total * 100)
        else:
            progress = round(len(done) / total * 100) if total else 0
        sprints = []
        seen = set()
        for story in stories:
            sprint_id = story.get("sprint_id")
            if sprint_id and sprint_id not in seen:
                seen.add(sprint_id)
                sprints.append({"id": sprint_id, "name": story.get("sprint_name") or "", "status": story.get("sprint_status") or ""})
        return {
            "task_id": task_id,
            "stories": stories,
            "stories_total": total,
            "stories_done": len(done),
            "stories_in_progress": len(in_progress),
            "stories_pending": max(0, total - len(done) - len(in_progress)),
            "points_total": points_total,
            "points_done": points_done,
            "scrum_progress": progress,
            "sprints": sprints,
        }

    @router.post("/api/sprints")
    def create_sprint(payload: SprintIn) -> Dict[str, Any]:
        with db() as conn:
            return create_cycle_record(conn, payload)

    @router.post("/api/agile-cycles")
    def create_agile_cycle(payload: AgileCycleIn) -> Dict[str, Any]:
        with db() as conn:
            return create_cycle_record(conn, payload)
    
    
    @router.post("/api/stories")
    def create_story(payload: StoryIn) -> Dict[str, Any]:
        with db() as conn:
            return create_work_item_record(conn, payload)

    @router.post("/api/work-items")
    def create_work_item(payload: WorkItemIn) -> Dict[str, Any]:
        with db() as conn:
            return create_work_item_record(conn, payload)
    
    
    @router.put("/api/stories/{story_id}")
    def update_story(story_id: int, payload: StoryIn) -> Dict[str, Any]:
        with db() as conn:
            current = one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))
            if not current:
                raise HTTPException(status_code=404, detail="Historia no encontrada")
            get_project_or_404(conn, payload.project_id)
            validate_story_links(conn, payload)
            completed_at = status_timestamp(payload.status, payload.completed_at or current.get("completed_at") or "")
            conn.execute(
                """UPDATE stories
                   SET project_id=?, sprint_id=?, master_task_id=?, component_id=?, deliverable_id=?, title=?,
                       description=?, work_type=?, status=?, points=?, assignee=?, priority=?, blocked_reason=?,
                       started_at=?, completed_at=?, labels_json=?, board_order=?
                   WHERE id=?""",
                (
                    payload.project_id,
                    payload.sprint_id,
                    payload.master_task_id,
                    payload.component_id,
                    payload.deliverable_id,
                    payload.title,
                    payload.description,
                    payload.work_type,
                    payload.status,
                    payload.points,
                    payload.assignee,
                    payload.priority,
                    payload.blocked_reason,
                    payload.started_at,
                    completed_at,
                    dumps(payload.labels),
                    payload.board_order,
                    story_id,
                ),
            )
            conn.commit()
            item = one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))
            add_history(conn, payload.project_id, "Trabajo Agil", payload.title, "Item actualizado", payload.status)
            return item

    @router.put("/api/work-items/{item_id}")
    def update_work_item(item_id: int, payload: WorkItemIn) -> Dict[str, Any]:
        return update_story(item_id, payload)

    @router.get("/api/projects/{project_id}/tasks/{task_id}/scrum-summary")
    def task_scrum_summary(project_id: int, task_id: int) -> Dict[str, Any]:
        with db() as conn:
            return scrum_summary(conn, project_id, task_id)

    @router.get("/api/projects/{project_id}/scrum/linkable-tasks")
    def linkable_tasks(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, project_id)
            return {"tasks": all_rows(conn, "SELECT id, title, status, end_date, task_type, outline_level, order_index FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))}
    

    return router


