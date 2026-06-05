"""Recruitment domain DTOs and value objects."""

from app.modules.recruitment.schemas.candidate import (
    CandidateCreate,
    CandidateMappingItem,
    CandidatePage,
    CandidateResponse,
    CandidateUpdate,
    ExperienceFilter,
)
from app.modules.recruitment.schemas.pipeline import (
    PipelineBoard,
    PipelineStageColumn,
    StageMappingItem,
    StageMoveRequest,
    StageMoveResponse,
)
from app.modules.recruitment.schemas.position import (
    ClientOption,
    MapCandidateRequest,
    MapCandidateResponse,
    MappedPreview,
    PositionCreate,
    PositionFiltersResponse,
    PositionListItem,
    PositionMappedCandidate,
    PositionPage,
    PositionUpdate,
    TopCandidateItem,
)
from app.modules.recruitment.schemas.shared import ResumeConfirm, TenantScope

__all__ = [
    # Candidate DTOs
    "CandidateCreate",
    "CandidateUpdate",
    "CandidateResponse",
    "CandidateMappingItem",
    "CandidatePage",
    "ExperienceFilter",
    # Position DTOs
    "MappedPreview",
    "PositionListItem",
    "PositionCreate",
    "PositionUpdate",
    "TopCandidateItem",
    "MapCandidateRequest",
    "MapCandidateResponse",
    "PositionMappedCandidate",
    "ClientOption",
    "PositionFiltersResponse",
    "PositionPage",
    # Pipeline DTOs
    "PipelineBoard",
    "PipelineStageColumn",
    "StageMappingItem",
    "StageMoveRequest",
    "StageMoveResponse",
    # Shared
    "TenantScope",
    "ResumeConfirm",
]
