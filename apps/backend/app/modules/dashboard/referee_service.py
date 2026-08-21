"""Referee portal business logic and dashboard service."""

import secrets
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.modules.dashboard.email_service import EmailService
from app.modules.recruitment.enums import (
    REFEREE_STAGE_ORDER,
    PaymentStatus,
    PipelineStage,
    RefereeKanbanStage,
)
from app.modules.recruitment.models import PaymentBatch, RefereeUser, ReferralRecord

if TYPE_CHECKING:
    from app.modules.recruitment.models import Mapping

# Every referee email links back to the same portal landing page.
PORTAL_URL = f"{settings.FRONTEND_URL}/referee"

# Referrals still in play: not yet paid, so still worth syncing and pricing.
UNPAID_STATUSES = {"$in": [PaymentStatus.pending.value, PaymentStatus.owed.value]}


# A held mapping is the one case with no stage of its own to show: the hold is
# temporary and the candidate is still in play, so the timeline freezes at
# whatever it last reached rather than moving.
_FROZEN_STAGES = (PipelineStage.on_hold,)

# What the referee sees for each internal recruiter stage.
#
# Two pairs deliberately collapse onto one step. sourced and sent_to_client are
# both "CV Reviewed": from the referee's side the meaningful event is that their
# CV reached a client, and the split between mapped and formally sent is internal
# detail they cannot act on. rejected and candidate_dropped both fall back to
# "CV Reviewed" because the referral is out of play — leaving it parked at
# "Interview Round(s)" would keep showing progress that no longer exists.
#
# "CV Received" is absent on purpose: it is the state of a candidate with no
# mapping at all, which is resolved from the absence of mappings, not from a
# stage. See resolve_referee_stage.
_REFEREE_STAGE_BY_INTERNAL: dict[str, RefereeKanbanStage] = {
    PipelineStage.sourced.value: RefereeKanbanStage.cv_reviewed,
    PipelineStage.sent_to_client.value: RefereeKanbanStage.cv_reviewed,
    PipelineStage.interview.value: RefereeKanbanStage.interview,
    PipelineStage.selected.value: RefereeKanbanStage.selected,
    PipelineStage.joined.value: RefereeKanbanStage.joined,
    PipelineStage.rejected.value: RefereeKanbanStage.cv_reviewed,
    PipelineStage.candidate_dropped.value: RefereeKanbanStage.cv_reviewed,
}


def map_stage_to_referee(internal_stage: str) -> str:
    """Map one internal ATS PipelineStage to the Referee-facing stage."""
    return _REFEREE_STAGE_BY_INTERNAL.get(internal_stage, RefereeKanbanStage.cv_reviewed).value


def _stage_for_mapping(mapping: "Mapping") -> RefereeKanbanStage:
    """The referee-facing stage a single mapping is currently worth.

    A frozen (on-hold) mapping reports the last stage it actually reached, read
    back out of its own history, instead of snapping to a default.
    """
    if mapping.stage in _FROZEN_STAGES:
        for event in reversed(mapping.history):
            if event.stage not in _FROZEN_STAGES:
                return _REFEREE_STAGE_BY_INTERNAL.get(
                    event.stage.value, RefereeKanbanStage.cv_reviewed
                )
    return _REFEREE_STAGE_BY_INTERNAL.get(mapping.stage.value, RefereeKanbanStage.cv_reviewed)


def resolve_referee_stage(mappings: list["Mapping"]) -> RefereeKanbanStage:
    """The stage the referee portal shows for one candidate.

    A candidate can be in play with several clients at once — one Mapping per
    position — so the furthest-along mapping wins. A drop at one client never
    hides live progress at another; it only pulls the timeline back when it is
    the only mapping the candidate has.

    No mappings at all means the CV has been submitted but not yet put in front
    of a client, which is the one case that reads as CV Received.
    """
    if not mappings:
        return RefereeKanbanStage.cv_received
    return max((_stage_for_mapping(m) for m in mappings), key=REFEREE_STAGE_ORDER.index)


