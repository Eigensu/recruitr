"""Ingesting parsed leads: idempotency, deduplication, and round-robin assignment.

These run against a real Mongo (the autouse fixture in tests/conftest.py) but
never touch the network — the sheet read is the one thing stubbed out, because
everything worth asserting here happens after the rows have been parsed.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import CandidateStatus, IntakeLeadStatus
from app.modules.recruitment.models import Candidate, CandidateEvent, Employee, IntakeLead
from app.modules.recruitment.service.intake_service import (
    before_cutoff,
    contact_coverage,
    ingest_leads,
    next_assignee,
    plan_ingest,
)
from app.modules.recruitment.utils.lead_sheet import parse_rows

from .test_sheet_mapping import HEADERS, _row

_BRAND = PydanticObjectId()
_OTHER_BRAND = PydanticObjectId()


def _leads(*rows: list[str]):
    leads, _ = parse_rows([HEADERS, *rows])
    return leads


async def _employee(name: str, role: UserRole, *, brand_id=_BRAND, active: bool = True) -> Employee:
    employee = Employee(
        brand_id=brand_id,
        name=name,
        email=f"{name.lower()}@binge.consulting",
        role=role.value,
        is_active=active,
    )
    await employee.insert()
    return employee


@pytest_asyncio.fixture
async def callers() -> list[Employee]:
    return [
        await _employee("Caller1", UserRole.telecaller),
        await _employee("Caller2", UserRole.telecaller),
    ]


# ── Creating candidates ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_new_lead_becomes_a_pending_candidate(callers):
    result = await ingest_leads(_leads(_row()), brand_id=_BRAND)

    assert (result.created, result.assigned, result.matched_existing) == (1, 1, 0)
    candidate = await Candidate.find_one({"brand_id": _BRAND})
    assert candidate.full_name == "Asha Rao"
    assert candidate.phone == "+91 98765 43210"
    assert candidate.source == "external"
    assert candidate.source_channel == "Instagram"
    # PENDING, so they stay out of the recruiter directory until a telecaller
    # has actually spoken to them.
    assert candidate.status == CandidateStatus.pending
    # Nobody sourced them, so the CV stays shared rather than owned.
    assert candidate.created_by_id is None


@pytest.mark.asyncio
async def test_the_lead_records_where_it_came_from(callers):
    await ingest_leads(_leads(_row()), brand_id=_BRAND)

    lead = await IntakeLead.find_one({"brand_id": _BRAND})
    assert lead.external_id == "l_1001"
    assert lead.attribution.campaign_name == "F&B Hiring Sept"
    assert lead.source_channel == "Instagram"
    assert lead.status == IntakeLeadStatus.pending_telecaller
    assert lead.telecaller_assigned_at is not None
    # The whole row survives, so a mapping bug stays diagnosable afterwards.
    assert lead.raw["your_current_location?"] == "Andheri"


@pytest.mark.asyncio
async def test_arrival_is_recorded_on_the_candidate_history(callers):
    await ingest_leads(_leads(_row()), brand_id=_BRAND)

    event = await CandidateEvent.find_one({"brand_id": _BRAND})
    assert event is not None
    assert "Instagram" in (event.note or "")


# ── Idempotency ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_re_reading_the_same_row_changes_nothing(callers):
    rows = _leads(_row())

    first = await ingest_leads(rows, brand_id=_BRAND)
    second = await ingest_leads(rows, brand_id=_BRAND)

    assert (first.created, second.created) == (1, 0)
    assert second.already_ingested == 1
    assert await Candidate.find({"brand_id": _BRAND}).count() == 1
    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 1


@pytest.mark.asyncio
async def test_a_lead_id_is_only_taken_within_its_own_brand(callers):
    rows = _leads(_row())

    await ingest_leads(rows, brand_id=_BRAND)
    other = await ingest_leads(rows, brand_id=_OTHER_BRAND, assign=False)

    assert other.created == 1


# ── Deduplication ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_lead_for_someone_already_in_the_pool_links_instead_of_duplicating(callers):
    # Stored in a different format from the sheet's "+91 98765 43210".
    existing = Candidate(brand_id=_BRAND, full_name="Asha R", phone="09876543210")
    await existing.insert()

    result = await ingest_leads(_leads(_row()), brand_id=_BRAND)

    assert (result.created, result.matched_existing) == (0, 1)
    assert await Candidate.find({"brand_id": _BRAND}).count() == 1
    lead = await IntakeLead.find_one({"brand_id": _BRAND})
    assert lead.status == IntakeLeadStatus.duplicate
    assert lead.candidate_id == existing.id
    # A duplicate is never anybody's work.
    assert lead.telecaller_id is None


@pytest.mark.asyncio
async def test_an_email_match_also_counts_as_the_same_person(callers):
    existing = Candidate(brand_id=_BRAND, full_name="Asha R", email="asha@example.com")
    await existing.insert()

    result = await ingest_leads(_leads(_row()), brand_id=_BRAND)

    assert result.matched_existing == 1


@pytest.mark.asyncio
async def test_the_same_person_twice_in_one_sheet_creates_one_candidate(callers):
    # Meta issues a new lead id each time someone submits the form again, so
    # both rows are new to the external_id check.
    rows = _leads(
        _row(id="l_1"),
        _row(id="l_2", email="asha.rao@example.com"),
    )

    result = await ingest_leads(rows, brand_id=_BRAND)

    assert (result.created, result.matched_existing) == (1, 1)
    assert await Candidate.find({"brand_id": _BRAND}).count() == 1
    # Both leads are kept: two ad clicks were genuinely paid for.
    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 2


@pytest.mark.asyncio
async def test_a_candidate_from_another_brand_is_not_a_match(callers):
    other = Candidate(brand_id=_OTHER_BRAND, full_name="Asha R", phone="9876543210")
    await other.insert()

    result = await ingest_leads(_leads(_row()), brand_id=_BRAND)

    assert result.created == 1


# ── Assignment ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_leads_are_shared_out_between_telecallers(callers):
    # Distinct phone *and* email per row: sharing either would make rows 2-4
    # duplicates of row 1, which is a different test.
    rows = _leads(
        *[
            _row(id=f"l_{n}", phone_number=f"98765432{n:02d}", email=f"lead{n}@example.com")
            for n in range(4)
        ]
    )

    await ingest_leads(rows, brand_id=_BRAND)

    leads = await IntakeLead.find({"brand_id": _BRAND}).to_list()
    per_caller = {caller.id: 0 for caller in callers}
    for lead in leads:
        per_caller[lead.telecaller_id] += 1
    assert sorted(per_caller.values()) == [2, 2]


@pytest.mark.asyncio
async def test_with_no_telecaller_the_lead_waits_rather_than_disappearing():
    result = await ingest_leads(_leads(_row()), brand_id=_BRAND)

    assert (result.created, result.assigned, result.unassigned) == (1, 0, 1)
    lead = await IntakeLead.find_one({"brand_id": _BRAND})
    assert lead.status == IntakeLeadStatus.unassigned
    assert lead.telecaller_id is None


@pytest.mark.asyncio
async def test_inactive_and_non_telecaller_staff_are_not_assigned_leads():
    await _employee("Recruiter", UserRole.employee)
    await _employee("Boss", UserRole.maintainer)
    await _employee("Former", UserRole.telecaller, active=False)
    await _employee("Elsewhere", UserRole.telecaller, brand_id=_OTHER_BRAND)

    result = await ingest_leads(_leads(_row()), brand_id=_BRAND)

    assert result.unassigned == 1


@pytest.mark.asyncio
async def test_assignment_can_be_withheld_for_a_historical_import(callers):
    # What the backfill uses: leads months old would breach their SLA on the
    # next sweep, all at once.
    result = await ingest_leads(_leads(_row()), brand_id=_BRAND, assign=False)

    assert (result.created, result.assigned, result.unassigned) == (1, 0, 1)
    lead = await IntakeLead.find_one({"brand_id": _BRAND})
    assert lead.status == IntakeLeadStatus.unassigned


@pytest.mark.asyncio
async def test_the_round_robin_returns_nobody_when_the_roster_is_empty():
    assert await next_assignee(_BRAND, telecallers=True) is None


@pytest.mark.asyncio
async def test_recruiters_include_rows_written_before_the_role_field_existed():
    legacy = Employee(brand_id=_BRAND, name="Legacy", email="legacy@binge.consulting")
    await legacy.get_motor_collection().update_one(
        {"_id": (await legacy.insert()).id}, {"$unset": {"role": ""}}
    )

    chosen = await next_assignee(_BRAND, telecallers=False)

    assert chosen is not None and chosen.name == "Legacy"


# ── Activation cutoff ──────────────────────────────────────────────────────────


def test_leads_from_before_activation_are_left_to_the_backfill():
    cutoff = datetime(2026, 9, 15, tzinfo=UTC)
    (old,) = _leads(_row(created_time="2026-09-14T10:00:00+00:00"))
    (new,) = _leads(_row(created_time="2026-09-16T10:00:00+00:00"))

    assert before_cutoff(old, cutoff) is True
    assert before_cutoff(new, cutoff) is False


def test_a_lead_with_no_readable_date_is_treated_as_current():
    # Meta always sends created_time, so a missing one means the column was
    # renamed or the value was unparseable. Dropping live leads over a
    # formatting change is worse than importing an old one.
    (undated,) = _leads(_row(created_time=""))

    assert before_cutoff(undated, datetime.now(UTC) - timedelta(days=1)) is False


def test_without_a_cutoff_everything_is_current():
    (lead,) = _leads(_row())

    assert before_cutoff(lead, None) is False


# ── Report mode ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_preview_writes_nothing():
    await plan_ingest(_leads(_row()), brand_id=_BRAND)

    assert await Candidate.find({"brand_id": _BRAND}).count() == 0
    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 0


@pytest.mark.asyncio
async def test_the_preview_predicts_what_the_import_does(callers):
    existing = Candidate(brand_id=_BRAND, full_name="Known", phone="9000000001")
    await existing.insert()
    rows = _leads(
        _row(id="l_1", phone_number="9000000001", email="known@example.com"),  # already a candidate
        _row(id="l_2", phone_number="9000000002", email="new@example.com"),  # new
        _row(id="l_3", phone_number="9000000002", email="again@example.com"),  # l_2 again
    )

    plan = await plan_ingest(rows, brand_id=_BRAND)
    result = await ingest_leads(rows, brand_id=_BRAND)

    assert (plan.new, plan.matched_existing, plan.duplicate_in_sheet) == (1, 1, 1)
    # The preview and the import agree, because they share one implementation
    # of "have I seen this person".
    assert result.created == plan.new
    assert result.matched_existing == plan.matched_existing + plan.duplicate_in_sheet


@pytest.mark.asyncio
async def test_the_preview_counts_rows_already_ingested(callers):
    rows = _leads(_row())
    await ingest_leads(rows, brand_id=_BRAND)

    plan = await plan_ingest(rows, brand_id=_BRAND)

    assert (plan.already_ingested, plan.new) == (1, 0)


@pytest.mark.asyncio
async def test_coverage_reports_how_many_candidates_can_be_matched_at_all():
    await Candidate(brand_id=_BRAND, full_name="Has phone", phone="9876543210").insert()
    await Candidate(brand_id=_BRAND, full_name="Has email", email="e@example.com").insert()
    await Candidate(brand_id=_BRAND, full_name="Has neither").insert()
    await Candidate(brand_id=_BRAND, full_name="Unusable phone", phone="123").insert()

    total, reachable = await contact_coverage(_BRAND)

    assert (total, reachable) == (4, 2)


# ── Timestamps out of Mongo ────────────────────────────────────────────────────


def test_the_activation_cutoff_survives_a_naive_timestamp():
    # Mongo stores UTC and hands it back without a timezone, so activated_at
    # read from a document is naive while a parsed lead time is aware. Python
    # raises TypeError on that comparison rather than guessing, which would have
    # taken down every poll once activation was set.
    naive_cutoff = datetime(2026, 9, 15)  # noqa: DTZ001 - exactly what Mongo returns
    (old,) = _leads(_row(created_time="2026-09-14T10:00:00+00:00"))
    (new,) = _leads(_row(created_time="2026-09-16T10:00:00+00:00"))

    assert before_cutoff(old, naive_cutoff) is True
    assert before_cutoff(new, naive_cutoff) is False


@pytest.mark.asyncio
async def test_a_stored_assignment_time_still_measures_a_response(callers):
    # Same hazard on the other leg: telecaller_assigned_at comes back naive.
    from app.modules.recruitment.service.intake_service import accept_lead

    await ingest_leads(_leads(_row()), brand_id=_BRAND)
    stored = await IntakeLead.find_one({"brand_id": _BRAND})
    assert stored.telecaller_assigned_at.tzinfo is None

    await accept_lead(stored)

    assert (await IntakeLead.get(stored.id)).telecaller_response_seconds is not None
