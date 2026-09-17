"""Accepting and rejecting a lead, over HTTP, as the people who really do it.

Signed in with real tokens and no dependency overrides, so the ownership rules
these endpoints add on top of the role guard are actually exercised: a
telecaller may work their own queue and nobody else's.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.recruitment.enums import (
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeRejectReason,
)
from app.modules.recruitment.models import (
    Candidate,
    CandidateEvent,
    Employee,
    IntakeLead,
)
from app.modules.recruitment.service.intake_service import as_utc

_BRAND = PydanticObjectId()


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _staff(name: str, role: UserRole) -> Employee:
    email = f"{name}@binge.consulting"
    await User(email=email, role=role).insert()
    employee = Employee(brand_id=_BRAND, name=name, email=email, role=role.value)
    await employee.insert()
    return employee


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _lead(
    *,
    telecaller: Employee | None = None,
    status: IntakeLeadStatus = IntakeLeadStatus.pending_telecaller,
    assigned_at: datetime | None = None,
) -> IntakeLead:
    candidate = Candidate(
        brand_id=_BRAND,
        full_name="Asha Rao",
        phone="9876543210",
        status=CandidateStatus.pending,
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=status,
        telecaller_id=telecaller.id if telecaller else None,
        telecaller_assigned_at=assigned_at or datetime.now(UTC),
    )
    await lead.insert()
    return lead


@pytest_asyncio.fixture
async def caller() -> Employee:
    return await _staff("caller", UserRole.telecaller)


# ── Accept ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accepting_approves_the_candidate_and_finds_a_recruiter(http, caller):
    recruiter = await _staff("recruiter", UserRole.employee)
    lead = await _lead(telecaller=caller, assigned_at=datetime.now(UTC) - timedelta(hours=3))

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/accept",
        json={"notes": "Keen, free from Monday"},
        headers=await _headers("caller"),
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == IntakeLeadStatus.pending_recruiter
    assert body["recruiter_id"] == str(recruiter.id)
    assert body["telecaller_decision"] == IntakeDecision.accept
    # Roughly three hours, in seconds — the number the SLA report is built on.
    assert 10700 < body["telecaller_response_seconds"] < 10900

    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.status == CandidateStatus.approved
    assert candidate.assigned_recruiter_id == recruiter.id


@pytest.mark.asyncio
async def test_acceptance_survives_having_no_recruiter_to_hand_it_to(http, caller):
    lead = await _lead(telecaller=caller)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/accept", json={}, headers=await _headers("caller")
    )

    # The call happened; the desk being empty is not the telecaller's problem,
    # and hiding their work would misreport it.
    assert res.json()["status"] == IntakeLeadStatus.unassigned
    assert (await Candidate.get(lead.candidate_id)).status == CandidateStatus.approved


@pytest.mark.asyncio
async def test_acceptance_is_recorded_on_the_candidate_history(http, caller):
    await _staff("recruiter", UserRole.employee)
    lead = await _lead(telecaller=caller)

    await http.post(
        f"/api/v1/intake/leads/{lead.id}/accept", json={}, headers=await _headers("caller")
    )

    events = await CandidateEvent.find({"candidate_id": lead.candidate_id}).to_list()
    assert any("telecaller" in (event.note or "").lower() for event in events)


# ── Reject ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejecting_marks_the_candidate_but_keeps_the_record(http, caller):
    lead = await _lead(telecaller=caller)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reject",
        json={"reason": IntakeRejectReason.not_interested.value, "notes": "Took another job"},
        headers=await _headers("caller"),
    )

    assert res.status_code == 200
    assert res.json()["status"] == IntakeLeadStatus.rejected
    assert res.json()["telecaller_reject_reason"] == IntakeRejectReason.not_interested

    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.status == CandidateStatus.rejected
    # Still on record: the directory hides them by filtering to APPROVED, but
    # "what are we rejecting, and why" stays answerable.
    assert candidate.is_active is True
    assert candidate.assigned_recruiter_id is None


@pytest.mark.asyncio
async def test_a_reason_is_optional(http, caller):
    lead = await _lead(telecaller=caller)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reject", json={}, headers=await _headers("caller")
    )

    assert res.status_code == 200
    assert res.json()["telecaller_reject_reason"] is None


# ── Who may act ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_telecaller_cannot_action_someone_elses_lead(http, caller):
    other = await _staff("other", UserRole.telecaller)
    lead = await _lead(telecaller=other)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/accept", json={}, headers=await _headers("caller")
    )

    assert res.status_code == 403
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.pending_telecaller


@pytest.mark.asyncio
async def test_a_maintainer_may_action_any_lead(http, caller):
    await _staff("boss", UserRole.maintainer)
    lead = await _lead(telecaller=caller)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reject", json={}, headers=await _headers("boss")
    )

    assert res.status_code == 200


@pytest.mark.asyncio
async def test_a_lead_cannot_be_actioned_twice(http, caller):
    lead = await _lead(telecaller=caller)
    headers = await _headers("caller")

    first = await http.post(f"/api/v1/intake/leads/{lead.id}/accept", json={}, headers=headers)
    second = await http.post(f"/api/v1/intake/leads/{lead.id}/reject", json={}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_a_lead_from_another_brand_is_not_found(http, caller):
    lead = await _lead(telecaller=caller)
    await lead.set({"brand_id": PydanticObjectId()})

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/accept", json={}, headers=await _headers("caller")
    )

    assert res.status_code == 404


# ── Queue ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_queue_shows_only_your_own_waiting_leads(http, caller):
    other = await _staff("other", UserRole.telecaller)
    mine = await _lead(telecaller=caller)
    await _lead(telecaller=other)
    actioned = await _lead(telecaller=caller, status=IntakeLeadStatus.rejected)

    res = await http.get("/api/v1/intake/leads/mine", headers=await _headers("caller"))

    assert [row["id"] for row in res.json()] == [str(mine.id)]
    assert str(actioned.id) not in {row["id"] for row in res.json()}


@pytest.mark.asyncio
async def test_the_queue_is_oldest_first(http, caller):
    now = datetime.now(UTC)
    newer = await _lead(telecaller=caller, assigned_at=now)
    older = await _lead(telecaller=caller, assigned_at=now - timedelta(days=1))

    res = await http.get("/api/v1/intake/leads/mine", headers=await _headers("caller"))

    # The oldest is the closest to breaching, so it is the one to call next.
    assert [row["id"] for row in res.json()] == [str(older.id), str(newer.id)]


@pytest.mark.asyncio
async def test_the_queue_carries_the_phone_number(http, caller):
    await _lead(telecaller=caller)

    res = await http.get("/api/v1/intake/leads/mine", headers=await _headers("caller"))

    # The number is the point of the screen; a second fetch per row would be
    # a round-trip for every person in the list.
    assert res.json()[0]["phone"] == "9876543210"
    assert res.json()[0]["full_name"] == "Asha Rao"


# ── Reassignment ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reassignment_restarts_the_clock_for_the_new_owner(http, caller):
    await _staff("boss", UserRole.maintainer)
    other = await _staff("other", UserRole.telecaller)
    stale = datetime.now(UTC) - timedelta(days=3)
    lead = await _lead(telecaller=caller, assigned_at=stale)
    await lead.set({"telecaller_sla_breached_at": stale})

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reassign",
        json={"employee_id": str(other.id)},
        headers=await _headers("boss"),
    )

    assert res.status_code == 200
    moved = await IntakeLead.get(lead.id)
    assert moved.telecaller_id == other.id
    # A fresh assignee does not inherit someone else's overdue clock...
    assert as_utc(moved.telecaller_assigned_at) > stale
    assert moved.telecaller_sla_breached_at is None
    # ...but the hand-off is counted, so this cannot hide a lead forever.
    assert moved.reassignment_count == 1


@pytest.mark.asyncio
async def test_a_telecaller_cannot_reassign(http, caller):
    other = await _staff("other", UserRole.telecaller)
    lead = await _lead(telecaller=caller)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reassign",
        json={"employee_id": str(other.id)},
        headers=await _headers("caller"),
    )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_an_actioned_lead_cannot_be_reassigned(http, caller):
    await _staff("boss", UserRole.maintainer)
    other = await _staff("other", UserRole.telecaller)
    lead = await _lead(telecaller=caller, status=IntakeLeadStatus.rejected)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reassign",
        json={"employee_id": str(other.id)},
        headers=await _headers("boss"),
    )

    assert res.status_code == 409
