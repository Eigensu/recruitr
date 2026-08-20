"""Celery periodic tasks for the dashboard module (including referee operations)."""

import asyncio
import logging

from app.celery_app import celery_app
from app.database import init_db
from app.modules.dashboard.notifications_service import (
    auto_join_overdue_candidates,
    send_pipeline_reminders,
)
from app.modules.dashboard.referee_service import (
    generate_payment_batch,
    process_daily_referee_updates,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="dashboard.daily_referee_processor")
def daily_referee_processor() -> None:
    """Daily cron task to handle referee eligibility, emails, and payments."""
    logger.info("Starting dashboard.daily_referee_processor")

    async def _run() -> None:
        # First process daily eligibility + emails
        await process_daily_referee_updates()
        # Then check if today is the payment processing day and generate payments
        await generate_payment_batch()

    try:
        asyncio.run(_run())
        logger.info("Successfully completed dashboard.daily_referee_processor")
    except Exception:
        logger.exception("Error in dashboard.daily_referee_processor")


@celery_app.task(name="dashboard.pipeline_action_reminders")
def pipeline_action_reminders() -> None:
    """Hourly sweep: notify the client (and staff, as a fallback) for every
    mapping sitting unactioned 2+ days at a decision or offer-upload gate."""
    logger.info("Starting dashboard.pipeline_action_reminders")

    async def _run() -> None:
        await init_db()
        await send_pipeline_reminders()

    try:
        asyncio.run(_run())
        logger.info("Successfully completed dashboard.pipeline_action_reminders")
    except Exception:
        logger.exception("Error in dashboard.pipeline_action_reminders")


@celery_app.task(name="dashboard.auto_join_candidates")
def auto_join_candidates() -> None:
    """Daily sweep: move every mapping whose joining_date has arrived to Joined."""
    logger.info("Starting dashboard.auto_join_candidates")

    async def _run() -> None:
        await init_db()
        await auto_join_overdue_candidates()

    try:
        asyncio.run(_run())
        logger.info("Successfully completed dashboard.auto_join_candidates")
    except Exception:
        logger.exception("Error in dashboard.auto_join_candidates")
