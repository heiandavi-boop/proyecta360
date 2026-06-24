"""Database connection, helpers and migration entrypoint.

Raw stdlib sqlite3 (no ORM). A connection is opened per request via the
``get_db`` FastAPI dependency, which guarantees the connection is closed and
rolled back on error. Alembic owns the schema (see ``run_migrations``).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional

from core.config import BASE_DIR, settings

# Module-level so tests can repoint it at a temporary database before startup.
DB_PATH = settings.db_path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: yields a connection, always closes it, and rolls
    back if the request handler raised."""
    conn = connect()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_migrations() -> None:
    """Bring the schema up to date via Alembic: creates everything on a fresh
    database and applies pending migrations on an existing one. Reads the
    module-level ``DB_PATH`` so tests can point it at a temporary database."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
    command.upgrade(cfg, "head")


# ---------- JSON / row helpers ----------
def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def loads(value: Optional[str], default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def rowdict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row else None


def one(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
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
