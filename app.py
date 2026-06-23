from __future__ import annotations

import json
import math
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("PROYECTA360_DB", BASE_DIR / "proyecta360.db"))

DEFAULT_PARAMETERS: Dict[str, Any] = {
    "control_model": "PMP para gobierno y control + Scrum para desarrollo",
    "execution_methodologies": ["Scrum", "Kanban", "Tradicional", "Híbrida", "XP", "Lean"],
    "selected_execution_methodology": "Scrum",
    "calendar": {
        "working_days": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
        "workday_start": "08:00",
        "workday_end": "17:00",
        "timezone": "America/Bogota",
    },
    "phases": ["Inicio", "Planeación", "Ejecución", "Pruebas", "Cierre"],
    "task_statuses": ["Pendiente", "En progreso", "Bloqueada", "Completada"],
    "story_statuses": ["Por hacer", "En progreso", "Hecho"],
    "sprint": {"duration_days": 14, "story_point_scale": [1, 2, 3, 5, 8, 13]},
    "risk_matrix": {
        "probability_scale": [1, 2, 3, 4, 5],
        "impact_scale": [1, 2, 3, 4, 5],
        "high_threshold": 15,
        "medium_threshold": 8,
    },
    "governance": {
        "critical_path_enabled": True,
        "budget_control_enabled": True,
        "weekly_status_report": True,
        "stage_gate_approval": True,
    },
    "ai": {
        "enabled": False,
        "provider": "OpenAI / Azure OpenAI",
        "model": "configurable",
        "use_project_documents": True,
        "allow_create_tasks": True,
        "allow_create_risks": True,
    },
}

# Explicit allow-lists for the dynamic UPDATE builders. Column names are
# interpolated into SQL, so they must never come from arbitrary input — only
# from these sets. Keys outside the set fail loud instead of writing silently.
PROJECT_UPDATE_COLUMNS = {
    "name", "description", "sponsor", "project_manager", "start_date", "end_date",
    "methodology", "status", "budget", "currency", "parameters_json",
}
TASK_UPDATE_COLUMNS = {
    "title", "phase", "task_type", "start_date", "end_date", "progress", "owner",
    "status", "story_points", "budget", "description", "order_index",
}
STORY_UPDATE_COLUMNS = {
    "project_id", "sprint_id", "title", "status", "points", "assignee", "priority",
}

