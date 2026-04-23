"""Gamification service — leaderboard and lazy daily score reset."""

from datetime import datetime

from beanie import PydanticObjectId

from app.modules.gamification.models import RecruiterProfile
from app.modules.gamification.schemas import LeaderboardEntry


async def get_recruiter_with_lazy_reset(user_id: str) -> RecruiterProfile | None:
    """Fetch a recruiter profile, lazily resetting daily_score if the date has changed.

    No scheduler needed — the check runs on every read/write, costing one
    date comparison and a conditional save. Negligible at CRM scale.
    """
    recruiter = await RecruiterProfile.find_one(
        RecruiterProfile.user_id == user_id
    )
    if not recruiter:
        return None

    now = datetime.utcnow()
    last = recruiter.last_reset

    # Reset daily
    if now.date() > last.date():
        recruiter.daily_score = 0

        # Reset weekly if it's a new ISO week (or more than 7 days have passed)
        if now.isocalendar()[1] != last.isocalendar()[1] or (now - last).days >= 7:
            recruiter.weekly_score = 0

        recruiter.last_reset = now
        await recruiter.save()

    return recruiter


async def get_leaderboard(brand_id: str, period: str = "daily") -> list[LeaderboardEntry]:
    sort_field = f"{period}_score"

    recruiters = await RecruiterProfile.find(
        RecruiterProfile.brand_id == PydanticObjectId(brand_id)
    ).sort(-getattr(RecruiterProfile, sort_field)).to_list()

    return [
        LeaderboardEntry(
            user_id=rec.user_id,
            daily_score=rec.daily_score,
            weekly_score=rec.weekly_score,
            badges=rec.badges,
            rank=i + 1,
        )
        for i, rec in enumerate(recruiters)
    ]


async def award_badge(user_id: str, badge: str) -> RecruiterProfile | None:
    recruiter = await RecruiterProfile.find_one(
        RecruiterProfile.user_id == user_id
    )
    if recruiter and badge not in recruiter.badges:
        recruiter.badges.append(badge)
        await recruiter.save()
    return recruiter
