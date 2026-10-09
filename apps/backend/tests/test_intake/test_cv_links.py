"""CV upload links: whoever holds a lead asks its candidate for their CV.

The link is made by the telecaller screening the lead, the recruiter deciding
it in their Review tab, or a maintainer; the candidate opens it with no account
and uploads. Signed in with real tokens, like test_recruiter_review.py, so the
new guard is exercised rather than assumed. The Cloudinary upload is the one
thing stubbed: everything worth asserting happens either side of it.
"""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.brands.models import Brand
from app.modules.recruitment.controller import public_controller
from app.modules.recruitment.enums import (
    CandidateEventType,
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
    NotificationKind,
)
from app.modules.recruitment.models import (
    Candidate,
    CandidateEvent,
    Employee,
    IntakeLead,
    Notification,
)
from app.modules.recruitment.utils.resume_parser import ParsedResume
from tests.staff import auth_headers, make_staff

_BRAND = PydanticObjectId()
_UPLOADED = "https://res.cloudinary.com/demo/raw/upload/cv_1.pdf"


@pytest_asyncio.fixture(autouse=True)
async def brand() -> Brand:
    doc = Brand(
        id=_BRAND, name="Binge Consulting", owner_id=str(PydanticObjectId()), domain="binge.test"
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def caller() -> Employee:
    return await make_staff(_BRAND, "caller", UserRole.telecaller)


@pytest_asyncio.fixture
async def rec() -> Employee:
    return await make_staff(_BRAND, "rec", UserRole.employee)


@pytest.fixture
def uploads(monkeypatch) -> list[str]:
    """Stand in for Cloudinary; returns the files 'stored', in order."""
    stored: list[str] = []

    async def fake_process(file_bytes, filename, automation, **_):
        stored.append(filename)
        return (
            "Bartender, 3 years",
            ParsedResume(skills=["Bartending"]),
            _UPLOADED,
            f"cv_{len(stored)}",
        )

    monkeypatch.setattr(public_controller, "process_resume_bytes", fake_process)
    return stored


async def _lead(
    *,
    status: IntakeLeadStatus,
    telecaller: Employee | None = None,
    recruiter: Employee | None = None,
) -> IntakeLead:
    candidate = Candidate(
        brand_id=_BRAND, full_name="Asha Rao", phone="9876543210", status=CandidateStatus.pending
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=status,
        telecaller_id=telecaller.id if telecaller else None,
        recruiter_id=recruiter.id if recruiter else None,
        telecaller_decision=(
            IntakeDecision.accept if status == IntakeLeadStatus.pending_recruiter else None
        ),
    )
    await lead.insert()
    return lead


async def _make_link(http, lead: IntakeLead, who: str):
    return await http.post(
        f"/api/v1/intake/leads/{lead.id}/cv-link", headers=await auth_headers(who)
    )


async def _token(http, lead: IntakeLead, who: str) -> str:
    res = await _make_link(http, lead, who)
    assert res.status_code == 200, res.text
    return res.json()["token"]


async def _upload(http, token: str, filename: str = "asha.pdf"):
    return await http.post(
        f"/api/v1/public/cv-upload/{token}",
        files={"resume": (filename, b"%PDF-1.4 cv", "application/pdf")},
    )


# ── Who may make one ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_telecaller_makes_a_link_for_a_lead_in_their_queue(http, caller):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)

    res = await _make_link(http, lead, "caller")

    assert res.status_code == 200
    body = res.json()
    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(days=6, hours=23) < expires - datetime.now(UTC) <= timedelta(days=7)
    # Only the hash is kept: a database read must not hand out working links.
    stored = await IntakeLead.get(lead.id)
    assert stored.cv_upload_token_hash == hashlib.sha256(body["token"].encode()).hexdigest()
    assert stored.cv_upload_requested_by_id == caller.id


@pytest.mark.asyncio
async def test_a_recruiter_makes_a_link_for_a_lead_in_their_review_tab(http, rec):
    lead = await _lead(status=IntakeLeadStatus.pending_recruiter, recruiter=rec)

    assert (await _make_link(http, lead, "rec")).status_code == 200


@pytest.mark.asyncio
async def test_a_maintainer_makes_a_link_for_any_open_lead(http, caller):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(status=IntakeLeadStatus.pending_review, telecaller=caller)

    assert (await _make_link(http, lead, "boss")).status_code == 200


@pytest.mark.asyncio
async def test_nobody_else_can_make_one(http, caller, rec):
    await make_staff(_BRAND, "caller2", UserRole.telecaller)
    await make_staff(_BRAND, "rec2", UserRole.employee)
    screening = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    reviewing = await _lead(
        status=IntakeLeadStatus.pending_recruiter, telecaller=caller, recruiter=rec
    )

    refused = [
        (await _make_link(http, screening, "caller2")).status_code,  # another telecaller's
        (await _make_link(http, screening, "rec")).status_code,  # still being screened
        (await _make_link(http, reviewing, "rec2")).status_code,  # another recruiter's
        (await _make_link(http, reviewing, "caller")).status_code,  # moved on from them
    ]

    assert refused == [403, 403, 403, 403]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.client, UserRole.referee])