# ---------- DB helpers ----------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
                order_index INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                dependency_type TEXT DEFAULT 'FS'
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
                status TEXT DEFAULT 'Abierto',
                owner TEXT DEFAULT ''
            );

            -- Secondary indexes: every per-project query filters by project_id,
            -- and the dependency graph / hierarchy traversals filter by edges.
            CREATE INDEX IF NOT EXISTS idx_resources_project ON resources(project_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
            CREATE INDEX IF NOT EXISTS idx_dependencies_project ON dependencies(project_id);
            CREATE INDEX IF NOT EXISTS idx_dependencies_pred ON dependencies(project_id, predecessor_id);
            CREATE INDEX IF NOT EXISTS idx_dependencies_succ ON dependencies(project_id, successor_id);
            CREATE INDEX IF NOT EXISTS idx_sprints_project ON sprints(project_id);
            CREATE INDEX IF NOT EXISTS idx_stories_project ON stories(project_id);
            CREATE INDEX IF NOT EXISTS idx_stories_sprint ON stories(sprint_id);
            CREATE INDEX IF NOT EXISTS idx_risks_project ON risks(project_id);
            """
        )
        conn.commit()


# ---------- Schemas ----------
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    sponsor: str = ""
    project_manager: str = ""
    start_date: date
    end_date: date
    methodology: str = "Híbrida PMP + Scrum"
    status: str = "En ejecución"
    budget: float = Field(default=0, ge=0)
    currency: str = Field(default="COP", min_length=1, max_length=8)
    parameters: Dict[str, Any] = Field(default_factory=lambda: json.loads(dumps(DEFAULT_PARAMETERS)))

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectIn":
        if self.end_date < self.start_date:
            raise ValueError("La fecha fin no puede ser menor a la fecha inicio")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = None
    sponsor: Optional[str] = None
    project_manager: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    methodology: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=8)
    parameters: Optional[Dict[str, Any]] = None


class TaskIn(BaseModel):
    project_id: int
    parent_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=220)
    phase: str = "Ejecución"
    task_type: str = "task"
    start_date: date
    end_date: date
    progress: int = Field(default=0, ge=0, le=100)
    owner: str = ""
    status: str = "Pendiente"
    story_points: int = Field(default=0, ge=0)
    budget: float = Field(default=0, ge=0)
    description: str = ""
    order_index: int = Field(default=0, ge=0)
    predecessor_id: Optional[int] = None

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        if value not in {"task", "milestone", "summary"}:
            raise ValueError("Tipo de tarea inválido")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "TaskIn":
        if self.end_date < self.start_date:
            raise ValueError("La fecha fin no puede ser menor a la fecha inicio")
        return self


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=220)
    phase: Optional[str] = None
    task_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    owner: Optional[str] = None
    status: Optional[str] = None
    story_points: Optional[int] = Field(default=None, ge=0)
    budget: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    order_index: Optional[int] = Field(default=None, ge=0)

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"task", "milestone", "summary"}:
            raise ValueError("Tipo de tarea inválido")
        return value


class DependencyIn(BaseModel):
    project_id: int
    predecessor_id: int
    successor_id: int
    dependency_type: str = "FS"


class SprintIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=160)
    goal: str = ""
    start_date: date
    end_date: date
    status: str = "Planeado"
    velocity: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_dates(self) -> "SprintIn":
        if self.end_date < self.start_date:
            raise ValueError("La fecha fin no puede ser menor a la fecha inicio")
        return self


class StoryIn(BaseModel):
    project_id: int
    sprint_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=220)
    status: str = "Por hacer"
    points: int = Field(default=0, ge=0)
    assignee: str = ""
    priority: str = "Media"


class StoryUpdate(BaseModel):
    project_id: Optional[int] = None
    sprint_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=220)
    status: Optional[str] = None
    points: Optional[int] = Field(default=None, ge=0)
    assignee: Optional[str] = None
    priority: Optional[str] = None


class RiskIn(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=220)
    probability: int = Field(default=1, ge=1, le=5)
    impact: int = Field(default=1, ge=1, le=5)
    response: str = ""
    status: str = "Abierto"
    owner: str = ""


class ResourceIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=160)
    role: str = ""
    email: str = ""
    capacity: int = Field(default=100, ge=0, le=100)


class AiPlanIn(BaseModel):
    project_id: int
    objective: str = Field(min_length=1, max_length=1200)
    execution_methodology: str = "Scrum"
    horizon_weeks: int = Field(default=12, ge=4, le=52)
    create_records: bool = True


class AiReportIn(BaseModel):
    project_id: int
    audience: str = "Comité Directivo"


# ---------- Serializers ----------
def serialize_project(p: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(p)
    out["parameters"] = loads(out.pop("parameters_json", "{}"), DEFAULT_PARAMETERS)
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


def calculate_metrics(conn: sqlite3.Connection, project_id: int) -> Dict[str, Any]:
    p = get_project_or_404(conn, project_id)
    tasks = all_rows(conn, "SELECT * FROM tasks WHERE project_id = ?", (project_id,))
    risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ?", (project_id,))
    stories = all_rows(conn, "SELECT * FROM stories WHERE project_id = ?", (project_id,))
    deps = all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (project_id,))
    work_tasks = [t for t in tasks if t["task_type"] != "summary"]
    progress = round(sum(int(t["progress"] or 0) for t in work_tasks) / len(work_tasks), 1) if work_tasks else 0
    spent = round(sum(float(t["budget"] or 0) * int(t["progress"] or 0) / 100 for t in work_tasks), 2)
    high_risks = len([r for r in risks if r["level"] == "Alto" and r["status"] != "Cerrado"])
    open_risks = len([r for r in risks if r["status"] != "Cerrado"])
    completed_points = sum(int(s["points"] or 0) for s in stories if s["status"] == "Hecho")
    total_points = sum(int(s["points"] or 0) for s in stories) or 1
    today = date.today().isoformat()
    delayed_tasks = [t for t in work_tasks if t["end_date"] < today and int(t["progress"] or 0) < 100 and t["task_type"] != "milestone"]
    critical_ids = set()
    for d in deps:
        critical_ids.add(d["predecessor_id"])
        critical_ids.add(d["successor_id"])
    critical_open = [t for t in work_tasks if t["id"] in critical_ids and int(t["progress"] or 0) < 100]
    health = "Saludable"
    if high_risks >= 2 or len(delayed_tasks) >= 3:
        health = "En riesgo"
    if high_risks >= 4 or len(delayed_tasks) >= 6:
        health = "Crítico"
    return {
        "progress": progress,
        "budget": float(p["budget"] or 0),
        "spent": spent,
        "remaining_budget": max(float(p["budget"] or 0) - spent, 0),
        "open_risks": open_risks,
        "high_risks": high_risks,
        "critical_path_tasks": len(critical_open),
        "delayed_tasks": len(delayed_tasks),
        "story_completion": round(completed_points / total_points * 100, 1),
        "health": health,
    }


def bootstrap_payload(conn: sqlite3.Connection, project_id: Optional[int] = None) -> Dict[str, Any]:
    projects = all_rows(conn, "SELECT * FROM projects ORDER BY id")
    if not projects:
        # Seeding happens once at startup (lifespan). A normal GET must never
        # write demo data; return an empty-but-valid payload instead of crashing.
        return {
            "projects": [],
            "current_project": None,
            "tasks": [],
            "dependencies": [],
            "sprints": [],
            "stories": [],
            "risks": [],
            "resources": [],
            "metrics": {},
            "defaults": DEFAULT_PARAMETERS,
        }
    selected = project_id or projects[0]["id"]
    current = get_project_or_404(conn, selected)
    return {
        "projects": [serialize_project(p) for p in projects],
        "current_project": serialize_project(current),
        "tasks": all_rows(conn, "SELECT * FROM tasks WHERE project_id = ? ORDER BY order_index, id", (selected,)),
        "dependencies": all_rows(conn, "SELECT * FROM dependencies WHERE project_id = ?", (selected,)),
        "sprints": all_rows(conn, "SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date", (selected,)),
        "stories": all_rows(conn, "SELECT * FROM stories WHERE project_id = ? ORDER BY id", (selected,)),
        "risks": [serialize_risk(r) for r in all_rows(conn, "SELECT * FROM risks WHERE project_id = ? ORDER BY id", (selected,))],
        "resources": all_rows(conn, "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (selected,)),
        "metrics": calculate_metrics(conn, selected),
        "defaults": DEFAULT_PARAMETERS,
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
            "Plataforma Cliente 360",
            "Implementación de una solución empresarial con control PMP y ejecución Scrum.",
            "Comité de Dirección",
            "Carlos Méndez",
            start.isoformat(),
            end.isoformat(),
            "Híbrida PMP + Scrum",
            "En ejecución",
            125000000,
            "COP",
            dumps(DEFAULT_PARAMETERS),
        ),
    )
    project_id = cur.lastrowid
    people = [
        ("Ana López", "Project Manager", "ana@empresa.com", 80),
        ("Carlos Méndez", "PMO Director", "carlos@empresa.com", 70),
        ("María González", "Líder Técnica", "maria@empresa.com", 100),
        ("Equipo Dev", "Desarrollo", "dev@empresa.com", 100),
        ("QA Team", "Calidad", "qa@empresa.com", 90),
        ("DevOps", "Infraestructura", "devops@empresa.com", 60),
    ]
    conn.executemany("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", [(project_id, *p) for p in people])

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
        ("Cambios de alcance no controlados", 3, 3, "Activar comité de cambios y backlog grooming", "Abierto", "Carlos Méndez"),
        ("Aprobación tardía del sponsor", 2, 4, "Agendar stage gates desde la planeación", "Mitigado", "Ana López"),
    ]
    conn.executemany("INSERT INTO risks (project_id, title, probability, impact, level, response, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(project_id, title, prob, impact, risk_level(prob, impact), response, status, owner) for title, prob, impact, response, status, owner in risks])
    conn.commit()


def cors_origins() -> List[str]:
    raw = os.getenv("PROYECTA360_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with db() as conn:
        seed_database(conn)
    yield


# ---------- API ----------
app = FastAPI(title="Proyecta360 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "app": "Proyecta360", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/bootstrap")
def bootstrap(project_id: Optional[int] = None) -> Dict[str, Any]:
    with db() as conn:
        return bootstrap_payload(conn, project_id)


@app.post("/api/seed")
def seed() -> Dict[str, str]:
    with db() as conn:
        seed_database(conn)
    return {"message": "Datos base cargados"}


@app.post("/api/projects")
def create_project(payload: ProjectIn) -> Dict[str, Any]:
    with db() as conn:
        parameters = deep_merge(DEFAULT_PARAMETERS, payload.parameters)
        cur = conn.execute(
            """INSERT INTO projects (name, description, sponsor, project_manager, start_date, end_date, methodology, status, budget, currency, parameters_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.name, payload.description, payload.sponsor, payload.project_manager, iso_value(payload.start_date), iso_value(payload.end_date), payload.methodology, payload.status, payload.budget, payload.currency, dumps(parameters)),
        )
        conn.commit()
        return serialize_project(get_project_or_404(conn, cur.lastrowid))


