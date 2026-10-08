"""The Candidates page's Review tab: a recruiter accepts or rejects the leads a
team's round-robin handed them.

Accept actions the lead (the recruiter's clock stops there, without waiting for
a mapping). Reject archives it and soft-deletes the candidate. The Candidates
tab leaves out anyone still waiting in someone's Review tab.

Signed in with real tokens, like test_review.py, so the role guards are
exercised rather than assumed.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeRejectReason,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeLead
from tests.staff import auth_headers, make_staff

_BRAND = PydanticObjectId()


@pytest_asyncio.fixture
async def rec() -> Employee:
    return await make_staff(_BRAND, "rec", UserRole.employee)


async def _with_recruiter(recruiter: Employee, name: str = "Asha Rao") -> IntakeLead:
    """A lead an admin has handed to `recruiter`'s team, waiting in their Review tab."""
    candidate = Candidate(
        brand_id=_BRAND,
        full_name=name,
        phone="9876543210",
        status=CandidateStatus.approved,
        assigned_recruiter_id=recruiter.id,
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=IntakeLeadStatus.pending_recruiter,
        telecaller_decision=IntakeDecision.accept,
        recruiter_id=recruiter.id,
        recruiter_assigned_at=datetime.now(UTC) - timedelta(hours=2),
    )
    await lead.insert()
    return lead


# ── The list ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_recruiter_sees_only_their_own_review_leads(http, rec):
    other = await make_staff(_BRAND, "other", UserRole.employee)
    mine = await _with_recruiter(rec, "Mine")
    await _with_recruiter(other, "Theirs")

    # Asking for someone else's is ignored, not honoured.
    res = await http.get(
        f"/api/v1/intake/leads/review?recruiter_id={other.id}", headers=await auth_headers("rec")
    )

    assert res.status_code == 200
    assert [row["id"] for row in res.json()] == [str(mine.id)]
    assert res.json()[0]["full_name"] == "Mine"


@pytest.mark.asyncio
async def test_a_maintainer_sees_every_recruiters_review_leads_and_can_filter(http, rec):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    other = await make_staff(_BRAND, "other", UserRole.employee)
    await _with_recruiter(rec, "Mine")
    theirs = await _with_recruiter(other, "Theirs")
    headers = await auth_headers("boss")

    everyone = await http.get("/api/v1/intake/leads/review", headers=headers)
    one = await http.get(f"/api/v1/intake/leads/review?recruiter_id={other.id}", headers=headers)

    assert {row["full_name"] for row in everyone.json()} == {"Mine", "Theirs"}
    assert [row["id"] for row in one.json()] == [str(theirs.id)]
    assert one.json()[0]["recruiter_name"] == "other"


@pytest.mark.asyncio
async def test_only_leads_waiting_on_a_recruiter_are_listed(http, rec):
    waiting = await _with_recruiter(rec)
    done = await _with_recruiter(rec, "Done")
    await done.set({"status": IntakeLeadStatus.actioned})

    res = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("rec"))

    assert [row["id"] for row in res.json()] == [str(waiting.id)]


@pytest.mark.asyncio
async def test_a_telecaller_cannot_open_the_review_tab(http):
    await make_staff(_BRAND, "caller", UserRole.telecaller)

    res = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("caller"))

    assert res.status_code == 403


# ── Accept ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accepting_actions_the_lead_and_stops_the_clock(http, rec):
    lead = await _with_recruiter(rec)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-accept", headers=await auth_headers("rec")
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == IntakeLeadStatus.actioned
    assert body["recruiter_decision"] == IntakeDecision.accept
    assert body["recruiter_response_seconds"] >= 2 * 3600
    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.is_active is True
    assert candidate.status == CandidateStatus.approved


@pytest.mark.asyncio
async def test_a_recruiter_cannot_decide_someone_elses_lead(http, rec):
    other = await make_staff(_BRAND, "other", UserRole.employee)
    lead = await _with_recruiter(other)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-accept", headers=await auth_headers("rec")
    )

    assert res.status_code == 403
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.pending_recruiter


@pytest.mark.asyncio
async def test_a_maintainer_may_decide_on_a_recruiters_behalf(http, rec):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _with_recruiter(rec)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-accept", headers=await auth_headers("boss")
    )

    assert res.status_code == 200
    assert res.json()["status"] == IntakeLeadStatus.actioned


@pytest.mark.asyncio
async def test_a_lead_cannot_be_decided_twice(http, rec):
    lead = await _with_recruiter(rec)
    headers = await auth_headers("rec")

    await http.post(f"/api/v1/intake/leads/{lead.id}/recruiter-accept", headers=headers)
    again = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-reject", json={}, headers=headers
    )

    assert again.status_code == 409
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.actioned
    assert (await Candidate.get(lead.candidate_id)).is_active is True


# ── Reject ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejecting_archives_the_lead_and_hides_the_candidate(http, rec):
    lead = await _with_recruiter(rec)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-reject",
        json={"reason": IntakeRejectReason.not_eligible.value, "notes": "No experience"},
        headers=await auth_headers("rec"),
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == IntakeLeadStatus.archived
    assert body["recruiter_decision"] == IntakeDecision.reject
    assert body["recruiter_reject_reason"] == IntakeRejectReason.not_eligible
    assert body["recruiter_notes"] == "No experience"
    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.is_active is False
    assert candidate.status == CandidateStatus.rejected


@pytest.mark.asyncio
async def test_a_reject_reason_is_optional(http, rec):
    lead = await _with_recruiter(rec)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-reject",
        json={},
        headers=await auth_headers("rec"),
    )

    assert res.status_code == 200
    assert res.json()["recruiter_reject_reason"] is None


# ── The Candidates tab ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_candidates_tab_leaves_out_people_still_in_review(http, rec):
    in_review = await _with_recruiter(rec, "Waiting")
    accepted = await _with_recruiter(rec, "Accepted")
    headers = await auth_headers("rec")
    await http.post(f"/api/v1/intake/leads/{accepted.id}/recruiter-accept", headers=headers)
    plain = Candidate(brand_id=_BRAND, full_name="Walk-in", status=CandidateStatus.approved)
    await plain.insert()

    tab = await http.get("/api/v1/candidates?exclude_in_review=true", headers=headers)
    everyone = await http.get("/api/v1/candidates", headers=headers)

    assert {row["full_name"] for row in tab.json()["items"]} == {"Accepted", "Walk-in"}
    # The filter is opt-in: other callers of the list still see them.
    assert str(in_review.candidate_id) in {row["id"] for row in everyone.json()["items"]}
