"""Pipeline and Kanban board DTOs."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.recruitment.enums import PipelineStage


class StageMappingItem(BaseModel):
    """A candidate mapping on the Kanban board."""

    mapping_id: str
    candidate_id: str
    candidate_name: str
    candidate_email: str
    position_id: str
    position_code: str
    position_role: str
    position_client: str
    employee_id: str | None = None
    stage: PipelineStage
    match_score: float | None = None
    decision: str = "pending"
    mapped_at: datetime
    stage_entered_at: datetime | None = None
    interview_date: datetime | None = None
    joining_date: datetime | None = None
    offer_letter_url: str | None = None
    salary_offered: float | None = None
    dropped_notes: str | None = None


class PipelineStageColumn(BaseModel):
    """One column on the Kanban board (e.g., Interview, Offer, etc.)."""

    stage: PipelineStage
    label: str
    count: int
    mappings: list[StageMappingItem] = []


class PipelineBoard(BaseModel):
    """Complete Kanban board state — all stages with their mappings."""

    stages: list[PipelineStageColumn]


class StageMoveRequest(BaseModel):
    """Move a mapping to a new stage."""

    new_stage: PipelineStage
    dropped_notes: str | None = None
    offer_letter_url: str | None = None
    joining_date: datetime | None = None
    salary_offered: float | None = None
    brand: str | None = None


class StageMoveResponse(BaseModel):
    """Result of a stage move."""

    mapping_id: str
    candidate_id: str
    position_id: str
    old_stage: PipelineStage
    new_stage: PipelineStage
    decision: str = "pending"
    recruiter_score_delta: int = 0  # Varies by stage
    activity_id: str | None = None


class PipelineSetInterviewRequest(BaseModel):
    interview_date: datetime


class PipelineSetJoiningRequest(BaseModel):
    joining_date: datetime
    # The client portal collects the salary alongside the joining date and has
    # always sent it here; the field was simply never declared, so pydantic
    # dropped it and Mapping.salary_offered stayed null forever.
    salary_offered: float | None = None


class PipelineCandidateDroppedRequest(BaseModel):
    dropped_notes: str
