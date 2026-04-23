"""Pydantic schemas for the Positions API."""

from typing import Literal

from pydantic import BaseModel


class MatchedCandidateSchema(BaseModel):
    candidate_id: str
    status: Literal["pending", "accepted", "rejected"]
    feedback: str | None = None


class PositionCreate(BaseModel):
    title: str
    requirements: list[str]


class PositionUpdate(BaseModel):
    title: str | None = None
    requirements: list[str] | None = None
    status: Literal["open", "filled", "archived"] | None = None


class PositionResponse(BaseModel):
    id: str
    brand_id: str
    title: str
    requirements: list[str]
    status: Literal["open", "filled", "archived"]
    matched_candidates: list[MatchedCandidateSchema]

    model_config = {"from_attributes": True}
