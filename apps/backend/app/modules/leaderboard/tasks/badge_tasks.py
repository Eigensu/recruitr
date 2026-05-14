import asyncio

from beanie import PydanticObjectId

from app.celery_app import celery_app
from app.database import init_db
from app.modules.leaderboard.models import EmployeeStat
from app.modules.leaderboard.repository.writes import unlock_badges
from app.modules.leaderboard.utils.badge_engine import evaluate_badges
from app.modules.leaderboard.utils.cache_manager import invalidate_leaderboard_cache


async def _evaluate(employee_id: str) -> int:
    await init_db()
    oid = PydanticObjectId(employee_id)
    stat = await EmployeeStat.get_motor_collection().find_one({"employee_id": oid})
    if not stat:
        return 0
    badges = evaluate_badges(stat)
    await unlock_badges(oid, badges)
    await invalidate_leaderboard_cache()
    return len(badges)


@celery_app.task(name="leaderboard.evaluate_badges")
def evaluate_recruiter_badges(employee_id: str) -> int:
    return asyncio.run(_evaluate(employee_id))