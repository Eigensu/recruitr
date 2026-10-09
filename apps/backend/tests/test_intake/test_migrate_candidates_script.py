"""The one-time move of un-actioned candidates onto the Leads page.

Run through the script's own `run()`, since this is the piece an operator
points at production: report mode must write nothing, and a second run must
find nothing left to do.
"""

from datetime import UTC, datetime, timedelta

import pytest
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeSource,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeAttribution, IntakeLead
from scripts import migrate_candidates_to_leads as migrate

_BRAND = PydanticObjectId()


async def _candidate(name: str, status: CandidateStatus, **fields) -> Candidate:
    doc = Candidate(brand_id=_BRAND, full_name=name, status=status, **fields)
    await doc.insert()
    return doc


async def _lead_for(candidate: Candidate, **fields) -> IntakeLead:
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        **fields,
    )
    await lead.insert()
    return lead


@pytest.mark.asyncio
async def test_report_mode_writes_nothing():
    orphan = await _candidate("Old applicant", CandidateStatus.pending)

    counts = await migrate.run(confirm=False)

    assert counts["would_open"] == 1
    assert await IntakeLead.find({"candidate_id": orphan.id}).count() == 0


@pytest.mark.asyncio
async def test_with_assign_pending_candidates_without_a_lead_are_queued_for_a_telecaller():
    caller = Employee(
        brand_id=_BRAND, name="Caller", email="caller@binge.consulting", role=UserRole.telecaller
    )
    await caller.insert()
    orphan = await _candidate("Old applicant", CandidateStatus.pending)
    screened = await _candidate("Already a lead", CandidateStatus.pending)
    await _lead_for(screened, status=IntakeLeadStatus.pending_review)
    await _candidate("Approved", CandidateStatus.approved)

    counts = await migrate.run(confirm=True, assign=True)

    assert counts["leads_opened"] == 1
    lead = await IntakeLead.find_one({"candidate_id": orphan.id})
    assert lead.status == IntakeLeadStatus.pending_telecaller
    assert lead.telecaller_id == caller.id
    assert lead.source == IntakeSource.public_form
    assert await IntakeLead.find({"candidate_id": screened.id}).count() == 1


@pytest.mark.asyncio
async def test_with_no_telecaller_the_lead_waits_unassigned():
    await _candidate("Old applicant", CandidateStatus.pending)

    counts = await migrate.run(confirm=True, assign=True)

    assert counts == counts | {"leads_opened": 1, "unassigned": 1}


@pytest.mark.asyncio
async def test_by_default_leads_are_left_unassigned_and_dated_when_they_applied():
    """A backlog handed out at once would breach every telecaller a day later,
    and dating it today would file months of applicants under this week."""
    caller = Employee(
        brand_id=_BRAND, name="Caller", email="caller@binge.consulting", role=UserRole.telecaller
    )
    await caller.insert()
    applied = datetime.now(UTC).replace(microsecond=0) - timedelta(days=40)
    orphan = await _candidate("Old applicant", CandidateStatus.pending, created_at=applied)

    await migrate.run(confirm=True)

    lead = await IntakeLead.find_one({"candidate_id": orphan.id})
    assert lead.status == IntakeLeadStatus.unassigned
    assert lead.telecaller_id is None
    assert lead.telecaller_assigned_at is None
    assert lead.external_created_at.replace(tzinfo=UTC) == applied
    assert lead.ingested_at.replace(tzinfo=UTC) == applied


@pytest.mark.asyncio
async def test_someone_whose_only_lead_is_a_duplicate_has_that_row_queued():
    """Their first lead was removed and the next ingest filed their own sheet
    row as a duplicate of them. That row is queued, not a new public-form lead:
    it holds the ad that brought them and the day they applied."""
    orphan = await _candidate("Lost by an ingest", CandidateStatus.pending)
    applied = datetime(2026, 9, 9, 14, 46, 47, tzinfo=UTC)
    their_row = await _lead_for(
        orphan,
        status=IntakeLeadStatus.duplicate,
        source=IntakeSource.google_sheet,
        external_created_at=applied,
        attribution=IntakeAttribution(campaign_name="Video Campaign"),
    )

    report = await migrate.run(confirm=False)
    counts = await migrate.run(confirm=True)

    assert (report["would_queue_duplicate"], report["would_open"]) == (1, 0)
    assert (counts["duplicates_queued"], counts["leads_opened"], counts["unassigned"]) == (1, 0, 1)
    [lead] = await IntakeLead.find({"candidate_id": orphan.id}).to_list()
    assert lead.id == their_row.id
    assert lead.status == IntakeLeadStatus.unassigned
    assert lead.source == IntakeSource.google_sheet
    assert lead.attribution.campaign_name == "Video Campaign"
    assert lead.external_created_at.replace(tzinfo=UTC) == applied


