"""The Candidates page's Review tab: a recruiter accepts or rejects the leads a
team's round-robin handed them.

The candidate stays PENDING until the recruiter accepts, so someone in review is
in that Review tab and in no list of approved people anywhere, and cannot be
mapped. Accept approves them but does not action the lead: the recruiter's
clock runs on to their first mapping, which a click cannot stand in for. Reject
archives the lead and soft-deletes the candidate.

Signed in with real tokens, like test_review.py, so the role guards are
exercised rather than assumed.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

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
from app.modules.recruitment.models import Candidate, Client, Employee, IntakeLead, Position
from app.modules.recruitment.service.intake_service import (
    close_lead_for_mapping,
    reassign_lead,
    recruiter_reject_lead,
)
from app.modules.recruitment.service.intake_sla import sweep_breaches
from tests.staff import auth_headers, make_staff

_BRAND = PydanticObjectId()


@pytest_asyncio.fixture
async def rec() -> Employee:
    return await make_staff(_BRAND, "rec", UserRole.employee)


async def _with_recruiter(
    recruiter: Employee,
    name: str = "Asha Rao",
    *,
    status: CandidateStatus = CandidateStatus.pending,
    **candidate_fields,
) -> IntakeLead:
    """A lead an admin has handed to `recruiter`'s team, waiting in their Review tab.

    PENDING, as team assignment leaves it. `status=APPROVED` is a lead assigned
    before the Review step existed, when assignment approved the candidate.
    """
    candidate = Candidate(
        brand_id=_BRAND,
        full_name=name,
        phone="9876543210",
        status=status,
        assigned_recruiter_id=recruiter.id,
        **candidate_fields,
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


async def _position() -> Position:
    client = Client(brand_id=_BRAND, code="CLI-001", name="Hunger Inc")
    await client.insert()
    position = Position(
        brand_id=_BRAND,
        code="CLI-001-POS-001",
        client_id=client.id,
        client_name=client.name,
        role="Steward",
        total_seats=1,
        remaining_seats=1,
    )
    await position.insert()
    return position


async def _map(http, position: Position, lead: IntakeLead, who: str = "rec"):
    return await http.post(
        f"/api/v1/positions/{position.id}/map-candidate",
        json={"candidate_id": str(lead.candidate_id)},
        headers=await auth_headers(who),
    )


async def _accept(http, lead: IntakeLead, who: str = "rec"):
    return await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-accept", headers=await auth_headers(who)
    )


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
async def test_only_leads_still_waiting_on_a_decision_are_listed(http, rec):
    waiting = await _with_recruiter(rec)
    done = await _with_recruiter(rec, "Done")
    await done.set({"status": IntakeLeadStatus.actioned})
    accepted = await _with_recruiter(rec, "Accepted")
    await _accept(http, accepted)

    res = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("rec"))

    assert [row["id"] for row in res.json()] == [str(waiting.id)]


@pytest.mark.asyncio
async def test_the_review_list_carries_the_cv_so_the_card_can_link_it(http, rec):
    await _with_recruiter(rec, "With CV", resume_url="https://res.cloudinary.com/x/cv.pdf")
    await _with_recruiter(rec, "Without")

    res = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("rec"))

    rows = {row["full_name"]: row for row in res.json()}
    assert rows["With CV"]["resume_url"] == "https://res.cloudinary.com/x/cv.pdf"
    assert rows["With CV"]["cv_locked"] is False
    without = rows["Without"]
    assert (without["cv_link"], without["resume_url"], without["cv_locked"]) == (None, None, False)


@pytest.mark.asyncio
async def test_a_cv_another_recruiter_sourced_stays_theirs_in_the_review_tab(http, rec):
    # The directory's rule (utils/cv_access): the card must not be a way round it.
    other = await make_staff(_BRAND, "other", UserRole.employee)
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    await _with_recruiter(rec, cv_link="https://drive.example/cv", created_by_id=other.id)

    mine = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("rec"))
    boss = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("boss"))

    assert (mine.json()[0]["cv_link"], mine.json()[0]["cv_locked"]) == (None, True)
    assert (boss.json()[0]["cv_link"], boss.json()[0]["cv_locked"]) == (
        "https://drive.example/cv",
        False,
    )


@pytest.mark.asyncio
async def test_a_telecaller_cannot_open_the_review_tab(http):
    await make_staff(_BRAND, "caller", UserRole.telecaller)

    res = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("caller"))

    assert res.status_code == 403


# ── The REVIEWED tab ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accepted_leads_move_to_the_reviewed_tab(http, rec):
    waiting = await _with_recruiter(rec, "Waiting")
    accepted = await _with_recruiter(rec, "Accepted")
    await _accept(http, accepted)
    headers = await auth_headers("rec")

    reviewed = await http.get("/api/v1/intake/leads/reviewed", headers=headers)
    review = await http.get("/api/v1/intake/leads/review", headers=headers)

    assert reviewed.status_code == 200
    assert [row["id"] for row in reviewed.json()] == [str(accepted.id)]
    assert [row["id"] for row in review.json()] == [str(waiting.id)]


@pytest.mark.asyncio
async def test_a_lead_stays_reviewed_after_its_first_mapping_closes_it(http, rec):
    lead = await _with_recruiter(rec)
    await _accept(http, lead)
    assert (await _map(http, await _position(), lead)).status_code == 200

    res = await http.get("/api/v1/intake/leads/reviewed", headers=await auth_headers("rec"))

    assert [row["id"] for row in res.json()] == [str(lead.id)]
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.actioned


@pytest.mark.asyncio
async def test_a_rejected_lead_is_not_reviewed(http, rec):
    lead = await _with_recruiter(rec)
    await recruiter_reject_lead(lead, actor_id=rec.id, reason=None, notes=None)

    res = await http.get("/api/v1/intake/leads/reviewed", headers=await auth_headers("rec"))

    assert res.json() == []


@pytest.mark.asyncio
async def test_a_recruiter_sees_only_their_own_reviewed_leads_and_a_maintainer_all(http, rec):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    other = await make_staff(_BRAND, "other", UserRole.employee)
    mine = await _with_recruiter(rec, "Mine")
    theirs = await _with_recruiter(other, "Theirs")
    await _accept(http, mine)
    await _accept(http, theirs, who="other")

    own = await http.get(
        f"/api/v1/intake/leads/reviewed?recruiter_id={other.id}", headers=await auth_headers("rec")
    )
    boss = await http.get("/api/v1/intake/leads/reviewed", headers=await auth_headers("boss"))
    one = await http.get(
        f"/api/v1/intake/leads/reviewed?recruiter_id={other.id}",
        headers=await auth_headers("boss"),
    )

    assert [row["id"] for row in own.json()] == [str(mine.id)]
    assert {row["full_name"] for row in boss.json()} == {"Mine", "Theirs"}
    assert [row["id"] for row in one.json()] == [str(theirs.id)]


@pytest.mark.asyncio
async def test_a_telecaller_cannot_open_the_reviewed_tab(http):
    await make_staff(_BRAND, "caller", UserRole.telecaller)

    res = await http.get("/api/v1/intake/leads/reviewed", headers=await auth_headers("caller"))

    assert res.status_code == 403


# ── Accept ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accepting_approves_the_candidate_but_leaves_the_clock_running(http, rec):
    lead = await _with_recruiter(rec)

    res = await _accept(http, lead)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == IntakeLeadStatus.pending_recruiter
    assert body["recruiter_decision"] == IntakeDecision.accept
    assert body["recruiter_accepted_at"] is not None
    assert body["recruiter_actioned_at"] is None
    assert body["recruiter_response_seconds"] is None
    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.is_active is True
    assert candidate.status == CandidateStatus.approved


@pytest.mark.asyncio
async def test_the_first_mapping_after_accepting_stops_the_clock(http, rec):
    lead = await _with_recruiter(rec)
    position = await _position()
    await _accept(http, lead)

    res = await _map(http, position, lead)

    assert res.status_code == 200, res.text
    stored = await IntakeLead.get(lead.id)
    assert stored.status == IntakeLeadStatus.actioned
    assert stored.recruiter_decision == IntakeDecision.accept
    assert stored.recruiter_response_seconds >= 2 * 3600


@pytest.mark.asyncio
async def test_an_accepted_lead_still_breaches_if_nobody_is_put_forward(http, rec):
    lead = await _with_recruiter(rec)
    await lead.set({"recruiter_assigned_at": datetime.now(UTC) - timedelta(hours=30)})
    await _accept(http, lead)

    await sweep_breaches()

    assert (await IntakeLead.get(lead.id)).recruiter_sla_breached_at is not None


@pytest.mark.asyncio
async def test_a_recruiter_cannot_decide_someone_elses_lead(http, rec):
    other = await make_staff(_BRAND, "other", UserRole.employee)
    lead = await _with_recruiter(other)

    res = await _accept(http, lead)

    assert res.status_code == 403
    stored = await IntakeLead.get(lead.id)
    assert stored.recruiter_decision is None
    assert (await Candidate.get(lead.candidate_id)).status == CandidateStatus.pending


@pytest.mark.asyncio
async def test_a_maintainer_may_decide_on_a_recruiters_behalf(http, rec):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _with_recruiter(rec)

    res = await _accept(http, lead, who="boss")

    assert res.status_code == 200
    assert res.json()["recruiter_decision"] == IntakeDecision.accept


@pytest.mark.asyncio
async def test_a_lead_cannot_be_decided_twice(http, rec):
    lead = await _with_recruiter(rec)
    headers = await auth_headers("rec")

    await _accept(http, lead)
    reject = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-reject", json={}, headers=headers
    )
    accept_again = await _accept(http, lead)

    assert reject.status_code == 409
    assert accept_again.status_code == 409
    stored = await IntakeLead.get(lead.id)
    assert stored.status == IntakeLeadStatus.pending_recruiter
    assert stored.recruiter_decision == IntakeDecision.accept
    candidate = await Candidate.get(lead.candidate_id)
    assert (candidate.is_active, candidate.status) == (True, CandidateStatus.approved)


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


@pytest.mark.asyncio
async def test_a_rejected_leads_profile_can_still_be_opened(http, rec):
    """Hidden from every list, but the Leads page links to them by id."""
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _with_recruiter(rec)
    headers = await auth_headers("boss")
    await http.post(f"/api/v1/intake/leads/{lead.id}/recruiter-reject", json={}, headers=headers)
    cid = lead.candidate_id

    profile = await http.get(f"/api/v1/candidates/{cid}", headers=headers)
    history = await http.get(f"/api/v1/candidates/{cid}/history", headers=headers)
    mappings = await http.get(f"/api/v1/candidates/{cid}/mappings", headers=headers)
    # Reading only: an edit on a row no list shows stays refused.
    edit = await http.patch(f"/api/v1/candidates/{cid}", json={"city": "Pune"}, headers=headers)

    assert profile.status_code == 200, profile.text
    assert profile.json()["status"] == CandidateStatus.rejected
    assert history.status_code == 200
    assert mappings.status_code == 200
    assert edit.status_code == 404


@pytest.mark.asyncio
async def test_a_reject_that_cannot_hide_the_candidate_goes_back_to_review(http, rec, monkeypatch):
    """The lead is archived first. Left that way, a failed candidate write would
    keep the person PENDING behind a lead no Review tab lists — in no list at
    all, with nothing left to retry."""
    lead = await _with_recruiter(rec)

    async def fail(self, *args, **kwargs):
        raise RuntimeError("write failed")

    with monkeypatch.context() as patch:
        patch.setattr(Candidate, "set", fail)
        with pytest.raises(RuntimeError):
            await recruiter_reject_lead(
                lead, actor_id=rec.id, reason=IntakeRejectReason.not_eligible, notes="No"
            )

    stored = await IntakeLead.get(lead.id)
    assert stored.status == IntakeLeadStatus.pending_recruiter
    assert stored.recruiter_decision is None
    assert stored.recruiter_reject_reason is None
    assert stored.recruiter_notes is None
    assert stored.recruiter_actioned_at is None
    assert stored.recruiter_response_seconds is None
    candidate = await Candidate.get(lead.candidate_id)
    assert (candidate.is_active, candidate.status) == (True, CandidateStatus.pending)
    # Back in the tab, so the recruiter can simply try again.
    retry = await http.post(
        f"/api/v1/intake/leads/{lead.id}/recruiter-reject",
        json={},
        headers=await auth_headers("rec"),
    )
    assert retry.status_code == 200


# ── Everywhere else ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_someone_in_review_is_in_no_approved_list_until_accepted(http, rec):
    in_review = await _with_recruiter(rec, "Waiting")
    accepted = await _with_recruiter(rec, "Accepted")
    await _accept(http, accepted)
    plain = Candidate(brand_id=_BRAND, full_name="Walk-in", status=CandidateStatus.approved)
    await plain.insert()
    position = await _position()
    headers = await auth_headers("rec")

    directory = await http.get("/api/v1/candidates", headers=headers)
    top = await http.get(f"/api/v1/positions/{position.id}/top-candidates", headers=headers)

    assert {row["full_name"] for row in directory.json()["items"]} == {"Accepted", "Walk-in"}
    assert "Waiting" not in {row["full_name"] for row in top.json()}
    assert (await _map(http, position, in_review)).status_code == 409


@pytest.mark.asyncio
async def test_someone_in_review_cannot_be_approved_around_the_recruiter(http, rec):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _with_recruiter(rec)

    res = await http.post(
        f"/api/v1/candidates/{lead.candidate_id}/approve", headers=await auth_headers("boss")
    )

    assert res.status_code == 409
    assert (await Candidate.get(lead.candidate_id)).status == CandidateStatus.pending


@pytest.mark.asyncio
async def test_reassigning_an_accept_from_before_the_review_step_does_not_ask_again(http, rec):
    """Accepted when no recruiter was free, and approved by the flow of the day.
    Given to a recruiter now, they are already in the Candidates tab, so they
    must not also land in Review, where a reject would hide them."""

    async def accepted_unassigned(name: str, status: CandidateStatus) -> IntakeLead:
        lead = await _with_recruiter(rec, name, status=status)
        await lead.set(
            {
                "status": IntakeLeadStatus.unassigned,
                "recruiter_id": None,
                "recruiter_assigned_at": None,
            }
        )
        return await IntakeLead.get(lead.id)

    approved = await accepted_unassigned("Approved then", CandidateStatus.approved)
    pending = await accepted_unassigned("Still pending", CandidateStatus.pending)

    await reassign_lead(approved, assignee=rec)
    await reassign_lead(pending, assignee=rec)

    stored = await IntakeLead.get(approved.id)
    assert stored.status == IntakeLeadStatus.pending_recruiter
    assert stored.recruiter_decision == IntakeDecision.accept
    assert stored.recruiter_accepted_at is not None
    # Someone the old flow never approved still gets the recruiter's decision.
    assert (await IntakeLead.get(pending.id)).recruiter_decision is None
    res = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("rec"))
    assert [row["full_name"] for row in res.json()] == ["Still pending"]


@pytest.mark.asyncio
async def test_a_mapping_does_not_reopen_a_lead_rejected_while_it_ran(rec, monkeypatch):
    """The mapping reads the lead as waiting, a reject lands, then the mapping
    writes. Its write must miss rather than flip the archived lead to actioned.

    A lead assigned before the Review step (candidate already APPROVED) is the
    case where both can happen: it is mappable and still undecided.
    """
    lead = await _with_recruiter(rec, status=CandidateStatus.approved)
    stale = await IntakeLead.get(lead.id)
    await lead.set({"status": IntakeLeadStatus.archived})
    real = IntakeLead.find_one
    calls = 0

    def find_one(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:  # the mapping's read, from before the reject

            async def read():
                return stale

            return read()
        return real(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(IntakeLead, "find_one", find_one)
        await close_lead_for_mapping(
            SimpleNamespace(id=PydanticObjectId(), brand_id=_BRAND, candidate_id=lead.candidate_id)
        )

    assert calls == 2
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.archived
