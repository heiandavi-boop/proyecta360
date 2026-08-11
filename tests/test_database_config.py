from pathlib import Path

from proyecta360 import main as main_module
from proyecta360.core.database import connect, database_backend_from_url
from proyecta360.core.schema import create_schema, postgres_schema_sql


def test_sqlite_is_default_backend(tmp_path):
    db_path = tmp_path / "local.db"

    with connect(db_path) as conn:
        assert database_backend_from_url("") == "sqlite"
        assert database_backend_from_url(None) == "sqlite"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_sqlite_schema_creation(tmp_path):
    db_path = tmp_path / "schema.db"

    with connect(db_path) as conn:
        create_schema(conn)
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }

    assert {"projects", "tasks", "users", "ai_recommendations"}.issubset(tables)
    assert {"organizations", "audit_events"}.issubset(tables)


def test_postgres_database_url_is_recognized():
    assert database_backend_from_url("postgresql://user:pass@localhost:5432/prunin") == "postgresql"
    assert database_backend_from_url("postgres://user:pass@localhost:5432/prunin") == "postgresql"


def test_postgres_schema_avoids_sqlite_only_autoincrement():
    sql = postgres_schema_sql()

    assert "AUTOINCREMENT" not in sql
    assert "SERIAL PRIMARY KEY" in sql
    assert "CURRENT_TIMESTAMP::text" in sql


def test_main_db_uses_database_url_when_configured(monkeypatch, tmp_path):
    calls = {}

    def fake_connect(db_path: Path, database_url: str):
        calls["db_path"] = db_path
        calls["database_url"] = database_url
        return object()

    monkeypatch.setattr(main_module, "DB_PATH", tmp_path / "ignored.db")
    monkeypatch.setattr(main_module, "DATABASE_URL", "postgresql://user:pass@localhost:5432/prunin")
    monkeypatch.setattr(main_module, "connect", fake_connect)

    main_module.db()

    assert calls["database_url"].startswith("postgresql://")
