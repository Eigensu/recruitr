"""Pydantic schemas for the Candidates API."""

from pydantic import BaseModel, EmailStr


class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    extracted_skills: list[str] = []


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

    model_config = {"from_attributes": True}


class CandidateMatchScore(CandidateResponse):
    """Candidate with a computed keyword match score (from aggregation)."""

    match_score: float
