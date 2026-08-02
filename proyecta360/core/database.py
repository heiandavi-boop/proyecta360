from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def connect(db_path: Path) -> sqlite3.Connection:
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
