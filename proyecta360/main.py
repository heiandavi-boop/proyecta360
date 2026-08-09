from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from proyecta360.app_factory import create_app
from proyecta360.core import config as app_config
from proyecta360.core.database import all_rows, connect, database_backend_from_url, deep_merge, dumps, iso_value, loads, one
from proyecta360.core.schema import create_schema, ensure_schema_columns
from proyecta360.core.security import hash_password, hash_token, password_needs_rehash, public_user, safe_filename, verify_password
from proyecta360.core.seed import ensure_mvp_data as seed_ensure_mvp_data
from proyecta360.core.seed import ensure_proyecta360_lac_strategic_framework
from proyecta360.core.seed import seed_database as seed_seed_database
from proyecta360.services import analytics as analytics_service
from proyecta360.services.domain import add_history, assert_component_in_project, assert_task_in_project
from proyecta360.services.domain import get_project_or_404, get_task_or_404, get_thread_or_404
from proyecta360.services.domain import risk_level, serialize_evidence, serialize_project, serialize_risk, validate_dependency
from proyecta360.services.project_schedule import critical_path_task_ids, normalize_task_dates, parse_iso, recalculate_project_schedule
from proyecta360.services.project_schedule import refresh_outline_levels, task_duration_days

BASE_DIR = app_config.BASE_DIR
DB_PATH = app_config.DB_PATH
DATABASE_URL = app_config.DATABASE_URL
APP_ENV = app_config.APP_ENV
UPLOAD_DIR = app_config.UPLOAD_DIR
MAX_UPLOAD_BYTES = app_config.MAX_UPLOAD_BYTES

DEFAULT_PARAMETERS = app_config.DEFAULT_PARAMETERS
SUPPORTED_CURRENCIES = app_config.SUPPORTED_CURRENCIES
DEPENDENCY_TYPES = app_config.DEPENDENCY_TYPES
TOKEN_TTL_MINUTES = app_config.ACCESS_TOKEN_EXPIRE_MINUTES
DEFAULT_ADMIN_PASSWORD = os.getenv("PROYECTA360_ADMIN_PASSWORD", "admin123")
DEFAULT_PM_PASSWORD = os.getenv("PROYECTA360_PM_PASSWORD", "demo123")
DEFAULT_READONLY_PASSWORD = os.getenv("PROYECTA360_READONLY_PASSWORD", "consulta123")

def db() -> Any:
    return connect(DB_PATH, DATABASE_URL)


