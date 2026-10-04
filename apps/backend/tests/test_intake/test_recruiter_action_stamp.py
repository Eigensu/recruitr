"""The recruiter's clock stops at their first mapping of an inbound lead.

"Actioned" is deliberately the first real recruiting act rather than an
acknowledgement click: it is already an auditable event, and it cannot be
satisfied by opening a page.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.recruitment.enums import IntakeLeadStatus
from app.modules.recruitment.models import Candidate, Client, Employee, IntakeLead, Position
from app.modules.recruitment.schemas import TenantScope
from app.modules.recruitment.service import map_candidate

_BRAND = PydanticObjectId()


@pytest_asyncio.fixture
async def recruiter() -> Employee:
    employee = Employee(brand_id=_BRAND, name="Rec", email="rec@binge.consulting", role="employee")
    await employee.insert()
    return employee


@pytest_asyncio.fixture
async def position() -> Position:
    client = Client(brand_id=_BRAND, code="CLI-1", name="Hunger Inc")
    await client.insert()
    pos = Position(
        brand_id=_BRAND,
        code="CLI-1-POS-1",
        client_id=client.id,
        client_name=client.name,
        role="Bartender",
        total_seats=2,
        remaining_seats=2,
    )
    await pos.insert()
    return pos


async def _lead_awaiting_recruiter(recruiter: Employee, *, assigned_hours_ago: int = 5):
    candidate = Candidate(brand_id=_BRAND, full_name="Asha Rao", phone="9876543210")
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=IntakeLeadStatus.pending_recruiter,
        recruiter_id=recruiter.id,
        recruiter_assigned_at=datetime.now(UTC) - timedelta(hours=assigned_hours_ago),
    )
    await lead.insert()
    return candidate, lead


@pytest.mark.asyncio
async def test_the_first_mapping_stops_the_clock(recruiter, position):
    candidate, lead = await _lead_awaiting_recruiter(recruiter)
    scope = TenantScope(brand_id=_BRAND, employee_id=recruiter.id)

    mapping = await map_candidate(
        scope=scope, candidate_id=candidate.id, position=position, match_score=None
    )

    stamped = await IntakeLead.get(lead.id)
    assert stamped.status == IntakeLeadStatus.actioned
    assert stamped.recruiter_action_mapping_id == mapping.id
    assert 17900 < stamped.recruiter_response_seconds < 18100  # ~5 hours


@pytest.mark.asyncio
async def test_a_second_mapping_does_not_move_the_clock(recruiter, position):
    candidate, lead = await _lead_awaiting_recruiter(recruiter)
    scope = TenantScope(brand_id=_BRAND, employee_id=recruiter.id)
    await map_candidate(scope=scope, candidate_id=candidate.id, position=position, match_score=None)
    first = await IntakeLead.get(lead.id)

    other = Position(
        brand_id=_BRAND,
        code="CLI-1-POS-2",
        client_id=position.client_id,
        client_name=position.client_name,
        role="Barback",
        total_seats=1,
        remaining_seats=1,
    )
    await other.insert()
    await map_candidate(scope=scope, candidate_id=candidate.id, position=other, match_score=None)

    again = await IntakeLead.get(lead.id)
    assert again.recruiter_actioned_at == first.recruiter_actioned_at
    assert again.recruiter_action_mapping_id == first.recruiter_action_mapping_id


@pytest.mark.asyncio
async def test_mapping_a_candidate_who_never_was_a_lead_is_fine(recruiter, position):
    candidate = Candidate(brand_id=_BRAND, full_name="Walk-in", phone="9000000000")
    await candidate.insert()

    mapping = await map_candidate(
        scope=TenantScope(brand_id=_BRAND, employee_id=recruiter.id),
        candidate_id=candidate.id,
        position=position,
        match_score=None,
    )

    assert mapping is not None


@pytest.mark.asyncio
async def test_a_lead_still_with_the_telecaller_is_left_alone(recruiter, position):
    candidate, lead = await _lead_awaiting_recruiter(recruiter)
    await lead.set({"status": IntakeLeadStatus.pending_telecaller})

    await map_candidate(
        scope=TenantScope(brand_id=_BRAND, employee_id=recruiter.id),
        candidate_id=candidate.id,
        position=position,
        match_score=None,
    )

    untouched = await IntakeLead.get(lead.id)
    assert untouched.status == IntakeLeadStatus.pending_telecaller
    assert untouched.recruiter_actioned_at is None


@pytest.mark.asyncio
async def test_a_failing_stamp_does_not_lose_the_mapping(recruiter, position, monkeypatch):
    # The mapping is the real work; the timestamp only measures it. Same rule
    # the gamification and referral writes beside it follow.
    candidate, lead = await _lead_awaiting_recruiter(recruiter)

    async def _boom(_mapping):
        raise RuntimeError("intake stamp exploded")

    monkeypatch.setattr(
        "app.modules.recruitment.service.intake_service.close_lead_for_mapping", _boom
    )

    mapping = await map_candidate(
        scope=TenantScope(brand_id=_BRAND, employee_id=recruiter.id),
        candidate_id=candidate.id,
        position=position,
        match_score=None,
    )

    assert mapping is not None
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.pending_recruiter
