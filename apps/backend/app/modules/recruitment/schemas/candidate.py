"""Candidate resource DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.common.dtos.pagination import PaginatedResponse
from app.modules.recruitment.enums import CandidateStatus, Gender, PipelineStage


class CandidateCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float = Field(default=0, ge=0)
    education_level: str | None = None
    city: str | None = None
    area: str | None = None
    gender: Gender | None = None
    age: int | None = Field(default=None, ge=0)
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    communication: str | None = None
    education: str | None = None
    brand_experience: str | None = None
    department: str | None = None
    specialization: str | None = None
    preferred_train_line: str | None = None
    cv_link: str | None = None
    current_role: str | None = None
    previous_role: str | None = None
    expected_salary: float | None = Field(default=None, ge=0)
    notice_period: str | None = None
    source: str | None = None
    source_channel: str | None = None
    connect_code: str | None = None
    salary: float | None = Field(default=None, ge=0)
    notes: str | None = None


class CandidateUpdate(BaseModel):
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
    communication: str | None = None
    education: str | None = None
    brand_experience: str | None = None
    department: str | None = None
    specialization: str | None = None
    preferred_train_line: str | None = None
    cv_link: str | None = None
    current_role: str | None = None
    previous_role: str | None = None
    expected_salary: float | None = Field(default=None, ge=0)
    notice_period: str | None = None
    source: str | None = None
    source_channel: str | None = None
    connect_code: str | None = None
    salary: float | None = Field(default=None, ge=0)
    notes: str | None = None
    status: CandidateStatus | None = None


class CandidateResponse(BaseModel):
    id: str
    full_name: str
    email: str
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
    communication: str | None = None
    education: str | None = None
    brand_experience: str | None = None
    department: str | None = None
    specialization: str | None = None
    preferred_train_line: str | None = None
    cv_link: str | None = None
    resume_url: str | None = None
    current_stage: PipelineStage
    mappings_count: int = 0
    current_role: str | None = None
    previous_role: str | None = None
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
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_document(cls, doc, mappings_count: int = 0) -> "CandidateResponse":
        """Build the response from a Candidate document.

        Lives on the DTO because both the authenticated candidate endpoints and
        the public application form return this shape. They each spelled the
        same field list out by hand, so the two copies could drift and every new
        field had to be remembered twice.

        Not model_validate(doc): `id` needs str() from an ObjectId, and
        mappings_count is a per-request count that is not on the document.
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
            cv_link=doc.cv_link,
            resume_url=doc.resume_url,
            current_stage=doc.current_stage,
            mappings_count=mappings_count,
            current_role=doc.current_role,
            previous_role=doc.previous_role,
            expected_salary=doc.expected_salary,
            notice_period=doc.notice_period,
            salary=doc.salary,
            notes=doc.notes,
            source=doc.source,
            source_channel=doc.source_channel,
            connect_code=doc.connect_code,
            status=doc.status,
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
