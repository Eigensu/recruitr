"""What the referee portal shows as a referral moves through the recruiter's pipeline.

The referee's timeline is derived from the canonical `Mapping` rows rather than
from anything the pipeline writes for it, so these pin the derivation: which
internal stage surfaces as which referee stage, which mapping wins when a
candidate is in play with more than one client, and what a candidate falling out
of the pipeline does to a timeline that had already moved on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.dashboard.referee_service import (
    ensure_referral_record,
    get_referrals,
    resolve_referee_stage,
    sync_referral_with_mapping,
)
from app.modules.recruitment.enums import PipelineStage, RefereeKanbanStage
from app.modules.recruitment.models import Candidate, Mapping, ReferralRecord, StageEvent

_BRAND = PydanticObjectId()
_REFEREE = PydanticObjectId()
_EMP = PydanticObjectId()


def _ago(days: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


async def _candidate(*, referee_id: PydanticObjectId | None = _REFEREE) -> Candidate:
    doc = Candidate(
        brand_id=_BRAND,
        full_name="Priya Sharma",
        email=f"{PydanticObjectId()}@example.com",
        referee_id=referee_id,
    )
    await doc.insert()
    return doc


async def _mapping(
    candidate: Candidate,
    *,
    stage: PipelineStage,
    history: list[tuple[PipelineStage, float]] | None = None,
    mapped_days_ago: float = 30.0,
) -> Mapping:
    doc = Mapping(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        position_id=PydanticObjectId(),
        employee_id=_EMP,
        stage=stage,
        mapped_at=_ago(mapped_days_ago),
        history=[StageEvent(stage=s, at=_ago(days)) for s, days in (history or [])],
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def candidate() -> Candidate:
    return await _candidate()


# ── stage mapping ─────────────────────────────────────────────────────────────


async def test_unmapped_candidate_is_cv_received() -> None:
    """Submitted but not yet in front of a client — the one CV Received case."""
    assert resolve_referee_stage([]) == RefereeKanbanStage.cv_received


async def test_sourced_shows_as_cv_reviewed(candidate: Candidate) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.sourced)

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.cv_reviewed


async def test_sent_to_client_shows_as_cv_reviewed(candidate: Candidate) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.sent_to_client)

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.cv_reviewed


async def test_interview_shows_as_interview(candidate: Candidate) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.interview)

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.interview


async def test_selected_shows_as_selected(candidate: Candidate) -> None:
    """Regression: three duplicate `selected` keys used to make this Offer Accepted."""
    mapping = await _mapping(candidate, stage=PipelineStage.selected)

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.selected


async def test_joined_shows_as_joined(candidate: Candidate) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.joined)

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.joined


# ── falling out of the pipeline ───────────────────────────────────────────────


async def test_dropped_falls_back_to_cv_reviewed(candidate: Candidate) -> None:
    """A candidate who drops out of an interview is shown back at CV Reviewed."""
    mapping = await _mapping(
        candidate,
        stage=PipelineStage.candidate_dropped,
        history=[(PipelineStage.interview, 5), (PipelineStage.candidate_dropped, 1)],
    )

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.cv_reviewed


async def test_rejected_falls_back_to_cv_reviewed(candidate: Candidate) -> None:
    mapping = await _mapping(
        candidate,
        stage=PipelineStage.rejected,
        history=[(PipelineStage.selected, 5), (PipelineStage.rejected, 1)],
    )

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.cv_reviewed


async def test_on_hold_freezes_at_the_stage_it_reached(candidate: Candidate) -> None:
    """A hold is temporary and the candidate is still live, so the timeline holds."""
    mapping = await _mapping(
        candidate,
        stage=PipelineStage.on_hold,
        history=[(PipelineStage.interview, 5), (PipelineStage.on_hold, 1)],
    )

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.interview


async def test_on_hold_without_history_reads_as_cv_reviewed(candidate: Candidate) -> None:
    """Seeded and migrated mappings carry no history to freeze against."""
    mapping = await _mapping(candidate, stage=PipelineStage.on_hold)

    assert resolve_referee_stage([mapping]) == RefereeKanbanStage.cv_reviewed


# ── several clients at once ───────────────────────────────────────────────────


async def test_furthest_along_mapping_wins(candidate: Candidate) -> None:
    behind = await _mapping(candidate, stage=PipelineStage.sent_to_client)
    ahead = await _mapping(candidate, stage=PipelineStage.selected)

    assert resolve_referee_stage([behind, ahead]) == RefereeKanbanStage.selected
    assert resolve_referee_stage([ahead, behind]) == RefereeKanbanStage.selected


async def test_a_drop_at_one_client_does_not_hide_progress_at_another(
    candidate: Candidate,
) -> None:
    dropped = await _mapping(
        candidate,
        stage=PipelineStage.candidate_dropped,
        history=[(PipelineStage.interview, 5), (PipelineStage.candidate_dropped, 1)],
    )
    live = await _mapping(candidate, stage=PipelineStage.interview)

    assert resolve_referee_stage([dropped, live]) == RefereeKanbanStage.interview


# ── the ledger record ─────────────────────────────────────────────────────────


async def test_mapping_a_referred_candidate_opens_a_referral_record(
    candidate: Candidate,
) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.sourced)

    record = await ensure_referral_record(mapping)

    assert record is not None
    assert record.referee_id == _REFEREE
    assert record.candidate_id == candidate.id
    assert record.kanban_stage == RefereeKanbanStage.cv_reviewed.value


async def test_no_referral_record_for_a_candidate_who_came_in_another_way() -> None:
    candidate = await _candidate(referee_id=None)
    mapping = await _mapping(candidate, stage=PipelineStage.sourced)

    assert await ensure_referral_record(mapping) is None
    assert await ReferralRecord.find({"candidate_id": candidate.id}).count() == 0


async def test_a_second_mapping_reuses_the_same_referral_record(
    candidate: Candidate,
) -> None:
    """The ledger entry is per referred candidate, not per position they go for."""
    first = await ensure_referral_record(await _mapping(candidate, stage=PipelineStage.sourced))
    second = await ensure_referral_record(await _mapping(candidate, stage=PipelineStage.sourced))

    assert first.id == second.id
    assert await ReferralRecord.find({"candidate_id": candidate.id}).count() == 1


async def test_sync_follows_the_recruiter_and_captures_the_joining_date(
    candidate: Candidate,
) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.sourced)
    record = await ensure_referral_record(mapping)

    joined_at = _ago(2)
    mapping.stage = PipelineStage.joined
    mapping.history = [StageEvent(stage=PipelineStage.joined, at=joined_at)]
    await mapping.save()

    await sync_referral_with_mapping(record)

    reloaded = await ReferralRecord.get(record.id)
    assert reloaded.kanban_stage == RefereeKanbanStage.joined.value
    assert reloaded.joining_date is not None


# ── what the portal actually returns ──────────────────────────────────────────


async def test_portal_reflects_the_recruiters_move_without_a_sync(
    candidate: Candidate,
) -> None:
    """The regression this whole change exists for.

    Every referral used to read CV Received forever: nothing created a
    ReferralRecord, so the portal fell through to a hardcoded stage.
    """
    await _mapping(candidate, stage=PipelineStage.interview)

    referrals = await get_referrals(_BRAND, _REFEREE)

    assert len(referrals) == 1
    assert referrals[0]["kanban_stage"] == RefereeKanbanStage.interview.value


async def test_portal_shows_cv_received_before_any_mapping(candidate: Candidate) -> None:
    referrals = await get_referrals(_BRAND, _REFEREE)

    assert referrals[0]["kanban_stage"] == RefereeKanbanStage.cv_received.value


async def test_portal_prefers_live_mappings_over_a_stale_cached_stage(
    candidate: Candidate,
) -> None:
    mapping = await _mapping(candidate, stage=PipelineStage.selected)
    record = await ensure_referral_record(mapping)
    record.kanban_stage = RefereeKanbanStage.cv_received.value
    await record.save()

    referrals = await get_referrals(_BRAND, _REFEREE)

    assert referrals[0]["kanban_stage"] == RefereeKanbanStage.selected.value
