"""Gamification API router."""

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.gamification import service
from app.modules.gamification.schemas import LeaderboardEntry, RecruiterStatsResponse

router = APIRouter()


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    brand_id: str = Query(..., description="Brand (org) ObjectId"),
    period: str = Query("daily", pattern="^(daily|weekly)$"),
    _: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> list[LeaderboardEntry]:
    """Return ranked recruiter list for a brand, sorted by daily or weekly score."""
    return await service.get_leaderboard(brand_id, period)


@router.get("/me", response_model=RecruiterStatsResponse)
async def get_my_stats(
    current_user: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> RecruiterStatsResponse:
    """Return the current recruiter's personal gamification stats."""
    recruiter = await service.get_recruiter_with_lazy_reset(current_user.sub)
    if not recruiter:
        return RecruiterStatsResponse(
            user_id=current_user.sub,
            daily_score=0,
            weekly_score=0,
            badges=[],
        )

    return RecruiterStatsResponse(
        user_id=recruiter.user_id,
        daily_score=recruiter.daily_score,
        weekly_score=recruiter.weekly_score,
        badges=recruiter.badges,
    )
