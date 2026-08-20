"""Candidate resource DTOs."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.common.dtos.pagination import PaginatedResponse
from app.modules.recruitment.enums import (
    CandidateEventType,
    CandidateStatus,
    Department,
    Gender,
    PipelineStage,
)


class CandidateStructuredTags(BaseModel):
    communication: str | None = None
    education: str | None = None
    brand_experience: str | None = None
    department: Department | None = None
    specialization: str | None = None

    @model_validator(mode="after")
    def validate_department_specialization(self) -> "CandidateStructuredTags":
        if self.department and not self.specialization:
            raise ValueError("Specialization is required when a department is selected")
        return self


class CandidateCreate(CandidateStructuredTags):
    full_name: str
    email: EmailStr | None = None
    phone: str = Field(..., min_length=1)
    previous_company: str | None = None
    experience_years: float = Field(default=0, ge=0)
    education_level: str | None = None
    city: str | None = None
    area: str | None = None
    gender: Gender | None = None
    age: int | None = Field(default=None, ge=0)
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    preferred_train_line: str | None = None
    cv_link: str | None = None
    current_role: str | None = None
    expected_salary: float | None = Field(default=None, ge=0)
    notice_period: str | None = None
    source: str | None = None
    source_channel: str | None = None
    connect_code: str | None = None
    salary: float | None = Field(default=None, ge=0)
    notes: str | None = None


class CandidateCreateStrict(CandidateCreate):
    """Strictly validates all recruiter-presented fields during manual creation & bulk upload.
    This preserves CandidateCreate and CandidateUpdate as partials for legacy operations."""

    full_name: str = Field(..., min_length=1)
    email: EmailStr | None = None
    phone: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    communication: str = Field(..., min_length=1)
    education: str = Field(..., min_length=1)
    brand_experience: str = Field(..., min_length=1)
    department: Department = Field(...)
    specialization: str = Field(..., min_length=1)
    current_role: str = Field(..., min_length=1)
    experience_years: float = Field(..., ge=0)
    city: str = Field(..., min_length=1)
    area: str | None = None
    gender: Gender = Field(...)
    age: int | None = Field(default=None, gt=0)
    expected_salary: float = Field(..., ge=0)
    salary: float = Field(..., ge=0)
    notice_period: str = Field(..., min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_conditional(self) -> "CandidateCreateStrict":
        if self.source:
            self.source = self.source.strip()

        if self.source not in ("internal", "external"):
            raise ValueError("Source must be internal or external")

        if self.source == "external":
            if not self.source_channel or not self.source_channel.strip():
                raise ValueError("Source Channel is required for external source")
            if not self.cv_link or not self.cv_link.strip():
                raise ValueError("CV Link is required for external source")

            self.cv_link = self.cv_link.strip()
            if not re.match(r"^https?://", self.cv_link, re.IGNORECASE):
                raise ValueError("CV Link must be a valid HTTP(S) URL")

        return self


class CandidateUpdate(CandidateStructuredTags):
    full_name: str | None = None
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float | None = Field(default=None, ge=0)
    education_level: str | None = None
    city: str | None = None
    area: str | None = None
    gender: Gender | None = None
    age: int | None = Field(default=None, ge=0)
    skills: list[str] | None = None
    tags: list[str] | None = None
    preferred_train_line: str | None = None
    cv_link: str | None = None
    current_role: str | None = None
    expected_salary: float | None = Field(default=None, ge=0)
    notice_period: str | None = None
    source: str | None = None
    source_channel: str | None = None
    connect_code: str | None = None
    salary: float | None = Field(default=None, ge=0)
    notes: str | None = None
    status: CandidateStatus | None = None


class CandidateResponse(CandidateStructuredTags):
    id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float
    education_level: str | None = None
    city: str | None = None
    area: str | None = None
    gender: Gender | None = None
    age: int | None = None
    skills: list[str]
    tags: list[str] = Field(default_factory=list)
    preferred_train_line: str | None = None
    cv_link: str | None = None
    resume_url: str | None = None
    current_stage: PipelineStage
    mappings_count: int = 0
    current_role: str | None = None
    expected_salary: float | None = None
    notice_period: str | None = None
    source: str | None = None
    source_channel: str | None = None
    connect_code: str | None = None
    salary: float | None = None
    notes: str | None = None
    # Defaulted, not required: candidates created before `status` existed have no
    # such field, and the list endpoint validates raw aggregation output rather
    # than Beanie documents — so a required field here 500s the whole directory.
    # Mirrors Candidate.status, and matches the query's treatment of a missing
    # status as approved.
    status: CandidateStatus = CandidateStatus.approved
    # The recruiter who added this candidate. Null for public-form applications
    # and for records that predate the field.
    created_by_id: str | None = None
    created_by_name: str | None = None
    # True when the CV was withheld from this viewer because another recruiter
    # sourced the candidate — resume_url and cv_link are null for that reason,
    # not because the candidate has no CV on file. See utils/cv_access.py.
    cv_locked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_document(
        cls,
        doc,
        mappings_count: int = 0,
        *,
        created_by_name: str | None = None,
        cv_locked: bool = False,
    ) -> "CandidateResponse":
        """Build the response from a Candidate document.

        Lives on the DTO because both the authenticated candidate endpoints and
        the public application form return this shape. They each spelled the
        same field list out by hand, so the two copies could drift and every new
        field had to be remembered twice.

        Not model_validate(doc): `id` needs str() from an ObjectId, and
        mappings_count is a per-request count that is not on the document.

        `cv_locked` is decided by the caller, which knows who is asking; the
        blanking itself happens here so no call site can set the flag and still
        hand the URL over.
        """
        return cls(
            id=str(doc.id),
            full_name=doc.full_name,
            email=doc.email,
            phone=doc.phone,
            previous_company=doc.previous_company,
            experience_years=doc.experience_years,
            education_level=doc.education_level,
            city=doc.city,
            area=doc.area,
            gender=doc.gender,
            age=doc.age,
            skills=doc.skills,
            tags=doc.tags,
            communication=doc.communication,
            education=doc.education,
            brand_experience=doc.brand_experience,
            department=doc.department,
            specialization=doc.specialization,
            preferred_train_line=doc.preferred_train_line,
            cv_link=None if cv_locked else doc.cv_link,
            resume_url=None if cv_locked else doc.resume_url,
            current_stage=doc.current_stage,
            mappings_count=mappings_count,
            current_role=doc.current_role,
            expected_salary=doc.expected_salary,
            notice_period=doc.notice_period,
            salary=doc.salary,
            notes=doc.notes,
            source=doc.source,
            source_channel=doc.source_channel,
            connect_code=doc.connect_code,
            status=doc.status,
            created_by_id=str(doc.created_by_id) if doc.created_by_id else None,
            created_by_name=created_by_name,
            cv_locked=cv_locked,
            created_at=doc.created_at,
        )


class CandidateMappingItem(BaseModel):
    """One active position mapping — returned by GET /candidates/{id}/mappings."""

    mapping_id: str
    position_id: str
    position_code: str
    role: str
    client_name: str
    city: str | None = None
    stage: PipelineStage
    match_score: float | None = None
    mapped_at: datetime


class CandidateHistoryEvent(BaseModel):
    """One entry in the candidate's permanent employment history."""

    # Null on the synthetic opening entry, which is derived from the candidate
    # record itself for profiles created before history was recorded.
    id: str | None = None
    at: datetime
    event_type: CandidateEventType
    employee_id: str | None = None
    employee_name: str | None = None
    position_id: str | None = None
    position_code: str | None = None
    position_role: str | None = None
    client_name: str | None = None
    from_stage: PipelineStage | None = None
    to_stage: PipelineStage | None = None
    note: str | None = None


class CandidatePlacement(BaseModel):
    """A company this candidate was actually placed with.

    Recorded at the point the outcome happened, so it stays on the profile after
    the position closes or the candidate is taken off the board.
    """

    position_id: str | None = None
    position_code: str | None = None
    role: str | None = None
    client_name: str | None = None
    stage: PipelineStage  # offer_accepted or position_close
    at: datetime
    employee_name: str | None = None
    # False once the candidate is no longer sitting in that stage — the
    # placement happened, but something moved afterwards.
    is_current: bool = True


class CandidateHistoryResponse(BaseModel):
    """GET /candidates/{id}/history — the ATS view of one person."""

    events: list[CandidateHistoryEvent]
    placements: list[CandidatePlacement]


class CandidatePage(PaginatedResponse[CandidateResponse]):
    pass


ExperienceFilter = Literal["lt2", "2to5", "gt5"]


class BulkUploadFailure(BaseModel):
    filename: str
    reason: str


class BulkUploadResult(BaseModel):
    created: int
    updated: int
    failed: list[BulkUploadFailure]
