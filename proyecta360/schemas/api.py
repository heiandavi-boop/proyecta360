from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from proyecta360.core.config import DEFAULT_PARAMETERS, DEPENDENCY_TYPES, SUPPORTED_CURRENCIES
from proyecta360.core.database import dumps
from proyecta360.services.schedule import end_from_duration, task_duration_days


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    sponsor: str = ""
    project_manager: str = ""
    start_date: date
    end_date: Optional[date] = None
    contractual_end_date: Optional[date] = None
    methodology: str = "Híbrida PMP + Scrum"
    status: str = "En ejecución"
    budget: float = Field(default=0, ge=0)
    currency: str = Field(default="COP", min_length=1, max_length=8)
    parameters: Dict[str, Any] = Field(default_factory=lambda: json.loads(dumps(DEFAULT_PARAMETERS)))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.upper().strip()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("Moneda inválida. Selecciona una moneda del catálogo.")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectIn":
        if self.end_date is None:
            self.end_date = self.start_date
        if self.contractual_end_date and self.contractual_end_date < self.start_date:
            raise ValueError("La fecha compromiso no puede ser menor a la fecha inicio")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = None
    sponsor: Optional[str] = None
    project_manager: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    contractual_end_date: Optional[date] = None
    methodology: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=8)
    parameters: Optional[Dict[str, Any]] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.upper().strip()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("Moneda inválida. Selecciona una moneda del catálogo.")
        return value


PROJECT_PROFILE_FIELDS = {"project_code", "requesting_area", "project_type", "priority", "responsible_team"}
PROJECT_CONTEXT_FIELDS = {
    "problem_statement", "current_situation", "consequence_if_not_done", "general_objective",
    "specific_objectives", "objective_indicators", "scope_included", "scope_excluded",
    "success_criteria", "assumptions", "constraints", "project_context", "political_context",
    "geographic_context", "socioeconomic_context", "cultural_context", "institutional_context",
    "stakeholders", "stakeholders_context", "external_dependencies", "regulatory_constraints",
}


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    project_code: str = ""
    description: str = ""
    sponsor: str = ""
    project_manager: str = ""
    requesting_area: str = ""
    project_type: str = ""
    start_date: date
    end_date: Optional[date] = None
    contractual_end_date: Optional[date] = None
    methodology: str = "Hibrida"
    priority: str = "Media"
    status: str = "En ejecucion"
    budget: float = Field(default=0, ge=0)
    currency: str = Field(default="COP", min_length=1, max_length=8)
    responsible_team: str = ""
    problem_statement: str = ""
    current_situation: str = ""
    consequence_if_not_done: str = ""
    general_objective: str = ""
    specific_objectives: str = ""
    objective_indicators: str = ""
    scope_included: str = ""
    scope_excluded: str = ""
    success_criteria: str = ""
    assumptions: str = ""
    constraints: str = ""
    project_context: str = ""
    political_context: str = ""
    geographic_context: str = ""
    socioeconomic_context: str = ""
    cultural_context: str = ""
    institutional_context: str = ""
    stakeholders: str = ""
    stakeholders_context: str = ""
    external_dependencies: str = ""
    regulatory_constraints: str = ""
    parameters: Dict[str, Any] = Field(default_factory=lambda: json.loads(dumps(DEFAULT_PARAMETERS)))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.upper().strip()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("Moneda invalida. Selecciona una moneda del catalogo.")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectIn":
        if self.end_date is None:
            self.end_date = self.start_date
        if self.contractual_end_date and self.contractual_end_date < self.start_date:
            raise ValueError("La fecha compromiso no puede ser menor a la fecha inicio")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    project_code: Optional[str] = None
    description: Optional[str] = None
    sponsor: Optional[str] = None
    project_manager: Optional[str] = None
    requesting_area: Optional[str] = None
    project_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    contractual_end_date: Optional[date] = None
    methodology: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=8)
    responsible_team: Optional[str] = None
    problem_statement: Optional[str] = None
    current_situation: Optional[str] = None
    consequence_if_not_done: Optional[str] = None
    general_objective: Optional[str] = None
    specific_objectives: Optional[str] = None
    objective_indicators: Optional[str] = None
    scope_included: Optional[str] = None
    scope_excluded: Optional[str] = None
    success_criteria: Optional[str] = None
    assumptions: Optional[str] = None
    constraints: Optional[str] = None
    project_context: Optional[str] = None
    political_context: Optional[str] = None
    geographic_context: Optional[str] = None
    socioeconomic_context: Optional[str] = None
    cultural_context: Optional[str] = None
    institutional_context: Optional[str] = None
    stakeholders: Optional[str] = None
    stakeholders_context: Optional[str] = None
    external_dependencies: Optional[str] = None
    regulatory_constraints: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.upper().strip()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("Moneda invalida. Selecciona una moneda del catalogo.")
        return value


