"""The one-time move of un-actioned candidates onto the Leads page.

Run through the script's own `run()`, since this is the piece an operator
points at production: report mode must write nothing, and a second run must
find nothing left to do.
"""

import pytest
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeSource,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeLead
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
async def test_pending_candidates_without_a_lead_are_queued_for_a_telecaller():
    caller = Employee(
        brand_id=_BRAND, name="Caller", email="caller@binge.consulting", role=UserRole.telecaller
    )
    await caller.insert()
    orphan = await _candidate("Old applicant", CandidateStatus.pending)
    screened = await _candidate("Already a lead", CandidateStatus.pending)
    await _lead_for(screened, status=IntakeLeadStatus.pending_review)
    await _candidate("Approved", CandidateStatus.approved)

    counts = await migrate.run(confirm=True)

    assert counts["leads_opened"] == 1
    lead = await IntakeLead.find_one({"candidate_id": orphan.id})
    assert lead.status == IntakeLeadStatus.pending_telecaller
    assert lead.telecaller_id == caller.id
    assert lead.source == IntakeSource.public_form
    assert await IntakeLead.find({"candidate_id": screened.id}).count() == 1


@pytest.mark.asyncio
async def test_with_no_telecaller_the_lead_waits_unassigned():
    await _candidate("Old applicant", CandidateStatus.pending)

    counts = await migrate.run(confirm=True)

    assert counts == counts | {"leads_opened": 1, "unassigned": 1}


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
    await migrate.run(confirm=True)

    again = await migrate.run(confirm=False)

    assert again["would_open"] == 0
    assert again["would_hide"] == 0
