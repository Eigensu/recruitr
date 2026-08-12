"""Referee portal business logic and dashboard service."""

import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.dashboard.email_service import EmailService
from app.modules.recruitment.enums import PaymentStatus, PipelineStage, RefereeKanbanStage
from app.modules.recruitment.models import PaymentBatch, RefereeUser, ReferralRecord


def map_stage_to_referee(internal_stage: str) -> str:
    """Map the internal ATS PipelineStage to the Referee-facing stage."""
    mapping = {
        PipelineStage.sourced.value: RefereeKanbanStage.cv_received.value,
        PipelineStage.sent_to_client.value: RefereeKanbanStage.cv_reviewed.value,
        PipelineStage.interview.value: RefereeKanbanStage.interview.value,
        PipelineStage.decision_pending.value: RefereeKanbanStage.interview.value,
        PipelineStage.offer.value: RefereeKanbanStage.offer_extended.value,
        PipelineStage.offer_accepted.value: RefereeKanbanStage.offer_accepted.value,
        PipelineStage.position_close.value: RefereeKanbanStage.joined.value,
    }
    return mapping.get(internal_stage, RefereeKanbanStage.cv_received.value)


async def sync_referral_with_mapping(r: ReferralRecord) -> None:
    """Sync the kanban_stage and joining_date from the canonical Mapping."""
    from app.modules.recruitment.models import Mapping

    mapping = await Mapping.get(r.mapping_id)
    if not mapping:
        return

    # 1. Sync stage
    if mapping.stage not in (PipelineStage.rejected, PipelineStage.on_hold):
        r.kanban_stage = map_stage_to_referee(mapping.stage.value)

    # 2. Sync joining_date
    if mapping.stage == PipelineStage.position_close and not r.joining_date:
        for event in mapping.history:
            if event.stage == PipelineStage.position_close:
                r.joining_date = event.at
                break

    await r.save()


async def get_dashboard_summary(
    brand_id: PydanticObjectId, referee_id: PydanticObjectId
) -> dict[str, Any]:
    """Calculate summary statistics for the referee's dashboard."""
    referrals = await ReferralRecord.find(
        {"brand_id": brand_id, "referee_id": referee_id}
    ).to_list()

    for r in referrals:
        await sync_referral_with_mapping(r)

    cvs_shared = len(referrals)

    from app.modules.recruitment.enums import CandidateEventType
    from app.modules.recruitment.models import CandidateEvent

    cvs_actioned = 0
    for r in referrals:
        if r.kanban_stage != RefereeKanbanStage.cv_received.value:
            cvs_actioned += 1
            continue

        has_activity = await CandidateEvent.find(
            {
                "brand_id": brand_id,
                "candidate_id": r.candidate_id,
                "position_id": r.position_id,
                "event_type": {"$ne": CandidateEventType.mapped.value},
            }
        ).exists()

        if has_activity:
            cvs_actioned += 1

    accrued_earnings = sum(
        r.incentive_amount
        for r in referrals
        if r.payment_status == PaymentStatus.owed.value and r.incentive_amount is not None
    )

    return {
        "cvs_shared": cvs_shared,
        "cvs_actioned": cvs_actioned,
        "accrued_earnings": accrued_earnings,
    }


def calculate_incentive_amount(role_level: str, total_eligible_in_cycle: int) -> float:
    """Determine the incentive amount based on the payment matrix."""
    if role_level == "Entry":
        if total_eligible_in_cycle >= 5:
            return 1500.0
        elif total_eligible_in_cycle >= 3:
            return 1200.0
        else:
            return 1000.0
    elif role_level == "Mid":
        if total_eligible_in_cycle >= 5:
            return 1200.0
        elif total_eligible_in_cycle >= 3:
            return 1000.0
        else:
            return 800.0
    return 0.0


async def process_daily_referee_updates() -> None:
    """Check +7 calendar days eligibility, update matrix, and send emails."""
    now = datetime.now(UTC)
    today = now.date()
    current_cycle_month = today.strftime("%Y-%m")

    # Find ALL referrals that are active but not yet paid (Pending or Owed)
    # We do this globally to process all referees
    referrals = await ReferralRecord.find(
        {"payment_status": {"$in": [PaymentStatus.pending.value, PaymentStatus.owed.value]}}
    ).to_list()

    # Group by referee to recalculate incentives per cycle
    from collections import defaultdict

    referee_map = defaultdict(list)

    from app.modules.recruitment.models import Candidate

    for r in referrals:
        await sync_referral_with_mapping(r)

        # 1. Actioned notification
        if not r.notified_actioned and r.kanban_stage != RefereeKanbanStage.cv_received.value:
            ref_user = await RefereeUser.get(r.referee_id)
            candidate = await Candidate.get(r.candidate_id)
            if ref_user and candidate:
                EmailService.send_referee_actioned(
                    email=ref_user.email,
                    candidate_name=candidate.full_name,
                    stage=r.kanban_stage,
                    portal_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/referee",
                )
                r.notified_actioned = True
                await r.save()

        # 2. Joined notification
        if not r.notified_joined and r.joining_date:
            ref_user = await RefereeUser.get(r.referee_id)
            candidate = await Candidate.get(r.candidate_id)
            if ref_user and candidate:
                EmailService.send_referee_joined(
                    email=ref_user.email,
                    candidate_name=candidate.full_name,
                    joining_date=r.joining_date,
                    portal_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/referee",
                )
                r.notified_joined = True
                await r.save()

        # 3. +7 Day Eligibility Check
        if r.joining_date and not r.joining_plus7_eligible:
            eligible_date = (r.joining_date + timedelta(days=7)).date()
            if eligible_date <= today:
                # Becomes eligible today! Lock in the cycle month.
                r.joining_plus7_eligible = True
                r.payment_status = PaymentStatus.owed.value
                r.cycle_month = current_cycle_month
                await r.save()

        # Collect for incentive calculation if eligible
        if r.joining_plus7_eligible and r.cycle_month:
            referee_map[r.referee_id].append(r)

    # 4. Recalculate incentives per referee and per cycle month
    for _referee_id, refs in referee_map.items():
        # Group by cycle_month for this referee
        cycle_groups = defaultdict(list)
        for r in refs:
            cycle_groups[r.cycle_month].append(r)

        for _cycle_month, cycle_refs in cycle_groups.items():
            eligible_count = len(cycle_refs)
            for r in cycle_refs:
                new_incentive = calculate_incentive_amount(r.role_level or "Entry", eligible_count)
                if r.incentive_amount != new_incentive:
                    r.incentive_amount = new_incentive
                    await r.save()