@app.put("/api/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate) -> Dict[str, Any]:
    with db() as conn:
        current = get_project_or_404(conn, project_id)
        data = payload.model_dump(exclude_unset=True)
        start_date = iso_value(data.get("start_date", current["start_date"]))
        end_date = iso_value(data.get("end_date", current["end_date"]))
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="La fecha fin no puede ser menor a la fecha inicio")
        if "parameters" in data and data["parameters"] is not None:
            existing_parameters = loads(current["parameters_json"], DEFAULT_PARAMETERS)
            data["parameters_json"] = dumps(deep_merge(existing_parameters, data.pop("parameters")))
        fields = []
        args = []
        for k, v in data.items():
            if k not in PROJECT_UPDATE_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Campo no actualizable: {k}")
            fields.append(f"{k} = ?")
            args.append(iso_value(v))
        if fields:
            args.append(project_id)
            conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", tuple(args))
            conn.commit()
        return serialize_project(get_project_or_404(conn, project_id))


@app.post("/api/tasks")
def create_task(payload: TaskIn) -> Dict[str, Any]:
    with db() as conn:
        get_project_or_404(conn, payload.project_id)
        if payload.parent_id:
            parent = assert_task_in_project(conn, payload.parent_id, payload.project_id, "La tarea padre")
            if parent["id"] == payload.parent_id and parent["id"] == payload.predecessor_id:
                raise HTTPException(status_code=400, detail="La tarea padre no puede ser también dependencia inicial")
        if payload.predecessor_id:
            assert_task_in_project(conn, payload.predecessor_id, payload.project_id, "La tarea predecesora")
        cur = conn.execute(
            """INSERT INTO tasks (project_id, parent_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, description, order_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.project_id, payload.parent_id, payload.title, payload.phase, payload.task_type, iso_value(payload.start_date), iso_value(payload.end_date), payload.progress, payload.owner, payload.status, payload.story_points, payload.budget, payload.description, payload.order_index),
        )
        if payload.predecessor_id:
            conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", (payload.project_id, payload.predecessor_id, cur.lastrowid))
        conn.commit()
        return one(conn, "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,))


@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate) -> Dict[str, Any]:
    with db() as conn:
        get_task_or_404(conn, task_id)
        data = payload.model_dump(exclude_unset=True)
        fields, args = [], []
        for k, v in data.items():
            if k not in TASK_UPDATE_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Campo no actualizable: {k}")
            fields.append(f"{k} = ?")
            args.append(iso_value(v))
        if fields:
            args.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", tuple(args))
            t = one(conn, "SELECT start_date, end_date FROM tasks WHERE id = ?", (task_id,))
            if t and t["end_date"] < t["start_date"]:
                raise HTTPException(status_code=400, detail="La fecha fin no puede ser menor a la fecha inicio")
            conn.commit()
        return one(conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int) -> Dict[str, str]:
    with db() as conn:
        get_task_or_404(conn, task_id)
        conn.execute("DELETE FROM dependencies WHERE predecessor_id = ? OR successor_id = ?", (task_id, task_id))
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return {"message": "Tarea eliminada"}


@app.post("/api/dependencies")
def create_dependency(payload: DependencyIn) -> Dict[str, Any]:
    with db() as conn:
        get_project_or_404(conn, payload.project_id)
        validate_dependency(conn, payload.project_id, payload.predecessor_id, payload.successor_id)
        existing = one(conn, "SELECT * FROM dependencies WHERE project_id = ? AND predecessor_id = ? AND successor_id = ?", (payload.project_id, payload.predecessor_id, payload.successor_id))
        if existing:
            return existing
        cur = conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, ?)", (payload.project_id, payload.predecessor_id, payload.successor_id, payload.dependency_type))
        conn.commit()
        return one(conn, "SELECT * FROM dependencies WHERE id = ?", (cur.lastrowid,))


@app.delete("/api/dependencies/{dependency_id}")
def delete_dependency(dependency_id: int) -> Dict[str, str]:
    with db() as conn:
        cur = conn.execute("DELETE FROM dependencies WHERE id = ?", (dependency_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Dependencia no encontrada")
        conn.commit()
        return {"message": "Dependencia eliminada"}


@app.post("/api/sprints")
def create_sprint(payload: SprintIn) -> Dict[str, Any]:
    with db() as conn:
        get_project_or_404(conn, payload.project_id)
        cur = conn.execute("INSERT INTO sprints (project_id, name, goal, start_date, end_date, status, velocity) VALUES (?, ?, ?, ?, ?, ?, ?)", (payload.project_id, payload.name, payload.goal, iso_value(payload.start_date), iso_value(payload.end_date), payload.status, payload.velocity))
        conn.commit()
        return one(conn, "SELECT * FROM sprints WHERE id = ?", (cur.lastrowid,))


@app.post("/api/stories")
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


@app.put("/api/stories/{story_id}")
def update_story(story_id: int, payload: StoryUpdate) -> Dict[str, Any]:
    with db() as conn:
        story = one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))
        if not story:
            raise HTTPException(status_code=404, detail="Historia no encontrada")
        data = payload.model_dump(exclude_unset=True)
        project_id = data.get("project_id", story["project_id"])
        if "project_id" in data:
            get_project_or_404(conn, project_id)
        if data.get("sprint_id"):
            sprint = one(conn, "SELECT project_id FROM sprints WHERE id = ?", (data["sprint_id"],))
            if not sprint:
                raise HTTPException(status_code=404, detail="Sprint no encontrado")
            if sprint["project_id"] != project_id:
                raise HTTPException(status_code=400, detail="El sprint no pertenece al proyecto")
        fields, args = [], []
        for k, v in data.items():
            if k not in STORY_UPDATE_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Campo no actualizable: {k}")
            fields.append(f"{k} = ?")
            args.append(v)
        if fields:
            args.append(story_id)
            conn.execute(f"UPDATE stories SET {', '.join(fields)} WHERE id = ?", tuple(args))
            conn.commit()
        return one(conn, "SELECT * FROM stories WHERE id = ?", (story_id,))


@app.post("/api/risks")
def create_risk(payload: RiskIn) -> Dict[str, Any]:
    with db() as conn:
        p = get_project_or_404(conn, payload.project_id)
        params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
        level = risk_level(payload.probability, payload.impact, params)
        cur = conn.execute("INSERT INTO risks (project_id, title, probability, impact, level, response, status, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (payload.project_id, payload.title, payload.probability, payload.impact, level, payload.response, payload.status, payload.owner))
        conn.commit()
        return serialize_risk(one(conn, "SELECT * FROM risks WHERE id = ?", (cur.lastrowid,)))


@app.post("/api/resources")
def create_resource(payload: ResourceIn) -> Dict[str, Any]:
    with db() as conn:
        get_project_or_404(conn, payload.project_id)
        cur = conn.execute("INSERT INTO resources (project_id, name, role, email, capacity) VALUES (?, ?, ?, ?, ?)", (payload.project_id, payload.name, payload.role, payload.email, payload.capacity))
        conn.commit()
        return one(conn, "SELECT * FROM resources WHERE id = ?", (cur.lastrowid,))


@app.get("/api/projects/{project_id}/metrics")
def metrics(project_id: int) -> Dict[str, Any]:
    with db() as conn:
        return calculate_metrics(conn, project_id)


@app.post("/api/ai/generate-plan")
def ai_generate_plan(payload: AiPlanIn) -> Dict[str, Any]:
    with db() as conn:
        p = get_project_or_404(conn, payload.project_id)
        params = loads(p["parameters_json"], DEFAULT_PARAMETERS)
        phases = params.get("phases", DEFAULT_PARAMETERS["phases"])
        base = date.fromisoformat(p["start_date"])
        project_end = date.fromisoformat(p["end_date"])
        horizon_days = max(30, payload.horizon_weeks * 7)
        segment = max(5, math.floor(horizon_days / max(len(phases), 1)))
        last_order = one(conn, "SELECT COALESCE(MAX(order_index), 0) AS mx FROM tasks WHERE project_id = ?", (p["id"],))["mx"]
        generated, previous_id = [], None
        for idx, phase in enumerate(phases):
            s = base + timedelta(days=idx * segment)
            e = min(base + timedelta(days=(idx + 1) * segment - 2), project_end)
            title = f"{phase}: entregable principal"
            item = {
                "project_id": p["id"], "title": title, "phase": phase, "task_type": "task", "start_date": s.isoformat(), "end_date": e.isoformat(), "progress": 0,
                "owner": p["project_manager"] or "PM", "status": "Pendiente", "story_points": 8 if phase.lower().startswith("ej") else 0,
                "budget": round(float(p["budget"] or 0) / max(len(phases), 1) * 0.12, 2), "description": f"Generado para el objetivo: {payload.objective}", "order_index": last_order + idx + 1,
            }
            generated.append(item)
            if payload.create_records:
                cur = conn.execute("""INSERT INTO tasks (project_id, title, phase, task_type, start_date, end_date, progress, owner, status, story_points, budget, description, order_index)
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (item["project_id"], item["title"], item["phase"], item["task_type"], item["start_date"], item["end_date"], item["progress"], item["owner"], item["status"], item["story_points"], item["budget"], item["description"], item["order_index"]))
                if previous_id:
                    conn.execute("INSERT INTO dependencies (project_id, predecessor_id, successor_id, dependency_type) VALUES (?, ?, ?, 'FS')", (p["id"], previous_id, cur.lastrowid))
                previous_id = cur.lastrowid
        if payload.create_records:
            conn.commit()
        return {"message": "Plan generado con motor IA-ready. Sustituible por OpenAI/Azure OpenAI cuando se configure la llave.", "generated_tasks": generated}


