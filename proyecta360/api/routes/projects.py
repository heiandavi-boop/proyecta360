from __future__ import annotations

import csv
import html
import io
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from proyecta360.schemas.api import (
    PROJECT_CONTEXT_FIELDS,
    PROJECT_PROFILE_FIELDS,
    ProjectIn,
    ProjectUpdate,
)


def build_router(ctx) -> APIRouter:
    router = APIRouter()
    add_history = ctx.add_history
    all_rows = ctx.all_rows
    calculate_metrics = ctx.calculate_metrics
    db = ctx.db
    deep_merge = ctx.deep_merge
    DEFAULT_PARAMETERS = ctx.DEFAULT_PARAMETERS
    dumps = ctx.dumps
    get_project_or_404 = ctx.get_project_or_404
    init_db = ctx.init_db
    iso_value = ctx.iso_value
    loads = ctx.loads
    MAX_UPLOAD_BYTES = ctx.MAX_UPLOAD_BYTES
    normalize_task_dates = ctx.normalize_task_dates
    project_intelligence = ctx.project_intelligence
    recalculate_project_schedule = ctx.recalculate_project_schedule
    refresh_outline_levels = ctx.refresh_outline_levels
    risk_level = ctx.risk_level
    serialize_evidence = ctx.serialize_evidence
    serialize_project = ctx.serialize_project
    serialize_risk = ctx.serialize_risk
    validate_dependency = ctx.validate_dependency

    def clean_row(row: Dict[str, Any]) -> Dict[str, str]:
        return {str(k or "").strip(): str(v or "").strip() for k, v in row.items() if str(k or "").strip()}

    def pick(row: Dict[str, str], key: str, default: Any = "") -> Any:
        value = row.get(key)
        return default if value is None or value == "" else value

    def as_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return default

    def as_float(value: Any, default: float = 0) -> float:
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def norm_key(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def first_by_normalized(rows: List[Dict[str, Any]], field: str, value: Any) -> Optional[Dict[str, Any]]:
        key = norm_key(value)
        if not key:
            return None
        return next((row for row in rows if norm_key(row.get(field)) == key), None)

    def bump(summary: Dict[str, Dict[str, int]], bucket: str, entity: str, amount: int = 1) -> None:
        summary[bucket][entity] = summary[bucket].get(entity, 0) + amount

    def nullable_id(value: Any, refs: Dict[str, int]) -> Optional[int]:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw in refs:
            return refs[raw]
        return as_int(raw, 0) or None

    def task_wbs_map(conn: sqlite3.Connection, project_id: int) -> Dict[str, int]:
        task_rows = all_rows(conn, "SELECT id, parent_id, outline_level FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
        counters: List[int] = []
        result: Dict[str, int] = {}
        for task in task_rows:
            level = max(0, as_int(task.get("outline_level", 0), 0))
            if level > 0 and not counters:
                counters.append(1)
            while len(counters) <= level:
                counters.append(0)
            counters[level] += 1
            del counters[level + 1:]
            result[".".join(str(value) for value in counters)] = int(task["id"])
        return result

    def strategic_from_project_row(row: Dict[str, str]) -> Dict[str, str]:
        keys = [
            "problem_statement", "current_situation", "main_gap", "general_objective", "specific_objectives",
            "objective_indicators", "consequence_if_not_done", "scope_included", "scope_excluded",
            "expected_results", "success_criteria", "project_context", "political_context", "geographic_context",
            "socioeconomic_context", "cultural_context", "stakeholders_context", "institutional_context",
            "stakeholders", "external_dependencies", "regulatory_constraints", "target_population",
            "direct_beneficiaries", "indirect_beneficiaries", "assumptions", "constraints",
        ]
        return {key: row[key] for key in keys if row.get(key)}

    def project_profile_from_row(row: Dict[str, str]) -> Dict[str, str]:
        keys = ["project_code", "requesting_area", "project_type", "priority", "responsible_team"]
        return {key: row[key] for key in keys if row.get(key)}

    def merge_project_context(params: Dict[str, Any], payload: Any, only_set: bool = False) -> Dict[str, Any]:
        merged = deep_merge(DEFAULT_PARAMETERS, params or {})
        profile = dict(merged.get("project_profile") or {})
        strategic = dict(merged.get("strategic_framework") or {})
        data = payload.model_dump(exclude_unset=only_set) if hasattr(payload, "model_dump") else dict(payload)
        for key in PROJECT_PROFILE_FIELDS:
            if key in data and data[key] is not None:
                profile[key] = data[key]
        for key in PROJECT_CONTEXT_FIELDS:
            if key in data and data[key] is not None:
                strategic[key] = data[key]
        if strategic.get("problem_statement") and not strategic.get("main_gap"):
            strategic["main_gap"] = strategic["problem_statement"]
        if strategic.get("stakeholders") and not strategic.get("stakeholders_context"):
            strategic["stakeholders_context"] = strategic["stakeholders"]
        merged["project_profile"] = profile
        merged["strategic_framework"] = strategic
        return merged

    def csv_row_number(row: Dict[str, str]) -> int:
        return as_int(row.get("__row_number", 0), 0)

    def add_csv_error(errors: List[Dict[str, Any]], row: Dict[str, str], field: str, message: str) -> None:
        errors.append({"row": csv_row_number(row), "field": field, "message": message})

    def valid_iso_date(value: Any) -> bool:
        if not str(value or "").strip():
            return True
        try:
            date.fromisoformat(str(value).strip())
            return True
        except ValueError:
            return False

    def validate_import_rows(rows: List[Dict[str, str]]) -> Dict[str, Any]:
        allowed_entities = {
            "project", "proyecto", "component", "components", "resource", "resources", "task", "tasks",
            "budget", "budgets", "budget_entry", "budget_entries",
            "dependency", "dependencies", "sprint", "sprints", "story", "stories", "risk", "risks",
            "deliverable", "deliverables", "conversation_thread", "conversation_threads",
            "conversation_message", "conversation_messages",
        }
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        has_project = False
        import_ids: Dict[str, set[str]] = {"component": set(), "task": set(), "sprint": set(), "conversation_thread": set()}
        for row in rows:
            entity = (row.get("entity") or row.get("tipo") or "").strip().lower()
            if not entity:
                add_csv_error(errors, row, "entity", "La entidad es obligatoria.")
                continue
            if entity not in allowed_entities:
                add_csv_error(errors, row, "entity", f"Entidad no soportada: {entity}.")
                continue
            if entity in {"project", "proyecto"}:
                has_project = True
                if not pick(row, "name", row.get("nombre", "")):
                    add_csv_error(errors, row, "name", "El proyecto debe incluir nombre.")
                if not valid_iso_date(pick(row, "start_date", "")):
                    add_csv_error(errors, row, "start_date", "Fecha invalida. Usa YYYY-MM-DD.")
                if not valid_iso_date(pick(row, "end_date", "")):
                    add_csv_error(errors, row, "end_date", "Fecha invalida. Usa YYYY-MM-DD.")
                if pick(row, "start_date", "") and pick(row, "end_date", "") and pick(row, "end_date") < pick(row, "start_date"):
                    add_csv_error(errors, row, "end_date", "La fecha fin no puede ser menor a la fecha inicio.")
                if as_float(pick(row, "budget", 0), 0) < 0:
                    add_csv_error(errors, row, "budget", "El presupuesto no puede ser negativo.")
            if entity in {"component", "components", "resource", "resources", "deliverable", "deliverables"} and not pick(row, "name", ""):
                add_csv_error(errors, row, "name", "El nombre es obligatorio para esta entidad.")
            if entity in {"budget", "budgets", "budget_entry", "budget_entries"}:
                if not pick(row, "month", ""):
                    add_csv_error(errors, row, "month", "El registro presupuestal requiere mes YYYY-MM.")
                if pick(row, "month", "") and len(pick(row, "month", "")) != 7:
                    add_csv_error(errors, row, "month", "El mes debe tener formato YYYY-MM.")
                if as_float(pick(row, "planned_amount", 0), 0) < 0 or as_float(pick(row, "executed_amount", 0), 0) < 0:
                    add_csv_error(errors, row, "amount", "Los valores presupuestales no pueden ser negativos.")
            if entity in {"task", "tasks"}:
                if not pick(row, "title", pick(row, "name", "")):
                    add_csv_error(errors, row, "title", "La tarea debe incluir titulo.")
                if not valid_iso_date(pick(row, "start_date", "")):
                    add_csv_error(errors, row, "start_date", "Fecha invalida. Usa YYYY-MM-DD.")
                if not valid_iso_date(pick(row, "end_date", "")):
                    add_csv_error(errors, row, "end_date", "Fecha invalida. Usa YYYY-MM-DD.")
                progress = as_int(pick(row, "progress", 0), 0)
                if progress < 0 or progress > 100:
                    add_csv_error(errors, row, "progress", "El avance debe estar entre 0 y 100.")
                task_type = pick(row, "task_type", "task")
                if task_type != "milestone" and as_int(pick(row, "duration_days", 1), 1) < 1:
                    add_csv_error(errors, row, "duration_days", "La duracion debe ser mayor o igual a 1.")
            if entity in {"dependency", "dependencies"}:
                if not pick(row, "predecessor_ref", pick(row, "predecessor_id", "")):
                    add_csv_error(errors, row, "predecessor_ref", "La dependencia requiere predecesora.")
                if not pick(row, "successor_ref", pick(row, "successor_id", "")):
                    add_csv_error(errors, row, "successor_ref", "La dependencia requiere sucesora.")
                dep_type = pick(row, "dependency_type", "FS").upper()
                if dep_type not in {"FS", "SS", "FF", "SF"}:
                    add_csv_error(errors, row, "dependency_type", "Tipo de dependencia invalido.")
            if entity in {"risk", "risks"}:
                if not pick(row, "title", pick(row, "name", "")):
                    add_csv_error(errors, row, "title", "El riesgo debe incluir titulo.")
                for field in ("probability", "impact"):
                    value = as_int(pick(row, field, 1), 1)
                    if value < 1 or value > 5:
                        add_csv_error(errors, row, field, "Debe estar entre 1 y 5.")
            if entity in {"sprint", "sprints"}:
                if not pick(row, "name", ""):
                    add_csv_error(errors, row, "name", "El sprint debe incluir nombre.")
                if not valid_iso_date(pick(row, "start_date", "")):
                    add_csv_error(errors, row, "start_date", "Fecha invalida. Usa YYYY-MM-DD.")
                if not valid_iso_date(pick(row, "end_date", "")):
                    add_csv_error(errors, row, "end_date", "Fecha invalida. Usa YYYY-MM-DD.")
            import_id = str(row.get("import_id") or "").strip()
            canonical = {"components": "component", "tasks": "task", "sprints": "sprint", "conversation_threads": "conversation_thread"}.get(entity, entity)
            if import_id and canonical in import_ids:
                if import_id in import_ids[canonical]:
                    add_csv_error(errors, row, "import_id", f"import_id duplicado para {canonical}.")
                import_ids[canonical].add(import_id)
        if not has_project:
            errors.append({"row": 0, "field": "entity", "message": "El CSV debe incluir una fila entity=project."})
        return {"errors": errors, "warnings": warnings}

    def import_project_from_rows(conn: sqlite3.Connection, rows: List[Dict[str, str]]) -> Dict[str, Any]:
        by_entity: Dict[str, List[Dict[str, str]]] = {}
        for row in rows:
            entity = (row.get("entity") or row.get("tipo") or "").strip().lower()
            if entity:
                by_entity.setdefault(entity, []).append(row)
        project_rows = by_entity.get("project") or by_entity.get("proyecto") or []
        project_row = project_rows[0] if project_rows else {}
        if not project_row.get("name") and not project_row.get("nombre"):
            raise HTTPException(status_code=400, detail="El CSV debe incluir una fila entity=project con el campo name")

        params = deep_merge(DEFAULT_PARAMETERS, loads(project_row.get("parameters_json"), {}) or {})
        strategic = strategic_from_project_row(project_row)
        if strategic:
            params["strategic_framework"] = deep_merge(params.get("strategic_framework", {}), strategic)
        profile = project_profile_from_row(project_row)
        if profile:
            params["project_profile"] = deep_merge(params.get("project_profile", {}), profile)
        start = pick(project_row, "start_date", date.today().isoformat())
        end = pick(project_row, "end_date", start)
        summary: Dict[str, Dict[str, int]] = {
            "created": {},
            "updated": {},
            "skipped": {},
            "errors": {},
        }
        project_name = pick(project_row, "name", project_row.get("nombre", "Proyecto importado"))
        explicit_project_id = as_int(pick(project_row, "project_id", pick(project_row, "id", 0)), 0)
        existing_project = None
        if explicit_project_id:
            existing_project = all_rows(conn, "SELECT * FROM projects WHERE id = ?", (explicit_project_id,))
            existing_project = existing_project[0] if existing_project else None
        if not existing_project:
            existing_project = first_by_normalized(all_rows(conn, "SELECT * FROM projects", ()), "name", project_name)
        if existing_project:
            project_id = int(existing_project["id"])
            existing_parameters = loads(existing_project.get("parameters_json"), DEFAULT_PARAMETERS)
            params = deep_merge(existing_parameters, params)
            conn.execute(
                """UPDATE projects
                   SET name = ?, description = ?, sponsor = ?, project_manager = ?, start_date = ?, end_date = ?,
                       contractual_end_date = ?, methodology = ?, status = ?, budget = ?, currency = ?, parameters_json = ?
                   WHERE id = ?""",
                (
                    project_name,
                    pick(project_row, "description", existing_project.get("description", "")),
                    pick(project_row, "sponsor", existing_project.get("sponsor", "")),
                    pick(project_row, "project_manager", existing_project.get("project_manager", "")),
                    start,
                    end,
                    pick(project_row, "contractual_end_date", existing_project.get("contractual_end_date", "")),
                    pick(project_row, "methodology", existing_project.get("methodology", "Hibrida PMP + Scrum")),
                    pick(project_row, "status", existing_project.get("status", "Planeado")),
                    as_float(pick(project_row, "budget", existing_project.get("budget", 0))),
                    pick(project_row, "currency", existing_project.get("currency", "COP")).upper(),
                    dumps(params),
                    project_id,
                ),
            )
            bump(summary, "updated", "projects")
        else:
            cur = conn.execute(
                """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, contractual_end_date, methodology, status, budget, currency, parameters_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_name,
                    pick(project_row, "description", ""),
                    pick(project_row, "sponsor", ""),
                    pick(project_row, "project_manager", ""),
                    start,
                    end,
                    pick(project_row, "contractual_end_date", ""),
                    pick(project_row, "methodology", "Hibrida PMP + Scrum"),
                    pick(project_row, "status", "Planeado"),
                    as_float(pick(project_row, "budget", 0)),
                    pick(project_row, "currency", "COP").upper(),
                    dumps(params),
                ),
            )
            project_id = int(cur.lastrowid)
            bump(summary, "created", "projects")
        refs: Dict[str, Dict[str, int]] = {"component": {}, "task": {}, "sprint": {}, "conversation_thread": {}}
        warnings: List[str] = []
        counts: Dict[str, int] = {"projects": 1, "components": 0, "resources": 0, "tasks": 0, "dependencies": 0, "sprints": 0, "stories": 0, "risks": 0, "deliverables": 0, "conversation_threads": 0, "conversation_messages": 0}

        for row in by_entity.get("component", []) + by_entity.get("components", []):
            name = pick(row, "name", "Componente importado")
            existing = first_by_normalized(all_rows(conn, "SELECT * FROM components WHERE project_id = ?", (project_id,)), "name", name)
            if existing:
                conn.execute(
                    "UPDATE components SET methodology = ?, owner = ?, objective = ?, progress = ? WHERE id = ?",
                    (pick(row, "methodology", existing.get("methodology", "Hibrida")), pick(row, "owner", existing.get("owner", "")), pick(row, "objective", existing.get("objective", "")), as_int(pick(row, "progress", existing.get("progress", 0))), existing["id"]),
                )
                component_id = int(existing["id"])
                bump(summary, "updated", "components")
            else:
                cur = conn.execute(
                    "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, name, pick(row, "methodology", "Hibrida"), pick(row, "owner", ""), pick(row, "objective", ""), as_int(pick(row, "progress", 0))),
                )
                component_id = int(cur.lastrowid)
                bump(summary, "created", "components")
            if row.get("import_id"):
                refs["component"][row["import_id"]] = component_id
            counts["components"] += 1
        for row in by_entity.get("resource", []) + by_entity.get("resources", []):
            name = pick(row, "name", "Recurso importado")
            existing = first_by_normalized(all_rows(conn, "SELECT * FROM resources WHERE project_id = ?", (project_id,)), "name", name)
            if existing:
                conn.execute("UPDATE resources SET role = ?, email = ?, capacity = ? WHERE id = ?", (pick(row, "role", existing.get("role", "")), pick(row, "email", existing.get("email", "")), as_int(pick(row, "capacity", existing.get("capacity", 100)), 100), existing["id"]))
                bump(summary, "updated", "resources")
            else:
                conn.execute("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", (project_id, name, pick(row, "role", ""), pick(row, "email", ""), as_int(pick(row, "capacity", 100), 100)))
                bump(summary, "created", "resources")
            counts["resources"] += 1

        for row in by_entity.get("budget", []) + by_entity.get("budgets", []) + by_entity.get("budget_entry", []) + by_entity.get("budget_entries", []):
            month = pick(row, "month", "")
            category = pick(row, "category", "General")
            existing = one(conn, "SELECT * FROM budget_entries WHERE project_id = ? AND month = ? AND category = ?", (project_id, month, category))
            if existing:
                conn.execute(
                    "UPDATE budget_entries SET planned_amount = ?, executed_amount = ?, notes = ? WHERE id = ?",
                    (as_float(pick(row, "planned_amount", existing.get("planned_amount", 0))), as_float(pick(row, "executed_amount", existing.get("executed_amount", 0))), pick(row, "notes", existing.get("notes", "")), existing["id"]),
                )
                bump(summary, "updated", "budget_entries")
            else:
                conn.execute(
                    "INSERT INTO budget_entries (project_id, month, category, planned_amount, executed_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, month, category, as_float(pick(row, "planned_amount", 0)), as_float(pick(row, "executed_amount", 0)), pick(row, "notes", "")),
                )
                bump(summary, "created", "budget_entries")

        task_rows = by_entity.get("task", []) + by_entity.get("tasks", [])
        pending_task_updates: List[tuple[int, Dict[str, str]]] = []
        for index, row in enumerate(task_rows, start=1):
            start_s, end_s, duration = normalize_task_dates(pick(row, "start_date", start), pick(row, "end_date", "") or None, as_int(pick(row, "duration_days", 1), 1), pick(row, "task_type", "task"))
            parent_id = nullable_id(pick(row, "parent_id", ""), refs["task"])
            component_id = nullable_id(pick(row, "component_ref", pick(row, "component_id", "")), refs["component"])
            title = pick(row, "title", pick(row, "name", "Tarea importada"))
            order_index = as_int(pick(row, "order_index", index), index)
            existing_tasks = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
            existing = first_by_normalized(existing_tasks, "title", title)
            if not existing:
                existing = next((task for task in existing_tasks if as_int(task.get("order_index"), -1) == order_index and norm_key(task.get("title")) == norm_key(title)), None)
            if existing:
                conn.execute(
                    """UPDATE tasks
                       SET parent_id = ?, component_id = ?, title = ?, phase = ?, task_type = ?, start_date = ?, end_date = ?,
                           duration_days = ?, progress = ?, owner = ?, status = ?, story_points = ?, budget = ?,
                           description = ?, order_index = ?, outline_level = ?, is_expanded = ?
                       WHERE id = ?""",
                    (parent_id, component_id, title, pick(row, "phase", existing.get("phase", "")), pick(row, "task_type", existing.get("task_type", "task")), start_s, end_s, duration, as_int(pick(row, "progress", existing.get("progress", 0))), pick(row, "owner", existing.get("owner", "")), pick(row, "status", existing.get("status", "Pendiente")), as_int(pick(row, "story_points", existing.get("story_points", 0))), as_float(pick(row, "budget", existing.get("budget", 0))), pick(row, "description", existing.get("description", "")), order_index, as_int(pick(row, "outline_level", existing.get("outline_level", 0))), as_int(pick(row, "is_expanded", existing.get("is_expanded", 1)), 1), existing["id"]),
                )
                new_id = int(existing["id"])
                bump(summary, "updated", "tasks")
            else:
                cur = conn.execute(
                    """INSERT INTO tasks (project_id, parent_id, component_id, title, phase, task_type, start_date, end_date, duration_days, progress, owner, status, story_points, budget, description, order_index, outline_level, is_expanded)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (project_id, parent_id, component_id, title, pick(row, "phase", ""), pick(row, "task_type", "task"), start_s, end_s, duration, as_int(pick(row, "progress", 0)), pick(row, "owner", ""), pick(row, "status", "Pendiente"), as_int(pick(row, "story_points", 0)), as_float(pick(row, "budget", 0)), pick(row, "description", ""), order_index, as_int(pick(row, "outline_level", 0)), as_int(pick(row, "is_expanded", 1), 1)),
                )
                new_id = int(cur.lastrowid)
                bump(summary, "created", "tasks")
            if row.get("import_id"):
                refs["task"][row["import_id"]] = new_id
            pending_task_updates.append((new_id, row))
            counts["tasks"] += 1
        for task_id, row in pending_task_updates:
            parent_id = nullable_id(pick(row, "parent_ref", ""), refs["task"])
            if parent_id:
                conn.execute("UPDATE tasks SET parent_id = ? WHERE id = ?", (parent_id, task_id))
        refresh_outline_levels(conn, project_id)
        wbs_refs = task_wbs_map(conn, project_id)

        for row in by_entity.get("dependency", []) + by_entity.get("dependencies", []):
            pred = nullable_id(pick(row, "predecessor_ref", pick(row, "predecessor_id", "")), refs["task"])
            succ = nullable_id(pick(row, "successor_ref", pick(row, "successor_id", "")), refs["task"])
            if pred and succ:
                validate_dependency(conn, project_id, pred, succ)
                dependency_type = pick(row, "dependency_type", "FS").upper()
                existing = all_rows(conn, "SELECT id FROM dependencies WHERE project_id = ? AND predecessor_id = ? AND successor_id = ? AND dependency_type = ?", (project_id, pred, succ, dependency_type))
                if existing:
                    bump(summary, "skipped", "dependencies")
                else:
                    conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type, lag_days) VALUES (?, ?, ?, ?, ?)", (project_id, pred, succ, dependency_type, as_int(pick(row, "lag_days", 0))))
                    bump(summary, "created", "dependencies")
                counts["dependencies"] += 1
        for row in by_entity.get("sprint", []) + by_entity.get("sprints", []):
            name = pick(row, "name", "Sprint importado")
            existing = first_by_normalized(all_rows(conn, "SELECT * FROM sprints WHERE project_id = ?", (project_id,)), "name", name)
            if existing:
                conn.execute("UPDATE sprints SET goal = ?, start_date = ?, end_date = ?, status = ?, velocity = ? WHERE id = ?", (pick(row, "goal", existing.get("goal", "")), pick(row, "start_date", existing.get("start_date", start)), pick(row, "end_date", existing.get("end_date", start)), pick(row, "status", existing.get("status", "Planeado")), as_int(pick(row, "velocity", existing.get("velocity", 0))), existing["id"]))
                sprint_id = int(existing["id"])
                bump(summary, "updated", "sprints")
            else:
                cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, name, pick(row, "goal", ""), pick(row, "start_date", start), pick(row, "end_date", start), pick(row, "status", "Planeado"), as_int(pick(row, "velocity", 0))))
                sprint_id = int(cur.lastrowid)
                bump(summary, "created", "sprints")
            if row.get("import_id"):
                refs["sprint"][row["import_id"]] = sprint_id
            counts["sprints"] += 1
        for row in by_entity.get("story", []) + by_entity.get("stories", []):
            sprint_id = nullable_id(pick(row, "sprint_ref", pick(row, "sprint_id", "")), refs["sprint"])
            master_task_id = nullable_id(pick(row, "master_task_id", ""), refs["task"])
            master_task_wbs = str(pick(row, "master_task_wbs", "")).strip()
            if not master_task_id and master_task_wbs:
                master_task_id = wbs_refs.get(master_task_wbs)
                if not master_task_id:
                    warnings.append(f"Historia '{pick(row, 'title', 'Historia importada')}' importada sin vinculo: WBS {master_task_wbs} no encontrado.")
            title = pick(row, "title", "Historia importada")
            stories = all_rows(conn, "SELECT * FROM stories WHERE project_id = ?", (project_id,))
            existing = next(
                (
                    story for story in stories
                    if norm_key(story.get("title")) == norm_key(title)
                    and (sprint_id is None or story.get("sprint_id") == sprint_id)
                ),
                None,
            )
            if existing:
                conn.execute(
                    "UPDATE stories SET sprint_id = ?, master_task_id = ?, status = ?, points = ?, assignee = ?, priority = ? WHERE id = ?",
                    (sprint_id, master_task_id, pick(row, "status", existing.get("status", "Por hacer")), as_int(pick(row, "points", existing.get("points", 0))), pick(row, "assignee", existing.get("assignee", "")), pick(row, "priority", existing.get("priority", "Media")), existing["id"]),
                )
                bump(summary, "updated", "stories")
            else:
                conn.execute("INSERT INTO stories (project_id, sprint_id, master_task_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (project_id, sprint_id, master_task_id, title, pick(row, "status", "Por hacer"), as_int(pick(row, "points", 0)), pick(row, "assignee", ""), pick(row, "priority", "Media")))
                bump(summary, "created", "stories")
            counts["stories"] += 1
        for row in by_entity.get("risk", []) + by_entity.get("risks", []):
            probability, impact = as_int(pick(row, "probability", 1), 1), as_int(pick(row, "impact", 1), 1)
            title = pick(row, "title", pick(row, "name", "Riesgo importado"))
            existing = first_by_normalized(all_rows(conn, "SELECT * FROM risks WHERE project_id = ?", (project_id,)), "title", title)
            values = (probability, impact, pick(row, "level", risk_level(probability, impact, params)), pick(row, "response", ""), pick(row, "mitigation_plan", ""), pick(row, "contingency_plan", ""), pick(row, "status", "Abierto"), pick(row, "owner", ""))
            if existing:
                conn.execute("UPDATE risks SET probability = ?, impact = ?, level = ?, response = ?, mitigation_plan = ?, contingency_plan = ?, status = ?, owner = ? WHERE id = ?", (*values, existing["id"]))
                bump(summary, "updated", "risks")
            else:
                conn.execute("INSERT INTO risks (project_id, title, probability, impact, level, response, mitigation_plan, contingency_plan, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (project_id, title, *values))
                bump(summary, "created", "risks")
            counts["risks"] += 1
        for row in by_entity.get("deliverable", []) + by_entity.get("deliverables", []):
            component_id = nullable_id(pick(row, "component_ref", pick(row, "component_id", "")), refs["component"])
            name = pick(row, "name", "Entregable importado")
            existing = first_by_normalized(all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ?", (project_id,)), "name", name)
            values = (component_id, pick(row, "deliverable_type", "Entregable"), pick(row, "status", "Planeado"), pick(row, "owner", ""), pick(row, "due_date", ""), pick(row, "evidence_url", ""), pick(row, "description", ""))
            if existing:
                conn.execute("""UPDATE deliverables SET component_id = ?, deliverable_type = ?, status = ?, owner = ?, due_date = ?, evidence_url = ?, description = ? WHERE id = ?""", (*values, existing["id"]))
                bump(summary, "updated", "deliverables")
            else:
                conn.execute("""INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, owner, due_date, evidence_url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (project_id, values[0], name, *values[1:]))
                bump(summary, "created", "deliverables")
            counts["deliverables"] += 1
        for row in by_entity.get("conversation_thread", []) + by_entity.get("conversation_threads", []):
            title = pick(row, "title", "Conversacion importada")
            existing = first_by_normalized(all_rows(conn, "SELECT * FROM conversation_threads WHERE project_id = ?", (project_id,)), "title", title)
            values = (pick(row, "context_type", "Proyecto"), as_int(pick(row, "context_id", 0)) or None, pick(row, "category", "Seguimiento"), pick(row, "status", "Abierta"), pick(row, "created_by", ""))
            if existing:
                conn.execute("UPDATE conversation_threads SET context_type = ?, context_id = ?, category = ?, status = ?, created_by = ? WHERE id = ?", (*values, existing["id"]))
                thread_id = int(existing["id"])
                bump(summary, "updated", "conversation_threads")
            else:
                cur = conn.execute("INSERT INTO conversation_threads (project_id, title, context_type, context_id, category, status, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, title, *values))
                thread_id = int(cur.lastrowid)
                bump(summary, "created", "conversation_threads")
            if row.get("import_id"):
                refs["conversation_thread"][row["import_id"]] = thread_id
            counts["conversation_threads"] += 1
        for row in by_entity.get("conversation_message", []) + by_entity.get("conversation_messages", []):
            thread_id = nullable_id(pick(row, "thread_ref", pick(row, "thread_id", "")), refs["conversation_thread"])
            if thread_id:
                message = pick(row, "message", "")
                existing = all_rows(conn, "SELECT id FROM conversation_messages WHERE project_id = ? AND thread_id = ? AND message = ?", (project_id, thread_id, message))
                if existing:
                    bump(summary, "skipped", "conversation_messages")
                else:
                    conn.execute("INSERT INTO conversation_messages (thread_id, project_id, author, message, mentions, evidence_url, message_type) VALUES (?, ?, ?, ?, ?, ?, ?)", (thread_id, project_id, pick(row, "author", ""), message, pick(row, "mentions", ""), pick(row, "evidence_url", ""), pick(row, "message_type", "Comentario")))
                    bump(summary, "created", "conversation_messages")
                counts["conversation_messages"] += 1

        refresh_outline_levels(conn, project_id)
        if counts["tasks"]:
            recalculate_project_schedule(conn, project_id)
        add_history(conn, project_id, "Importacion", pick(project_row, "name", "Proyecto importado"), "CSV importado", f"Filas procesadas: {len(rows)}")
        return {"project_id": project_id, "counts": counts, "summary": summary, "warnings": warnings}

    @router.post("/api/projects")
    def create_project(payload: ProjectIn) -> Dict[str, Any]:
        init_db()
        with db() as conn:
            parameters = merge_project_context(payload.parameters, payload)
            calculated_end = payload.end_date or payload.start_date
            cur = conn.execute(
                """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, contractual_end_date, methodology, status, budget, currency, parameters_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload.name, payload.description, payload.sponsor, payload.project_manager, iso_value(payload.start_date), iso_value(calculated_end), iso_value(payload.contractual_end_date) if payload.contractual_end_date else "", payload.methodology, payload.status, payload.budget, payload.currency, dumps(parameters)),
            )
            add_history(conn, cur.lastrowid, "Proyecto", payload.name, "Creado", "Proyecto creado con fecha fin calculada por cronograma.")
            conn.commit()
            return serialize_project(get_project_or_404(conn, cur.lastrowid))

    @router.post("/api/projects/import/csv")
    async def import_project_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
        init_db()
        filename = file.filename or ""
        if not filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos CSV")
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="El archivo supera el tamano permitido")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        fields = {str(name or "").strip() for name in (reader.fieldnames or [])}
        if "entity" not in fields:
            raise HTTPException(status_code=400, detail="El CSV debe incluir la columna entity")
        rows = []
        for index, row in enumerate(reader, start=2):
            clean = clean_row(row)
            clean["__row_number"] = str(index)
            rows.append(clean)
        if not rows:
            raise HTTPException(status_code=400, detail="El CSV no contiene filas para importar")
        validation = validate_import_rows(rows)
        if validation["errors"]:
            raise HTTPException(status_code=400, detail={"message": "El CSV contiene errores de validacion", "errors": validation["errors"]})
        with db() as conn:
            result = import_project_from_rows(conn, rows)
            if validation["warnings"]:
                result.setdefault("warnings", []).extend(validation["warnings"])
            project = serialize_project(get_project_or_404(conn, result["project_id"]))
            conn.commit()
            return {"message": "Proyecto importado", "project": project, **result}
    
    
    @router.put("/api/projects/{project_id}")
    def update_project(project_id: int, payload: ProjectUpdate) -> Dict[str, Any]:
        with db() as conn:
            current = get_project_or_404(conn, project_id)
            data = payload.model_dump(exclude_unset=True)
            parameter_patch = {key: data.pop(key) for key in list(data.keys()) if key in PROJECT_PROFILE_FIELDS or key in PROJECT_CONTEXT_FIELDS}
            start_date = iso_value(data.get("start_date", current["start_date"]))
            end_date = iso_value(data.get("end_date", current["end_date"]))
            if end_date and start_date and end_date < start_date:
                raise HTTPException(status_code=400, detail="La fecha fin no puede ser menor a la fecha inicio")
            existing_parameters = loads(current["parameters_json"], DEFAULT_PARAMETERS)
            if "parameters" in data and data["parameters"] is not None:
                existing_parameters = deep_merge(existing_parameters, data.pop("parameters"))
            if parameter_patch:
                existing_parameters = merge_project_context(existing_parameters, parameter_patch)
            if parameter_patch or "parameters" in payload.model_fields_set:
                data["parameters_json"] = dumps(existing_parameters)
            fields = []
            args = []
            for k, v in data.items():
                fields.append(f"{k} = ?")
                args.append(iso_value(v))
            if fields:
                args.append(project_id)
                conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", tuple(args))
                conn.commit()
            return serialize_project(get_project_or_404(conn, project_id))
    

    @router.get("/api/projects/{project_id}/metrics")
    def metrics(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            return calculate_metrics(conn, project_id)
    
    
    @router.get("/api/projects/{project_id}/intelligence")
    def intelligence(project_id: int) -> Dict[str, Any]:
        with db() as conn:
            get_project_or_404(conn, project_id)
            return project_intelligence(conn, project_id)
    

    def export_project_data(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
        project = serialize_project(get_project_or_404(conn, project_id))
        return {
            "project": project,
            "components": all_rows(conn, "SELECT * FROM components WHERE project_id = ? ORDER BY id", (project_id,)),
            "resources": all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (project_id,)),
            "budget_entries": all_rows(conn, "SELECT * FROM budget_entries WHERE project_id = ? ORDER BY month, category, id", (project_id,)),
            "tasks": all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,)),
            "dependencies": all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ? ORDER BY id", (project_id,)),
            "sprints": all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date, id", (project_id,)),
            "stories": all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (project_id,)),
            "risks": [serialize_risk(r) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY id", (project_id,))],
            "deliverables": all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ? ORDER BY due_date, id", (project_id,)),
            "evidences": [serialize_evidence(r) for r in all_rows(conn, "SELECT * FROM evidence_files WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,))],
            "history": all_rows(conn, "SELECT * FROM change_log WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,)),
            "conversation_threads": all_rows(conn, "SELECT * FROM conversation_threads WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,)),
            "conversation_messages": all_rows(conn, "SELECT * FROM conversation_messages WHERE project_id = ? ORDER BY created_at, id", (project_id,)),
            "metrics": calculate_metrics(conn, project_id),
            "intelligence": project_intelligence(conn, project_id),
            "exported_at": datetime.utcnow().isoformat(),
        }

    def export_project_csv_content(data: Dict[str, Any]) -> str:
        strategic = (data["project"].get("parameters") or {}).get("strategic_framework", {})
        fieldnames = [
            "entity", "import_id", "name", "title", "description", "start_date", "end_date", "duration_days",
            "project_manager", "sponsor", "project_code", "requesting_area", "project_type", "priority",
            "responsible_team", "budget", "currency", "contractual_end_date", "methodology", "status",
            "month", "category", "planned_amount", "executed_amount", "notes",
            "parameters_json", "problem_statement", "current_situation", "main_gap", "consequence_if_not_done",
            "general_objective", "specific_objectives", "objective_indicators", "scope_included",
            "scope_excluded", "expected_results", "success_criteria", "project_context",
            "political_context", "geographic_context", "socioeconomic_context", "cultural_context",
            "stakeholders_context", "stakeholders", "institutional_context", "external_dependencies",
            "regulatory_constraints", "target_population", "direct_beneficiaries", "indirect_beneficiaries",
            "assumptions", "constraints", "component_ref", "component_id",
            "parent_ref", "parent_id", "phase", "task_type", "progress", "owner", "story_points",
            "order_index", "outline_level", "is_expanded", "predecessor_ref", "predecessor_id",
            "successor_ref", "successor_id", "dependency_type", "lag_days", "role", "email", "capacity",
            "objective", "goal", "velocity", "sprint_ref", "sprint_id", "points", "assignee", "priority",
            "master_task_wbs",
            "probability", "impact", "level", "response", "mitigation_plan", "contingency_plan",
            "deliverable_type", "due_date", "evidence_url", "thread_ref", "thread_id", "context_type",
            "context_id", "category", "created_by", "author", "message", "mentions", "message_type",
        ]
        rows: List[Dict[str, Any]] = []
        project = data["project"]
        profile = (project.get("parameters") or {}).get("project_profile", {})
        rows.append({
            "entity": "project",
            "name": project.get("name", ""),
            "description": project.get("description", ""),
            "start_date": project.get("start_date", ""),
            "end_date": project.get("end_date", ""),
            "project_manager": project.get("project_manager", ""),
            "sponsor": project.get("sponsor", ""),
            **{key: profile.get(key, "") for key in ["project_code", "requesting_area", "project_type", "priority", "responsible_team"]},
            "budget": project.get("budget", ""),
            "currency": project.get("currency", ""),
            "contractual_end_date": project.get("contractual_end_date", ""),
            "methodology": project.get("methodology", ""),
            "status": project.get("status", ""),
            "parameters_json": dumps(project.get("parameters", {})),
            **{key: strategic.get(key, "") for key in [
                "problem_statement", "current_situation", "main_gap", "general_objective", "specific_objectives",
                "objective_indicators", "consequence_if_not_done", "scope_included", "scope_excluded",
                "expected_results", "success_criteria", "project_context", "political_context",
                "geographic_context", "socioeconomic_context", "cultural_context", "stakeholders_context",
                "stakeholders", "institutional_context", "external_dependencies", "regulatory_constraints",
                "target_population", "direct_beneficiaries", "indirect_beneficiaries", "assumptions", "constraints",
            ]},
        })
        component_refs = {c["id"]: f"C{c['id']}" for c in data["components"]}
        task_refs = {t["id"]: f"T{t['id']}" for t in data["tasks"]}
        counters: List[int] = []
        task_wbs_by_id: Dict[int, str] = {}
        for task in data["tasks"]:
            level = max(0, as_int(task.get("outline_level", 0), 0))
            if level > 0 and not counters:
                counters.append(1)
            while len(counters) <= level:
                counters.append(0)
            counters[level] += 1
            del counters[level + 1:]
            task_wbs_by_id[int(task["id"])] = ".".join(str(value) for value in counters)
        sprint_refs = {s["id"]: f"S{s['id']}" for s in data["sprints"]}
        thread_refs = {t["id"]: f"TH{t['id']}" for t in data["conversation_threads"]}
        for c in data["components"]:
            rows.append({"entity": "component", "import_id": component_refs[c["id"]], "name": c.get("name", ""), "methodology": c.get("methodology", ""), "owner": c.get("owner", ""), "objective": c.get("objective", ""), "progress": c.get("progress", "")})
        for r in data["resources"]:
            rows.append({"entity": "resource", "name": r.get("name", ""), "role": r.get("role", ""), "email": r.get("email", ""), "capacity": r.get("capacity", "")})
        for entry in data["budget_entries"]:
            rows.append({"entity": "budget", "month": entry.get("month", ""), "category": entry.get("category", ""), "planned_amount": entry.get("planned_amount", ""), "executed_amount": entry.get("executed_amount", ""), "notes": entry.get("notes", "")})
        for t in data["tasks"]:
            rows.append({
                "entity": "task", "import_id": task_refs[t["id"]], "title": t.get("title", ""), "description": t.get("description", ""),
                "start_date": t.get("start_date", ""), "end_date": t.get("end_date", ""), "duration_days": t.get("duration_days", ""),
                "component_ref": component_refs.get(t.get("component_id"), ""), "parent_ref": task_refs.get(t.get("parent_id"), ""),
                "phase": t.get("phase", ""), "task_type": t.get("task_type", ""), "progress": t.get("progress", ""),
                "owner": t.get("owner", ""), "status": t.get("status", ""), "story_points": t.get("story_points", ""),
                "budget": t.get("budget", ""), "order_index": t.get("order_index", ""), "outline_level": t.get("outline_level", ""),
                "is_expanded": t.get("is_expanded", ""),
            })
        for d in data["dependencies"]:
            rows.append({"entity": "dependency", "predecessor_ref": task_refs.get(d.get("predecessor_id"), ""), "successor_ref": task_refs.get(d.get("successor_id"), ""), "dependency_type": d.get("dependency_type", ""), "lag_days": d.get("lag_days", "")})
        for s in data["sprints"]:
            rows.append({"entity": "sprint", "import_id": sprint_refs[s["id"]], "name": s.get("name", ""), "goal": s.get("goal", ""), "start_date": s.get("start_date", ""), "end_date": s.get("end_date", ""), "status": s.get("status", ""), "velocity": s.get("velocity", "")})
        for story in data["stories"]:
            rows.append({"entity": "story", "title": story.get("title", ""), "status": story.get("status", ""), "points": story.get("points", ""), "assignee": story.get("assignee", ""), "priority": story.get("priority", ""), "sprint_ref": sprint_refs.get(story.get("sprint_id"), ""), "master_task_wbs": task_wbs_by_id.get(story.get("master_task_id"), "")})
        for r in data["risks"]:
            rows.append({"entity": "risk", "title": r.get("title", ""), "probability": r.get("probability", ""), "impact": r.get("impact", ""), "level": r.get("level", ""), "response": r.get("response", ""), "mitigation_plan": r.get("mitigation_plan", ""), "contingency_plan": r.get("contingency_plan", ""), "status": r.get("status", ""), "owner": r.get("owner", "")})
        for d in data["deliverables"]:
            rows.append({"entity": "deliverable", "name": d.get("name", ""), "description": d.get("description", ""), "component_ref": component_refs.get(d.get("component_id"), ""), "deliverable_type": d.get("deliverable_type", ""), "status": d.get("status", ""), "owner": d.get("owner", ""), "due_date": d.get("due_date", ""), "evidence_url": d.get("evidence_url", "")})
        for t in data["conversation_threads"]:
            rows.append({"entity": "conversation_thread", "import_id": thread_refs[t["id"]], "title": t.get("title", ""), "context_type": t.get("context_type", ""), "context_id": t.get("context_id", ""), "category": t.get("category", ""), "status": t.get("status", ""), "created_by": t.get("created_by", "")})
        for m in data["conversation_messages"]:
            rows.append({"entity": "conversation_message", "thread_ref": thread_refs.get(m.get("thread_id"), ""), "author": m.get("author", ""), "message": m.get("message", ""), "mentions": m.get("mentions", ""), "evidence_url": m.get("evidence_url", ""), "message_type": m.get("message_type", "")})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()
    
    
    @router.get("/api/projects/{project_id}/export/json")
    def export_project_json(project_id: int) -> Response:
        init_db()
        with db() as conn:
            data = export_project_data(conn, project_id)
            add_history(conn, project_id, "Exportación", data["project"]["name"], "JSON generado", "Descarga completa del proyecto")
            conn.commit()
        filename = f"proyecta360_proyecto_{project_id}.json"
        return Response(
            content=dumps(data),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @router.get("/api/projects/{project_id}/export/csv")
    def export_project_csv(project_id: int) -> Response:
        init_db()
        with db() as conn:
            data = export_project_data(conn, project_id)
            content = export_project_csv_content(data)
            add_history(conn, project_id, "Exportación", data["project"]["name"], "CSV generado", "Archivo compatible con importación CSV")
            conn.commit()
        filename = f"proyecta360_proyecto_{project_id}.csv"
        return Response(
            content="\ufeff" + content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    
    
    @router.get("/api/projects/{project_id}/export/html")
    def export_project_html(project_id: int) -> Response:
        init_db()
        with db() as conn:
            data = export_project_data(conn, project_id)
            p, m, intel = data["project"], data["metrics"], data["intelligence"]
            risks = data["risks"][:6]
            tasks = data["tasks"][:12]
            deliverables = data["deliverables"][:8]
            add_history(conn, project_id, "Exportación", p["name"], "HTML generado", "Reporte ejecutivo descargado")
            conn.commit()
        def esc(x: Any) -> str:
            return html.escape(str(x if x is not None else ""))
        html_doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Reporte {esc(p['name'])}</title>
        <style>body{{font-family:Arial,sans-serif;margin:32px;color:#0f172a}}.card{{border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin:12px 0}}h1{{color:#2563eb}}table{{border-collapse:collapse;width:100%;margin-top:10px}}td,th{{border-bottom:1px solid #e2e8f0;padding:8px;text-align:left}}.pill{{display:inline-block;padding:5px 10px;border-radius:999px;background:#eff6ff;color:#2563eb;font-weight:700}}</style></head><body>
        <h1>Reporte ejecutivo Proyecta360</h1><h2>{esc(p['name'])}</h2><p>{esc(p.get('description',''))}</p>
        <div class='card'><span class='pill'>{esc(m['health'])}</span><p><b>Avance:</b> {esc(m['progress'])}% | <b>Presupuesto ejecutado:</b> {esc(m['spent'])} de {esc(m['budget'])} {esc(p['currency'])} | <b>Riesgos altos:</b> {esc(m['high_risks'])}</p></div>
        <div class='card'><h3>Recomendaciones</h3><ul>{''.join(f'<li>{esc(x)}</li>' for x in intel.get('recommendations', []))}</ul></div>
        <div class='card'><h3>Actividades principales</h3><table><tr><th>Actividad</th><th>Responsable</th><th>Avance</th><th>Fecha fin</th></tr>{''.join(f'<tr><td>{esc(t["title"])}</td><td>{esc(t["owner"])}</td><td>{esc(t["progress"])}%</td><td>{esc(t["end_date"])}</td></tr>' for t in tasks)}</table></div>
        <div class='card'><h3>Riesgos</h3><table><tr><th>Riesgo</th><th>Nivel</th><th>Responsable</th><th>Respuesta</th></tr>{''.join(f'<tr><td>{esc(r["title"])}</td><td>{esc(r["level"])}</td><td>{esc(r["owner"])}</td><td>{esc(r["response"])}</td></tr>' for r in risks)}</table></div>
        <div class='card'><h3>Entregables y productos</h3><table><tr><th>Nombre</th><th>Tipo</th><th>Estado</th><th>Fecha</th></tr>{''.join(f'<tr><td>{esc(d["name"])}</td><td>{esc(d["deliverable_type"])}</td><td>{esc(d["status"])}</td><td>{esc(d["due_date"])}</td></tr>' for d in deliverables)}</table></div>
        <p><small>Generado automáticamente por Proyecta360 · {esc(datetime.utcnow().isoformat())}</small></p></body></html>"""
        filename = f"proyecta360_reporte_{project_id}.html"
        return Response(
            content=html_doc,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    

    return router


