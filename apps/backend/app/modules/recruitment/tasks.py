"""Celery periodic tasks for the recruitment module (reminders)."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.celery_app import celery_app
from app.config import settings
from app.modules.dashboard.email_service import EmailService
from app.modules.recruitment.enums.pipeline_stage import PipelineStage
from app.modules.recruitment.models import Candidate, ClientUser, Mapping, Position

logger = logging.getLogger(__name__)


async def _process_reminders_async() -> None:
    now = datetime.now(UTC)
    two_days_ago = now - timedelta(days=2)

    # 1. Client action reminder (sent_to_client for > 2 days)
    mappings_sent = await Mapping.find(
        Mapping.stage == PipelineStage.sent_to_client,
        Mapping.updated_at < two_days_ago,
    ).to_list()

    for mapping in mappings_sent:
        # Use a hash key tied to the timestamp it entered the stage (updated_at)
        reminder_key = f"client_action_{mapping.updated_at.isoformat()}"
        if reminder_key not in mapping.reminders_sent:
            await _send_client_reminders(mapping, "client_action")
            mapping.reminders_sent.append(reminder_key)
            await mapping.save()

    # 2. Interview follow-up reminder (interview_date > 2 days ago)
    mappings_interview = await Mapping.find(
        Mapping.stage == PipelineStage.interview,
        Mapping.interview_date != None,  # noqa: E711
        Mapping.interview_date < two_days_ago,
    ).to_list()

    for mapping in mappings_interview:
        reminder_key = f"interview_followup_{mapping.interview_date.isoformat() if mapping.interview_date else 'none'}"
        if reminder_key not in mapping.reminders_sent:
            await _send_client_reminders(mapping, "interview_followup")
            mapping.reminders_sent.append(reminder_key)
            await mapping.save()

    # 3. Offer upload reminder (selected for > 2 days, no offer letter)
    mappings_selected = await Mapping.find(
        Mapping.stage == PipelineStage.selected,
        Mapping.offer_letter_url == None,  # noqa: E711
        Mapping.updated_at < two_days_ago,
    ).to_list()

    for mapping in mappings_selected:
        reminder_key = f"offer_upload_{mapping.updated_at.isoformat()}"
        if reminder_key not in mapping.reminders_sent:
            await _send_client_reminders(mapping, "offer_upload")
            mapping.reminders_sent.append(reminder_key)
            await mapping.save()


async def _send_client_reminders(mapping: Mapping, reminder_type: str) -> None:
    if not mapping.client_id:
        return

    position = await Position.get(mapping.position_id)
    if not position:
        return

    candidate = await Candidate.get(mapping.candidate_id)
    if not candidate:
        return

    # Find active client users for this client_id
    client_users = await ClientUser.find(
        ClientUser.client_id == mapping.client_id,
        ClientUser.is_active == True,  # noqa: E712
    ).to_list()

    if not client_users:
        return

    portal_url = f"{settings.FRONTEND_URL}/pipeline"

    for user in client_users:
        if reminder_type == "client_action":
            EmailService.send_client_action_reminder(
                email=user.email,
                candidate_name=candidate.full_name,
                position_code=position.code,
                portal_url=portal_url,
            )
        elif reminder_type == "interview_followup":
            EmailService.send_interview_followup(
                email=user.email,
                candidate_name=candidate.full_name,
                position_code=position.code,
                portal_url=portal_url,
            )
        elif reminder_type == "offer_upload":
            EmailService.send_offer_upload_reminder(
                email=user.email,
                candidate_name=candidate.full_name,
                position_code=position.code,
                portal_url=portal_url,
            )


@celery_app.task(name="recruitment.process_reminders")
def process_reminders() -> None:
    """Run daily to send reminders to clients."""
    from app.database import init_db

    async def run():
        await init_db()
        await _process_reminders_async()

    asyncio.run(run())
