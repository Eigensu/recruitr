"""Pydantic schemas for the Candidates API."""

from typing import Literal

from pydantic import BaseModel, EmailStr


class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    extracted_skills: list[str] = []
    # ── New ───────────────────────────────────────────────────────────────────
    cv_link: str | None = None
    source: Literal["internal", "external"] = "internal"
    tags: list[str] = []


class CandidateUpdate(BaseModel):
    """Partial update — all fields optional."""

    name: str | None = None
    phone: str | None = None
    cv_link: str | None = None
    source: Literal["internal", "external"] | None = None
    tags: list[str] | None = None


class CandidateListFilters(BaseModel):
    """Query parameters for GET /candidates."""

    search: str | None = None
    source: Literal["internal", "external"] | None = None
    tags: list[str] | None = None  # ?tags=python&tags=senior  (AND semantics)
    has_resume: bool | None = None
    has_cv_link: bool | None = None
    page: int = 1
    limit: int = 50


class CandidateUploadConfirm(BaseModel):
    """Sent after a successful Cloudinary upload to register the asset."""

    candidate_id: str
    resume_public_id: str
    resume_url: str


class CandidateResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None = None
    resume_url: str | None = None
    extracted_skills: list[str]
    # ── New ───────────────────────────────────────────────────────────────────
    tags: list[str] = []
    source: Literal["internal", "external"] = "internal"
    cv_link: str | None = None

    model_config = {"from_attributes": True}


class CandidateMatchScore(CandidateResponse):
    """Candidate with a computed keyword match score (from aggregation)."""

    match_score: float


class BulkUploadFailure(BaseModel):
    filename: str
    reason: str


class BulkUploadResult(BaseModel):
    created: int
    updated: int
    failed: list[BulkUploadFailure]
