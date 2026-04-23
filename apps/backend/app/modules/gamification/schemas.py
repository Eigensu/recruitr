"""Pydantic schemas for gamification endpoints."""

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    user_id: str
    daily_score: int
    weekly_score: int
    badges: list[str]
    rank: int


class RecruiterStatsResponse(BaseModel):
    user_id: str
    daily_score: int
    weekly_score: int
    badges: list[str]
