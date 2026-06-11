"""Pydantic schemas for the dashboard module."""

from datetime import UTC, datetime
from functools import partial
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.common.dtos.pagination import PaginatedResponse
from app.modules.recruitment.enums import ActivityType, PipelineStage, PositionStatus

# ── Nested helper schema ───────────────────────────────────────────────────────


class EmployeeMappings(BaseModel):
    offers_sent: int = 0
    joined_candidates: int = 0
    rejected_candidates: int = 0


# ── Filters ────────────────────────────────────────────────────────────────────


class DashboardFilters(BaseModel):
    brand_id: str | None = None  # tenant scope — always set by the controller
    employee_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    client_id: str | None = None  # Position.client_id (was job_opening_id)
    pipeline_stage: PipelineStage | None = None


# ── Overview ───────────────────────────────────────────────────────────────────


class DashboardKpiSummary(BaseModel):
    open_positions: int = 0
    total_seats_open: int = 0
    seats_filled: int = 0
    candidates_in_pipeline: int = 0
    offers_accepted: int = 0
    joined_candidates: int = 0


class PipelineStageMetric(BaseModel):
    stage: PipelineStage
    label: str
    count: int
    percent: float


class DashboardOverviewResponse(BaseModel):
    summary: DashboardKpiSummary
    pipeline: list[PipelineStageMetric] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=partial(datetime.now, UTC))


class DashboardPipelineResponse(BaseModel):
    stages: list[PipelineStageMetric] = Field(default_factory=list)
    total_candidates: int = 0
    generated_at: datetime = Field(default_factory=partial(datetime.now, UTC))


# ── Analytics item schemas ─────────────────────────────────────────────────────


class EmployeeAnalyticsItem(BaseModel):
    id: str
    name: str
    email: str
    mappings: EmployeeMappings
    total_mappings: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ClientAnalyticsItem(BaseModel):
    id: str
    client_name: str
    role: str
    total_seats: int
    filled_seats: int
    remaining_seats: int
    status: PositionStatus
    candidate_count: int = 0
    pipeline_candidates: int = 0
    offers_accepted: int = 0
    joined_candidates: int = 0
    created_at: datetime
    updated_at: datetime
    is_active: bool


class CandidateAnalyticsItem(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float = 0
    skills: list[str] = Field(default_factory=list)
    resume_url: str | None = None
    current_stage: PipelineStage = PipelineStage.sourced
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    @model_validator(mode="before")
    @classmethod
    def _from_unified_candidate(cls, data: Any) -> Any:
        """Accept the unified Candidate shape (name/extracted_skills/cv_link)."""
        if isinstance(data, dict):
            if not data.get("full_name") and data.get("name"):
                data["full_name"] = data["name"]
            if not data.get("skills") and data.get("extracted_skills"):
                data["skills"] = data["extracted_skills"]
            if not data.get("resume_url"):
                data["resume_url"] = data.get("resume_url") or data.get("cv_link") or data.get("resume_link")
            if not data.get("current_stage"):
                data["current_stage"] = PipelineStage.sourced.value
        return data


class MappingAnalyticsItem(BaseModel):
    id: str
    employee_id: str
    candidate_id: str
    position_id: str
    pipeline_stage: PipelineStage
    mapped_at: datetime
    updated_at: datetime


class ActivityAnalyticsItem(BaseModel):
    id: str
    employee_id: str | None = None
    activity_type: ActivityType
    target_entity_type: str
    target_entity_id: str
    description: str
    created_at: datetime


# ── Paginated responses ────────────────────────────────────────────────────────


class ClientProfileRow(BaseModel):
    client_name: str
    total_open_positions: int
    total_candidates: int
    active_recruiters: int
    last_activity: datetime | None = None
    status: str  # "active" | "on_hold" | "closed"


class DashboardEmployeePage(PaginatedResponse[EmployeeAnalyticsItem]):
    pass


class DashboardClientPage(PaginatedResponse[ClientAnalyticsItem]):
    pass


class DashboardCandidatePage(PaginatedResponse[CandidateAnalyticsItem]):
    pass


class DashboardMappingPage(PaginatedResponse[MappingAnalyticsItem]):
    pass


class DashboardActivityPage(PaginatedResponse[ActivityAnalyticsItem]):
    pass


class DashboardClientProfilePage(PaginatedResponse[ClientProfileRow]):
    pass
