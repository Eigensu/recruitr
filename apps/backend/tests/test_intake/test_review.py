"""The review step: a screened lead waits for an admin to pick a team, and the
team's own round-robin picks the recruiter.

Also covers the two ways into that flow added with it — the public form opening
a lead for every applicant, and the External tab refusing to decide a candidate
the flow still owns — and the telecaller-only routes that feed the accept form.

Signed in with real tokens and no dependency overrides, like test_decisions.py,
so the role guards are exercised rather than assumed.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.brands.models import Brand
from app.modules.recruitment.enums import (
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeSource,
)
from app.modules.recruitment.models import (
    Candidate,
    Client,
    Employee,
    IntakeLead,
    Mapping,
    Position,
    Team,
)
from app.modules.recruitment.service.intake_service import close_lead_for_mapping

_BRAND = PydanticObjectId()


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _staff(name: str, role: UserRole, *, team: Team | None = None) -> Employee:
    email = f"{name}@binge.consulting"
    await User(email=email, role=role).insert()
    employee = Employee(
        brand_id=_BRAND,
        name=name,
        email=email,
        role=role.value,
        team_id=team.id if team else None,
    )
    await employee.insert()
    return employee


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _team(name: str) -> Team:
    team = Team(brand_id=_BRAND, name=name)
    await team.insert()
    return team


async def _reviewed_lead(name: str = "Asha Rao") -> IntakeLead:
    """A lead a telecaller has already accepted, waiting for a team."""
    candidate = Candidate(
        brand_id=_BRAND, full_name=name, phone="9876543210", status=CandidateStatus.pending
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=IntakeLeadStatus.pending_review,
        telecaller_decision=IntakeDecision.accept,
        telecaller_actioned_at=datetime.now(UTC) - timedelta(hours=1),
    )
    await lead.insert()
    return lead


@pytest_asyncio.fixture
async def boss() -> Employee:
    return await _staff("boss", UserRole.maintainer)


async def _assign(http, leads, team, who="boss"):
    return await http.post(
        "/api/v1/intake/leads/assign-team",
        json={"lead_ids": [str(lead.id) for lead in leads], "team_id": str(team.id)},
        headers=await _headers(who),
    )


# ── Assigning to a team ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_team_shares_its_leads_round_robin(http, boss):
    north = await _team("North")
    south = await _team("South")
    first = await _staff("first", UserRole.employee, team=north)
    second = await _staff("second", UserRole.employee, team=north)
    outsider = await _staff("outsider", UserRole.employee, team=south)
    leads = [await _reviewed_lead(f"Lead {n}") for n in range(4)]

    res = await _assign(http, leads, north)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["skipped"] == []
    owners = [row["recruiter_id"] for row in body["assigned"]]
    # Evenly across the team, and never to someone on another team.
    assert sorted(owners) == sorted([str(first.id), str(second.id)] * 2)
    assert str(outsider.id) not in owners
    assert {row["team_name"] for row in body["assigned"]} == {"North"}
    assert {row["status"] for row in body["assigned"]} == {IntakeLeadStatus.pending_recruiter}


@pytest.mark.asyncio
async def test_assignment_approves_the_candidate_and_starts_the_recruiter_clock(http, boss):
    team = await _team("North")
    recruiter = await _staff("recruiter", UserRole.employee, team=team)
    lead = await _reviewed_lead()

    await _assign(http, [lead], team)

    stored = await IntakeLead.get(lead.id)
    assert stored.team_id == team.id
    assert stored.reviewed_by_id == boss.id
    assert stored.recruiter_id == recruiter.id
    assert stored.recruiter_assigned_at is not None
    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.status == CandidateStatus.approved
    assert candidate.assigned_recruiter_id == recruiter.id


@pytest.mark.asyncio
async def test_managers_on_a_team_are_not_handed_leads(http, boss):
    team = await _team("North")
    await _staff("lead", UserRole.maintainer, team=team)
    recruiter = await _staff("recruiter", UserRole.employee, team=team)
    leads = [await _reviewed_lead(f"Lead {n}") for n in range(3)]

    body = (await _assign(http, leads, team)).json()

    assert {row["recruiter_id"] for row in body["assigned"]} == {str(recruiter.id)}


@pytest.mark.asyncio
async def test_a_team_with_no_recruiters_is_refused(http, boss):
    empty = await _team("Empty")
    lead = await _reviewed_lead()

    res = await _assign(http, [lead], empty)

    assert res.status_code == 409
    assert "no active recruiters" in res.json()["detail"]
    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.pending_review


@pytest.mark.asyncio
async def test_leads_no_longer_awaiting_review_are_skipped(http, boss):
    team = await _team("North")
    await _staff("recruiter", UserRole.employee, team=team)
    waiting = await _reviewed_lead("Waiting")
    taken = await _reviewed_lead("Taken")
    await taken.set({"status": IntakeLeadStatus.pending_recruiter})

    body = (await _assign(http, [waiting, taken], team)).json()

    assert [row["id"] for row in body["assigned"]] == [str(waiting.id)]
    assert body["skipped"] == [str(taken.id)]


@pytest.mark.asyncio
async def test_a_recruiter_cannot_assign_teams(http):
    team = await _team("North")
    await _staff("recruiter", UserRole.employee, team=team)
    lead = await _reviewed_lead()

    res = await _assign(http, [lead], team, who="recruiter")

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_a_team_from_another_brand_is_not_found(http, boss):
    other = Team(brand_id=PydanticObjectId(), name="Elsewhere")
    await other.insert()
    lead = await _reviewed_lead()

    res = await _assign(http, [lead], other)

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_the_first_mapping_still_closes_a_team_assigned_lead(http, boss):
    team = await _team("North")
    await _staff("recruiter", UserRole.employee, team=team)
    lead = await _reviewed_lead()
    await _assign(http, [lead], team)

    mapping = Mapping(
        brand_id=_BRAND,
        candidate_id=lead.candidate_id,
        position_id=PydanticObjectId(),
        employee_id=PydanticObjectId(),
    )
    await close_lead_for_mapping(mapping)

    assert (await IntakeLead.get(lead.id)).status == IntakeLeadStatus.actioned


@pytest.mark.asyncio
async def test_team_options_show_size_and_load(http, boss):
    team = await _team("North")
    await _team("Empty")
    await _staff("recruiter", UserRole.employee, team=team)
    await _assign(http, [await _reviewed_lead()], team)

    res = await http.get("/api/v1/intake/teams", headers=await _headers("boss"))

    rows = {row["name"]: row for row in res.json()}
    assert rows["North"]["recruiters"] == 1
    assert rows["North"]["open_leads"] == 1
    assert rows["Empty"]["recruiters"] == 0


@pytest.mark.asyncio
async def test_the_review_list_is_the_lead_list_filtered(http, boss):
    waiting = await _reviewed_lead()

    res = await http.get(
        "/api/v1/intake/leads?status=pending_review", headers=await _headers("boss")
    )

    assert [row["id"] for row in res.json()["items"]] == [str(waiting.id)]


# ── The public form ────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def brand() -> Brand:
    doc = Brand(id=_BRAND, owner_id="owner", name="Binge Talent", domain="binge.test")
    await doc.insert()
    return doc


def _application(email: str = "rhea@applicant.test") -> dict[str, str]:
    return {
        "brand_id": str(_BRAND),
        "full_name": "Rhea Kapoor",
        "email": email,
        "phone": "+91 90000 11111",
        "source_channel": "LinkedIn",
    }


@pytest.mark.asyncio
async def test_an_applicant_is_queued_for_a_telecaller(http, brand):
    caller = await _staff("caller", UserRole.telecaller)

    res = await http.post("/api/v1/public/apply", data=_application())

    assert res.status_code == 201, res.text
    lead = await IntakeLead.find_one({"candidate_id": PydanticObjectId(res.json()["id"])})
    assert lead.source == IntakeSource.public_form
    assert lead.status == IntakeLeadStatus.pending_telecaller
    assert lead.telecaller_id == caller.id
    assert lead.source_channel == "LinkedIn"


@pytest.mark.asyncio
async def test_an_applicant_with_no_telecaller_is_kept_unassigned(http, brand):
    res = await http.post("/api/v1/public/apply", data=_application())

    lead = await IntakeLead.find_one({"candidate_id": PydanticObjectId(res.json()["id"])})
    assert lead.status == IntakeLeadStatus.unassigned


@pytest.mark.asyncio
async def test_the_external_tab_cannot_decide_a_candidate_in_screening(http, brand, boss):
    await _staff("caller", UserRole.telecaller)
    applied = await http.post("/api/v1/public/apply", data=_application())
    cid = applied.json()["id"]

    approve = await http.post(f"/api/v1/candidates/{cid}/approve", headers=await _headers("boss"))
    reject = await http.post(f"/api/v1/candidates/{cid}/reject", headers=await _headers("boss"))

    assert approve.status_code == 409
    assert reject.status_code == 409
    assert (await Candidate.get(PydanticObjectId(cid))).status == CandidateStatus.pending


# ── The accept form's own routes ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_telecaller_can_read_the_candidate_on_their_own_lead(http):
    caller = await _staff("caller", UserRole.telecaller)
    other = await _staff("other", UserRole.telecaller)
    candidate = Candidate(
        brand_id=_BRAND,
        full_name="Asha Rao",
        phone="9876543210",
        city="Pune",
        experience_years=3,
        status=CandidateStatus.pending,
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id="l_1",
        telecaller_id=caller.id,
        telecaller_assigned_at=datetime.now(UTC),
    )
    await lead.insert()

    mine = await http.get(
        f"/api/v1/intake/leads/{lead.id}/candidate", headers=await _headers("caller")
    )
    theirs = await http.get(
        f"/api/v1/intake/leads/{lead.id}/candidate", headers=await _headers("other")
    )

    assert mine.status_code == 200
    assert mine.json()["city"] == "Pune"
    assert mine.json()["experience_years"] == 3
    assert mine.json()["has_resume"] is False
    assert theirs.status_code == 403
    assert other.id != caller.id


@pytest.mark.asyncio
async def test_a_telecaller_can_load_the_role_catalog(http):
    await _staff("caller", UserRole.telecaller)

    res = await http.get("/api/v1/intake/role-catalog", headers=await _headers("caller"))

    assert res.status_code == 200
    assert "Steward" in res.json()["Service"]


# ── Nobody skips the flow ──────────────────────────────────────────────────────


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


@pytest.mark.asyncio
async def test_candidates_still_in_intake_are_not_suggested_or_mappable(http):
    """Found in the browser: a lead the telecaller had rejected was offered in
    a position's top matches and could be mapped, and so could one still being
    screened — either way skipping the telecaller and the review."""
    await _staff("recruiter", UserRole.employee)
    position = await _position()
    screening = await _reviewed_lead("Still Screening")
    rejected = Candidate(
        brand_id=_BRAND, full_name="Turned Away", phone="1", status=CandidateStatus.rejected
    )
    await rejected.insert()
    approved = Candidate(brand_id=_BRAND, full_name="Ready", phone="2")
    await approved.insert()
    headers = await _headers("recruiter")

    top = await http.get(f"/api/v1/positions/{position.id}/top-candidates", headers=headers)
    names = {row["full_name"] for row in top.json()}
    blocked = [
        await http.post(
            f"/api/v1/positions/{position.id}/map-candidate",
            json={"candidate_id": str(candidate_id)},
            headers=headers,
        )
        for candidate_id in (screening.candidate_id, rejected.id)
    ]
    allowed = await http.post(
        f"/api/v1/positions/{position.id}/map-candidate",
        json={"candidate_id": str(approved.id)},
        headers=headers,
    )

    assert names == {"Ready"}
    assert [res.status_code for res in blocked] == [409, 409]
    assert allowed.status_code == 200, allowed.text


# ── Review fixes ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_applicant_nobody_can_screen_can_be_decided_from_the_external_tab(
    http, brand, boss
):
    # No telecaller exists, so the lead can never be worked on the Leads page.
    applied = await http.post("/api/v1/public/apply", data=_application())
    cid = applied.json()["id"]

    res = await http.post(f"/api/v1/candidates/{cid}/reject", headers=await _headers("boss"))

    assert res.status_code == 200, res.text
    assert (await Candidate.get(PydanticObjectId(cid))).status == CandidateStatus.rejected


@pytest.mark.asyncio
async def test_a_patch_cannot_change_a_candidates_status(http, boss):
    lead = await _reviewed_lead()

    res = await http.patch(
        f"/api/v1/candidates/{lead.candidate_id}",
        json={"status": "APPROVED", "city": "Pune"},
        headers=await _headers("boss"),
    )

    assert res.status_code == 200, res.text
    stored = await Candidate.get(lead.candidate_id)
    assert stored.status == CandidateStatus.pending
    assert stored.city == "Pune"


@pytest.mark.asyncio
async def test_a_failed_candidate_write_hands_the_lead_back_to_review(http, boss, monkeypatch):
    team = await _team("North")
    await _staff("recruiter", UserRole.employee, team=team)
    lead = await _reviewed_lead()

    async def broken(self, *args, **kwargs):
        raise RuntimeError("write failed")

    with monkeypatch.context() as patch:
        patch.setattr(Candidate, "set", broken)
        with pytest.raises(RuntimeError):
            await _assign(http, [lead], team)

    stored = await IntakeLead.get(lead.id)
    assert stored.status == IntakeLeadStatus.pending_review
    assert stored.recruiter_id is None
    assert stored.team_id is None
    # ...so the reviewer can simply try again.
    retry = await _assign(http, [lead], team)
    assert retry.status_code == 200
    assert len(retry.json()["assigned"]) == 1


@pytest.mark.asyncio
async def test_a_telecaller_cannot_read_the_candidate_after_deciding(http):
    caller = await _staff("caller", UserRole.telecaller)
    candidate = Candidate(
        brand_id=_BRAND, full_name="Asha Rao", phone="9876543210", status=CandidateStatus.pending
    )
    await candidate.insert()
    lead = IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id="l_done",
        telecaller_id=caller.id,
        status=IntakeLeadStatus.pending_review,
        telecaller_decision=IntakeDecision.accept,
    )
    await lead.insert()

    res = await http.get(
        f"/api/v1/intake/leads/{lead.id}/candidate", headers=await _headers("caller")
    )

    assert res.status_code == 409