async def get_referrals(
    brand_id: PydanticObjectId, referee_id: PydanticObjectId
) -> list[dict[str, Any]]:
    """Get the candidate journey for the referee."""
    # DO NOT call update_eligibility_and_incentives here. This is a read-only endpoint.

    referrals = await ReferralRecord.find(
        {"brand_id": brand_id, "referee_id": referee_id}
    ).to_list()

    from app.modules.recruitment.models import Candidate

    result = []
    for r in referrals:
        candidate = await Candidate.get(r.candidate_id)
        candidate_name = candidate.full_name if candidate else "Unknown Candidate"

        parts = candidate_name.split()
        masked_name = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else candidate_name

        result.append(
            {
                "id": str(r.id),
                "candidate_name": masked_name,
                "role_level": r.role_level,
                "submission_date": r.submission_date,
                "kanban_stage": r.kanban_stage,
                "joining_date": r.joining_date,
                "joining_plus7_eligible": r.joining_plus7_eligible,
                "incentive_status": r.payment_status,
                "incentive_amount": r.incentive_amount,
                "payment_status": r.payment_status,
                "payment_date": r.payment_date,
            }
        )

    return result


def is_bank_holiday(d: datetime) -> bool:
    """
    Check if the given date is a bank holiday.

    LIMITATION: The project currently lacks an authoritative HRIS holiday
    calendar source. Live bank-holiday detection remains configuration-dependent.
    For now, this safely returns False to avoid fabricating holidays.
    """
    # TODO: Integrate with actual company holiday configuration mechanism
    return False


def _get_next_working_day(d: datetime) -> datetime:
    """Move to next working day if weekend or bank holiday."""
    # 5 = Saturday, 6 = Sunday
    while d.weekday() >= 5 or is_bank_holiday(d):
        d += timedelta(days=1)
    return d


async def generate_payment_batch() -> None:
    """Cron-ready service to generate a payment batch for the previous month."""
    now = datetime.now(UTC)

    # Calculate the payment processing day for the current month
    scheduled_payment_date = datetime(now.year, now.month, 7, tzinfo=UTC)
    actual_payment_date = _get_next_working_day(scheduled_payment_date)

    # If today is not the actual payment date, do nothing
    if now.date() != actual_payment_date.date():
        return

    # The cycle being paid is the previous month
    first_day_of_this_month = datetime(now.year, now.month, 1)
    last_month_date = first_day_of_this_month - timedelta(days=1)
    target_cycle_month = last_month_date.strftime("%Y-%m")

    # Find all eligible unpaid referrals for the target cycle
    referrals = await ReferralRecord.find(
        {"payment_status": PaymentStatus.owed.value, "cycle_month": target_cycle_month}
    ).to_list()

    # Group by referee
    from collections import defaultdict

    by_referee = defaultdict(list)
    for r in referrals:
        by_referee[(r.brand_id, r.referee_id)].append(r)

    for (brand_id, referee_id), refs in by_referee.items():
        total = sum(r.incentive_amount for r in refs if r.incentive_amount)
        if total > 0:
            batch_id = f"PAY-{target_cycle_month}-{secrets.token_hex(4).upper()}"
            batch = PaymentBatch(
                brand_id=brand_id,
                batch_id=batch_id,
                cycle_month=target_cycle_month,
                referee_id=referee_id,
                total_amount=total,
                paid_on=now,
                payment_reference=f"REF-{batch_id}",
            )

            try:
                # Idempotent insert thanks to unique index on (brand_id, referee_id, cycle_month)
                await batch.insert()
            except DuplicateKeyError:
                # A worker already processed this referee's payment batch for this cycle
                continue

            # Update records
            for r in refs:
                r.payment_status = PaymentStatus.paid.value
                r.payment_date = now
                await r.save()

            # Send Email
            ref_user = await RefereeUser.get(referee_id)
            if ref_user and not batch.notified_paid:
                EmailService.send_referee_payment(
                    email=ref_user.email,
                    amount=batch.total_amount,
                    cycle_month=batch.cycle_month,
                    payment_ref=batch.payment_reference,
                    portal_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/referee",
                )
                batch.notified_paid = True
                await batch.save()
