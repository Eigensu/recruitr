import asyncio
import logging

from app.celery_app import celery_app
from app.database import init_db
from app.modules.leaderboard.enums import ActivityTypeEnum
from app.modules.leaderboard.service.leaderboard_service import handle_activity

logger = logging.getLogger(__name__)


async def _run_activity(
    employee_id: str,
    candidate_id: str | None,
    action_type: str,
    reference_id: str,
    title: str,
    description: str,
) -> bool:
    await init_db()
    try:
        activity_type = ActivityTypeEnum(action_type)
    except ValueError:
        logger.exception("Invalid leaderboard activity type: %s", action_type)
        return False
    return await handle_activity(
        employee_id, candidate_id, activity_type, reference_id, title, description
    )


@celery_app.task(name="leaderboard.process_activity")
def process_activity(
    employee_id: str,
    candidate_id: str | None,
    action_type: str,
    activity_reference_id: str,
    title: str,
    description: str,
) -> bool:
    return asyncio.run(
        _run_activity(
            employee_id, candidate_id, action_type, activity_reference_id, title, description
        )
    )
