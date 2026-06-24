"""drop risks.level (now derived on read)

The risk level (Bajo/Medio/Alto) is computed from probability*impact against
the project's thresholds at read time (services/serializers.risk_level), so
storing it would let it go stale when thresholds change.

Done with an explicit, controlled table rebuild (not Alembic batch mode):
batch reflection on SQLite silently drops the FK ``ON DELETE CASCADE`` action,
so we recreate the table by hand preserving the cascade exactly.

Revision ID: 0002_drop_risks_level
Revises: 0001_baseline
Create Date: 2026-06-23
"""
from alembic import op

revision = "0002_drop_risks_level"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE risks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            probability INTEGER DEFAULT 1,
            impact INTEGER DEFAULT 1,
            response TEXT DEFAULT '',
            status TEXT DEFAULT 'Abierto',
            owner TEXT DEFAULT ''
        );
        """
    )
    op.execute(
        """
        INSERT INTO risks_new (id, project_id, title, probability, impact, response, status, owner)
        SELECT id, project_id, title, probability, impact, response, status, owner FROM risks;
        """
    )
    op.execute("DROP TABLE risks;")
    op.execute("ALTER TABLE risks_new RENAME TO risks;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_risks_project ON risks(project_id);")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE risks_old (
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
    op.execute(
        """
        INSERT INTO risks_old (id, project_id, title, probability, impact, response, status, owner)
        SELECT id, project_id, title, probability, impact, response, status, owner FROM risks;
        """
    )
    op.execute("DROP TABLE risks;")
    op.execute("ALTER TABLE risks_old RENAME TO risks;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_risks_project ON risks(project_id);")
