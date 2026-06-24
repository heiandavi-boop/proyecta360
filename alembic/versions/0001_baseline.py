"""baseline schema (7 tables + secondary indexes)

Transcribes the schema previously created by app.init_db() so Alembic becomes
the single source of truth for DDL. Written with ``IF NOT EXISTS`` so it is a
safe no-op on the already-deployed database (which gets stamped to this
revision on first run) and creates everything on a fresh database.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-23
"""
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
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
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            role TEXT DEFAULT '',
            email TEXT DEFAULT '',
            capacity INTEGER DEFAULT 100
        );
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            dependency_type TEXT DEFAULT 'FS'
        );
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
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
        """
    )

    # Secondary indexes: every per-project query filters by project_id, and the
    # dependency graph / hierarchy traversals filter by their edge columns.
    for stmt in (
        "CREATE INDEX IF NOT EXISTS idx_resources_project ON resources(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);",
        "CREATE INDEX IF NOT EXISTS idx_dependencies_project ON dependencies(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_dependencies_pred ON dependencies(project_id, predecessor_id);",
        "CREATE INDEX IF NOT EXISTS idx_dependencies_succ ON dependencies(project_id, successor_id);",
        "CREATE INDEX IF NOT EXISTS idx_sprints_project ON sprints(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_stories_project ON stories(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_stories_sprint ON stories(sprint_id);",
        "CREATE INDEX IF NOT EXISTS idx_risks_project ON risks(project_id);",
    ):
        op.execute(stmt)


def downgrade() -> None:
    for table in ("dependencies", "stories", "sprints", "risks", "tasks", "resources", "projects"):
        op.execute(f"DROP TABLE IF EXISTS {table};")
