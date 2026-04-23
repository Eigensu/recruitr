"""Beanie Document model for job Positions."""

from typing import Literal

from beanie import Document
from beanie import PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import IndexModel


class MatchedCandidate(BaseModel):
    candidate_id: PydanticObjectId
    status: Literal["pending", "accepted", "rejected"] = "pending"
    feedback: str | None = None


class Position(Document):
    brand_id: PydanticObjectId
    title: str
    requirements: list[str] = Field(default_factory=list)  # keyword list
    status: Literal["open", "filled", "archived"] = "open"
    matched_candidates: list[MatchedCandidate] = Field(default_factory=list)

    class Settings:
        name = "positions"
        indexes = [
            IndexModel("brand_id"),
            IndexModel("status"),
        ]
