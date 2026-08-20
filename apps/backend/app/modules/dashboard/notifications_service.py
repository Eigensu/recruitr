"""Pipeline-action reminder + auto-join background jobs.

Two-day-stuck detection for the client dashboard action widget, and the daily
sweep that moves a mapping to Joined once its joining_date arrives — see
controller/pipeline.py's decision/offer/joining-date endpoints for the
actions these jobs are reminding about or completing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import Decision, NotificationKind, PipelineStage
from app.modules.recruitment.models import Mapping, Notification
from app.modules.recruitment.repository_impl import move_stage
from app.modules.recruitment.schemas import TenantScope

logger = logging.getLogger(__name__)

_STUCK_AFTER = timedelta(days=2)

# (stage, extra match, notification kind, message)
_REMINDER_RULES: list[tuple[PipelineStage, dict, NotificationKind, str]] = [
    (
        PipelineStage.sent_to_client,
        {"decision": Decision.pending.value},
        NotificationKind.awaiting_decision,
        "A candidate is waiting on your decision to move to interview.",
    ),
    (
        PipelineStage.decision_pending,
        {"decision": Decision.pending.value},
        NotificationKind.awaiting_interview_decision,
        "A candidate is waiting on your post-interview decision.",
    ),
    (
        PipelineStage.offer,
        {"offer_document_url": None},
        NotificationKind.awaiting_offer_upload,
        "A selected candidate is waiting on their offer letter.",
    ),
]


async def _notify_once(
    *,
    brand_id: PydanticObjectId,
    client_id: PydanticObjectId | None,
    mapping_id: PydanticObjectId,
    kind: NotificationKind,
    message: str,
) -> None:
    """Create a Notification unless an unread one for this (mapping, kind, recipient)
    already exists — the periodic task runs hourly, this is what stops it spamming
    a new row every run for the same stuck mapping."""
    existing = await Notification.find_one(
        {"mapping_id": mapping_id, "kind": kind.value, "client_id": client_id, "read_at": None}
    )
    if existing:
        return
    await Notification(
        brand_id=brand_id,
        client_id=client_id,
        mapping_id=mapping_id,
        kind=kind,
        message=message,
    ).insert()


async def send_pipeline_reminders() -> None:
    """Notify the client, and staff as a fallback, for every mapping stuck 2+ days
    at a decision/offer gate — the PDF's "Review Action button" requirement."""
    cutoff = datetime.now(UTC) - _STUCK_AFTER

    for stage, extra_match, kind, message in _REMINDER_RULES:
        match = {"stage": stage.value, "updated_at": {"$lte": cutoff}, **extra_match}
        mappings = await Mapping.find(match).to_list()
        for mapping in mappings:
            # mapping.client_id is denormalized and null on mappings written
            # before that field existed (see utils/scoping.py) — skip the
            # client-side notification rather than misfiling it as staff-wide
            # (client_id=None also means "staff"), but always still notify staff.
            if mapping.client_id is not None:
                await _notify_once(
                    brand_id=mapping.brand_id,
                    client_id=mapping.client_id,
                    mapping_id=mapping.id,
                    kind=kind,
                    message=message,
                )
            await _notify_once(
                brand_id=mapping.brand_id,
                client_id=None,
                mapping_id=mapping.id,
                kind=kind,
                message=message,
            )


async def auto_join_overdue_candidates() -> None:
    """Move every offer_accepted mapping whose joining_date has arrived to Joined.

    The PDF's "On said joining date candidate to move to joined" rule. The
    manual "didn't join" override (POST /pipeline/mappings/{id}/mark-not-joined)
    covers the other outcome.
    """
    now = datetime.now(UTC)
    mappings = await Mapping.find(
        {"stage": PipelineStage.offer_accepted.value, "joining_date": {"$lte": now}}
    ).to_list()

    for mapping in mappings:
        scope = TenantScope(brand_id=mapping.brand_id, employee_id=None, role=UserRole.employee)
        try:
            await move_stage(
                mapping=mapping,
                new_stage=PipelineStage.position_close,
                decision=Decision.selected,
                scope=scope,
                actor="system",
            )
        except Exception:
            logger.exception("Failed to auto-join mapping %s", mapping.id)
