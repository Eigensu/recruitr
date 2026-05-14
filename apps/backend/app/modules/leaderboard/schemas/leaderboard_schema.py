from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.common.dtos.pagination import PaginationMeta
from app.modules.leaderboard.enums import BadgeTypeEnum


class LeaderboardFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)
    search: str | None = None
    sort_by: str = "rank"
    month: str | None = None


class LeaderboardRecruiterItem(BaseModel):
    id: str
    name: str
    email: str
    initials: str
    rank: int
    xp: int
    level: int
    totalMappings: int
    offersReceived: int
    joined: int
    rejected: int
    monthlyGrowth: float
    successRate: float
    badge: BadgeTypeEnum
    badges: list[BadgeTypeEnum] = Field(default_factory=list)
    monthlyData: list[int] = Field(default_factory=list)
    avatarColor: str


class LeaderboardPage(BaseModel):
    items: list[LeaderboardRecruiterItem]
    meta: PaginationMeta
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class LeaderboardKpi(BaseModel):
    id: str
    label: str
    value: float
    suffix: str | None = None
    helper: str
    tone: Literal["yellow", "green", "red", "navy", "neutral"]


class LeaderboardOverviewResponse(BaseModel):
    kpis: list[LeaderboardKpi]
    top_recruiter: LeaderboardRecruiterItem | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class MonthlyGrowthSeries(BaseModel):
    employee_id: str
    name: str
    monthlyData: list[int]


class MonthlyGrowthResponse(BaseModel):
    labels: list[str]
    series: list[MonthlyGrowthSeries]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CompanyProgressItem(BaseModel):
    company: str
    role: str
    totalSeats: int
    filled: int
    recruiterCount: int


class CompanyProgressResponse(BaseModel):
    items: list[CompanyProgressItem]
    generated_at: datetime = Field(default_factory=datetime.utcnow)