import asyncio
from datetime import datetime

from app.celery_app import celery_app
from app.database import init_db
from app.modules.leaderboard.service.leaderboard_service import refresh_monthly_snapshot, refresh_rankings


async def _refresh() -> bool:
    await init_db()
    await refresh_rankings()
    return True


async def _snapshot(month: str | None = None) -> int:
    await init_db()
    target = month or datetime.utcnow().strftime("%Y-%m")
    count = await refresh_monthly_snapshot(target)
    await refresh_rankings()
    return count


@celery_app.task(name="leaderboard.refresh_cache")
def refresh_cache() -> bool:
    return asyncio.run(_refresh())


@celery_app.task(name="leaderboard.create_monthly_snapshot")
def create_monthly_snapshot(month: str | None = None) -> int:
    return asyncio.run(_snapshot(month))