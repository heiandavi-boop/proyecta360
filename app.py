from __future__ import annotations

import json
import os
import sqlite3
import hashlib
import hmac
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from proyecta360.api.routers import build_api_router
from proyecta360.core import config as app_config
from proyecta360.core.database import connect
from proyecta360.core.security import safe_filename as sanitize_filename
from proyecta360.services import analytics as analytics_service
from proyecta360.services import schedule as schedule_service

BASE_DIR = app_config.BASE_DIR
DB_PATH = app_config.DB_PATH
UPLOAD_DIR = app_config.UPLOAD_DIR
MAX_UPLOAD_BYTES = app_config.MAX_UPLOAD_BYTES

DEFAULT_PARAMETERS = app_config.DEFAULT_PARAMETERS
SUPPORTED_CURRENCIES = app_config.SUPPORTED_CURRENCIES
DEPENDENCY_TYPES = app_config.DEPENDENCY_TYPES
MUTATION_ROLES = {"Administrador", "Project Manager"}
READ_ROLES = {"Administrador", "Project Manager", "Consulta"}
PASSWORD_ITERATIONS = int(os.getenv("PROYECTA360_PASSWORD_ITERATIONS", "260000"))
TOKEN_TTL_HOURS = int(os.getenv("PROYECTA360_TOKEN_TTL_HOURS", "12"))
DEFAULT_ADMIN_PASSWORD = os.getenv("PROYECTA360_ADMIN_PASSWORD", "admin123")
DEFAULT_PM_PASSWORD = os.getenv("PROYECTA360_PM_PASSWORD", "demo123")
DEFAULT_READONLY_PASSWORD = os.getenv("PROYECTA360_READONLY_PASSWORD", "consulta123")

