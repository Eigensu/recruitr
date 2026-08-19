"""Position resource DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.common.dtos.pagination import PaginatedResponse
from app.modules.recruitment.enums.department import Department
from app.modules.recruitment.enums.position_approval_status import PositionApprovalStatus


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
    department: Department | None = None
    salary: str | None = None
    mumbai_area: str | None = None
    city: str | None = None
    train_line: str | None = None
    seniority: str
    status: str
    approval_status: PositionApprovalStatus | None = None
    total_seats: int
    filled_seats: int
    remaining_seats: int
    mapped_count: int = 0
    mapped_preview: list[MappedPreview] = Field(default_factory=list)
    assigned_employee_id: str | None = None
    assigned_employee_name: str | None = None
    requirements: list[str] = Field(default_factory=list)
    date_opened: datetime
    target_close: datetime | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class PositionCreate(BaseModel):
    client_id: str
    role: str
    department: Department | None = None
    salary: str | None = None
    mumbai_area: str | None = None
    city: str | None = None
    train_line: str | None = None
    seniority: str = "Mid"
    requirements: list[str] = Field(default_factory=list)
    total_seats: int = Field(default=1, ge=1)
    date_opened: datetime | None = None
    target_close: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_category_and_role(self) -> "PositionCreate":
        # Only enforce role mapping if a department is specified.
        # This allows internal users to potentially bypass it if needed in the future,
        # but the prompt specifically wants client flow to enforce it.
        # The prompt says Category is required for the client portal.
        # So we require department if role is provided and they must match.
        from app.modules.recruitment.constants import ROLES_BY_CATEGORY

        if self.department:
            allowed_roles = ROLES_BY_CATEGORY.get(self.department, [])
            if self.role not in allowed_roles:
                raise ValueError(
                    f"Role '{self.role}' is not valid for category '{self.department.value}'"
                )
        elif self.client_id is not None:
            # If it's a client creating it (they pass client_id in the payload usually, wait, client_id is in PositionCreate)
            # We enforce department is required
            raise ValueError("Category (department) is required.")

        # If city is provided and it is not mumbai, clear mumbai_area
        if self.city is not None and self.city.strip().lower() != "mumbai":
            self.mumbai_area = None

        return self


class PositionUpdate(BaseModel):
    role: str | None = None
    department: Department | None = None
    salary: str | None = None
    mumbai_area: str | None = None
    city: str | None = None
    train_line: str | None = None
    seniority: str | None = None
    requirements: list[str] | None = None
    total_seats: int | None = Field(default=None, ge=0)
    status: str | None = None
    approval_status: PositionApprovalStatus | None = None
    assigned_employee_id: str | None = None
    target_close: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_category_and_role(self) -> "PositionUpdate":
        from app.modules.recruitment.constants import ROLES_BY_CATEGORY

        if self.department and self.role:
            allowed_roles = ROLES_BY_CATEGORY.get(self.department, [])
            if self.role not in allowed_roles:
                raise ValueError(
                    f"Role '{self.role}' is not valid for category '{self.department.value}'"
                )

        # also if city is provided and it is not mumbai, clear mumbai_area if not explicitly provided
        if self.city is not None and self.city.strip().lower() != "mumbai":
            self.mumbai_area = None

        return self


class PositionApprovalRequest(BaseModel):
    approval_status: str


class TopCandidateItem(BaseModel):
    """Ranked candidate returned by GET /positions/{id}/top-candidates."""

    id: str
    full_name: str
    email: str
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float
    education_level: str | None = None
    skills: list[str]
    tags: list[str] = Field(default_factory=list)
    preferred_train_line: str | None = None
    resume_url: str | None = None
    # True when resume_url was withheld because another recruiter sourced this
    # candidate — see recruitment/utils/cv_access.py.
    cv_locked: bool = False
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
