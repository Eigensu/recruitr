"""Position resource DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.dtos.pagination import PaginatedResponse


class MappedPreview(BaseModel):
    """Compact candidate stub shown as avatar previews on the position card."""

    id: str
    full_name: str


class PositionListItem(BaseModel):
    """Position list row — includes denormalized counts and avatar previews."""

    id: str
    code: str
    client_id: str
    client_name: str
    role: str
    department: str | None = None
    city: str | None = None
    seniority: str
    status: str
    total_seats: int
    filled_seats: int
    remaining_seats: int
    mapped_count: int = 0
    mapped_preview: list[MappedPreview] = Field(default_factory=list)
    assigned_employee_id: str | None = None
    assigned_employee_name: str | None = None
    date_opened: datetime
    target_close: datetime | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class PositionCreate(BaseModel):
    client_id: str
    role: str
    department: str | None = None
    city: str | None = None
    seniority: str = "Mid"
    requirements: list[str] = Field(default_factory=list)
    total_seats: int = Field(default=0, ge=0)
    date_opened: datetime | None = None
    target_close: datetime | None = None
    notes: str | None = None


class PositionUpdate(BaseModel):
    role: str | None = None
    department: str | None = None
    city: str | None = None
    seniority: str | None = None
    requirements: list[str] | None = None
    total_seats: int | None = Field(default=None, ge=0)
    status: str | None = None
    assigned_employee_id: str | None = None
    target_close: datetime | None = None
    notes: str | None = None


class TopCandidateItem(BaseModel):
    """Ranked candidate returned by GET /positions/{id}/top-candidates."""

    id: str
    full_name: str
    email: str
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float
    skills: list[str]
    resume_url: str | None = None
    match_score: float | None = None  # null when position has no requirements
    is_mapped: bool = False


class MapCandidateRequest(BaseModel):
    candidate_id: str


class MapCandidateResponse(BaseModel):
    mapping_id: str
    position_id: str
    candidate_id: str
    stage: str
    match_score: float | None = None
    recruiter_score_delta: int = 4  # MAPPING_COMPLETED points


class PositionMappedCandidate(BaseModel):
    """Candidate already mapped to a position — returned by GET /positions/{id}/candidates."""

    mapping_id: str
    candidate_id: str
    full_name: str
    email: str
    previous_company: str | None = None
    experience_years: float
    skills: list[str]
    stage: str
    match_score: float | None = None


class ClientOption(BaseModel):
    id: str
    code: str
    name: str


class PositionFiltersResponse(BaseModel):
    clients: list[ClientOption] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)


class PositionPage(PaginatedResponse[PositionListItem]):
    pass
