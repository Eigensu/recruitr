"""Referee portal business logic and dashboard service."""

import secrets
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.modules.dashboard.email_service import EmailService
from app.modules.recruitment.enums import PaymentStatus, PipelineStage, RefereeKanbanStage
from app.modules.recruitment.models import PaymentBatch, RefereeUser, ReferralRecord

# Every referee email links back to the same portal landing page.
PORTAL_URL = f"{settings.FRONTEND_URL}/referee"

# Referrals still in play: not yet paid, so still worth syncing and pricing.
UNPAID_STATUSES = {"$in": [PaymentStatus.pending.value, PaymentStatus.owed.value]}


def map_stage_to_referee(internal_stage: str) -> str:
    """Map the internal ATS PipelineStage to the Referee-facing stage."""
    mapping = {
        PipelineStage.sourced.value: RefereeKanbanStage.cv_received.value,
        PipelineStage.sent_to_client.value: RefereeKanbanStage.cv_reviewed.value,
        PipelineStage.interview.value: RefereeKanbanStage.interview.value,
        PipelineStage.selected.value: RefereeKanbanStage.interview.value,
        PipelineStage.selected.value: RefereeKanbanStage.offer_extended.value,
        PipelineStage.selected.value: RefereeKanbanStage.offer_accepted.value,
        PipelineStage.joined.value: RefereeKanbanStage.joined.value,
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
    if mapping.stage == PipelineStage.joined and not r.joining_date:
        for event in mapping.history:
            if event.stage == PipelineStage.joined:
                r.joining_date = event.at
                break

    await r.save()


async def get_dashboard_summary(
    brand_id: PydanticObjectId, referee_id: PydanticObjectId
) -> dict[str, Any]:
    """Calculate summary statistics for the referee's dashboard."""
    from app.modules.recruitment.enums import CandidateEventType
    from app.modules.recruitment.models import Candidate, CandidateEvent, Mapping

    candidates = await Candidate.find({"brand_id": brand_id, "referee_id": referee_id}).to_list()

    cvs_shared = len(candidates)

    cvs_actioned = 0
    candidate_ids = [c.id for c in candidates]

    if candidate_ids:
        mappings = await Mapping.find(
            {"brand_id": brand_id, "candidate_id": {"$in": candidate_ids}}
        ).to_list()

        mapped_candidate_ids = {m.candidate_id for m in mappings}

        for c in candidates:
            if c.id in mapped_candidate_ids:
                cvs_actioned += 1
                continue

            has_activity = await CandidateEvent.find(
                {
                    "brand_id": brand_id,
                    "candidate_id": c.id,
                    "event_type": {
                        "$nin": [CandidateEventType.applied.value, CandidateEventType.mapped.value]
                    },
                }
            ).exists()

            if has_activity:
                cvs_actioned += 1

    referrals = await ReferralRecord.find(
        {"brand_id": brand_id, "referee_id": referee_id}
    ).to_list()

    for r in referrals:
        await sync_referral_with_mapping(r)

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


async def _mark_eligible_if_due(r: ReferralRecord, today: date, cycle_month: str) -> None:
    """Flip a referral to owed once it is 7 calendar days past the joining date."""
    if not r.joining_date or r.joining_plus7_eligible:
        return
    if (r.joining_date + timedelta(days=7)).date() > today:
        return

    r.joining_plus7_eligible = True
    r.payment_status = PaymentStatus.owed.value
    r.cycle_month = cycle_month
    await r.save()


async def _reprice_cycle(cycle_refs: list[ReferralRecord]) -> None:
    """Apply the payment matrix across one referee's referrals for one cycle.

    The rate depends on how many of that referee's referrals landed in the same
    cycle, so the whole group is priced together rather than one at a time.
    """
    eligible_count = len(cycle_refs)
    for r in cycle_refs:
        new_incentive = calculate_incentive_amount(r.role_level or "Entry", eligible_count)
        if r.incentive_amount != new_incentive:
            r.incentive_amount = new_incentive
            await r.save()


async def _process_referral_incentives(referrals: list[ReferralRecord]) -> None:
    """Check +7 calendar days eligibility and update matrix for a list of referrals."""
    today = datetime.now(UTC).date()
    current_cycle_month = today.strftime("%Y-%m")

    # Keyed by (referee, cycle): the matrix rate is per referee per month.
    by_referee_cycle: dict[tuple, list[ReferralRecord]] = defaultdict(list)

    for r in referrals:
        await _mark_eligible_if_due(r, today, current_cycle_month)
        if r.joining_plus7_eligible and r.cycle_month:
            by_referee_cycle[(r.referee_id, r.cycle_month)].append(r)

    for cycle_refs in by_referee_cycle.values():
        await _reprice_cycle(cycle_refs)


async def update_eligibility_and_incentives(
    brand_id: PydanticObjectId, referee_id: PydanticObjectId
) -> None:
    """Check +7 calendar days eligibility and update matrix for a specific referee."""
    referrals = await ReferralRecord.find(
        {
            "brand_id": brand_id,
            "referee_id": referee_id,
            "payment_status": UNPAID_STATUSES,
        }
    ).to_list()

    for r in referrals:
        await sync_referral_with_mapping(r)

    await _process_referral_incentives(referrals)


async def _notify_actioned(r: ReferralRecord) -> None:
    """Tell the referee their candidate has moved off the initial stage. Once only."""
    from app.modules.recruitment.models import Candidate

    if r.notified_actioned or r.kanban_stage == RefereeKanbanStage.cv_received.value:
        return

    ref_user = await RefereeUser.get(r.referee_id)
    candidate = await Candidate.get(r.candidate_id)
    if not ref_user or not candidate:
        return

    EmailService.send_referee_actioned(
        email=ref_user.email,
        candidate_name=candidate.full_name,
        stage=r.kanban_stage,
        portal_url=PORTAL_URL,
    )
    r.notified_actioned = True
    await r.save()


async def _notify_joined(r: ReferralRecord) -> None:
    """Tell the referee their candidate joined. Once only."""
    from app.modules.recruitment.models import Candidate

    if r.notified_joined or not r.joining_date:
        return

    ref_user = await RefereeUser.get(r.referee_id)
    candidate = await Candidate.get(r.candidate_id)
    if not ref_user or not candidate:
        return

    EmailService.send_referee_joined(
        email=ref_user.email,
        candidate_name=candidate.full_name,
        joining_date=r.joining_date,
        portal_url=PORTAL_URL,
    )
    r.notified_joined = True
    await r.save()


async def process_daily_referee_updates() -> None:
    """Check +7 calendar days eligibility, update matrix, and send emails."""
    # Every referee's active referrals at once: this runs as a nightly job, not
    # per request, so it is not scoped to a brand or a referee.
    referrals = await ReferralRecord.find({"payment_status": UNPAID_STATUSES}).to_list()

    for r in referrals:
        await sync_referral_with_mapping(r)
        await _notify_actioned(r)
        await _notify_joined(r)

    await _process_referral_incentives(referrals)


async def get_referrals(
    brand_id: PydanticObjectId, referee_id: PydanticObjectId
) -> list[dict[str, Any]]:
    """Get the candidate journey for the referee."""
    # DO NOT call update_eligibility_and_incentives here. This is a read-only endpoint.
    from app.modules.recruitment.models import Candidate

    candidates = await Candidate.find({"brand_id": brand_id, "referee_id": referee_id}).to_list()

    referrals = await ReferralRecord.find(
        {"brand_id": brand_id, "referee_id": referee_id}
    ).to_list()

    referral_map = {r.candidate_id: r for r in referrals}

    result = []
    for candidate in candidates:
        candidate_name = candidate.full_name if candidate.full_name else "Unknown Candidate"
        parts = candidate_name.split()
        masked_name = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else candidate_name

        if candidate.id in referral_map:
            r = referral_map[candidate.id]
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
        else:
            # A candidate the referee submitted that has no ReferralRecord yet.
            # Statuses come from the enums, not literals: the portal and the
            # payment jobs both compare against those exact values.
            result.append(
                {
                    "id": str(candidate.id),
                    "candidate_name": masked_name,
                    "role_level": None,
                    "submission_date": candidate.created_at,
                    "kanban_stage": RefereeKanbanStage.cv_received.value,
                    "joining_date": None,
                    "joining_plus7_eligible": False,
                    "incentive_status": PaymentStatus.pending.value,
                    "incentive_amount": 0.0,
                    "payment_status": PaymentStatus.pending.value,
                    "payment_date": None,
                }
            )

    result.sort(key=lambda x: x["submission_date"], reverse=True)
    return result


def is_bank_holiday(_date: datetime) -> bool:
    """Whether the given date is a bank holiday.

    Always False, deliberately. There is no authoritative holiday calendar to
    read — no HRIS feed and no configured list — and inventing one would move
    real payment dates onto wrong days. The date argument is kept so callers
    read correctly and so a real calendar can be dropped in behind them.
    """
    return False


def _get_next_working_day(d: datetime) -> datetime:
    """Move to next working day if weekend or bank holiday."""
    # weekday() numbers Monday 0 through Sunday 6, so 5 and above is the weekend.
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

    by_referee: dict[tuple, list[ReferralRecord]] = defaultdict(list)
    for r in referrals:
        by_referee[(r.brand_id, r.referee_id)].append(r)

    for (brand_id, referee_id), refs in by_referee.items():
        await _pay_referee_cycle(brand_id, referee_id, refs, target_cycle_month, now)


async def _pay_referee_cycle(
    brand_id: PydanticObjectId,
    referee_id: PydanticObjectId,
    refs: list[ReferralRecord],
    cycle_month: str,
    now: datetime,
) -> None:
    """Batch one referee's owed referrals for one cycle, then mark them paid."""
    total = sum(r.incentive_amount for r in refs if r.incentive_amount)
    if total <= 0:
        return

    batch_id = f"PAY-{cycle_month}-{secrets.token_hex(4).upper()}"
    batch = PaymentBatch(
        brand_id=brand_id,
        batch_id=batch_id,
        cycle_month=cycle_month,
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
        return

    for r in refs:
        r.payment_status = PaymentStatus.paid.value
        r.payment_date = now
        await r.save()

    ref_user = await RefereeUser.get(referee_id)
    if ref_user and not batch.notified_paid:
        EmailService.send_referee_payment(
            email=ref_user.email,
            amount=batch.total_amount,
            cycle_month=batch.cycle_month,
            payment_ref=batch.payment_reference,
            portal_url=PORTAL_URL,
        )
        batch.notified_paid = True
        await batch.save()
