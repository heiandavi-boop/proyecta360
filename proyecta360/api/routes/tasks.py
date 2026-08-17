from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from fastapi import APIRouter

from proyecta360.schemas.api import (
    DependencyIn,
    TaskIn,
    TaskUpdate,
)


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    db = ctx.db
    get_project_or_404 = ctx.get_project_or_404
    get_task_or_404 = ctx.get_task_or_404
    iso_value = ctx.iso_value
    normalize_task_dates = ctx.normalize_task_dates
    one = ctx.one
    parse_iso = ctx.parse_iso
    recalculate_project_schedule = ctx.recalculate_project_schedule
    refresh_outline_levels = ctx.refresh_outline_levels
    task_duration_days = ctx.task_duration_days
    validate_dependency = ctx.validate_dependency
    assert_component_in_project = ctx.assert_component_in_project
    assert_task_in_project = ctx.assert_task_in_project

    def has_children(conn, task_id: int) -> bool:
        return bool(one(conn, "SELECT id FROM tasks WHERE parent_id = ? LIMIT 1", (task_id,)))

    @router.post("/api/tasks")
    def create_task(payload: TaskIn) -> Dict[str, Any]:
        with db() as conn:
            if payload.parent_id:
                parent = assert_task_in_project(conn, payload.parent_id, payload.project_id, "La tarea padre")
                if parent["id"] == payload.predecessor_id:
                    raise HTTPException(status_code=400, detail="La tarea padre no puede ser tambi\u00e9n dependencia inicial")
            if payload.predecessor_id:
                assert_task_in_project(conn, payload.predecessor_id, payload.project_id, "La tarea predecesora")
            if payload.component_id:
                assert_component_in_project(conn, payload.component_id, payload.project_id)
            if payload.start_date is None:
                project = get_project_or_404(conn, payload.project_id)
                payload.start_date = parse_iso(project["start_date"])
            start_s, end_s, duration = normalize_task_dates(payload.start_date, payload.end_date, payload.duration_days, payload.task_type)
            if payload.order_index <= 0:
                row = one(conn, "SELECT COALESCE(MAX(order_index), 0) + 1 AS next_order FROM tasks WHERE project_id = ?", (payload.project_id,))
                payload.order_index = int(row["next_order"] or 1)
            cur = conn.execute(
                """INSERT INTO tasks (project_id, parent_id, component_id, title, phase, task_type, start_date, end_date, duration_days, progress, owner, status, story_points, budget, description, order_index, outline_level, is_expanded)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload.project_id, payload.parent_id, payload.component_id, payload.title, payload.phase, payload.task_type, start_s, end_s, duration, payload.progress, payload.owner, payload.status, payload.story_points, payload.budget, payload.description, payload.order_index, payload.outline_level, payload.is_expanded),
            )
            new_id = int(cur.lastrowid)
            if payload.parent_id:
                conn.execute("UPDATE tasks SET task_type = 'summary' WHERE id = ?", (payload.parent_id,))
            if payload.predecessor_id:
                validate_dependency(conn, payload.project_id, payload.predecessor_id, new_id)
                conn.execute(
                    "INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type, lag_days) VALUES (?, ?, ?, ?, ?)",
                    (payload.project_id, payload.predecessor_id, new_id, payload.dependency_type, payload.lag_days),
                )
            refresh_outline_levels(conn, payload.project_id)
            recalculate_project_schedule(conn, payload.project_id)
            add_history(conn, payload.project_id, "Actividad", payload.title, "Creada", f"Duracion: {duration} dias. Fecha fin calculada por cronograma.")
            conn.commit()
            return one(conn, "SELECT * FROM tasks WHERE id = ?", (new_id,))
    
    
    @router.put("/api/tasks/{task_id}")
    def update_task(task_id: int, payload: TaskUpdate) -> Dict[str, Any]:
        with db() as conn:
            task = get_task_or_404(conn, task_id)
            data = payload.model_dump(exclude_unset=True)
            if data.get("component_id"):
                assert_component_in_project(conn, data["component_id"], task["project_id"])
            if data.get("parent_id"):
                if int(data["parent_id"]) == task_id:
                    raise HTTPException(status_code=400, detail="Una tarea no puede ser padre de s\u00ed misma")
                assert_task_in_project(conn, int(data["parent_id"]), task["project_id"], "La tarea padre")
            next_type = data.get("task_type", task["task_type"])
            if has_children(conn, task_id):
                for calculated_field in ("start_date", "end_date", "duration_days", "progress"):
                    data.pop(calculated_field, None)
                data["task_type"] = "summary"
                next_type = "summary"
            start_value = data.get("start_date", parse_iso(task["start_date"]))
            end_value = data.get("end_date", parse_iso(task["end_date"])) if data.get("end_date") is not None else None
            duration_value = data.get("duration_days", task.get("duration_days") if task.get("duration_days") is not None else task_duration_days(task["start_date"], task["end_date"], next_type))
            if any(k in data for k in ("start_date", "end_date", "duration_days", "task_type")):
                start_s, end_s, duration = normalize_task_dates(start_value, end_value, duration_value, next_type)
                data["start_date"] = start_s
                data["end_date"] = end_s
                data["duration_days"] = duration
            fields, args = [], []
            for k, v in data.items():
                fields.append(f"{k} = ?")
                args.append(iso_value(v))
            if fields:
                args.append(task_id)
                conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", tuple(args))
                refresh_outline_levels(conn, task["project_id"])
                recalculate_project_schedule(conn, task["project_id"])
                add_history(conn, task["project_id"], "Actividad", data.get("title", task["title"]), "Actualizada", "Cronograma recalculado.")
                conn.commit()
            return one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    
    
    @router.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int) -> Dict[str, str]:
        with db() as conn:
            task = get_task_or_404(conn, task_id)
            conn.execute("UPDATE tasks SET parent_id = NULL WHERE parent_id = ?", (task_id,))
            conn.execute("DELETE FROM dependencies WHERE predecessor_id = ? OR successor_id = ?", (task_id, task_id))
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            refresh_outline_levels(conn, task["project_id"])
            recalculate_project_schedule(conn, task["project_id"])
            conn.commit()
            return {"message": "Tarea eliminada"}
    
    
    @router.post("/api/tasks/{task_id}/indent")
    def indent_task(task_id: int) -> Dict[str, Any]:
        with db() as conn:
            task = get_task_or_404(conn, task_id)
            previous = one(conn, "SELECT * FROM tasks WHERE project_id = ? AND order_index < ? ORDER BY order_index DESC, id DESC LIMIT 1", (task["project_id"], task["order_index"]))
            if not previous:
                raise HTTPException(status_code=400, detail="No hay tarea anterior para aplicar sangr\u00eda")
            conn.execute("UPDATE tasks SET parent_id = ? WHERE id = ?", (previous["id"], task_id))
            conn.execute("UPDATE tasks SET task_type = 'summary' WHERE id = ?", (previous["id"],))
            refresh_outline_levels(conn, task["project_id"])
            recalculate_project_schedule(conn, task["project_id"])
            conn.commit()
            return one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    
    
    @router.post("/api/tasks/{task_id}/outdent")
    def outdent_task(task_id: int) -> Dict[str, Any]:
        with db() as conn:
            task = get_task_or_404(conn, task_id)
            if not task.get("parent_id"):
                raise HTTPException(status_code=400, detail="La tarea ya est\u00e1 en el nivel principal")
            parent = get_task_or_404(conn, int(task["parent_id"]))
            conn.execute("UPDATE tasks SET parent_id = ? WHERE id = ?", (parent.get("parent_id"), task_id))
            refresh_outline_levels(conn, task["project_id"])
            recalculate_project_schedule(conn, task["project_id"])
            conn.commit()
            return one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    
    
    @router.post("/api/tasks/{task_id}/toggle")
    def toggle_task(task_id: int) -> Dict[str, Any]:
        with db() as conn:
            task = get_task_or_404(conn, task_id)
            current = task.get("is_expanded")
            current_value = 1 if current is None else int(current)
            new_value = 0 if current_value else 1
            conn.execute("UPDATE tasks SET is_expanded = ? WHERE id = ?", (new_value, task_id))
            conn.commit()
            return one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    
    
    @router.post("/api/dependencies")
    def create_dependency(payload: DependencyIn) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, payload.project_id)
            validate_dependency(conn, payload.project_id, payload.predecessor_id, payload.successor_id)
            existing = one(conn, "SELECT * FROM dependencies WHERE project_id = ? AND predecessor_id = ? AND successor_id = ?", (payload.project_id, payload.predecessor_id, payload.successor_id))
            if existing:
                conn.execute("UPDATE dependencies SET dependency_type = ?, lag_days = ? WHERE id = ?", (payload.dependency_type, payload.lag_days, existing["id"]))
                recalculate_project_schedule(conn, payload.project_id)
                conn.commit()
                return one(conn, "SELECT * FROM dependencies WHERE id = ?", (existing["id"],))
            cur = conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type, lag_days) VALUES (?, ?, ?, ?, ?)", (payload.project_id, payload.predecessor_id, payload.successor_id, payload.dependency_type, payload.lag_days))
            recalculate_project_schedule(conn, payload.project_id)
            conn.commit()
            return one(conn, "SELECT * FROM dependencies WHERE id = ?", (cur.lastrowid,))
    
    
    @router.delete("/api/dependencies/{dependency_id}")
    def delete_dependency(dependency_id: int) -> Dict[str, str]:
        with db() as conn:
            dep = one(conn, "SELECT * FROM dependencies WHERE id = ?", (dependency_id,))
            if not dep:
                raise HTTPException(status_code=404, detail="Dependencia no encontrada")
            conn.execute("DELETE FROM dependencies WHERE id = ?", (dependency_id,))
            recalculate_project_schedule(conn, int(dep["project_id"]))
            conn.commit()
            return {"message": "Dependencia eliminada"}
    

    return router