async def _candidate_mappings(
    brand_id: PydanticObjectId, candidate_id: PydanticObjectId
) -> list["Mapping"]:
    from app.modules.recruitment.models import Mapping

    return await Mapping.find({"brand_id": brand_id, "candidate_id": candidate_id}).to_list()


async def _mappings_by_candidate(
    brand_id: PydanticObjectId, candidate_ids: list[PydanticObjectId]
) -> dict[PydanticObjectId, list["Mapping"]]:
    """Every mapping for a set of candidates, grouped, in one query."""
    from app.modules.recruitment.models import Mapping

    if not candidate_ids:
        return {}

    grouped: dict[PydanticObjectId, list[Mapping]] = defaultdict(list)
    for m in await Mapping.find(
        {"brand_id": brand_id, "candidate_id": {"$in": candidate_ids}}
    ).to_list():
        grouped[m.candidate_id].append(m)
    return grouped


def _joined_at(mappings: list["Mapping"]) -> datetime | None:
    """When the candidate actually joined, taken from the mapping that got them there."""
    for m in mappings:
        if m.stage != PipelineStage.joined:
            continue
        for event in m.history:
            if event.stage == PipelineStage.joined:
                return event.at
        if m.joining_date:
            return m.joining_date
    return None


async def ensure_referral_record(mapping: "Mapping") -> ReferralRecord | None:
    """Open a referral ledger entry when a referee's candidate is mapped.

    The ReferralRecord is what the portal's earnings column and the whole payment
    pipeline hang off; without one a referral accrues nothing no matter how far
    the candidate goes. Map time is the right moment to open it because that is
    when the referral first becomes worth money — the CV has reached a client.

    Returns None for candidates who did not come in through a referee, and the
    existing record for a candidate already mapped to another position: the
    ledger entry is per referred candidate, not per mapping.
    """
    from app.modules.recruitment.models import Candidate

    candidate = await Candidate.get(mapping.candidate_id)
    if not candidate or not candidate.referee_id:
        return None

    existing = await ReferralRecord.find_one(
        {"brand_id": mapping.brand_id, "candidate_id": mapping.candidate_id}
    )
    if existing:
        return existing

    # role_level is left unset rather than guessed from the position's seniority:
    # the incentive matrix prices "Entry"/"Mid" and Position carries
    # Junior/Mid/Senior, so writing the seniority straight through would price a
    # Junior referral at zero. Unset falls back to Entry pricing, which is what
    # every referral is already priced at today.
    record = ReferralRecord(
        brand_id=mapping.brand_id,
        referee_id=candidate.referee_id,
        mapping_id=mapping.id,
        candidate_id=mapping.candidate_id,
        position_id=mapping.position_id,
        submission_date=candidate.created_at,
        kanban_stage=resolve_referee_stage([mapping]).value,
    )
    await record.insert()
    return record


async def backfill_missing_referral_records(
    brand_id: PydanticObjectId, referee_id: PydanticObjectId
) -> None:
    """Open ledger entries for referred candidates mapped before this existed.

    No code path created a ReferralRecord until map_candidate started doing it,
    so every referral made before then has real mappings and no ledger entry —
    and therefore accrues nothing. Opening them lazily when the referee loads
    their own dashboard keeps this self-healing instead of relying on a one-shot
    migration that goes stale the moment a straggler is mapped.
    """
    from app.modules.recruitment.models import Candidate

    candidates = await Candidate.find({"brand_id": brand_id, "referee_id": referee_id}).to_list()
    if not candidates:
        return

    recorded = {
        r.candidate_id
        for r in await ReferralRecord.find(
            {"brand_id": brand_id, "referee_id": referee_id}
        ).to_list()
    }
    missing = [c.id for c in candidates if c.id not in recorded]

    for candidate_mappings in (await _mappings_by_candidate(brand_id, missing)).values():
        # The earliest mapping opens the entry: it is the one that first put this
        # CV in front of a client.
        await ensure_referral_record(min(candidate_mappings, key=lambda m: m.mapped_at))


