"""Candidate resource DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.common.dtos.pagination import PaginatedResponse
from app.modules.recruitment.enums import PipelineStage


class CandidateCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float = Field(default=0, ge=0)
    education_level: str | None = None
    skills: list[str] = Field(default_factory=list)
    ai_tags: list[str] = Field(default_factory=list)
    recruiter_tags: list[str] = Field(default_factory=list)
    preferred_train_line: str | None = None
    cv_link: str | None = None
    current_role: str | None = None
    salary: float | None = Field(default=None, ge=0)
    notes: str | None = None


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float | None = Field(default=None, ge=0)
    education_level: str | None = None
    skills: list[str] | None = None
    ai_tags: list[str] | None = None
    recruiter_tags: list[str] | None = None
    preferred_train_line: str | None = None
    cv_link: str | None = None
    current_role: str | None = None
    salary: float | None = Field(default=None, ge=0)
    notes: str | None = None


class CandidateResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float
    education_level: str | None = None
    skills: list[str]
    ai_tags: list[str] = Field(default_factory=list)
    recruiter_tags: list[str] = Field(default_factory=list)
    preferred_train_line: str | None = None
    cv_link: str | None = None
    resume_url: str | None = None
    current_stage: PipelineStage
    mappings_count: int = 0
    current_role: str | None = None
    salary: float | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


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
