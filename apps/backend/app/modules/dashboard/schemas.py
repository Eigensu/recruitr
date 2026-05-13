"""Pydantic schemas for the dashboard module."""

from datetime import UTC, datetime
from functools import partial

from pydantic import BaseModel, Field

from app.common.dtos.pagination import PaginatedResponse
from app.modules.dashboard.enums import ActivityType, JobStatus, PipelineStage, TargetEntityType
from app.modules.dashboard.models import EmployeeMappings


class DashboardFilters(BaseModel):
    employee_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    client_id: str | None = None
    pipeline_stage: PipelineStage | None = None


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
    status: JobStatus
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
    experience: float = 0
    skills: list[str] = Field(default_factory=list)
    resume_link: str | None = None
    current_stage: PipelineStage
    created_at: datetime
    updated_at: datetime
    is_active: bool


class MappingAnalyticsItem(BaseModel):
    id: str
    employee_id: str
    candidate_id: str
    job_opening_id: str
    pipeline_stage: PipelineStage
    mapped_at: datetime
    updated_at: datetime


class ActivityAnalyticsItem(BaseModel):
    id: str
    employee_id: str | None = None
    activity_type: ActivityType
    target_entity_type: TargetEntityType
    target_entity_id: str
    description: str
    created_at: datetime


class DocumentAnalyticsItem(BaseModel):
    id: str
    candidate_id: str
    file_name: str
    file_type: str
    file_url: str
    uploaded_at: datetime


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
