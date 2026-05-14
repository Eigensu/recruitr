"""Leaderboard API route handlers."""

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, status

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.leaderboard.schemas import (
    ActivityPage,
    CompanyProgressResponse,
    LeaderboardFilters,
    LeaderboardOverviewResponse,
    LeaderboardPage,
    MonthlyGrowthResponse,
    RecruiterBadgesResponse,
)
from app.modules.leaderboard.schemas.analytics_schema import RecruiterAnalyticsResponse
from app.modules.leaderboard.service import leaderboard_service as service

router = APIRouter()


@router.get("/overview", response_model=LeaderboardOverviewResponse)
async def get_overview(_: TokenPayload = Depends(get_current_user)) -> LeaderboardOverviewResponse:
    return await service.get_overview()


@router.get("/rankings", response_model=LeaderboardPage)
async def get_rankings(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="rank"),
    month: str | None = Query(default=None),
    _: TokenPayload = Depends(get_current_user),
) -> LeaderboardPage:
    return await service.get_rankings(LeaderboardFilters(page=page, limit=limit, search=search, sort_by=sort_by, month=month))


@router.get("/recruiter/{employee_id}", response_model=RecruiterAnalyticsResponse)
async def get_recruiter(employee_id: str, _: TokenPayload = Depends(get_current_user)) -> RecruiterAnalyticsResponse:
    payload = await service.get_recruiter(employee_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found")
    return RecruiterAnalyticsResponse.model_validate(payload)


@router.get("/monthly-growth", response_model=MonthlyGrowthResponse)
async def get_monthly_growth(_: TokenPayload = Depends(get_current_user)) -> MonthlyGrowthResponse:
    return await service.get_monthly_growth()


@router.get("/company-progress", response_model=CompanyProgressResponse)
async def get_company_progress(_: TokenPayload = Depends(get_current_user)) -> CompanyProgressResponse:
    return await service.get_company_progress()


@router.get("/activity", response_model=ActivityPage)
async def get_activity(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> ActivityPage:
    return await service.get_activities(page, limit)


@router.get("/badges/{employee_id}", response_model=RecruiterBadgesResponse)
async def get_badges(employee_id: str, _: TokenPayload = Depends(get_current_user)) -> RecruiterBadgesResponse:
    return await service.get_badges(employee_id)