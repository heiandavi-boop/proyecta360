from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional


def parse_iso(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def task_duration_days(start_value: str, end_value: str, task_type: str = "task") -> int:
    if task_type == "milestone":
        return 0
    try:
        return max(1, (parse_iso(end_value) - parse_iso(start_value)).days + 1)
    except Exception:
        return 1


def end_from_duration(start_value: date | str, duration_days: int, task_type: str = "task") -> date:
    start = parse_iso(start_value) if isinstance(start_value, str) else start_value
    if task_type == "milestone":
        return start
    return start + timedelta(days=max(1, int(duration_days or 1)) - 1)


def normalize_task_dates(
    start_value: Any,
    end_value: Any,
    duration_days: Optional[int],
    task_type: str,
    iso_value,
) -> tuple[str, str, int]:
    start = parse_iso(iso_value(start_value)) if start_value else date.today()
    if task_type == "milestone":
        return start.isoformat(), start.isoformat(), 0
    if end_value is not None and str(end_value).strip() != "":
        end = parse_iso(iso_value(end_value))
        duration = task_duration_days(start.isoformat(), end.isoformat(), task_type)
        return start.isoformat(), end.isoformat(), duration
    duration = max(1, int(duration_days or 1))
    end = end_from_duration(start, duration, task_type)
    return start.isoformat(), end.isoformat(), duration
