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
from app.modules.recruitment.schemas.tag import RecruiterTagCreate, RecruiterTagResponse
from app.modules.recruitment.schemas.team import (
    BulkAssignEmployees,
    EmployeeTeamResponse,
    TeamCreate,
    TeamResponse,
)

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
    # Team & Tag DTOs
    "TeamCreate",
    "TeamResponse",
    "BulkAssignEmployees",
    "EmployeeTeamResponse",
    "RecruiterTagCreate",
    "RecruiterTagResponse",
    # Shared
    "TenantScope",
    "ResumeConfirm",
]
