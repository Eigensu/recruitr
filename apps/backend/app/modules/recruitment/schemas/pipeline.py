"""Pipeline and Kanban board DTOs."""

from datetime import datetime
from typing import Literal

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
    updated_at: datetime | None = None
    offer_document_url: str | None = None
    joining_date: datetime | None = None


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


# ── Client/staff dashboard actions ──────────────────────────────────────────
# The tick/cross + offer/joining-date flow a client (or staff, as a fallback)
# drives from the dashboard action widget — see controller/pipeline.py's
# "Mapping actions" section.


class DecisionRequest(BaseModel):
    """Tick ("selected") or cross ("rejected") on a mapping awaiting a decision."""

    decision: Literal["selected", "rejected"]


class JoiningDateRequest(BaseModel):
    """Set the candidate's joining date once an offer has been uploaded."""

    joining_date: datetime


class MappingActionResponse(BaseModel):
    """Result of a dashboard action (decision, offer upload, joining date, override)."""

    mapping_id: str
    stage: PipelineStage
    decision: str
    offer_document_url: str | None = None
    joining_date: datetime | None = None