# ---------- DB helpers ----------
def db() -> sqlite3.Connection:
    return connect(DB_PATH)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def loads(value: Optional[str], default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def rowdict(row: sqlite3.Row | None) -> Dict[str, Any] | None:
    return dict(row) if row else None


def one(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> Dict[str, Any] | None:
    return rowdict(conn.execute(sql, args).fetchone())


def all_rows(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def iso_value(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = json.loads(dumps(base))
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def legacy_hash_password(password: str) -> str:
    return hashlib.sha256((password + "::proyecta360-demo").encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected = parts[3]
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
            return hmac.compare_digest(digest, expected)
        except Exception:
            return False
    return hmac.compare_digest(stored_hash, legacy_hash_password(password))


def password_needs_rehash(stored_hash: str) -> bool:
    parts = (stored_hash or "").split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return True
    try:
        return int(parts[1]) < PASSWORD_ITERATIONS
    except ValueError:
        return True


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(user: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


def user_from_authorization(conn: sqlite3.Connection, authorization: Optional[str]) -> Optional[Dict[str, Any]]:
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


def protected_api_request(path: str, method: str) -> bool:
    if not path.startswith("/api/"):
        return False
    if path in {"/api/auth/login", "/api/health"}:
        return False
    return True


def role_allowed(path: str, method: str, role: str) -> bool:
    if method == "GET":
        return role in READ_ROLES
    return role in MUTATION_ROLES


def safe_filename(filename: str) -> str:
    return sanitize_filename(filename)



def ensure_schema_columns(conn: sqlite3.Connection) -> None:
    def columns(table: str) -> set[str]:
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    project_cols = columns("projects")
    if "contractual_end_date" not in project_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN contractual_end_date TEXT DEFAULT ''")

    task_cols = columns("tasks")
    task_alters = {
        "component_id": "ALTER TABLE tasks ADD COLUMN component_id INTEGER REFERENCES components(id) ON DELETE SET NULL",
        "duration_days": "ALTER TABLE tasks ADD COLUMN duration_days INTEGER DEFAULT 1",
        "outline_level": "ALTER TABLE tasks ADD COLUMN outline_level INTEGER DEFAULT 0",
        "is_expanded": "ALTER TABLE tasks ADD COLUMN is_expanded INTEGER DEFAULT 1",
    }
    for name, ddl in task_alters.items():
        if name not in task_cols:
            conn.execute(ddl)

    dep_cols = columns("dependencies")
    if "lag_days" not in dep_cols:
        conn.execute("ALTER TABLE dependencies ADD COLUMN lag_days INTEGER DEFAULT 0")

    risk_cols = columns("risks")
    if "mitigation_plan" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN mitigation_plan TEXT DEFAULT ''")
    if "contingency_plan" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN contingency_plan TEXT DEFAULT ''")

    user_cols = columns("users")
    if "access_token_hash" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN access_token_hash TEXT DEFAULT ''")
    if "token_expires_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN token_expires_at TEXT DEFAULT ''")
    conn.execute("UPDATE users SET access_token = '' WHERE access_token != ''")


def parse_iso(value: str) -> date:
    return schedule_service.parse_iso(value)


def task_duration_days(start_value: str, end_value: str, task_type: str = "task") -> int:
    return schedule_service.task_duration_days(start_value, end_value, task_type)


def end_from_duration(start_value: date | str, duration_days: int, task_type: str = "task") -> date:
    return schedule_service.end_from_duration(start_value, duration_days, task_type)


def normalize_task_dates(start_value: Any, end_value: Any, duration_days: Optional[int], task_type: str) -> tuple[str, str, int]:
    return schedule_service.normalize_task_dates(start_value, end_value, duration_days, task_type, iso_value)


def recalculate_project_schedule(conn: sqlite3.Connection, project_id: int) -> None:
    """Calcula fechas de cronograma: duración + predecesoras + resumen por hijos."""
    rows = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (project_id,))
    if not rows:
        return
    tasks = {int(t["id"]): dict(t) for t in rows}
    deps = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ? ORDER BY id", (project_id,))

    # Normalizar duración base de tareas no resumen.
    for t in tasks.values():
        if t.get("task_type") == "summary":
            continue
        duration = int(t.get("duration_days") if t.get("duration_days") is not None else task_duration_days(t["start_date"], t["end_date"], t.get("task_type") or "task"))
        start_s, end_s, duration = normalize_task_dates(t.get("start_date"), t.get("end_date"), duration, t.get("task_type") or "task")
        t["start_date"], t["end_date"], t["duration_days"] = start_s, end_s, duration

    # Propagaci?n iterativa de dependencias.
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
            else:  # FS
                candidate = p_end + timedelta(days=lag + 1)
                if candidate > s_start:
                    new_start = candidate
                    new_end = end_from_duration(new_start, duration, succ.get("task_type") or "task")
            if new_start != s_start or new_end != s_end:
                succ["start_date"], succ["end_date"] = new_start.isoformat(), new_end.isoformat()
                changed = True
        if not changed:
            break

    # Calcular tareas resumen de abajo hacia arriba con base en hijos.
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
        total_duration = sum(max(0, int(k.get("duration_days") or task_duration_days(k["start_date"], k["end_date"], k.get("task_type") or "task"))) for k in kids) or len(kids)
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

    end_candidates = [parse_iso(t["end_date"]) for t in tasks.values()]
    project_end = max(end_candidates).isoformat()
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

def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                sponsor TEXT DEFAULT '',
                project_manager TEXT DEFAULT '',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                contractual_end_date TEXT DEFAULT '',
                methodology TEXT DEFAULT 'Híbrida PMP + Scrum',
                status TEXT DEFAULT 'En ejecución',
                budget REAL DEFAULT 0,
                currency TEXT DEFAULT 'COP',
                parameters_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                role TEXT DEFAULT '',
                email TEXT DEFAULT '',
                capacity INTEGER DEFAULT 100
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
                component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                phase TEXT DEFAULT 'Ejecución',
                task_type TEXT DEFAULT 'task',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                owner TEXT DEFAULT '',
                status TEXT DEFAULT 'Pendiente',
                story_points INTEGER DEFAULT 0,
                budget REAL DEFAULT 0,
                description TEXT DEFAULT '',
                order_index INTEGER DEFAULT 0,
                duration_days INTEGER DEFAULT 1,
                outline_level INTEGER DEFAULT 0,
                is_expanded INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                methodology TEXT DEFAULT 'Hibrida',
                owner TEXT DEFAULT '',
                objective TEXT DEFAULT '',
                progress INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                dependency_type TEXT DEFAULT 'FS',
                lag_days INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                goal TEXT DEFAULT '',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT DEFAULT 'Planeado',
                velocity INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                sprint_id INTEGER REFERENCES sprints(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'Por hacer',
                points INTEGER DEFAULT 0,
                assignee TEXT DEFAULT '',
                priority TEXT DEFAULT 'Media'
            );
            CREATE TABLE IF NOT EXISTS risks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                probability INTEGER DEFAULT 1,
                impact INTEGER DEFAULT 1,
                level TEXT DEFAULT 'Bajo',
                response TEXT DEFAULT '',
                mitigation_plan TEXT DEFAULT '',
                contingency_plan TEXT DEFAULT '',
                status TEXT DEFAULT 'Abierto',
                owner TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS deliverables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
                name TEXT NOT NULL,
                deliverable_type TEXT DEFAULT 'Entregable',
                status TEXT DEFAULT 'Planeado',
                owner TEXT DEFAULT '',
                due_date TEXT DEFAULT '',
                evidence_url TEXT DEFAULT '',
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT DEFAULT 'Sistema',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS conversation_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                context_type TEXT DEFAULT 'Proyecto',
                context_id INTEGER,
                category TEXT DEFAULT 'Seguimiento',
                status TEXT DEFAULT 'Abierta',
                created_by TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL REFERENCES conversation_threads(id) ON DELETE CASCADE,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                author TEXT DEFAULT '',
                message TEXT NOT NULL,
                mentions TEXT DEFAULT '',
                evidence_url TEXT DEFAULT '',
                message_type TEXT DEFAULT 'Comentario',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS evidence_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                entity_type TEXT DEFAULT 'Proyecto',
                entity_id INTEGER,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                content_type TEXT DEFAULT 'application/octet-stream',
                size_bytes INTEGER DEFAULT 0,
                uploaded_by TEXT DEFAULT 'Sistema',
                description TEXT DEFAULT '',
                file_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT DEFAULT 'Miembro',
                password_hash TEXT NOT NULL,
                access_token TEXT DEFAULT '',
                access_token_hash TEXT DEFAULT '',
                token_expires_at TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        ensure_schema_columns(conn)
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


# ---------- Serializers ----------
def serialize_project(p: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(p)
    out["parameters"] = loads(out.pop("parameters_json", "{}"), DEFAULT_PARAMETERS)
    return out


def serialize_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(evidence)
    out.pop("file_path", None)
    out.pop("stored_filename", None)
    out["download_url"] = f"/api/evidences/{out['id']}/download"
    return out


def risk_level(probability: int, impact: int, parameters: Optional[Dict[str, Any]] = None) -> str:
    params = parameters or DEFAULT_PARAMETERS
    score = probability * impact
    high = params.get("risk_matrix", {}).get("high_threshold", 15)
    medium = params.get("risk_matrix", {}).get("medium_threshold", 8)
    if score >= high:
        return "Alto"
    if score >= medium:
        return "Medio"
    return "Bajo"


def serialize_risk(r: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(r)
    out["score"] = int(out.get("probability") or 0) * int(out.get("impact") or 0)
    return out


def get_project_or_404(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    p = one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return p


def get_task_or_404(conn: sqlite3.Connection, task_id: int) -> Dict[str, Any]:
    task = one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return task


def assert_task_in_project(conn: sqlite3.Connection, task_id: int, project_id: int, label: str = "Tarea") -> Dict[str, Any]:
    task = get_task_or_404(conn, task_id)
    if task["project_id"] != project_id:
        raise HTTPException(status_code=400, detail=f"{label} no pertenece al proyecto")
    return task


def dependency_creates_cycle(conn: sqlite3.Connection, project_id: int, predecessor_id: int, successor_id: int) -> bool:
    stack = [successor_id]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if current == predecessor_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        rows = all_rows(conn, "SELECT successor_id FROM dependencies WHERE project_id = ? AND predecessor_id = ?", (project_id, current))
        stack.extend(int(r["successor_id"]) for r in rows)
    return False


def validate_dependency(conn: sqlite3.Connection, project_id: int, predecessor_id: int, successor_id: int) -> None:
    if predecessor_id == successor_id:
        raise HTTPException(status_code=400, detail="Una tarea no puede depender de sí misma")
    assert_task_in_project(conn, predecessor_id, project_id, "La tarea predecesora")
    assert_task_in_project(conn, successor_id, project_id, "La tarea sucesora")
    if dependency_creates_cycle(conn, project_id, predecessor_id, successor_id):
        raise HTTPException(status_code=400, detail="La dependencia genera un ciclo")


def assert_component_in_project(conn: sqlite3.Connection, component_id: int, project_id: int) -> Dict[str, Any]:
    component = one(conn, "SELECT * FROM components WHERE id = ?", (component_id,))
    if not component:
        raise HTTPException(status_code=404, detail="Componente no encontrado")
    if component["project_id"] != project_id:
        raise HTTPException(status_code=400, detail="El componente no pertenece al proyecto")
    return component


def add_history(conn: sqlite3.Connection, project_id: int, entity_type: str, entity_name: str, action: str, notes: str = "", actor: str = "Sistema") -> None:
    conn.execute(
        "INSERT INTO change_log (project_id, entity_type, entity_name, action, notes, actor) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, entity_type, entity_name, action, notes, actor),
    )


def get_thread_or_404(conn: sqlite3.Connection, thread_id: int) -> Dict[str, Any]:
    thread = one(conn, "SELECT * FROM conversation_threads WHERE id = ?", (thread_id,))
    if not thread:
        raise HTTPException(status_code=404, detail="Conversacion no encontrada")
    return thread


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
    projects = all_rows(conn, "SELECT * FROM projects ORDER BY id")
    for project in projects:
        project_id = project["id"]
        if project["name"] == "Plataforma Cliente 360":
            conn.execute(
                """UPDATE projects
                   SET name = ?, description = ?, sponsor = ?, project_manager = ?, methodology = ?
                   WHERE id = ?""",
                (
                    "Proyecta360 LAC",
                    "Plataforma para la gestion integral de proyectos financiados y productos de conocimiento en investigacion, innovacion y cooperacion internacional.",
                    "Universidad / Cooperante LAC",
                    "Alejandra Trujillo",
                    "Hibrida por componentes",
                    project_id,
                ),
            )
            project = one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,)) or project
        if not one(conn, "SELECT id FROM components WHERE project_id = ? LIMIT 1", (project_id,)):
            defaults = [
                ("Componente cientifico", "Tradicional", project["project_manager"] or "Responsable cientifico", "Gestionar hitos y resultados cientificos", 0),
                ("Componente tecnologico", "Scrum", "Equipo tecnologico", "Construir y validar la plataforma web", 0),
                ("Componente administrativo", "Tradicional", project["sponsor"] or "Administrador de fondos", "Gestionar fondos, soportes y financiador", 0),
                ("Componente divulgacion", "Kanban", "Equipo divulgacion", "Publicar productos de conocimiento", 0),
            ]
            component_ids = []
            for item in defaults:
                cur = conn.execute(
                    "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, *item),
                )
                component_ids.append(cur.lastrowid)
            phases = {"Inicio": component_ids[2], "Planeación": component_ids[2], "Ejecución": component_ids[1], "Pruebas": component_ids[1], "Cierre": component_ids[3]}
            for task in all_rows(conn, "SELECT id, phase FROM tasks WHERE project_id = ?", (project_id,)):
                conn.execute("UPDATE tasks SET component_id = ? WHERE id = ? AND component_id IS NULL", (phases.get(task["phase"], component_ids[0]), task["id"]))
            add_history(conn, project_id, "Proyecto", project["name"], "Actualizado", "Backfill MVP: componentes por metodologia y fuente unica de informacion.")
        if not one(conn, "SELECT id FROM deliverables WHERE project_id = ? LIMIT 1", (project_id,)):
            components = all_rows(conn, "SELECT * FROM components WHERE project_id = ? ORDER BY id", (project_id,))
            component_lookup = {c["name"]: c["id"] for c in components}
            base = date.fromisoformat(project["start_date"])
            deliverables = [
                (component_lookup.get("Componente cientifico"), "Protocolo o resultado cientifico", "Producto de conocimiento", "Planeado", base + timedelta(days=35)),
                (component_lookup.get("Componente tecnologico"), "MVP web operativo", "Entregable", "Planeado", base + timedelta(days=70)),
                (component_lookup.get("Componente administrativo"), "Soporte de presupuesto y fondos", "Evidencia", "Planeado", base + timedelta(days=45)),
                (component_lookup.get("Componente divulgacion"), "Informe ejecutivo mensual", "Informe", "Planeado", base + timedelta(days=60)),
            ]
            conn.executemany(
                """INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, due_date, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(project_id, cid, name, dtype, status, due.isoformat(), "Registro inicial alineado al MVP.") for cid, name, dtype, status, due in deliverables],
            )
        if not one(conn, "SELECT id FROM conversation_threads WHERE project_id = ? LIMIT 1", (project_id,)):
            first_component = one(conn, "SELECT id, name FROM components WHERE project_id = ? ORDER BY id LIMIT 1", (project_id,))
            first_risk = one(conn, "SELECT id, title FROM risks WHERE project_id = ? ORDER BY probability * impact DESC, id LIMIT 1", (project_id,))
            first_deliverable = one(conn, "SELECT id, name FROM deliverables WHERE project_id = ? ORDER BY due_date, id LIMIT 1", (project_id,))
            thread_specs = [
                ("Seguimiento general del proyecto", "Proyecto", None, "Seguimiento", "Aqui se centralizan acuerdos, bloqueos y decisiones para evitar conversaciones dispersas."),
            ]
            if first_component:
                thread_specs.append((f"Coordinacion: {first_component['name']}", "Componente", first_component["id"], "Acuerdo", "Alinear metodologia, responsables y avances del componente."))
            if first_risk:
                thread_specs.append((f"Plan de contingencia: {first_risk['title']}", "Riesgo", first_risk["id"], "Bloqueo", "Registrar decisiones y acciones frente al riesgo principal."))
            if first_deliverable:
                thread_specs.append((f"Evidencia: {first_deliverable['name']}", "Entregable", first_deliverable["id"], "Seguimiento", "Conservar enlaces, soportes y comentarios del producto."))
            for title, context_type, context_id, category, message in thread_specs:
                cur = conn.execute(
                    """INSERT INTO conversation_threads (project_id, title, context_type, context_id, category, created_by)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (project_id, title, context_type, context_id, category, "Sistema"),
                )
                conn.execute(
                    """INSERT INTO conversation_messages (thread_id, project_id, author, message, message_type)
                       VALUES (?, ?, ?, ?, ?)""",
                    (cur.lastrowid, project_id, "Sistema", message, "Comentario"),
                )
    conn.commit()


def calculate_metrics(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    p = get_project_or_404(conn, project_id)
    tasks = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ?", (project_id,))
    risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ?", (project_id,))
    stories = all_rows(conn, "SELECT * FROM stories WHERE project_id = ?", (project_id,))
    deps = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (project_id,))
    return analytics_service.calculate_metrics(p, tasks, risks, stories, deps)



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
    return {
        "projects": [serialize_project(p) for p in projects],
        "portfolio": portfolio_summary(conn),
        "current_project": serialize_project(current),
        "tasks": all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (selected,)),
        "dependencies": all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (selected,)),
        "sprints": all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date", (selected,)),
        "stories": all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (selected,)),
        "risks": [serialize_risk(r) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY id", (selected,))],
        "resources": all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (selected,)),
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


# ---------- Seed ----------
def seed_database(conn: sqlite3.Connection) -> None:
    if one(conn, "SELECT id FROM projects LIMIT 1"):
        return
    start = date(2026, 7, 1)
    end = date(2026, 10, 15)
    cur = conn.execute(
        """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, methodology, status, budget, currency, parameters_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Proyecta360 LAC",
            "Plataforma para la gestion integral de proyectos financiados y productos de conocimiento en investigacion, innovacion y cooperacion internacional.",
            "Universidad / Cooperante LAC",
            "Alejandra Trujillo",
            start.isoformat(),
            end.isoformat(),
            "Hibrida por componentes",
            "En ejecución",
            125000000,
            "COP",
            dumps(DEFAULT_PARAMETERS),
        ),
    )
    project_id = cur.lastrowid
    people = [
        ("Alejandra Trujillo", "Gestora del proyecto", "alejandra@proyecta360.ai", 80),
        ("Investigador principal", "Componente cientifico", "investigacion@proyecta360.ai", 75),
        ("Equipo tecnologico", "Scrum / desarrollo", "tech@proyecta360.ai", 90),
        ("Administrador de fondos", "Finanzas y cooperacion", "fondos@proyecta360.ai", 70),
        ("Equipo divulgacion", "Productos de conocimiento", "divulgacion@proyecta360.ai", 85),
        ("PMO regional", "Gobierno y seguimiento", "pmo@proyecta360.ai", 60),
    ]
    conn.executemany("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", [(project_id, *p) for p in people])

    components = [
        ("Componente cientifico", "Tradicional", "Investigador principal", "Gestionar protocolo, hitos de investigacion y resultados cientificos", 55),
        ("Componente tecnologico", "Scrum", "Equipo tecnologico", "Construir la plataforma web asistida por IA", 48),
        ("Componente administrativo", "Tradicional", "Administrador de fondos", "Administrar presupuesto, financiador y soportes", 42),
        ("Componente divulgacion", "Kanban", "Equipo divulgacion", "Publicar entregables y productos de conocimiento", 35),
    ]
    component_ids: List[int] = []
    for c in components:
        cur = conn.execute(
            "INSERT INTO components (project_id, name, methodology, owner, objective, progress) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, *c),
        )
        component_ids.append(cur.lastrowid)

    rows = [
        ("Acta de constitución", "Inicio", "task", start, start + timedelta(days=3), 100, "Ana López", "Completada", 0, 4000000),
        ("Identificación de interesados", "Inicio", "task", start + timedelta(days=2), start + timedelta(days=7), 100, "Ana López", "Completada", 0, 3000000),
        ("Alcance preliminar", "Inicio", "task", start + timedelta(days=6), start + timedelta(days=10), 100, "Ana López", "Completada", 0, 2500000),
        ("Plan de gestión del proyecto", "Planeación", "task", start + timedelta(days=8), start + timedelta(days=18), 100, "Carlos Méndez", "Completada", 0, 6500000),
        ("Plan de alcance", "Planeación", "task", start + timedelta(days=14), start + timedelta(days=24), 85, "Carlos Méndez", "En progreso", 0, 5000000),
        ("Plan de tiempo / cronograma", "Planeación", "task", start + timedelta(days=20), start + timedelta(days=33), 80, "María González", "En progreso", 0, 7000000),
        ("Plan de costos", "Planeación", "task", start + timedelta(days=25), start + timedelta(days=37), 60, "Jorge Ramírez", "En progreso", 0, 4500000),
        ("Aprobación del plan", "Planeación", "milestone", start + timedelta(days=39), start + timedelta(days=39), 0, "Comité de Dirección", "Pendiente", 0, 0),
        ("Sprint 1 - Configuración inicial", "Ejecución", "task", start + timedelta(days=42), start + timedelta(days=55), 100, "Equipo Dev", "Completada", 21, 14500000),
        ("Sprint 2 - Módulo de Clientes", "Ejecución", "task", start + timedelta(days=56), start + timedelta(days=69), 65, "Equipo Dev", "En progreso", 34, 16000000),
        ("Sprint 3 - Integraciones", "Ejecución", "task", start + timedelta(days=70), start + timedelta(days=83), 20, "Equipo Dev", "En progreso", 34, 17000000),
        ("Sprint 4 - Reportes", "Ejecución", "task", start + timedelta(days=84), start + timedelta(days=97), 0, "Equipo Dev", "Pendiente", 28, 12000000),
        ("Pruebas funcionales", "Pruebas", "task", start + timedelta(days=88), start + timedelta(days=101), 30, "QA Team", "En progreso", 0, 9000000),
        ("Pruebas de integración", "Pruebas", "task", start + timedelta(days=98), start + timedelta(days=107), 10, "QA Team", "Pendiente", 0, 7000000),
        ("Pruebas de aceptación UAT", "Pruebas", "milestone", start + timedelta(days=108), start + timedelta(days=108), 0, "Usuarios Clave", "Pendiente", 0, 0),
        ("Despliegue a producción", "Cierre", "task", start + timedelta(days=110), start + timedelta(days=114), 0, "DevOps", "Pendiente", 0, 8000000),
        ("Cierre administrativo", "Cierre", "task", start + timedelta(days=115), start + timedelta(days=120), 0, "Carlos Méndez", "Pendiente", 0, 3000000),
        ("Lecciones aprendidas", "Cierre", "milestone", start + timedelta(days=121), start + timedelta(days=121), 0, "Carlos Méndez", "Pendiente", 0, 0),
    ]
    task_ids: List[int] = []
    for idx, row in enumerate(rows, start=1):
        cur = conn.execute(
            """INSERT INTO tasks (project_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, order_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, row[0], row[1], row[2], row[3].isoformat(), row[4].isoformat(), row[5], row[6], row[7], row[8], row[9], idx),
        )
        task_ids.append(cur.lastrowid)
    component_by_phase = {
        "Inicio": component_ids[2],
        "Planeación": component_ids[2],
        "Ejecución": component_ids[1],
        "Pruebas": component_ids[1],
        "Cierre": component_ids[3],
    }
    for task_id, row in zip(task_ids, rows):
        conn.execute("UPDATE tasks SET component_id = ? WHERE id = ?", (component_by_phase.get(row[1], component_ids[0]), task_id))
    dep_pairs = [(3, 4), (6, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (17, 18)]
    conn.executemany("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", [(project_id, task_ids[a-1], task_ids[b-1]) for a, b in dep_pairs])

    sprints = [
        ("Sprint 1 - Configuración inicial", "Preparar arquitectura base y pipeline", start + timedelta(days=42), start + timedelta(days=55), "Cerrado", 28),
        ("Sprint 2 - Módulo de Clientes", "Entregar gestión base de clientes", start + timedelta(days=56), start + timedelta(days=69), "En curso", 34),
        ("Sprint 3 - Integraciones", "Conectar APIs y servicios externos", start + timedelta(days=70), start + timedelta(days=83), "Planeado", 34),
    ]
    sprint_ids: List[int] = []
    for s in sprints:
        cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (project_id, s[0], s[1], s[2].isoformat(), s[3].isoformat(), s[4], s[5]))
        sprint_ids.append(cur.lastrowid)
    stories = [
        (sprint_ids[1], "US-21 Listado de clientes", "En progreso", 5, "María González", "Alta"),
        (sprint_ids[1], "US-22 Ficha de cliente", "En progreso", 8, "Equipo Dev", "Alta"),
        (sprint_ids[1], "US-23 Búsqueda avanzada", "En progreso", 5, "Equipo Dev", "Media"),
        (sprint_ids[1], "US-24 Validar datos de cliente", "Por hacer", 5, "QA Team", "Media"),
        (sprint_ids[1], "US-25 Carga masiva de clientes", "Por hacer", 8, "Equipo Dev", "Alta"),
        (sprint_ids[1], "US-26 Exportar reportes", "Por hacer", 5, "Equipo Dev", "Media"),
        (sprint_ids[0], "US-17 Configuración inicial", "Hecho", 3, "DevOps", "Alta"),
        (sprint_ids[0], "US-18 Modelos de datos", "Hecho", 8, "María González", "Alta"),
        (sprint_ids[0], "US-19 Servicios API", "Hecho", 8, "Equipo Dev", "Alta"),
    ]
    conn.executemany("INSERT INTO stories (project_id, sprint_id, title, status, points, assignee, priority) VALUES (?, ?, ?, ?, ?, ?, ?)", [(project_id, *s) for s in stories])
    risks = [
        ("Retraso por dependencias de integración", 4, 4, "Asegurar APIs tempranas y ambiente de pruebas", "Abierto", "María González"),
        ("Capacidad limitada de QA", 3, 4, "Priorizar pruebas críticas y automatizar regresión", "Abierto", "QA Team"),
        ("Cambios de alcance no controlados", 3, 3, "Activar comit? de cambios y backlog grooming", "Abierto", "Carlos Méndez"),
        ("Aprobación tardía del sponsor", 2, 4, "Agendar stage gates desde la planeaci?n", "Mitigado", "Ana López"),
    ]
    conn.executemany("INSERT INTO risks (project_id, title, probability, impact, level, response, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(project_id, title, prob, impact, risk_level(prob, impact), response, status, owner) for title, prob, impact, response, status, owner in risks])
    deliverables = [
        (component_ids[0], "Protocolo de investigacion validado", "Producto de conocimiento", "En revision", "Investigador principal", start + timedelta(days=35), "https://evidencias.local/protocolo", "Documento base del componente cientifico."),
        (component_ids[1], "MVP web Proyecta360", "Entregable", "En progreso", "Equipo tecnologico", start + timedelta(days=80), "https://evidencias.local/mvp", "Plataforma web con gestion hibrida, riesgos y reportes."),
        (component_ids[2], "Matriz de presupuesto y financiador", "Evidencia", "En progreso", "Administrador de fondos", start + timedelta(days=45), "https://evidencias.local/presupuesto", "Soporte para administracion de fondos del proyecto."),
        (component_ids[3], "Resumen ejecutivo mensual", "Producto de conocimiento", "Planeado", "Equipo divulgacion", start + timedelta(days=60), "", "Informe para financiadores y direccion."),
    ]
    conn.executemany(
        """INSERT INTO deliverables (project_id, component_id, name, deliverable_type, status, owner, due_date, evidence_url, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(project_id, component_id, name, dtype, status, owner, due.isoformat(), url, desc) for component_id, name, dtype, status, owner, due, url, desc in deliverables],
    )
    add_history(conn, project_id, "Proyecto", "Proyecta360 LAC", "Creado", "Seed alineado al MVP: componentes, fondos, riesgos, hitos y productos de conocimiento.")
    add_history(conn, project_id, "Documento", "MVP.docx", "Analizado", "Dolor: informacion dispersa; respuesta: fuente unica de avance, riesgos, presupuesto, hitos y resultados.")
    conn.commit()


def cors_origins() -> List[str]:
    raw = os.getenv("PROYECTA360_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
    return [origin.strip() for origin in raw.split(",") if origin.strip() and origin.strip() != "*"]


def add_security_headers(response, api_response: bool = False):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cache-Control", "no-store" if api_response else "no-cache")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with db() as conn:
        seed_database(conn)
        ensure_mvp_data(conn)
        for row in all_rows(conn, "SELECT id FROM projects", ()): 
            refresh_outline_levels(conn, int(row["id"]))
            recalculate_project_schedule(conn, int(row["id"]))
        conn.commit()
    yield


# ---------- API ----------
docs_enabled = os.getenv("PROYECTA360_ENABLE_DOCS", "").lower() in {"1", "true", "yes"}
app = FastAPI(
    title="Proyecta360 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def enforce_api_authorization(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()
    if protected_api_request(path, method):
        authorization = request.headers.get("Authorization")
        with db() as conn:
            user = user_from_authorization(conn, authorization)
        if not user:
            return add_security_headers(JSONResponse(status_code=401, content={"detail": "Sesion requerida"}), True)
        if not role_allowed(path, method, user["role"]):
            return add_security_headers(JSONResponse(status_code=403, content={"detail": "Permisos insuficientes"}), True)
    response = await call_next(request)
    return add_security_headers(response, path.startswith("/api/"))


app.include_router(build_api_router(SimpleNamespace(
    add_history=add_history,
    all_rows=all_rows,
    assert_component_in_project=assert_component_in_project,
    assert_task_in_project=assert_task_in_project,
    bootstrap_payload=bootstrap_payload,
    calculate_metrics=calculate_metrics,
    context_label=context_label,
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
    TOKEN_TTL_HOURS=TOKEN_TTL_HOURS,
)))


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")



