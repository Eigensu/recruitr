"""Beanie models for leaderboard collections."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, PydanticObjectId, Replace, Update, before_event
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.modules.leaderboard.enums import ActivityTypeEnum, BadgeRarityEnum, BadgeTypeEnum


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _touch(document: Document) -> None:
    document.updated_at = _utcnow()  # type: ignore[attr-defined]


class LeaderboardMappings(BaseModel):
    offers_received: int = 0
    joined_candidates: int = 0
    rejected_candidates: int = 0
    total_mappings: int = 0


class EmployeeStat(Document):
    employee_id: PydanticObjectId
    mappings: LeaderboardMappings = Field(default_factory=LeaderboardMappings)
    total_score: int = 0
    leaderboard_rank: int = 0
    monthly_growth: float = 0
    xp_points: int = 0
    level: int = 1
    streak_days: int = 0
    badges: list[BadgeTypeEnum] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "employee_stats"
        indexes = [
            IndexModel("employee_id", unique=True),
            IndexModel("total_score"),
            IndexModel("leaderboard_rank"),
            IndexModel("updated_at"),
        ]


class LeaderboardHistory(Document):
    employee_id: PydanticObjectId
    month: str
    total_mappings: int = 0
    offers_received: int = 0
    joined_candidates: int = 0
    rejected_candidates: int = 0
    success_rate: float = 0
    monthly_growth: float = 0
    leaderboard_rank: int = 0
    total_score: int = 0
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "leaderboard_history"
        indexes = [
            IndexModel([("employee_id", 1), ("month", 1)], unique=True),
            IndexModel("month"),
            IndexModel("leaderboard_rank"),
        ]


class Badge(Document):
    name: BadgeTypeEnum
    label: str
    description: str
    icon: str
    rarity: BadgeRarityEnum
    xp_reward: int
    condition_type: str
    condition_value: int
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "badges"
        indexes = [IndexModel("name", unique=True), IndexModel("rarity")]


class RecruiterActivity(Document):
    employee_id: PydanticObjectId
    activity_type: ActivityTypeEnum
    title: str
    description: str
    points_earned: int = 0
    candidate_id: PydanticObjectId | None = None
    activity_reference_id: str
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "recruiter_activity"
        indexes = [
            IndexModel("employee_id"),
            IndexModel("created_at", expireAfterSeconds=7776000),  # 90-day TTL
            IndexModel("activity_reference_id", unique=True),
        ]