async def sync_referral_with_mapping(r: ReferralRecord) -> None:
    """Refresh a referral's cached stage and joining date from its Mappings.

    The Mapping a recruiter drags on the kanban board is the source of truth;
    ReferralRecord only caches it for the portal and the payment jobs. This runs
    on every referee dashboard load and in the nightly job, so a recruiter's move
    reaches the referee without the pipeline needing a write path of its own.

    Reads every mapping the candidate has rather than only r.mapping_id: a
    candidate put forward to a second client gets a second Mapping, and the
    referral should track whichever one is furthest along.
    """
    mappings = await _candidate_mappings(r.brand_id, r.candidate_id)
    if not mappings:
        return

    stage = resolve_referee_stage(mappings).value
    joined_at = _joined_at(mappings)
    needs_joining_date = joined_at is not None and r.joining_date is None

    # Called in a loop over every one of a referee's referrals on each page load,
    # so an unchanged referral must not cost a write.
    if r.kanban_stage == stage and not needs_joining_date:
        return

    r.kanban_stage = stage
    if needs_joining_date:
        r.joining_date = joined_at
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
    await backfill_missing_referral_records(brand_id, referee_id)

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

    # Every mapping for every one of this referee's candidates, in one query —
    # this endpoint is polled, so it must not go per-referral. Serves two needs:
    # the timeline stage is resolved across all of a candidate's mappings, while
    # the portal's action buttons still key off the referral's own mapping (a
    # rejected one must stop offering Select/Reject), which is indexed by id
    # below out of the same result.
    mappings_by_candidate = await _mappings_by_candidate(brand_id, [c.id for c in candidates])
    mapping_by_id = {m.id: m for grouped in mappings_by_candidate.values() for m in grouped}

    result = []
    for candidate in candidates:
        candidate_name = candidate.full_name if candidate.full_name else "Unknown Candidate"
        parts = candidate_name.split()
        masked_name = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else candidate_name

        # Read off the live Mappings rather than the cached kanban_stage, so a
        # recruiter's move lands here on the referee's next load and a referral
        # whose record predates the sync still shows the right stage.
        candidate_mappings = mappings_by_candidate.get(candidate.id, [])
        kanban_stage = resolve_referee_stage(candidate_mappings).value

        if candidate.id in referral_map:
            r = referral_map[candidate.id]
            mapping = mapping_by_id.get(r.mapping_id)
            result.append(
                {
                    "id": str(r.id),
                    "mapping_id": str(r.mapping_id),
                    "pipeline_stage": (
                        PipelineStage(mapping.stage).value if mapping is not None else None
                    ),
                    "offer_letter_url": mapping.offer_letter_url if mapping is not None else None,
                    "candidate_name": masked_name,
                    "role_level": r.role_level,
                    "submission_date": r.submission_date,
                    "kanban_stage": kanban_stage,
                    "joining_date": r.joining_date or _joined_at(candidate_mappings),
                    "joining_plus7_eligible": r.joining_plus7_eligible,
                    "incentive_status": r.payment_status,
                    "incentive_amount": r.incentive_amount,
                    "payment_status": r.payment_status,
                    "payment_date": r.payment_date,
                }
            )
        else:
            # A candidate the referee submitted whose ReferralRecord has not been
            # opened yet — the money side is still empty, but the stage is real.
            # Statuses come from the enums, not literals: the portal and the
            # payment jobs both compare against those exact values.
            result.append(
                {
                    "id": str(candidate.id),
                    # No mapping yet, so nothing for the referee to act on.
                    "mapping_id": None,
                    "pipeline_stage": None,
                    "offer_letter_url": None,
                    "candidate_name": masked_name,
                    "role_level": None,
                    "submission_date": candidate.created_at,
                    "kanban_stage": kanban_stage,
                    "joining_date": _joined_at(candidate_mappings),
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
