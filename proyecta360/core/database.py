from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

POSTGRES_SCHEMES = ("postgresql://", "postgres://")


def database_backend_from_url(database_url: str | None) -> str:
    if database_url and database_url.strip().lower().startswith(POSTGRES_SCHEMES):
        return "postgresql"
    return "sqlite"


def database_backend(conn_or_url: Any) -> str:
    if isinstance(conn_or_url, str) or conn_or_url is None:
        return database_backend_from_url(conn_or_url)
    return getattr(conn_or_url, "backend", "sqlite")


def _to_postgres_sql(sql: str) -> str:
    return sql.replace("?", "%s")


def _is_insert_without_returning(sql: str) -> bool:
    normalized = sql.strip().lower()
    return normalized.startswith("insert into ") and " returning " not in normalized


class PostgresCursor:
    def __init__(self, cursor: Any, lastrowid: int | None = None, prefetched: Any = None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self._prefetched = prefetched

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> Any:
        if self._prefetched is not None:
            row = self._prefetched
            self._prefetched = None
            return row
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        first = []
        if self._prefetched is not None:
            first = [self._prefetched]
            self._prefetched = None
        return first + self._cursor.fetchall()


class PostgresConnection:
    backend = "postgresql"

    def __init__(self, database_url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL requiere instalar psycopg[binary].") from exc
        self._conn = psycopg.connect(database_url, row_factory=dict_row)

    def execute(self, sql: str, args: Iterable[Any] = ()) -> PostgresCursor:
        query = _to_postgres_sql(sql)
        cursor = self._conn.cursor()
        lastrowid = None
        prefetched = None
        if _is_insert_without_returning(query):
            query = f"{query.rstrip().rstrip(';')} RETURNING id"
            cursor.execute(query, tuple(args))
            prefetched = cursor.fetchone()
            if prefetched and "id" in prefetched:
                lastrowid = int(prefetched["id"])
        else:
            cursor.execute(query, tuple(args))
        return PostgresCursor(cursor, lastrowid=lastrowid, prefetched=prefetched)

    def executemany(self, sql: str, seq_of_args: Iterable[Iterable[Any]]) -> Any:
        cursor = self._conn.cursor()
        cursor.executemany(_to_postgres_sql(sql), [tuple(args) for args in seq_of_args])
        return cursor

    def executescript(self, script: str) -> None:
        statements = [part.strip() for part in script.split(";") if part.strip()]
        with self._conn.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect(db_path: Path | None = None, database_url: str | None = None) -> Any:
    if database_backend_from_url(database_url) == "postgresql":
        return PostgresConnection(database_url or "")
    if db_path is None:
        raise ValueError("db_path es requerido cuando DATABASE_URL no apunta a PostgreSQL.")
    conn = sqlite3.connect(db_path)
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
