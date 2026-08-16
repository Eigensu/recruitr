"""Celery periodic tasks for the dashboard module (including referee operations)."""

import asyncio
import logging

from app.celery_app import celery_app
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
