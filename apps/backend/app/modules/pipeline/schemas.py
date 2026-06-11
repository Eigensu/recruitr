"""Pydantic schemas for the pipeline (matching) module."""

from typing import Literal

from pydantic import BaseModel


class MatchRequest(BaseModel):
    position_id: str
    candidate_id: str
    target_status: Literal["pending", "accepted", "rejected"] = "pending"


class MatchResponse(BaseModel):
    position_id: str
    candidate_id: str
    status: str
    recruiter_daily_score: int


class FilteredCandidate(BaseModel):
    """Candidate row for the Kanban filtered view.

    `status` is the Kanban column (pending|accepted|rejected), derived from the
    underlying CandidateMapping.pipeline_stage.
    """

    id: str
    name: str
    email: str
    phone: str | None = None
    resume_url: str | None = None
    extracted_skills: list[str] = []
    tags: list[str] = []
    source: str = "internal"
    cv_link: str | None = None
    status: Literal["pending", "accepted", "rejected"] = "pending"
