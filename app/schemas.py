"""Pydantic request models and the column allow-lists used by the dynamic
UPDATE builders.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db import dumps
from core.defaults import DEFAULT_PARAMETERS

TASK_TYPES = {"task", "milestone", "summary"}


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
        if value not in TASK_TYPES:
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
        if value is not None and value not in TASK_TYPES:
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