class TaskIn(BaseModel):
    project_id: int
    parent_id: Optional[int] = None
    component_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=220)
    phase: str = ""
    task_type: str = "task"
    start_date: date
    end_date: Optional[date] = None
    duration_days: int = Field(default=1, ge=0)
    progress: int = Field(default=0, ge=0, le=100)
    owner: str = ""
    status: str = "Pendiente"
    story_points: int = Field(default=0, ge=0)
    budget: float = Field(default=0, ge=0)
    description: str = ""
    order_index: int = Field(default=0, ge=0)
    outline_level: int = Field(default=0, ge=0)
    is_expanded: int = Field(default=1, ge=0, le=1)
    predecessor_id: Optional[int] = None
    dependency_type: str = "FS"
    lag_days: int = 0

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        if value not in {"task", "milestone", "summary"}:
            raise ValueError("Tipo de tarea inválido")
        return value

    @field_validator("dependency_type")
    @classmethod
    def validate_dependency_type(cls, value: str) -> str:
        value = value.upper().strip()
        if value not in DEPENDENCY_TYPES:
            raise ValueError("Tipo de dependencia inválido")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "TaskIn":
        if self.task_type == "milestone":
            self.duration_days = 0
            self.end_date = self.start_date
        elif self.end_date is None:
            self.end_date = end_from_duration(self.start_date, self.duration_days, self.task_type)
        else:
            self.duration_days = task_duration_days(self.start_date.isoformat(), self.end_date.isoformat(), self.task_type)
        return self


class TaskUpdate(BaseModel):
    parent_id: Optional[int] = None
    component_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=220)
    phase: Optional[str] = None
    task_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[int] = Field(default=None, ge=0)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    owner: Optional[str] = None
    status: Optional[str] = None
    story_points: Optional[int] = Field(default=None, ge=0)
    budget: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    order_index: Optional[int] = Field(default=None, ge=0)
    outline_level: Optional[int] = Field(default=None, ge=0)
    is_expanded: Optional[int] = Field(default=None, ge=0, le=1)

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
    lag_days: int = 0

    @field_validator("dependency_type")
    @classmethod
    def validate_dependency_type(cls, value: str) -> str:
        value = value.upper().strip()
        if value not in DEPENDENCY_TYPES:
            raise ValueError("Tipo de dependencia inválido")
        return value


class SprintIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=160)
    goal: str = ""
    start_date: date
    end_date: date
    status: str = "Planeado"
    velocity: int = Field(default=0, ge=0)
    cycle_type: str = "Scrum"
    capacity: int = Field(default=0, ge=0)
    close_summary: str = ""

    @model_validator(mode="after")
    def validate_dates(self) -> "SprintIn":
        if self.end_date < self.start_date:
            raise ValueError("La fecha fin no puede ser menor a la fecha inicio")
        return self


class StoryIn(BaseModel):
    project_id: int
    sprint_id: Optional[int] = None
    master_task_id: Optional[int] = None
    component_id: Optional[int] = None
    deliverable_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=220)
    description: str = ""
    work_type: str = "Historia"
    status: str = "Por hacer"
    points: int = Field(default=0, ge=0)
    assignee: str = ""
    priority: str = "Media"
    blocked_reason: str = ""
    started_at: str = ""
    completed_at: str = ""
    labels: list[str] = Field(default_factory=list)
    board_order: int = Field(default=0, ge=0)


