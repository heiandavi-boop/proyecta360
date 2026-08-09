from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from proyecta360.core.database import all_rows, iso_value
from proyecta360.services import schedule as schedule_service


def parse_iso(value: str) -> date:
    return schedule_service.parse_iso(value)


def task_duration_days(start_value: str, end_value: str, task_type: str = "task") -> int:
    return schedule_service.task_duration_days(start_value, end_value, task_type)


def end_from_duration(start_value: date | str, duration_days: int, task_type: str = "task") -> date:
    return schedule_service.end_from_duration(start_value, duration_days, task_type)


def normalize_task_dates(start_value: Any, end_value: Any, duration_days: Optional[int], task_type: str) -> tuple[str, str, int]:
    return schedule_service.normalize_task_dates(start_value, end_value, duration_days, task_type, iso_value)


def critical_path_task_ids(tasks: List[Dict[str, Any]], dependencies: List[Dict[str, Any]]) -> set[int]:
    work_tasks = {int(t["id"]): t for t in tasks if t.get("task_type") != "summary"}
    if not work_tasks or not dependencies:
        return set()
    incoming: Dict[int, List[Dict[str, Any]]] = {task_id: [] for task_id in work_tasks}
    outgoing: Dict[int, List[Dict[str, Any]]] = {task_id: [] for task_id in work_tasks}
    for dep in dependencies:
        pred = int(dep["predecessor_id"])
        succ = int(dep["successor_id"])
        if pred in work_tasks and succ in work_tasks:
            incoming[succ].append(dep)
            outgoing[pred].append(dep)

    distances = {
        task_id: max(1, int(task.get("duration_days") or task_duration_days(task["start_date"], task["end_date"], task.get("task_type") or "task")))
        for task_id, task in work_tasks.items()
    }
    previous: Dict[int, int] = {}
    ordered = sorted(work_tasks.values(), key=lambda t: (str(t.get("start_date") or ""), int(t.get("order_index") or 0), int(t["id"])))
    for task in ordered:
        pred_id = int(task["id"])
        for dep in outgoing.get(pred_id, []):
            succ_id = int(dep["successor_id"])
            succ = work_tasks[succ_id]
            duration = max(1, int(succ.get("duration_days") or task_duration_days(succ["start_date"], succ["end_date"], succ.get("task_type") or "task")))
            candidate = distances[pred_id] + duration + max(0, int(dep.get("lag_days") or 0))
            if candidate > distances.get(succ_id, 0):
                distances[succ_id] = candidate
                previous[succ_id] = pred_id

    end_candidates = [task_id for task_id in work_tasks if not outgoing.get(task_id)]
    if not end_candidates:
        end_candidates = list(work_tasks)
    current = max(end_candidates, key=lambda task_id: distances.get(task_id, 0))
    result = {current}
    while current in previous:
        current = previous[current]
        result.add(current)
    return result


def recalculate_project_schedule(conn: sqlite3.Connection, project_id: int) -> None:
    """Calcula fechas de cronograma: duracion + predecesoras + resumen por hijos."""
    rows = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
    if not rows:
        return
    tasks = {int(t["id"]): dict(t) for t in rows}
    deps = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ? ORDER BY id", (project_id,))

    for t in tasks.values():
        if t.get("task_type") == "summary":
            continue
        duration = int(t.get("duration_days") if t.get("duration_days") is not None else task_duration_days(t["start_date"], t["end_date"], t.get("task_type") or "task"))
        start_s, end_s, duration = normalize_task_dates(t.get("start_date"), t.get("end_date"), duration, t.get("task_type") or "task")
        t["start_date"], t["end_date"], t["duration_days"] = start_s, end_s, duration

    for _ in range(max(1, len(tasks) + 2)):
        changed = False
        for dep in deps:
            pred = tasks.get(int(dep["predecessor_id"]))
            succ = tasks.get(int(dep["successor_id"]))
            if not pred or not succ or succ.get("task_type") == "summary":
                continue
            dtype = (dep.get("dependency_type") or "FS").upper()
            lag = int(dep.get("lag_days") or 0)
            p_start, p_end = parse_iso(pred["start_date"]), parse_iso(pred["end_date"])
            s_start, s_end = parse_iso(succ["start_date"]), parse_iso(succ["end_date"])
            duration = int(succ.get("duration_days") or 1)
            new_start, new_end = s_start, s_end
            if dtype == "SS":
                candidate = p_start + timedelta(days=lag)
                if candidate > s_start:
                    new_start = candidate
                    new_end = end_from_duration(new_start, duration, succ.get("task_type") or "task")
            elif dtype == "FF":
                candidate_end = p_end + timedelta(days=lag)
                if candidate_end > s_end:
                    new_end = candidate_end
                    new_start = new_end if succ.get("task_type") == "milestone" else new_end - timedelta(days=max(1, duration) - 1)
            elif dtype == "SF":
                candidate_end = p_start + timedelta(days=lag)
                if candidate_end > s_end:
                    new_end = candidate_end
                    new_start = new_end if succ.get("task_type") == "milestone" else new_end - timedelta(days=max(1, duration) - 1)
            else:
                candidate = p_end + timedelta(days=lag + 1)
                if candidate > s_start:
                    new_start = candidate
                    new_end = end_from_duration(new_start, duration, succ.get("task_type") or "task")
            if new_start != s_start or new_end != s_end:
                succ["start_date"], succ["end_date"] = new_start.isoformat(), new_end.isoformat()
                changed = True
        if not changed:
            break

    children: Dict[int, List[Dict[str, Any]]] = {}
    for t in tasks.values():
        if t.get("parent_id"):
            children.setdefault(int(t["parent_id"]), []).append(t)
    for parent_id in sorted(children.keys(), reverse=True):
        parent = tasks.get(parent_id)
        if not parent:
            continue
        kids = children[parent_id]
        min_start = min(parse_iso(k["start_date"]) for k in kids)
        max_end = max(parse_iso(k["end_date"]) for k in kids)
        progress = round(sum(int(k.get("progress") or 0) * max(1, int(k.get("duration_days") or 1)) for k in kids) / sum(max(1, int(k.get("duration_days") or 1)) for k in kids))
        parent.update({
            "task_type": "summary",
            "start_date": min_start.isoformat(),
            "end_date": max_end.isoformat(),
            "duration_days": max(1, (max_end - min_start).days + 1),
            "progress": progress,
        })

    for t in tasks.values():
        conn.execute(
            """UPDATE tasks SET start_date = ?, end_date = ?, duration_days = ?, progress = ?, task_type = ? WHERE id = ?""",
            (t["start_date"], t["end_date"], int(t.get("duration_days") or 0), int(t.get("progress") or 0), t.get("task_type") or "task", t["id"]),
        )

    project_end = max(parse_iso(t["end_date"]) for t in tasks.values()).isoformat()
    conn.execute("UPDATE projects SET end_date = ? WHERE id = ?", (project_end, project_id))


def refresh_outline_levels(conn: sqlite3.Connection, project_id: int) -> None:
    rows = all_rows(conn, "SELECT id, parent_id FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
    parent_map = {int(r["id"]): r["parent_id"] for r in rows}

    def level(task_id: int) -> int:
        seen = set()
        current = parent_map.get(task_id)
        n = 0
        while current and current not in seen:
            seen.add(current)
            n += 1
            current = parent_map.get(int(current))
        return min(n, 8)

    for r in rows:
        conn.execute("UPDATE tasks SET outline_level = ? WHERE id = ?", (level(int(r["id"])), int(r["id"])))
