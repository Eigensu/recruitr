from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.common.dtos.pagination import PaginationMeta
from app.modules.leaderboard.enums import ActivityTypeEnum
from app.modules.leaderboard.schemas.leaderboard_schema import LeaderboardRecruiterItem


class RecruiterAnalyticsResponse(BaseModel):
    recruiter: LeaderboardRecruiterItem
    rank_percentile: float
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ActivityItem(BaseModel):
    id: str
    recruiter: str
    initials: str
    action: str
    target: str
    timestamp: datetime
    tone: Literal["yellow", "green", "red", "neutral"]
    avatarColor: str
    activity_type: ActivityTypeEnum


class ActivityPage(BaseModel):
    items: list[ActivityItem]
    meta: PaginationMeta
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
