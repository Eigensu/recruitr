"""Beanie Document model for Recruiter gamification profiles."""

from datetime import datetime

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import IndexModel


class RecruiterProfile(Document):
    user_id: str
    brand_id: PydanticObjectId
    daily_score: int = 0
    weekly_score: int = 0
    badges: list[str] = Field(default_factory=list)
    last_reset: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "recruiters"
        indexes = [
            IndexModel("user_id", unique=True),
            IndexModel("brand_id"),
            IndexModel([("brand_id", 1), ("daily_score", -1)]),   # leaderboard sort
            IndexModel([("brand_id", 1), ("weekly_score", -1)]),
        ]
