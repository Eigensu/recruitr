"""Screening notes: a savable, append-only note at every stage of a lead.

Signed in with real tokens, like test_decisions.py, so who may write and who may
read are exercised through the real role guards rather than assumed.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    CandidateStatus,
    IntakeLeadStatus,
    IntakeNoteStage,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, LeadNote
from tests.staff import auth_headers, make_staff

_BRAND = PydanticObjectId()


async def _lead(
    *,
    telecaller: Employee | None = None,
    recruiter: Employee | None = None,
    status: IntakeLeadStatus = IntakeLeadStatus.pending_telecaller,
    candidate: Candidate | None = None,
    name: str = "Asha Rao",
) -> IntakeLead:
    if candidate is None:
        candidate = Candidate(
            brand_id=_BRAND, full_name=name, phone="9876543210", status=CandidateStatus.pending
        )
        await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=status,
        telecaller_id=telecaller.id if telecaller else None,
        telecaller_assigned_at=datetime.now(UTC) - timedelta(hours=1),
        recruiter_id=recruiter.id if recruiter else None,
        recruiter_assigned_at=datetime.now(UTC) if recruiter else None,
    )
    await lead.insert()
    return lead


@pytest_asyncio.fixture
async def caller() -> Employee:
    return await make_staff(_BRAND, "caller", UserRole.telecaller)


@pytest_asyncio.fixture
async def rec() -> Employee:
    return await make_staff(_BRAND, "rec", UserRole.employee)


async def _note(http, lead: IntakeLead, body: str, who: str):
    return await http.post(
        f"/api/v1/intake/leads/{lead.id}/notes",
        json={"body": body},
        headers=await auth_headers(who),
    )


async def _history(http, lead: IntakeLead, who: str):
    return await http.get(f"/api/v1/intake/leads/{lead.id}/notes", headers=await auth_headers(who))


# ── Writing ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_telecaller_saves_a_note_stamped_with_who_and_where(http, caller):
    lead = await _lead(telecaller=caller)

    res = await _note(http, lead, "  Keen, but only free after 6pm  ", "caller")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["body"] == "Keen, but only free after 6pm"
    assert body["stage"] == IntakeNoteStage.telecaller
    assert body["author_name"] == "caller"
    assert body["author_role"] == "telecaller"
    assert body["author_id"] == str(caller.id)
    stored = await LeadNote.find_one({"lead_id": lead.id})
    assert (stored.candidate_id, stored.author_id) == (lead.candidate_id, caller.id)


@pytest.mark.asyncio
async def test_a_blank_note_is_refused_and_nothing_is_saved(http, caller):
    lead = await _lead(telecaller=caller)

    for body in ("", "   "):
        res = await _note(http, lead, body, "caller")
        assert res.status_code == 422, (body, res.text)

    assert await LeadNote.find({"lead_id": lead.id}).count() == 0


@pytest.mark.asyncio
async def test_a_padded_note_that_fits_once_trimmed_is_accepted(http, caller):
    lead = await _lead(telecaller=caller)

    res = await _note(http, lead, f"  {'x' * 2000}  ", "caller")

    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_a_telecaller_cannot_note_someone_elses_lead(http, caller):
    other = await make_staff(_BRAND, "other", UserRole.telecaller)
    lead = await _lead(telecaller=other)

    res = await _note(http, lead, "mine now", "caller")

    assert res.status_code == 403
    assert await LeadNote.find({"lead_id": lead.id}).count() == 0


@pytest.mark.asyncio
async def test_a_telecaller_cannot_note_a_lead_that_has_moved_on(http, caller):
    lead = await _lead(telecaller=caller, status=IntakeLeadStatus.pending_review)

    res = await _note(http, lead, "too late", "caller")

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_the_stage_follows_where_the_lead_is_and_management_writes_at_review(
    http, caller, rec
):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    at_review = await _lead(telecaller=caller, status=IntakeLeadStatus.pending_review)
    with_recruiter = await _lead(
        telecaller=caller, recruiter=rec, status=IntakeLeadStatus.pending_recruiter
    )

    review = await _note(http, at_review, "Send to the Bandra team", "boss")
    recruiter = await _note(http, with_recruiter, "Call Monday", "rec")

    assert review.json()["stage"] == IntakeNoteStage.review
    assert recruiter.json()["stage"] == IntakeNoteStage.recruiter
    assert recruiter.json()["author_role"] == "employee"


@pytest.mark.asyncio
async def test_a_recruiter_may_still_note_after_the_first_mapping(http, caller, rec):
    lead = await _lead(telecaller=caller, recruiter=rec, status=IntakeLeadStatus.actioned)

    res = await _note(http, lead, "Placed, follow up in a month", "rec")

    assert res.status_code == 200, res.text
    assert res.json()["stage"] == IntakeNoteStage.recruiter


@pytest.mark.asyncio
async def test_a_recruiter_cannot_note_a_lead_that_is_not_theirs_or_not_yet_with_them(
    http, caller, rec
):
    other = await make_staff(_BRAND, "other", UserRole.employee)
    theirs = await _lead(
        telecaller=caller, recruiter=other, status=IntakeLeadStatus.pending_recruiter
    )
    at_review = await _lead(telecaller=caller, status=IntakeLeadStatus.pending_review)

    assert (await _note(http, theirs, "not mine", "rec")).status_code == 403
    assert (await _note(http, at_review, "not yet", "rec")).status_code == 403


@pytest.mark.asyncio
async def test_notes_cannot_be_edited_or_deleted(http, caller):
    lead = await _lead(telecaller=caller)
    note_id = (await _note(http, lead, "as written", "caller")).json()["id"]
    headers = await auth_headers("caller")

    patch = await http.patch(
        f"/api/v1/intake/leads/{lead.id}/notes/{note_id}", json={"body": "changed"}, headers=headers
    )
    delete = await http.delete(f"/api/v1/intake/leads/{lead.id}/notes/{note_id}", headers=headers)

    assert patch.status_code in (404, 405)
    assert delete.status_code in (404, 405)
    assert (await LeadNote.get(note_id)).body == "as written"


@pytest.mark.asyncio
async def test_the_authors_name_is_kept_as_it_was_when_they_wrote(http, caller):
    lead = await _lead(telecaller=caller)
    await _note(http, lead, "first", "caller")

    await caller.set({"name": "Renamed Caller"})

    res = await _history(http, lead, "caller")
    assert [n["author_name"] for n in res.json()] == ["caller"]


# ── Reading ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_recruiter_reads_every_stages_notes_and_a_telecaller_only_their_own(
    http, caller, rec
):
    boss = await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(telecaller=caller)
    await _note(http, lead, "Screened: good English", "caller")
    await lead.set({"status": IntakeLeadStatus.pending_review})
    await _note(http, lead, "Team A", "boss")
    await lead.set(
        {
            "status": IntakeLeadStatus.pending_recruiter,
            "recruiter_id": rec.id,
            "team_id": PydanticObjectId(),
        }
    )
    await _note(http, lead, "Calling tomorrow", "rec")
    assert boss.id is not None

    as_rec = await _history(http, lead, "rec")
    as_boss = await _history(http, lead, "boss")
    as_caller = await _history(http, lead, "caller")

    expected = [
        ("telecaller", "Screened: good English"),
        ("review", "Team A"),
        ("recruiter", "Calling tomorrow"),
    ]
    assert [(n["stage"], n["body"]) for n in as_rec.json()] == expected
    assert [(n["stage"], n["body"]) for n in as_boss.json()] == expected
    # The telecaller's own stage only, even though they are the lead's telecaller.
    assert [(n["stage"], n["body"]) for n in as_caller.json()] == expected[:1]


@pytest.mark.asyncio
async def test_a_note_keeps_its_stage_after_the_lead_moves_on(http, caller, rec):
    lead = await _lead(telecaller=caller)
    await _note(http, lead, "At my step", "caller")

    await lead.set({"status": IntakeLeadStatus.pending_recruiter, "recruiter_id": rec.id})

    res = await _history(http, lead, "rec")
    assert [n["stage"] for n in res.json()] == [IntakeNoteStage.telecaller]


@pytest.mark.asyncio
async def test_nobody_reads_the_notes_on_a_lead_that_is_not_theirs(http, caller, rec):
    other_caller = await make_staff(_BRAND, "other", UserRole.telecaller)
    other_rec = await make_staff(_BRAND, "otherrec", UserRole.employee)
    lead = await _lead(telecaller=other_caller, recruiter=other_rec)
    await _note(http, lead, "private to them", "other")

    assert (await _history(http, lead, "caller")).status_code == 403
    assert (await _history(http, lead, "rec")).status_code == 403


@pytest.mark.asyncio
async def test_a_recruiter_reads_all_the_notes_on_a_candidate_across_leads(http, caller, rec):
    candidate = Candidate(
        brand_id=_BRAND, full_name="Asha Rao", phone="9876543210", status=CandidateStatus.pending
    )
    await candidate.insert()
    first = await _lead(telecaller=caller, candidate=candidate)
    await _note(http, first, "First time round", "caller")
    await first.set({"status": IntakeLeadStatus.rejected})
    second = await _lead(telecaller=caller, candidate=candidate)
    await _note(http, second, "Back again", "caller")
    other = await _lead(telecaller=caller, name="Someone else")
    await _note(http, other, "Not this person", "caller")

    res = await http.get(
        f"/api/v1/candidates/{candidate.id}/screening-notes", headers=await auth_headers("rec")
    )

    assert res.status_code == 200, res.text
    assert [n["body"] for n in res.json()] == ["First time round", "Back again"]


@pytest.mark.asyncio
async def test_a_telecaller_cannot_read_the_candidate_level_notes(http, caller):
    lead = await _lead(telecaller=caller)

    res = await http.get(
        f"/api/v1/candidates/{lead.candidate_id}/screening-notes",
        headers=await auth_headers("caller"),
    )

    assert res.status_code == 403


# ── The management log ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_maintainer_reads_the_log_and_filters_by_author_stage_and_date(http, caller, rec):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(telecaller=caller, name="Asha Rao")
    await _note(http, lead, "from the caller", "caller")
    await lead.set({"status": IntakeLeadStatus.pending_recruiter, "recruiter_id": rec.id})
    await _note(http, lead, "from the recruiter", "rec")
    await LeadNote(
        brand_id=_BRAND,
        lead_id=lead.id,
        candidate_id=lead.candidate_id,
        stage=IntakeNoteStage.telecaller,
        body="last month",
        author_id=caller.id,
        author_name="caller",
        author_role="telecaller",
        created_at=datetime.now(UTC) - timedelta(days=30),
    ).insert()
    headers = await auth_headers("boss")
    since = (datetime.now(UTC) - timedelta(days=7)).isoformat()

    everything = await http.get("/api/v1/intake/notes", headers=headers)
    by_caller = await http.get(f"/api/v1/intake/notes?author_id={caller.id}", headers=headers)
    by_stage = await http.get("/api/v1/intake/notes?stage=recruiter", headers=headers)
    recent = await http.get("/api/v1/intake/notes", params={"start_date": since}, headers=headers)

    assert {n["body"] for n in everything.json()} == {
        "from the caller",
        "from the recruiter",
        "last month",
    }
    assert {n["candidate_name"] for n in everything.json()} == {"Asha Rao"}
    assert {n["body"] for n in by_caller.json()} == {"from the caller", "last month"}
    assert [n["body"] for n in by_stage.json()] == ["from the recruiter"]
    assert {n["body"] for n in recent.json()} == {"from the caller", "from the recruiter"}


@pytest.mark.asyncio
async def test_only_management_may_open_the_log(http, caller, rec):
    for who in ("caller", "rec"):
        res = await http.get("/api/v1/intake/notes", headers=await auth_headers(who))
        assert res.status_code == 403, who
