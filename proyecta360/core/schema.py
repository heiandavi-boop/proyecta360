from __future__ import annotations

import sqlite3

from proyecta360.core.database import database_backend


CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER DEFAULT 1,
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
CREATE TABLE IF NOT EXISTS budget_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    month TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    planned_amount REAL DEFAULT 0,
    executed_amount REAL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    velocity INTEGER DEFAULT 0,
    cycle_type TEXT DEFAULT 'Scrum',
    capacity INTEGER DEFAULT 0,
    close_summary TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sprint_id INTEGER REFERENCES sprints(id) ON DELETE SET NULL,
    master_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    component_id INTEGER REFERENCES components(id) ON DELETE SET NULL,
    deliverable_id INTEGER REFERENCES deliverables(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    work_type TEXT DEFAULT 'Historia',
    status TEXT DEFAULT 'Por hacer',
    points INTEGER DEFAULT 0,
    assignee TEXT DEFAULT '',
    priority TEXT DEFAULT 'Media',
    blocked_reason TEXT DEFAULT '',
    started_at TEXT DEFAULT '',
    completed_at TEXT DEFAULT '',
    labels_json TEXT DEFAULT '[]',
    board_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    owner TEXT DEFAULT '',
    materialized_date TEXT DEFAULT '',
    actual_impact TEXT DEFAULT '',
    observations TEXT DEFAULT ''
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
CREATE TABLE IF NOT EXISTS ai_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT DEFAULT 'openai',
    model TEXT DEFAULT 'gpt-4o-mini',
    api_key_encrypted TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'No configurado',
    last_test_at TEXT DEFAULT '',
    last_error TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ai_analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requested_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'completed',
    project_health TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    input_snapshot_json TEXT DEFAULT '{}',
    raw_output_json TEXT DEFAULT '{}',
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT DEFAULT '',
    error_message TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ai_detected_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER REFERENCES ai_analysis_runs(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT DEFAULT '',
    severity TEXT DEFAULT '',
    description TEXT DEFAULT '',
    related_entity_type TEXT DEFAULT '',
    related_entity_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id INTEGER REFERENCES ai_analysis_runs(id) ON DELETE SET NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    action_type TEXT NOT NULL,
    target_module TEXT DEFAULT '',
    target_entity_type TEXT DEFAULT '',
    target_entity_id INTEGER,
    justification TEXT DEFAULT '',
    expected_impact TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium',
    proposed_payload_json TEXT DEFAULT '{}',
    edited_payload_json TEXT DEFAULT '',
    status TEXT DEFAULT 'Pendiente',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decided_at TEXT DEFAULT '',
    applied_at TEXT DEFAULT '',
    error_message TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ai_recommendation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER NOT NULL REFERENCES ai_recommendations(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_detail TEXT DEFAULT '',
    previous_json TEXT DEFAULT '',
    new_json TEXT DEFAULT '',
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER DEFAULT 1,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT DEFAULT 'Miembro',
    password_hash TEXT NOT NULL,
    access_token TEXT DEFAULT '',
    access_token_hash TEXT DEFAULT '',
    token_expires_at TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    status TEXT DEFAULT 'Activa',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_email TEXT DEFAULT '',
    actor_role TEXT DEFAULT '',
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER DEFAULT 0,
    client_host TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_projects_organization ON projects(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_budget_entries_project_month ON budget_entries(project_id, month, category)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_project_order ON tasks(project_id, order_index, id)",
    "CREATE INDEX IF NOT EXISTS idx_dependencies_project_successor ON dependencies(project_id, successor_id)",
    "CREATE INDEX IF NOT EXISTS idx_risks_project_status ON risks(project_id, status, level)",
    "CREATE INDEX IF NOT EXISTS idx_deliverables_project_due ON deliverables(project_id, due_date)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at, id)",
]


def postgres_schema_sql() -> str:
    sql = CREATE_SCHEMA_SQL
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    sql = sql.replace("REAL DEFAULT", "DOUBLE PRECISION DEFAULT")
    sql = sql.replace("TEXT DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT (CURRENT_TIMESTAMP::text)")
    return sql


def create_schema(conn: sqlite3.Connection) -> None:
    if database_backend(conn) == "postgresql":
        conn.executescript(postgres_schema_sql())
        return
    conn.executescript(CREATE_SCHEMA_SQL)


def ensure_schema_columns(conn: sqlite3.Connection) -> None:
    def columns(table: str) -> set[str]:
        if database_backend(conn) == "postgresql":
            rows = conn.execute(
                "SELECT column_name AS name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = ?",
                (table,),
            ).fetchall()
            return {r["name"] for r in rows}
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    project_cols = columns("projects")
    if "organization_id" not in project_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN organization_id INTEGER DEFAULT 1")
    if "contractual_end_date" not in project_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN contractual_end_date TEXT DEFAULT ''")

    if database_backend(conn) == "postgresql":
        conn.execute(
            """CREATE TABLE IF NOT EXISTS budget_entries (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                month TEXT NOT NULL,
                category TEXT DEFAULT 'General',
                planned_amount DOUBLE PRECISION DEFAULT 0,
                executed_amount DOUBLE PRECISION DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP::text)
            )"""
        )
    else:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS budget_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                month TEXT NOT NULL,
                category TEXT DEFAULT 'General',
                planned_amount REAL DEFAULT 0,
                executed_amount REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )

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

    story_cols = columns("stories")
    story_alters = {
        "master_task_id": "ALTER TABLE stories ADD COLUMN master_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL",
        "component_id": "ALTER TABLE stories ADD COLUMN component_id INTEGER REFERENCES components(id) ON DELETE SET NULL",
        "deliverable_id": "ALTER TABLE stories ADD COLUMN deliverable_id INTEGER REFERENCES deliverables(id) ON DELETE SET NULL",
        "description": "ALTER TABLE stories ADD COLUMN description TEXT DEFAULT ''",
        "work_type": "ALTER TABLE stories ADD COLUMN work_type TEXT DEFAULT 'Historia'",
        "blocked_reason": "ALTER TABLE stories ADD COLUMN blocked_reason TEXT DEFAULT ''",
        "started_at": "ALTER TABLE stories ADD COLUMN started_at TEXT DEFAULT ''",
        "completed_at": "ALTER TABLE stories ADD COLUMN completed_at TEXT DEFAULT ''",
        "labels_json": "ALTER TABLE stories ADD COLUMN labels_json TEXT DEFAULT '[]'",
        "board_order": "ALTER TABLE stories ADD COLUMN board_order INTEGER DEFAULT 0",
        "created_at": "ALTER TABLE stories ADD COLUMN created_at TEXT DEFAULT ''",
    }
    for name, ddl in story_alters.items():
        if name not in story_cols:
            conn.execute(ddl)

    sprint_cols = columns("sprints")
    sprint_alters = {
        "cycle_type": "ALTER TABLE sprints ADD COLUMN cycle_type TEXT DEFAULT 'Scrum'",
        "capacity": "ALTER TABLE sprints ADD COLUMN capacity INTEGER DEFAULT 0",
        "close_summary": "ALTER TABLE sprints ADD COLUMN close_summary TEXT DEFAULT ''",
    }
    for name, ddl in sprint_alters.items():
        if name not in sprint_cols:
            conn.execute(ddl)

    risk_cols = columns("risks")
    if "mitigation_plan" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN mitigation_plan TEXT DEFAULT ''")
    if "contingency_plan" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN contingency_plan TEXT DEFAULT ''")
    if "materialized_date" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN materialized_date TEXT DEFAULT ''")
    if "actual_impact" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN actual_impact TEXT DEFAULT ''")
    if "observations" not in risk_cols:
        conn.execute("ALTER TABLE risks ADD COLUMN observations TEXT DEFAULT ''")

    user_cols = columns("users")
    if "organization_id" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN organization_id INTEGER DEFAULT 1")
    if "access_token_hash" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN access_token_hash TEXT DEFAULT ''")
    if "token_expires_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN token_expires_at TEXT DEFAULT ''")
    conn.execute("UPDATE users SET access_token = '' WHERE access_token != ''")

    ai_cols = columns("ai_settings")
    if "provider" not in ai_cols:
        conn.execute("ALTER TABLE ai_settings ADD COLUMN provider TEXT DEFAULT 'openai'")
    if "config_json" not in ai_cols:
        conn.execute("ALTER TABLE ai_settings ADD COLUMN config_json TEXT DEFAULT '{}'")
    if database_backend(conn) == "postgresql":
        conn.execute("INSERT INTO organizations (id, name, slug, status) VALUES (1, 'Organizacion principal', 'principal', 'Activa') ON CONFLICT (id) DO NOTHING")
    else:
        conn.execute("INSERT OR IGNORE INTO organizations (id, name, slug, status) VALUES (1, 'Organizacion principal', 'principal', 'Activa')")
    conn.execute("UPDATE users SET organization_id = 1 WHERE organization_id IS NULL")
    conn.execute("UPDATE projects SET organization_id = 1 WHERE organization_id IS NULL")
    for statement in INDEX_SQL:
        conn.execute(statement)