async def test_outsiders_are_refused_at_the_door(http, caller, role):
    await make_staff(_BRAND, "outsider", role)
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)

    assert (await _make_link(http, lead, "outsider")).status_code == 403


@pytest.mark.asyncio
async def test_a_closed_lead_has_no_cv_to_ask_for(http):
    await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(status=IntakeLeadStatus.rejected)

    assert (await _make_link(http, lead, "boss")).status_code == 409


# ── The candidate's page ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_page_greets_them_by_first_name_and_says_nothing_else(http, caller):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    token = await _token(http, lead, "caller")

    res = await http.get(f"/api/v1/public/cv-upload/{token}")

    assert res.status_code == 200
    body = res.json()
    # The link may be forwarded: no phone, no email, no surname.
    assert set(body) == {"first_name", "brand_name", "brand_logo_url", "expires_at", "uploaded"}
    assert (body["first_name"], body["brand_name"], body["uploaded"]) == (
        "Asha",
        "Binge Consulting",
        False,
    )


@pytest.mark.asyncio
async def test_a_new_link_cancels_the_old_one(http, caller):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    old = await _token(http, lead, "caller")
    new = await _token(http, lead, "caller")

    assert (await http.get(f"/api/v1/public/cv-upload/{old}")).status_code == 404
    assert (await http.get(f"/api/v1/public/cv-upload/{new}")).status_code == 200


@pytest.mark.asyncio
async def test_a_link_stops_working_after_seven_days(http, caller):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    token = await _token(http, lead, "caller")
    await lead.set({"cv_upload_expires_at": datetime.now(UTC) - timedelta(minutes=1)})

    assert (await http.get(f"/api/v1/public/cv-upload/{token}")).status_code == 404


@pytest.mark.asyncio
async def test_a_link_stops_working_once_the_lead_is_rejected(http, caller, uploads):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    token = await _token(http, lead, "caller")
    await lead.set({"status": IntakeLeadStatus.rejected})

    assert (await _upload(http, token)).status_code == 404
    assert uploads == []


@pytest.mark.asyncio
async def test_an_unknown_token_is_refused(http):
    assert (await http.get("/api/v1/public/cv-upload/not-a-real-token")).status_code == 404


# ── Uploading ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_upload_lands_on_the_candidate_and_tells_the_telecaller(http, caller, uploads):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    token = await _token(http, lead, "caller")

    res = await _upload(http, token)

    assert res.status_code == 200
    assert res.json()["uploaded"] is True
    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.resume_url == _UPLOADED
    assert candidate.resume_public_id == "cv_1"
    assert candidate.skills == ["Bartending"]
    assert (await IntakeLead.get(lead.id)).cv_uploaded_at is not None
    [note] = await Notification.find({"kind": NotificationKind.cv_uploaded}).to_list()
    assert (note.employee_id, note.intake_lead_id) == (caller.id, lead.id)
    assert note.message == "Asha Rao uploaded their CV."
    event = await CandidateEvent.find_one({"candidate_id": candidate.id})
    assert event.event_type == CandidateEventType.cv_uploaded


@pytest.mark.asyncio
async def test_an_upload_shows_on_the_review_tab_card_and_tells_the_recruiter(http, rec, uploads):
    lead = await _lead(status=IntakeLeadStatus.pending_recruiter, recruiter=rec)
    token = await _token(http, lead, "rec")

    await _upload(http, token)
    review = await http.get("/api/v1/intake/leads/review", headers=await auth_headers("rec"))

    [row] = review.json()
    assert row["resume_url"] == _UPLOADED
    assert row["cv_uploaded_at"] is not None
    note = await Notification.find_one({"kind": NotificationKind.cv_uploaded})
    assert note.employee_id == rec.id


@pytest.mark.asyncio
async def test_uploading_again_replaces_the_first_file(http, caller, uploads):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    token = await _token(http, lead, "caller")

    await _upload(http, token, "wrong.pdf")
    second = await _upload(http, token, "right.pdf")

    assert second.status_code == 200
    assert uploads == ["wrong.pdf", "right.pdf"]
    assert (await Candidate.get(lead.candidate_id)).resume_public_id == "cv_2"
    messages = [n.message for n in await Notification.find({}).sort("created_at").to_list()]
    assert messages == ["Asha Rao uploaded their CV.", "Asha Rao uploaded a new CV."]


@pytest.mark.asyncio
async def test_with_nobody_holding_the_lead_whoever_asked_is_told(http, caller, uploads):
    # Accepted by the telecaller, waiting for an admin to pick a team.
    boss = await make_staff(_BRAND, "boss", UserRole.maintainer)
    lead = await _lead(status=IntakeLeadStatus.pending_review, telecaller=caller)
    token = await _token(http, lead, "boss")

    await _upload(http, token)

    note = await Notification.find_one({"kind": NotificationKind.cv_uploaded})
    assert note.employee_id == boss.id


@pytest.mark.asyncio
async def test_only_pdf_and_docx_are_accepted(http, caller, uploads):
    lead = await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=caller)
    token = await _token(http, lead, "caller")

    res = await _upload(http, token, "cv.exe")

    assert res.status_code == 400
    assert uploads == []
    assert (await Candidate.get(lead.candidate_id)).resume_url is None
