"""A telecaller's call log: five unanswered calls close a lead, each with a note.

Signed in with real tokens, like test_decisions.py, so the ownership rules and the
role guards are exercised rather than assumed.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    MAX_CALL_ATTEMPTS,
    CandidateStatus,
    IntakeCallOutcome,
    IntakeLeadStatus,
    IntakeRejectReason,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, LeadCall
from tests.staff import auth_headers, make_staff
from tests.test_intake.test_decisions import ACCEPT

_BRAND = PydanticObjectId()


async def _lead(
    telecaller: Employee, *, assigned_hours_ago: int = 1, name: str = "Asha Rao", **fields
) -> IntakeLead:
    candidate = Candidate(
        brand_id=_BRAND, full_name=name, phone="9876543210", status=CandidateStatus.pending
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=IntakeLeadStatus.pending_telecaller,
        telecaller_id=telecaller.id,
        telecaller_assigned_at=datetime.now(UTC) - timedelta(hours=assigned_hours_ago),
        **fields,
    )
    await lead.insert()
    return lead


@pytest_asyncio.fixture
async def caller() -> Employee:
    return await make_staff(_BRAND, "caller", UserRole.telecaller)


async def _call(http, lead: IntakeLead, note: str | None = None, who: str = "caller"):
    body = {} if note is None else {"note": note}
    return await http.post(
        f"/api/v1/intake/leads/{lead.id}/calls", json=body, headers=await auth_headers(who)
    )


# ── Logging a call ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unanswered_call_is_counted_and_logged_with_its_note(http, caller):
    lead = await _lead(caller)

    res = await _call(http, lead, "  Rang out, will retry after lunch ")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dead"] is False
    assert body["lead"]["call_attempts"] == 1
    assert body["lead"]["max_call_attempts"] == MAX_CALL_ATTEMPTS
    assert body["lead"]["status"] == IntakeLeadStatus.pending_telecaller
    assert body["call"]["attempt"] == 1
    assert body["call"]["outcome"] == IntakeCallOutcome.no_answer
    assert body["call"]["note"] == "Rang out, will retry after lunch"
    assert body["call"]["telecaller_name"] == "caller"

    stored = await LeadCall.find_one({"lead_id": lead.id})
    assert (stored.telecaller_id, stored.attempt) == (caller.id, 1)
    assert (await IntakeLead.get(lead.id)).last_call_at is not None


@pytest.mark.asyncio
async def test_a_blank_note_is_no_note(http, caller):
    lead = await _lead(caller)

    res = await _call(http, lead, "   ")

    assert res.status_code == 200, res.text
    assert res.json()["call"]["note"] is None


@pytest.mark.asyncio
async def test_each_call_keeps_its_own_note_in_order(http, caller):
    lead = await _lead(caller)
    for note in ("first", "second", "third"):
        await _call(http, lead, note)

    res = await http.get(
        f"/api/v1/intake/leads/{lead.id}/calls", headers=await auth_headers("caller")
    )

    assert res.status_code == 200
    assert [(c["attempt"], c["note"]) for c in res.json()] == [
        (1, "first"),
        (2, "second"),
        (3, "third"),
    ]


@pytest.mark.asyncio
async def test_the_fifth_unanswered_call_closes_the_lead_as_unreachable(http, caller):
    lead = await _lead(caller)
    for _ in range(MAX_CALL_ATTEMPTS - 1):
        assert (await _call(http, lead)).json()["dead"] is False

    res = await _call(http, lead, "Phone switched off")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dead"] is True
    assert body["lead"]["call_attempts"] == MAX_CALL_ATTEMPTS
    assert body["lead"]["status"] == IntakeLeadStatus.rejected
    assert body["lead"]["telecaller_reject_reason"] == IntakeRejectReason.not_reachable
    stored = await IntakeLead.get(lead.id)
    assert stored.status == IntakeLeadStatus.rejected
    # The candidate is hidden like any telecaller reject.
    candidate = await Candidate.get(lead.candidate_id)
    assert (candidate.status, candidate.is_active) == (CandidateStatus.rejected, False)
    assert await LeadCall.find({"lead_id": lead.id}).count() == MAX_CALL_ATTEMPTS


@pytest.mark.asyncio
async def test_a_dead_lead_takes_no_sixth_call(http, caller):
    lead = await _lead(caller)
    for _ in range(MAX_CALL_ATTEMPTS):
        await _call(http, lead)

    res = await _call(http, lead)

    assert res.status_code == 409
    assert await LeadCall.find({"lead_id": lead.id}).count() == MAX_CALL_ATTEMPTS


@pytest.mark.asyncio
async def test_a_lead_from_before_call_tracking_is_counted_from_zero(http, caller):
    """Mongo holds old leads with no call_attempts field at all."""
    lead = await _lead(caller)
    await IntakeLead.get_motor_collection().update_one(
        {"_id": lead.id}, {"$unset": {"call_attempts": "", "last_call_at": ""}}
    )

    res = await _call(http, lead)

    assert res.status_code == 200, res.text
    assert res.json()["lead"]["call_attempts"] == 1


@pytest.mark.asyncio
async def test_a_telecaller_cannot_log_a_call_on_someone_elses_lead(http, caller):
    other = await make_staff(_BRAND, "other", UserRole.telecaller)
    lead = await _lead(other)

    res = await _call(http, lead)

    assert res.status_code == 403
    assert await LeadCall.find({"lead_id": lead.id}).count() == 0


@pytest.mark.asyncio
async def test_a_recruiter_cannot_log_or_read_calls(http, caller):
    await make_staff(_BRAND, "rec", UserRole.employee)
    lead = await _lead(caller)

    logged = await _call(http, lead, who="rec")
    read = await http.get(
        f"/api/v1/intake/leads/{lead.id}/calls", headers=await auth_headers("rec")
    )

    assert logged.status_code == 403
    assert read.status_code == 403


# ── Decisions are calls too ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accepting_logs_a_connected_call_after_the_unanswered_ones(http, caller):
    await make_staff(_BRAND, "recruiter", UserRole.employee)
    lead = await _lead(caller)
    await _call(http, lead)
    await _call(http, lead)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/accept",
        json={**ACCEPT, "notes": "Keen"},
        headers=await auth_headers("caller"),
    )

    assert res.status_code == 200, res.text
    assert res.json()["call_attempts"] == 3
    calls = await LeadCall.find({"lead_id": lead.id}).sort("attempt").to_list()
    assert [(c.attempt, c.outcome) for c in calls] == [
        (1, IntakeCallOutcome.no_answer),
        (2, IntakeCallOutcome.no_answer),
        (3, IntakeCallOutcome.connected),
    ]
    assert calls[2].note == "Keen"


@pytest.mark.asyncio
async def test_rejecting_as_not_reachable_logs_an_unanswered_call_and_any_other_reason_a_connected_one(
    http, caller
):
    unreachable = await _lead(caller, name="Unreachable")
    not_interested = await _lead(caller, name="Not interested")
    headers = await auth_headers("caller")

    await http.post(
        f"/api/v1/intake/leads/{unreachable.id}/reject",
        json={"reason": "not_reachable"},
        headers=headers,
    )
    await http.post(
        f"/api/v1/intake/leads/{not_interested.id}/reject",
        json={"reason": "not_interested"},
        headers=headers,
    )

    assert (await LeadCall.find_one({"lead_id": unreachable.id})).outcome == (
        IntakeCallOutcome.no_answer
    )
    assert (await LeadCall.find_one({"lead_id": not_interested.id})).outcome == (
        IntakeCallOutcome.connected
    )


@pytest.mark.asyncio
async def test_a_managers_decision_is_not_a_telecallers_call(http, caller):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(caller)

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reject",
        json={"reason": "wrong_number"},
        headers=await auth_headers("boss"),
    )

    assert res.status_code == 200, res.text
    assert await LeadCall.find({"lead_id": lead.id}).count() == 0


# ── The queue ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_called_leads_come_first_most_called_first_then_oldest(http, caller):
    fresh_old = await _lead(caller, name="Fresh old", assigned_hours_ago=48)
    fresh_new = await _lead(caller, name="Fresh new", assigned_hours_ago=1)
    once = await _lead(caller, name="Once", assigned_hours_ago=5, call_attempts=1)
    thrice = await _lead(caller, name="Thrice", assigned_hours_ago=2, call_attempts=3)
    # A lead from before the field existed sorts with the fresh ones.
    await IntakeLead.get_motor_collection().update_one(
        {"_id": fresh_old.id}, {"$unset": {"call_attempts": ""}}
    )

    res = await http.get("/api/v1/intake/leads/mine", headers=await auth_headers("caller"))

    assert res.status_code == 200
    assert [row["id"] for row in res.json()] == [
        str(thrice.id),
        str(once.id),
        str(fresh_old.id),
        str(fresh_new.id),
    ]
    assert [row["call_attempts"] for row in res.json()] == [3, 1, 0, 0]


# ── The management log ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_maintainer_reads_every_telecallers_log_and_can_filter(http, caller):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    other = await make_staff(_BRAND, "other", UserRole.telecaller)
    mine = await _lead(caller, name="Mine")
    theirs = await _lead(other, name="Theirs")
    await _call(http, mine, "m1")
    await _call(http, theirs, "t1", who="other")
    headers = await auth_headers("boss")

    everyone = await http.get("/api/v1/intake/calls", headers=headers)
    one = await http.get(f"/api/v1/intake/calls?telecaller_id={other.id}", headers=headers)

    assert everyone.status_code == 200
    assert {(c["lead_name"], c["telecaller_name"], c["note"]) for c in everyone.json()} == {
        ("Mine", "caller", "m1"),
        ("Theirs", "other", "t1"),
    }
    assert [(c["lead_name"], c["note"]) for c in one.json()] == [("Theirs", "t1")]


@pytest.mark.asyncio
async def test_the_management_log_can_be_narrowed_by_date(http, caller):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(caller)
    await _call(http, lead, "today")
    await LeadCall(
        brand_id=_BRAND,
        lead_id=lead.id,
        candidate_id=lead.candidate_id,
        telecaller_id=caller.id,
        attempt=1,
        outcome=IntakeCallOutcome.no_answer,
        note="last month",
        at=datetime.now(UTC) - timedelta(days=30),
    ).insert()
    since = (datetime.now(UTC) - timedelta(days=7)).isoformat()

    res = await http.get(
        "/api/v1/intake/calls", params={"start_date": since}, headers=await auth_headers("boss")
    )

    assert [c["note"] for c in res.json()] == ["today"]


@pytest.mark.asyncio
async def test_a_telecaller_cannot_open_the_management_log(http, caller):
    res = await http.get("/api/v1/intake/calls", headers=await auth_headers("caller"))

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_a_lead_left_at_the_limit_by_a_failed_close_is_closed_by_the_next_call(
    http, caller, monkeypatch
):
    """The fifth call was counted but the close failed: the lead must not be stuck."""
    from app.modules.recruitment.service import intake_service

    lead = await _lead(caller)
    for _ in range(MAX_CALL_ATTEMPTS - 1):
        await _call(http, lead)

    real_reject = intake_service.reject_lead

    async def failing_reject(*args, **kwargs):
        raise RuntimeError("mongo hiccup")

    monkeypatch.setattr(intake_service, "reject_lead", failing_reject)
    res = await _call(http, lead, "fifth")
    # The call happened and was logged, and the failed close is not a 500.
    assert res.status_code == 200, res.text
    assert res.json()["dead"] is False
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.pending_telecaller
    assert await LeadCall.find({"lead_id": lead.id}).count() == MAX_CALL_ATTEMPTS

    monkeypatch.setattr(intake_service, "reject_lead", real_reject)
    retry = await _call(http, lead)

    # Refused as it always was, but the lead is closed rather than stuck.
    assert retry.status_code == 409
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.rejected
    assert await LeadCall.find({"lead_id": lead.id}).count() == MAX_CALL_ATTEMPTS
