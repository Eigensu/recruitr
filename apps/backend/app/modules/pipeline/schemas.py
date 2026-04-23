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