@app.post("/api/ai/report")
def ai_report(payload: AiReportIn) -> Dict[str, Any]:
    with db() as conn:
        p = get_project_or_404(conn, payload.project_id)
        m = calculate_metrics(conn, payload.project_id)
        risks = all_rows(conn, "SELECT * FROM risks WHERE project_id = ? AND status != 'Cerrado' ORDER BY probability * impact DESC LIMIT 5", (payload.project_id,))
        report = f"""Informe ejecutivo para {payload.audience}
Proyecto: {p['name']}
Estado: {p['status']} | Salud: {m['health']}
Avance general: {m['progress']}%
Presupuesto ejecutado estimado: {m['spent']:,.0f} de {m['budget']:,.0f} {p['currency']}
Riesgos abiertos: {m['open_risks']} | Riesgos altos: {m['high_risks']}
Ruta crítica: {m['critical_path_tasks']} tareas abiertas con dependencias.

Foco recomendado:
1. Revisar tareas atrasadas y dependencias críticas.
2. Confirmar capacidad de recursos de QA y Desarrollo.
3. Mantener gobierno PMP para hitos y cambios de alcance, permitiendo ejecución ágil en sprints.
""".strip()
        if risks:
            report += "\n\nPrincipales riesgos:\n" + "\n".join([f"- {r['title']} ({r['level']})" for r in risks])
        return {"report": report}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")