def user_from_authorization(conn: Any, authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    scheme, _, raw_token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = raw_token.strip()
    if not token:
        return None
    token_digest = hash_token(token)
    user = one(conn, "SELECT * FROM users WHERE access_token_hash = ?", (token_digest,))
    if not user:
        return None
    expires_at = user.get("token_expires_at") or ""
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < datetime.utcnow():
                conn.execute("UPDATE users SET access_token = '', access_token_hash = '', token_expires_at = '' WHERE id = ?", (user["id"],))
                conn.commit()
                return None
        except ValueError:
            return None
    return user


def init_db() -> None:
    with db() as conn:
        create_schema(conn)
        ensure_schema_columns(conn)
        ensure_proyecta360_lac_strategic_framework(conn)
        if not one(conn, "SELECT id FROM users LIMIT 1"):
            conn.executemany(
                "INSERT INTO users (name, email, role, password_hash) VALUES (?, ?, ?, ?)",
                [
                    ("Administrador PMO", "admin@proyecta360.local", "Administrador", hash_password(DEFAULT_ADMIN_PASSWORD)),
                    ("Alejandra Trujillo", "alejandra@proyecta360.ai", "Project Manager", hash_password(DEFAULT_PM_PASSWORD)),
                    ("Equipo Consulta", "consulta@proyecta360.local", "Consulta", hash_password(DEFAULT_READONLY_PASSWORD)),
                ],
            )
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        conn.commit()


def context_label(conn: sqlite3.Connection, context_type: str, context_id: Optional[int]) -> str:
    if not context_id or context_type == "Proyecto":
        return "Proyecto"
    tables = {
        "Componente": ("components", "name"),
        "Actividad": ("tasks", "title"),
        "Riesgo": ("risks", "title"),
        "Entregable": ("deliverables", "name"),
    }
    table_info = tables.get(context_type)
    if not table_info:
        return context_type
    table, field = table_info
    row = one(conn, f"SELECT {field} AS label FROM {table} WHERE id = ?", (context_id,))
    return row["label"] if row else context_type


def project_intelligence(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    metrics = calculate_metrics(conn, project_id)
    risks = [serialize_risk(r) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? AND status != 'Cerrado' ORDER BY probability * impact DESC LIMIT 5", (project_id,))]
    milestones = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? AND task_type = 'milestone' ORDER BY end_date", (project_id,))
    deliverables = all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ? ORDER BY due_date, id", (project_id,))
    return analytics_service.project_intelligence(metrics, risks, milestones, deliverables)


def ensure_mvp_data(conn: sqlite3.Connection) -> None:
    seed_ensure_mvp_data(conn, add_history)


def calculate_metrics(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    p = get_project_or_404(conn, project_id)
    tasks = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ?", (project_id,))
    risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ?", (project_id,))
    stories = all_rows(conn, "SELECT * FROM stories WHERE project_id = ?", (project_id,))
    deps = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (project_id,))
    budget_entries = all_rows(conn, "SELECT * FROM budget_entries WHERE project_id = ? ORDER BY month, category, id", (project_id,))
    return analytics_service.calculate_metrics(p, tasks, risks, stories, deps, budget_entries)



def portfolio_summary(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    projects = all_rows(conn, "SELECT * FROM projects ORDER BY id")
    items: List[Dict[str, Any]] = []
    for p in projects:
        metrics = calculate_metrics(conn, int(p["id"]))
        items.append(analytics_service.portfolio_item(p, metrics))
    return items


def bootstrap_payload(conn: sqlite3.Connection, project_id: Optional[int] = None) -> Dict[str, Any]:
    if not one(conn, "SELECT id FROM projects LIMIT 1"):
        seed_database(conn)
    ensure_mvp_data(conn)
    projects = all_rows(conn, "SELECT * FROM projects ORDER BY id")
    selected = project_id or projects[0]["id"]
    current = get_project_or_404(conn, selected)
    tasks = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (selected,))
    dependencies = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (selected,))
    critical_ids = critical_path_task_ids(tasks, dependencies)
    for task in tasks:
        task["is_critical_path"] = bool(
            task["task_type"] != "summary"
            and task["id"] in critical_ids
            and int(task["progress"] or 0) < 100
        )
    return {
        "projects": [serialize_project(p) for p in projects],
        "portfolio": portfolio_summary(conn),
        "current_project": serialize_project(current),
        "tasks": tasks,
        "dependencies": dependencies,
        "sprints": all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date", (selected,)),
        "stories": all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (selected,)),
        "risks": [serialize_risk(r) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY id", (selected,))],
        "resources": all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (selected,)),
        "budget_entries": all_rows(conn, "SELECT * FROM budget_entries WHERE project_id = ? ORDER BY month, category, id", (selected,)),
        "components": all_rows(conn, "SELECT * FROM components WHERE project_id = ? ORDER BY id", (selected,)),
        "deliverables": all_rows(conn, "SELECT * FROM deliverables WHERE project_id = ? ORDER BY due_date, id", (selected,)),
        "evidences": [serialize_evidence(r) for r in all_rows(conn, "SELECT * FROM evidence_files WHERE project_id = ? ORDER BY created_at DESC, id DESC", (selected,))],
        "history": all_rows(conn, "SELECT * FROM change_log WHERE project_id = ? ORDER BY created_at DESC, id DESC LIMIT 40", (selected,)),
        "conversation_threads": all_rows(conn, "SELECT * FROM conversation_threads WHERE project_id = ? ORDER BY created_at DESC, id DESC", (selected,)),
        "conversation_messages": all_rows(conn, "SELECT * FROM conversation_messages WHERE project_id = ? ORDER BY created_at, id", (selected,)),
        "metrics": calculate_metrics(conn, selected),
        "intelligence": project_intelligence(conn, selected),
        "defaults": {**DEFAULT_PARAMETERS, "currencies": SUPPORTED_CURRENCIES, "dependency_types": sorted(DEPENDENCY_TYPES)},
    }


def seed_database(conn: sqlite3.Connection) -> None:
    seed_seed_database(conn, add_history, risk_level)


@asynccontextmanager
async def lifespan(_: Any):
    init_db()
    with db() as conn:
        seed_database(conn)
        ensure_mvp_data(conn)
        for row in all_rows(conn, "SELECT id FROM projects", ()): 
            refresh_outline_levels(conn, int(row["id"]))
            recalculate_project_schedule(conn, int(row["id"]))
        conn.commit()
    yield


def build_context() -> SimpleNamespace:
    return SimpleNamespace(
        add_history=add_history,
        all_rows=all_rows,
        APP_ENV=APP_ENV,
        assert_component_in_project=assert_component_in_project,
        assert_task_in_project=assert_task_in_project,
        BASE_DIR=BASE_DIR,
        bootstrap_payload=bootstrap_payload,
        calculate_metrics=calculate_metrics,
        context_label=context_label,
        DATABASE_BACKEND=database_backend_from_url(DATABASE_URL),
        db=db,
        deep_merge=deep_merge,
        DEFAULT_PARAMETERS=DEFAULT_PARAMETERS,
        dumps=dumps,
        get_project_or_404=get_project_or_404,
        get_task_or_404=get_task_or_404,
        get_thread_or_404=get_thread_or_404,
        hash_password=hash_password,
        hash_token=hash_token,
        init_db=init_db,
        iso_value=iso_value,
        loads=loads,
        MAX_UPLOAD_BYTES=MAX_UPLOAD_BYTES,
        normalize_task_dates=normalize_task_dates,
        one=one,
        parse_iso=parse_iso,
        portfolio_summary=portfolio_summary,
        project_intelligence=project_intelligence,
        public_user=public_user,
        recalculate_project_schedule=recalculate_project_schedule,
        refresh_outline_levels=refresh_outline_levels,
        risk_level=risk_level,
        safe_filename=safe_filename,
        seed_database=seed_database,
        serialize_evidence=serialize_evidence,
        serialize_project=serialize_project,
        serialize_risk=serialize_risk,
        task_duration_days=task_duration_days,
        UPLOAD_DIR=UPLOAD_DIR,
        user_from_authorization=user_from_authorization,
        validate_dependency=validate_dependency,
        verify_password=verify_password,
        password_needs_rehash=password_needs_rehash,
        TOKEN_TTL_MINUTES=TOKEN_TTL_MINUTES,
    )


app = create_app(
    base_dir=BASE_DIR,
    lifespan=lifespan,
    ctx=build_context(),
    db=db,
    user_from_authorization=user_from_authorization,
)