class AgileCycleIn(SprintIn):
    """Neutral API contract for agile cycles. Legacy sprints map here."""


class WorkItemIn(StoryIn):
    """Neutral API contract for agile work items. Legacy stories map here."""


class RiskIn(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=220)
    probability: int = Field(default=1, ge=1, le=5)
    impact: int = Field(default=1, ge=1, le=5)
    response: str = ""
    mitigation_plan: str = ""
    contingency_plan: str = ""
    status: str = "Activo"
    owner: str = ""
    materialized_date: Optional[date] = None
    actual_impact: str = ""
    observations: str = ""


class ResourceIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=160)
    role: str = ""
    email: str = ""
    capacity: int = Field(default=100, ge=0, le=100)


class BudgetEntryIn(BaseModel):
    project_id: int
    month: str = Field(min_length=7, max_length=7)
    category: str = Field(default="General", min_length=1, max_length=120)
    planned_amount: float = Field(default=0, ge=0)
    executed_amount: float = Field(default=0, ge=0)
    notes: str = ""

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        value = value.strip()
        try:
            year, month = value.split("-")
            if len(year) != 4 or len(month) != 2 or not (1 <= int(month) <= 12):
                raise ValueError
        except Exception:
            raise ValueError("El mes debe tener formato YYYY-MM")
        return value


class ComponentIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=160)
    methodology: str = "Hibrida"
    owner: str = ""
    objective: str = ""
    progress: int = Field(default=0, ge=0, le=100)


class DeliverableIn(BaseModel):
    project_id: int
    component_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=180)
    deliverable_type: str = "Entregable"
    status: str = "Planeado"
    owner: str = ""
    due_date: Optional[date] = None
    evidence_url: str = ""
    description: str = ""


class ConversationThreadIn(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=180)
    context_type: str = "Proyecto"
    context_id: Optional[int] = None
    category: str = "Seguimiento"
    status: str = "Abierta"
    created_by: str = ""


class ConversationMessageIn(BaseModel):
    thread_id: int
    project_id: int
    author: str = ""
    message: str = Field(min_length=1, max_length=2500)
    mentions: str = ""
    evidence_url: str = ""
    message_type: str = "Comentario"


class AiPlanIn(BaseModel):
    project_id: int
    objective: str = Field(min_length=1, max_length=1200)
    execution_methodology: str = "Scrum"
    horizon_weeks: int = Field(default=12, ge=4, le=52)
    create_records: bool = True


class AiReportIn(BaseModel):
    project_id: int
    audience: str = "Comité Directivo"


class AiChatIn(BaseModel):
    project_id: int
    question: str = Field(min_length=1, max_length=1200)
    author: str = "Usuario"


class AiSettingsIn(BaseModel):
    api_key: str = ""
    model: str = Field(default="gpt-4o-mini", max_length=120)
    provider: str = Field(default="openai", max_length=80)
    config: Dict[str, Any] = Field(default_factory=dict)


class AiAnalysisIn(BaseModel):
    include_schedule: bool = True
    include_risks: bool = True
    include_resources: bool = True
    include_deliverables: bool = True
    include_evidences: bool = True
    include_budget: bool = True
    include_history: bool = True
    include_conversations: bool = True


class AiRecommendationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=220)
    description: Optional[str] = None
    justification: Optional[str] = None
    expected_impact: Optional[str] = None
    priority: Optional[str] = None
    proposed_payload: Optional[Dict[str, Any]] = None
    edited_payload: Optional[Dict[str, Any]] = None


class AiProjectChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1600)
    mode: str = "consulta"

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"consulta", "accion"}:
            raise ValueError("Modo IA invalido")
        return value


class AuthLoginIn(BaseModel):
    email: str
    password: str
