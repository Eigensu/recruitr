"""Celery periodic tasks for the recruitment module (reminders)."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from beanie import PydanticObjectId

from app.celery_app import celery_app
from app.config import settings
from app.modules.dashboard.email_service import EmailService
from app.modules.recruitment.enums import NotificationKind
from app.modules.recruitment.enums.pipeline_stage import PipelineStage
from app.modules.recruitment.models import Candidate, ClientUser, Mapping, Notification, Position

logger = logging.getLogger(__name__)

# reminder_type (this module's own vocabulary, tied to reminder_key prefixes
# above) -> the in-app NotificationKind shown on the dashboard bell.
_NOTIFICATION_KIND = {
    "client_action": NotificationKind.awaiting_decision,
    "interview_followup": NotificationKind.awaiting_interview_decision,
    "offer_upload": NotificationKind.awaiting_offer_upload,
}
_NOTIFICATION_MESSAGE = {
    "client_action": "is waiting on your decision to move to interview.",
    "interview_followup": "is waiting on your post-interview decision.",
    "offer_upload": "has been selected — upload their offer letter.",
}


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


async def _create_notification(
    mapping: Mapping,
    reminder_type: str,
    client_id: PydanticObjectId | None,
    candidate_name: str,
) -> None:
    """Insert one in-app reminder for the dashboard bell.

    Called at most once per (mapping, reminder_type) — the caller only gets
    here once per reminder_key via Mapping.reminders_sent, so no separate
    idempotency check is needed here.
    """
    await Notification(
        brand_id=mapping.brand_id,
        client_id=client_id,
        mapping_id=mapping.id,
        kind=_NOTIFICATION_KIND[reminder_type],
        message=f"{candidate_name} {_NOTIFICATION_MESSAGE[reminder_type]}",
    ).insert()


async def _send_client_reminders(mapping: Mapping, reminder_type: str) -> None:
    candidate = await Candidate.get(mapping.candidate_id)
    if not candidate:
        return

    # Staff-wide in-app fallback (client_id=None) — independent of whether
    # this mapping has a client_id or any active client user yet, per the
    # spec's "these functionalities also to exist with my team" requirement.
    await _create_notification(mapping, reminder_type, None, candidate.full_name)

    if not mapping.client_id:
        return

    # Client-facing in-app notification, alongside the existing email below.
    await _create_notification(mapping, reminder_type, mapping.client_id, candidate.full_name)

    position = await Position.get(mapping.position_id)
    if not position:
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


@celery_app.task(name="recruitment.process_new_position_notifications")
def process_new_position_notifications(
    position_id: str, brand_id: str, created_by_name: str
) -> None:
    """Send notifications when a client creates a new position."""
    from app.database import init_db
    from app.modules.recruitment.enums.activity_type import ActivityType
    from app.modules.recruitment.models import ActivityLog, Employee, Position

    async def run():
        await init_db()
        from beanie import PydanticObjectId

        pos = await Position.get(PydanticObjectId(position_id))
        if not pos:
            return

        # 1. In-app notification via ActivityLog (for all recruiters in brand to see)
        desc = f"Client {pos.client_name} created a new position: {pos.role} ({pos.total_seats} seats)."
        activity = ActivityLog(
            brand_id=PydanticObjectId(brand_id),
            employee_id=None,
            activity_type=ActivityType.position_created,
            target_entity_type="position",
            target_entity_id=position_id,
            description=desc,
        )
        await activity.insert()

        # 2. Email notification
        # Fetch internal recipients (e.g. all active employees for this brand, or specific admins)
        # For now, email all active employees in the brand to ensure someone sees it.
        # Alternatively, we could email a configured master email.
        employees = await Employee.find(
            Employee.brand_id == PydanticObjectId(brand_id),
            Employee.is_active == True,  # noqa: E712
        ).to_list()

        portal_url = f"{settings.FRONTEND_URL}/positions/{position_id}"

        for emp in employees:
            EmailService.send_new_position_notification(
                email=emp.email,
                role=pos.role,
                client_name=pos.client_name,
                category=pos.department.value if pos.department else "N/A",
                salary=pos.salary,
                seats=pos.total_seats,
                city=pos.city,
                mumbai_area=pos.mumbai_area,
                seniority=pos.seniority.value if pos.seniority else "N/A",
                created_by=created_by_name,
                portal_url=portal_url,
            )

    asyncio.run(run())


@celery_app.task(name="recruitment.process_joining_dates")
def process_joining_dates() -> None:
    """Run daily to auto-transition candidates who have reached their joining date."""
    from app.database import init_db

    async def run():
        await init_db()
        from datetime import UTC, datetime

        from app.modules.recruitment.enums import Decision, PipelineStage
        from app.modules.recruitment.models import Mapping
        from app.modules.recruitment.repository_impl import move_stage
        from app.modules.recruitment.schemas import TenantScope

        now = datetime.now(UTC)

        # Find candidates whose joining date is today or in the past, and who are currently selected
        mappings_to_join = await Mapping.find(
            Mapping.stage == PipelineStage.selected.value,
            Mapping.joining_date != None,  # noqa: E711
            Mapping.joining_date <= now,
        ).to_list()

        for mapping in mappings_to_join:
            # We construct a mock system scope since this is a background job
            # The employee_id is None since it's an automated action
            sys_scope = TenantScope(brand_id=mapping.brand_id)

            # Transition to position_close (Joined). actor="system" so
            # move_stage() doesn't overwrite Mapping.employee_id (a required
            # field) with the None on this scope.
            await move_stage(
                mapping=mapping,
                new_stage=PipelineStage.joined,
                decision=Decision.pending,
                scope=sys_scope,
                actor="system",
            )

    import asyncio

    asyncio.run(run())
