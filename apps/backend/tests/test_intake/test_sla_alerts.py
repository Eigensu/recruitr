"""Nobody called them for a day: who finds out, and how often.

The two jobs have different promises to keep, and the tests are split the same
way. The hourly sweep must fire exactly once per lead — a lead stuck for a week
is one notification, not 168. The daily digest must describe the present, and
must stay silent when there is nothing to say.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.dashboard.services.email_service import EmailService
from app.modules.recruitment.enums import IntakeLeadStatus, NotificationKind
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, Notification
from app.modules.recruitment.service.intake_sla import build_digests, send_digests, sweep_breaches

_BRAND = PydanticObjectId()


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _staff(name: str, role: UserRole) -> Employee:
    email = f"{name}@binge.consulting"
    await User(email=email, role=role).insert()
    employee = Employee(brand_id=_BRAND, name=name.title(), email=email, role=role.value)
    await employee.insert()
    return employee


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest_asyncio.fixture
async def chief() -> Employee:
    return await _staff("chief", UserRole.admin)


async def _lead(
    *,
    status: IntakeLeadStatus = IntakeLeadStatus.pending_telecaller,
    telecaller: Employee | None = None,
    recruiter: Employee | None = None,
    hours_ago: float | None = None,
    brand_id: PydanticObjectId | None = None,
    name: str = "Asha Rao",
) -> IntakeLead:
    brand = brand_id or _BRAND
    assigned = datetime.now(UTC) - timedelta(hours=hours_ago) if hours_ago is not None else None
    candidate = Candidate(brand_id=brand, full_name=name, phone="9876543210")
    await candidate.insert()
    lead = IntakeLead(
        brand_id=brand,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=status,
        telecaller_id=telecaller.id if telecaller else None,
        telecaller_assigned_at=assigned if status == IntakeLeadStatus.pending_telecaller else None,
        recruiter_id=recruiter.id if recruiter else None,
        recruiter_assigned_at=assigned if status == IntakeLeadStatus.pending_recruiter else None,
    )
    await lead.insert()
    return lead


# ── The sweep ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_lead_past_the_limit_raises_an_alert_and_is_stamped(chief):
    caller = await _staff("caller", UserRole.telecaller)
    lead = await _lead(telecaller=caller, hours_ago=25)

    result = await sweep_breaches()

    assert result.breached == 1
    note = await Notification.find_one({"kind": NotificationKind.telecaller_sla_breach})
    assert note.employee_id == chief.id
    assert note.intake_lead_id == lead.id
    assert "Asha Rao" in note.message
    assert "Caller" in note.message
    assert (await IntakeLead.get(lead.id)).telecaller_sla_breached_at is not None


@pytest.mark.asyncio
async def test_a_lead_inside_the_limit_is_left_alone(chief):
    caller = await _staff("caller", UserRole.telecaller)
    lead = await _lead(telecaller=caller, hours_ago=5)

    result = await sweep_breaches()

    assert result.breached == 0
    assert await Notification.find({}).count() == 0
    assert (await IntakeLead.get(lead.id)).telecaller_sla_breached_at is None


@pytest.mark.asyncio
async def test_a_lead_stuck_for_a_week_still_raises_one_alert(chief):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=24 * 7)

    for _ in range(3):  # three hourly sweeps
        await sweep_breaches()

    # The stamp is the dedupe key, the same guarantee reminders_sent gives the
    # pipeline reminder job.
    assert await Notification.find({}).count() == 1


@pytest.mark.asyncio
async def test_every_admin_and_maintainer_hears_about_it(chief):
    await _staff("boss", UserRole.maintainer)
    await _staff("rec", UserRole.employee)  # cannot reassign, so is not told
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)

    result = await sweep_breaches()

    assert result.notified == 2
    recipients = {note.employee_id for note in await Notification.find({}).to_list()}
    assert len(recipients) == 2


@pytest.mark.asyncio
async def test_a_slow_recruiter_is_reported_too(chief):
    recruiter = await _staff("rec", UserRole.employee)
    await _lead(status=IntakeLeadStatus.pending_recruiter, recruiter=recruiter, hours_ago=30)

    await sweep_breaches()

    note = await Notification.find_one({})
    assert note.kind == NotificationKind.recruiter_sla_breach
    assert "put forward" in note.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [IntakeLeadStatus.rejected, IntakeLeadStatus.actioned, IntakeLeadStatus.duplicate],
)
async def test_a_finished_lead_is_never_late(chief, status):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(status=status, telecaller=caller, hours_ago=200)

    assert (await sweep_breaches()).breached == 0


@pytest.mark.asyncio
async def test_a_lead_nobody_was_given_has_no_clock_running(chief):
    await _lead(status=IntakeLeadStatus.unassigned, hours_ago=200)

    # No clock, because nobody was ever asked to do anything. The digest counts
    # these separately so they cannot pile up unseen.
    assert (await sweep_breaches()).breached == 0


@pytest.mark.asyncio
async def test_reassigning_lets_the_alert_fire_again_for_the_new_owner(chief):
    from app.modules.recruitment.service.intake_service import reassign_lead

    first = await _staff("first", UserRole.telecaller)
    second = await _staff("second", UserRole.telecaller)
    lead = await _lead(telecaller=first, hours_ago=30)
    await sweep_breaches()

    await reassign_lead(await IntakeLead.get(lead.id), assignee=second)
    moved = await IntakeLead.get(lead.id)
    assert moved.telecaller_sla_breached_at is None  # the new owner starts clean
    await moved.set({"telecaller_assigned_at": datetime.now(UTC) - timedelta(hours=30)})

    await sweep_breaches()

    assert await Notification.find({}).count() == 2


@pytest.mark.asyncio
async def test_a_brand_with_nobody_to_tell_does_not_crash_or_retry_forever():
    caller = await _staff("caller", UserRole.telecaller)
    lead = await _lead(telecaller=caller, hours_ago=30)

    result = await sweep_breaches()

    assert result.breached == 1
    assert result.notified == 0
    # Stamped anyway: the breach happened, whether or not anyone was listening.
    # The daily digest reports the current state and so catches this up.
    assert (await IntakeLead.get(lead.id)).telecaller_sla_breached_at is not None


@pytest.mark.asyncio
async def test_the_waiting_time_survives_the_trip_through_mongo(chief):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=31)

    await sweep_breaches()

    # Timestamps come back from Mongo without a timezone; subtracting one from
    # an aware "now" raises TypeError unless it goes through as_utc first.
    assert "31h" in (await Notification.find_one({})).message


# ── The inbox ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_alert_lands_in_the_admins_inbox(http, chief):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)
    await sweep_breaches()

    res = await http.get("/api/v1/notifications", headers=await _headers("chief"))

    assert res.status_code == 200
    assert any(row["kind"] == NotificationKind.telecaller_sla_breach for row in res.json())


@pytest.mark.asyncio
async def test_a_telecaller_does_not_see_the_complaint_about_themselves(http, chief):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)
    await sweep_breaches()

    res = await http.get("/api/v1/notifications", headers=await _headers("caller"))

    assert res.json() == []


# ── The digest ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_digest_groups_the_late_leads_by_whoever_owes_the_call(chief):
    busy = await _staff("busy", UserRole.telecaller)
    quiet = await _staff("quiet", UserRole.telecaller)
    await _lead(telecaller=busy, hours_ago=30, name="Asha Rao")
    await _lead(telecaller=busy, hours_ago=50, name="Ravi Menon")
    await _lead(telecaller=quiet, hours_ago=26, name="Priya Nair")

    digest = (await build_digests())[0]

    assert digest.total == 3
    assert [group["name"] for group in digest.groups] == ["Busy", "Quiet"]
    # Longest wait first inside a group — that is the one to chase.
    assert [lead["name"] for lead in digest.groups[0]["leads"]] == ["Ravi Menon", "Asha Rao"]
    assert digest.groups[0]["leads"][0]["hours"] == 50


@pytest.mark.asyncio
async def test_the_digest_counts_leads_in_nobody_queue_separately(chief):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)
    await _lead(status=IntakeLeadStatus.unassigned)
    await _lead(status=IntakeLeadStatus.unassigned)

    digest = (await build_digests())[0]

    # Not overdue — no clock ever started — but nobody would otherwise see them.
    assert digest.total == 1
    assert digest.unassigned == 2


@pytest.mark.asyncio
async def test_the_digest_reports_what_is_overdue_now_not_what_just_broke(chief):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)
    await sweep_breaches()  # already alerted on, and stamped

    digest = (await build_digests())[0]

    # The sweep fires once; the digest is a standing statement of what is late,
    # which is what makes it the safety net for anything the sweep missed.
    assert digest.total == 1


@pytest.mark.asyncio
async def test_nothing_overdue_means_no_email(chief, monkeypatch):
    sent = []
    monkeypatch.setattr(EmailService, "_send_email", lambda **kwargs: sent.append(kwargs))
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=2)

    assert await send_digests() == 0
    # A daily "all clear" teaches people to filter the alert away.
    assert sent == []


@pytest.mark.asyncio
async def test_each_admin_gets_the_mail(chief, monkeypatch):
    sent = []
    monkeypatch.setattr(EmailService, "_send_email", lambda **kwargs: sent.append(kwargs))
    await _staff("boss", UserRole.maintainer)
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)

    assert await send_digests() == 2
    assert {mail["to"] for mail in sent} == {
        "chief@binge.consulting",
        "boss@binge.consulting",
    }


@pytest.mark.asyncio
async def test_another_brands_overdue_leads_go_to_their_own_admins(chief):
    other_brand = PydanticObjectId()
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, hours_ago=30)
    await _lead(brand_id=other_brand, hours_ago=30)

    digests = await build_digests()

    # The other brand has no admins, so it produces no digest rather than
    # leaking its leads into this one's.
    assert [digest.brand_id for digest in digests] == [_BRAND]
    assert digests[0].total == 1


# ── The email itself ───────────────────────────────────────────────────────────


def test_the_mail_says_what_is_late_and_where_to_go(monkeypatch):
    sent = {}
    monkeypatch.setattr(EmailService, "_send_email", lambda **kwargs: sent.update(kwargs))

    EmailService.send_intake_sla_digest(
        email="chief@binge.consulting",
        total=2,
        unassigned=3,
        groups=[
            {"name": "Busy", "leg": "telecaller", "leads": [{"name": "Asha Rao", "hours": 31}]}
        ],
        portal_url="https://app.example.com/leads?overdue=true",
    )

    assert "2 inbound leads are overdue" in sent["subject"]
    assert "Busy (telecaller) — 1 overdue" in sent["body"]
    assert "Asha Rao: waiting 31h" in sent["body"]
    assert "3 leads are in nobody's queue" in sent["body"]
    assert "overdue=true" in sent["body"]


def test_a_candidate_named_after_a_script_tag_cannot_inject_one(monkeypatch):
    sent = {}
    monkeypatch.setattr(EmailService, "_send_email", lambda **kwargs: sent.update(kwargs))

    EmailService.send_intake_sla_digest(
        email="chief@binge.consulting",
        total=1,
        unassigned=0,
        groups=[
            {
                "name": "Busy",
                "leg": "telecaller",
                "leads": [{"name": "<script>alert(1)</script>", "hours": 30}],
            }
        ],
        portal_url="https://app.example.com/leads",
    )

    # The body is sent as HTML, and a name comes off an ad form a stranger filled in.
    assert "<script>" not in sent["body"]
    assert "&lt;script&gt;" in sent["body"]


def test_a_single_overdue_lead_reads_as_one(monkeypatch):
    sent = {}
    monkeypatch.setattr(EmailService, "_send_email", lambda **kwargs: sent.update(kwargs))

    EmailService.send_intake_sla_digest(
        email="chief@binge.consulting", total=1, unassigned=0, groups=[], portal_url="https://x/"
    )

    assert sent["subject"] == "1 inbound lead is overdue"
