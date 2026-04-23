"""Pydantic schemas for the pipeline (matching) module."""

from pydantic import BaseModel
from typing import Literal


class MatchRequest(BaseModel):
    position_id: str
    candidate_id: str
    target_status: Literal["pending", "accepted", "rejected"] = "pending"


class MatchResponse(BaseModel):
    position_id: str
    candidate_id: str
    status: str
    recruiter_daily_score: int