@pytest.mark.asyncio
async def test_of_several_duplicate_rows_the_earliest_is_queued_and_assigned_with_assign():
    caller = Employee(
        brand_id=_BRAND, name="Caller", email="caller@binge.consulting", role=UserRole.telecaller
    )
    await caller.insert()
    orphan = await _candidate("Applied twice", CandidateStatus.pending)
    first = datetime(2026, 9, 1, tzinfo=UTC)
    later = await _lead_for(
        orphan, status=IntakeLeadStatus.duplicate, external_created_at=first + timedelta(days=5)
    )
    earliest = await _lead_for(orphan, status=IntakeLeadStatus.duplicate, external_created_at=first)

    await migrate.run(confirm=True, assign=True)

    queued = await IntakeLead.get(earliest.id)
    assert queued.status == IntakeLeadStatus.pending_telecaller
    assert queued.telecaller_id == caller.id
    assert queued.telecaller_assigned_at is not None
    assert (await IntakeLead.get(later.id)).status == IntakeLeadStatus.duplicate


@pytest.mark.asyncio
async def test_candidates_approved_into_a_review_tab_go_back_to_pending():
    """The old flow approved at team assignment; only the recruiter's Accept does now."""
    waiting = await _candidate("Waiting on recruiter", CandidateStatus.approved)
    await _lead_for(waiting, status=IntakeLeadStatus.pending_recruiter)
    accepted = await _candidate("Accepted", CandidateStatus.approved)
    await _lead_for(
        accepted,
        status=IntakeLeadStatus.pending_recruiter,
        recruiter_decision=IntakeDecision.accept,
    )
    mapped = await _candidate("Already mapped", CandidateStatus.approved)
    await _lead_for(mapped, status=IntakeLeadStatus.actioned)

    counts = await migrate.run(confirm=True)

    assert counts["unapproved"] == 1
    assert (await Candidate.get(waiting.id)).status == CandidateStatus.pending
    assert (await Candidate.get(accepted.id)).status == CandidateStatus.approved
    assert (await Candidate.get(mapped.id)).status == CandidateStatus.approved


@pytest.mark.asyncio
async def test_only_telecaller_rejects_are_soft_deleted():
    by_caller = await _candidate("Caller said no", CandidateStatus.rejected)
    await _lead_for(
        by_caller,
        status=IntakeLeadStatus.rejected,
        telecaller_decision=IntakeDecision.reject,
    )
    by_button = await _candidate("Old reject button", CandidateStatus.rejected)

    counts = await migrate.run(confirm=True)

    assert counts["hidden"] == 1
    assert counts["left_alone"] == 1
    assert (await Candidate.get(by_caller.id)).is_active is False
    assert (await Candidate.get(by_button.id)).is_active is True


@pytest.mark.asyncio
async def test_a_second_run_finds_nothing_to_do():
    await _candidate("Old applicant", CandidateStatus.pending)
    rejected = await _candidate("Caller said no", CandidateStatus.rejected)
    await _lead_for(rejected, telecaller_decision=IntakeDecision.reject)
    in_review = await _candidate("Waiting on recruiter", CandidateStatus.approved)
    await _lead_for(in_review, status=IntakeLeadStatus.pending_recruiter)
    filed_as_duplicate = await _candidate("Lost by an ingest", CandidateStatus.pending)
    await _lead_for(filed_as_duplicate, status=IntakeLeadStatus.duplicate)
    await migrate.run(confirm=True)

    again = await migrate.run(confirm=False)

    assert again["would_open"] == 0
    assert again["would_queue_duplicate"] == 0
    assert again["would_hide"] == 0
    assert again["would_unapprove"] == 0
