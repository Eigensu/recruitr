"""The admin's view: the funnel, both SLA clocks, and where the ad spend went.

Driven over HTTP with real tokens, like the decision tests, so the role guard on
every one of these routes is exercised rather than asserted about. The numbers
are built from leads with hand-set timestamps: the point of this file is that a
reported average, median and "overdue" mean exactly what an admin will read them
to mean.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.recruitment.enums import IntakeDecision, IntakeLeadStatus, IntakeRejectReason
from app.modules.recruitment.models import (
    Candidate,
    Employee,
    IntakeAttribution,
    IntakeLead,
)
from app.modules.recruitment.service import intake_analytics

_BRAND = PydanticObjectId()
_HOUR = 3600


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
async def boss() -> Employee:
    return await _staff("boss", UserRole.maintainer)


@pytest_asyncio.fixture
async def admin() -> Employee:
    return await _staff("chief", UserRole.admin)


async def _lead(
    *,
    brand_id: PydanticObjectId | None = None,
    status: IntakeLeadStatus = IntakeLeadStatus.pending_telecaller,
    telecaller: Employee | None = None,
    recruiter: Employee | None = None,
    telecaller_hours_ago: float | None = None,
    recruiter_hours_ago: float | None = None,
    telecaller_seconds: int | None = None,
    recruiter_seconds: int | None = None,
    decision: IntakeDecision | None = None,
    reject_reason: IntakeRejectReason | None = None,
    campaign: str | None = None,
    ad: str | None = None,
    channel: str = "Instagram",
    ingested_hours_ago: float = 1,
    name: str = "Asha Rao",
) -> IntakeLead:
    brand = brand_id or _BRAND
    now = datetime.now(UTC)
    candidate = Candidate(brand_id=brand, full_name=name, phone="9876543210")
    await candidate.insert()
    lead = IntakeLead(
        brand_id=brand,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=status,
        source_channel=channel,
        attribution=IntakeAttribution(campaign_name=campaign, ad_name=ad),
        ingested_at=now - timedelta(hours=ingested_hours_ago),
        telecaller_id=telecaller.id if telecaller else None,
        telecaller_assigned_at=(
            now - timedelta(hours=telecaller_hours_ago)
            if telecaller_hours_ago is not None
            else None
        ),
        telecaller_actioned_at=now if decision else None,
        telecaller_decision=decision,
        telecaller_reject_reason=reject_reason,
        telecaller_response_seconds=telecaller_seconds,
        recruiter_id=recruiter.id if recruiter else None,
        recruiter_assigned_at=(
            now - timedelta(hours=recruiter_hours_ago) if recruiter_hours_ago is not None else None
        ),
        recruiter_actioned_at=now if recruiter_seconds is not None else None,
        recruiter_response_seconds=recruiter_seconds,
    )
    await lead.insert()
    return lead


# ── Percentiles ────────────────────────────────────────────────────────────────


def test_the_median_is_the_middle_not_the_mean():
    # One lead left over a weekend is exactly the case median exists to survive.
    assert intake_analytics._percentile([3600, 7200, 108000], 0.5) == 7200


def test_an_even_sample_interpolates():
    assert intake_analytics._percentile([0, 100], 0.5) == 50


def test_an_empty_sample_has_no_percentile():
    # None, not 0: nobody has actioned anything, which is not the same as
    # everybody having actioned instantly.
    assert intake_analytics._percentile([], 0.5) is None


# ── Funnel ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_funnel_counts_every_lead_exactly_once(http, boss):
    await _lead(status=IntakeLeadStatus.pending_telecaller, telecaller=boss)
    await _lead(status=IntakeLeadStatus.rejected, telecaller=boss)
    await _lead(status=IntakeLeadStatus.actioned, telecaller=boss)
    await _lead(status=IntakeLeadStatus.duplicate)
    await _lead(status=IntakeLeadStatus.unassigned)

    res = await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))

    funnel = res.json()["funnel"]
    assert funnel["ingested"] == 5
    assert funnel["pending_telecaller"] == 1
    assert funnel["rejected"] == 1
    assert funnel["actioned"] == 1
    assert funnel["duplicate"] == 1
    assert funnel["unassigned"] == 1
    # The parts add up, which is the whole reason to report a funnel.
    assert sum(funnel[key] for key in funnel if key != "ingested") == funnel["ingested"]


@pytest.mark.asyncio
async def test_another_brands_leads_are_not_counted(http, boss):
    await _lead(telecaller=boss)
    await _lead(brand_id=PydanticObjectId())

    res = await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))

    assert res.json()["funnel"]["ingested"] == 1


# ── Telecaller leg ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_average_median_and_p90_describe_the_same_sample(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    for seconds in (1 * _HOUR, 2 * _HOUR, 30 * _HOUR):
        await _lead(
            status=IntakeLeadStatus.rejected,
            telecaller=caller,
            telecaller_hours_ago=48,
            telecaller_seconds=seconds,
            decision=IntakeDecision.reject,
        )

    res = await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))

    leg = res.json()["telecaller"]
    assert leg["actioned"] == 3
    assert leg["avg_hours"] == 11.0  # dragged up by the one that sat for 30 hours
    assert leg["median_hours"] == 2.0  # ...which the median ignores
    assert leg["p90_hours"] == pytest.approx(24.4, abs=0.1)
    # Two of the three were inside the 24-hour SLA.
    assert leg["within_sla"] == 2
    assert leg["sla_compliance"] == pytest.approx(0.6667, abs=0.001)
    assert leg["sla_hours"] == 24


@pytest.mark.asyncio
async def test_a_lead_sitting_past_a_day_is_counted_overdue(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, telecaller_hours_ago=30)
    await _lead(telecaller=caller, telecaller_hours_ago=2)

    res = await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))

    leg = res.json()["telecaller"]
    assert leg["pending"] == 2
    assert leg["overdue"] == 1
    # The oldest waiting one, which is the one to chase.
    assert leg["oldest_pending_hours"] == pytest.approx(30, abs=0.1)


@pytest.mark.asyncio
async def test_an_actioned_lead_is_never_overdue_however_long_it_took(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(
        status=IntakeLeadStatus.rejected,
        telecaller=caller,
        telecaller_hours_ago=200,
        telecaller_seconds=200 * _HOUR,
        decision=IntakeDecision.reject,
    )

    leg = (
        await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))
    ).json()["telecaller"]
    assert leg["overdue"] == 0
    assert leg["oldest_pending_hours"] is None
    assert leg["within_sla"] == 0


@pytest.mark.asyncio
async def test_accept_rate_is_of_decisions_made_not_of_leads_held(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    for _ in range(2):
        await _lead(
            status=IntakeLeadStatus.pending_recruiter,
            telecaller=caller,
            telecaller_hours_ago=2,
            telecaller_seconds=_HOUR,
            decision=IntakeDecision.accept,
        )
    await _lead(
        status=IntakeLeadStatus.rejected,
        telecaller=caller,
        telecaller_hours_ago=2,
        telecaller_seconds=_HOUR,
        decision=IntakeDecision.reject,
    )
    # Still in the queue — no verdict yet, so it must not drag the rate down.
    await _lead(telecaller=caller, telecaller_hours_ago=1)

    leg = (
        await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))
    ).json()["telecaller"]
    assert leg["accepted"] == 2
    assert leg["rejected"] == 1
    assert leg["accept_rate"] == pytest.approx(0.6667, abs=0.001)


@pytest.mark.asyncio
async def test_a_team_with_no_decisions_has_no_rate_rather_than_zero(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    await _lead(telecaller=caller, telecaller_hours_ago=1)

    leg = (
        await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))
    ).json()["telecaller"]
    # 0% would read as "they reject everyone", which is a different claim.
    assert leg["accept_rate"] is None
    assert leg["sla_compliance"] is None
    assert leg["median_hours"] is None


# ── Recruiter leg ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_recruiter_leg_is_measured_from_its_own_handover(http, boss):
    recruiter = await _staff("rec", UserRole.employee)
    await _lead(
        status=IntakeLeadStatus.actioned,
        recruiter=recruiter,
        recruiter_hours_ago=10,
        recruiter_seconds=4 * _HOUR,
    )
    await _lead(
        status=IntakeLeadStatus.pending_recruiter, recruiter=recruiter, recruiter_hours_ago=30
    )

    leg = (
        await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))
    ).json()["recruiter"]
    assert leg["assigned"] == 2
    assert leg["actioned"] == 1
    assert leg["median_hours"] == 4.0
    assert leg["overdue"] == 1
    # The recruiter leg has no accept/reject decision to report on.
    assert leg["accepted"] is None
    assert leg["accept_rate"] is None


# ── Per-person tables ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_telecaller_table_names_people_and_leads_with_the_busiest(http, boss):
    busy = await _staff("busy", UserRole.telecaller)
    quiet = await _staff("quiet", UserRole.telecaller)
    for _ in range(3):
        await _lead(telecaller=busy, telecaller_hours_ago=2)
    await _lead(telecaller=quiet, telecaller_hours_ago=2)

    rows = (
        await http.get("/api/v1/intake/analytics/telecallers", headers=await _headers("boss"))
    ).json()

    assert [row["name"] for row in rows] == ["Busy", "Quiet"]
    assert rows[0]["assigned"] == 3
    assert rows[0]["email"] == "busy@binge.consulting"
    assert rows[0]["employee_id"] == str(busy.id)


@pytest.mark.asyncio
async def test_leads_held_by_a_deleted_employee_still_appear(http, boss):
    ghost = await _staff("ghost", UserRole.telecaller)
    await _lead(telecaller=ghost, telecaller_hours_ago=40)
    await ghost.delete()

    rows = (
        await http.get("/api/v1/intake/analytics/telecallers", headers=await _headers("boss"))
    ).json()

    # The work does not stop existing because the person left, and an overdue
    # lead nobody owns is precisely the one an admin needs to see.
    assert rows[0]["name"] == "(removed)"
    assert rows[0]["overdue"] == 1


@pytest.mark.asyncio
async def test_team_totals_and_the_per_person_rows_agree(http, boss):
    one = await _staff("one", UserRole.telecaller)
    two = await _staff("two", UserRole.telecaller)
    await _lead(telecaller=one, telecaller_hours_ago=30)
    await _lead(telecaller=two, telecaller_hours_ago=30)
    await _lead(telecaller=two, telecaller_hours_ago=1)
    headers = await _headers("boss")

    totals = (await http.get("/api/v1/intake/analytics/overview", headers=headers)).json()[
        "telecaller"
    ]
    rows = (await http.get("/api/v1/intake/analytics/telecallers", headers=headers)).json()

    assert totals["assigned"] == sum(row["assigned"] for row in rows)
    assert totals["overdue"] == sum(row["overdue"] for row in rows) == 2


# ── Reject reasons ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_reasons_are_ranked_and_the_unspecified_ones_are_named(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    for _ in range(2):
        await _lead(
            status=IntakeLeadStatus.rejected,
            telecaller=caller,
            decision=IntakeDecision.reject,
            reject_reason=IntakeRejectReason.wrong_number,
        )
    await _lead(status=IntakeLeadStatus.rejected, telecaller=caller, decision=IntakeDecision.reject)

    reasons = (
        await http.get("/api/v1/intake/analytics/overview", headers=await _headers("boss"))
    ).json()["reject_reasons"]

    assert reasons[0] == {"reason": "wrong_number", "count": 2}
    assert {"reason": "unspecified", "count": 1} in reasons


# ── Campaigns ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_campaigns_report_what_the_spend_produced(http, boss):
    await _lead(
        campaign="Diwali Hiring",
        status=IntakeLeadStatus.actioned,
        decision=IntakeDecision.accept,
    )
    await _lead(
        campaign="Diwali Hiring",
        status=IntakeLeadStatus.rejected,
        decision=IntakeDecision.reject,
    )
    await _lead(
        campaign="Always On", status=IntakeLeadStatus.rejected, decision=IntakeDecision.reject
    )

    rows = (
        await http.get("/api/v1/intake/analytics/campaigns", headers=await _headers("boss"))
    ).json()["rows"]

    diwali = next(row for row in rows if row["label"] == "Diwali Hiring")
    assert diwali["leads"] == 2
    assert diwali["accept_rate"] == 0.5
    assert diwali["actioned_rate"] == 0.5
    assert next(row for row in rows if row["label"] == "Always On")["accept_rate"] == 0.0


@pytest.mark.asyncio
async def test_leads_with_no_campaign_are_labelled_not_dropped(http, boss):
    await _lead(campaign=None)

    rows = (
        await http.get("/api/v1/intake/analytics/campaigns", headers=await _headers("boss"))
    ).json()["rows"]

    assert rows == [
        {
            "label": "(unattributed)",
            "leads": 1,
            "accepted": 0,
            "rejected": 0,
            "actioned": 0,
            "duplicate": 0,
            "accept_rate": None,
            "actioned_rate": 0.0,
        }
    ]


@pytest.mark.asyncio
async def test_the_same_leads_can_be_grouped_by_ad_or_channel(http, boss):
    await _lead(campaign="Diwali Hiring", ad="Reel A", channel="Instagram")
    await _lead(campaign="Diwali Hiring", ad="Reel B", channel="Facebook")
    headers = await _headers("boss")

    by_ad = (
        await http.get("/api/v1/intake/analytics/campaigns?group_by=ad", headers=headers)
    ).json()
    by_channel = (
        await http.get("/api/v1/intake/analytics/campaigns?group_by=channel", headers=headers)
    ).json()

    assert by_ad["group_by"] == "ad"
    assert {row["label"] for row in by_ad["rows"]} == {"Reel A", "Reel B"}
    assert {row["label"] for row in by_channel["rows"]} == {"Instagram", "Facebook"}


@pytest.mark.asyncio
async def test_an_unknown_grouping_is_refused(http, boss):
    res = await http.get(
        "/api/v1/intake/analytics/campaigns?group_by=whatever", headers=await _headers("boss")
    )

    assert res.status_code == 422


# ── The window ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_window_selects_the_leads_that_arrived_in_it(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    # Arrived last week, actioned today: belongs to last week's intake, and the
    # funnel it entered is the one it has to leave.
    await _lead(
        status=IntakeLeadStatus.rejected,
        telecaller=caller,
        ingested_hours_ago=24 * 8,
        telecaller_seconds=_HOUR,
        decision=IntakeDecision.reject,
    )
    await _lead(telecaller=caller, ingested_hours_ago=2)

    since = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    res = await http.get(
        "/api/v1/intake/analytics/overview",
        params={"start_date": since},  # via params: the "+00:00" offset needs encoding
        headers=await _headers("boss"),
    )

    body = res.json()
    assert body["funnel"]["ingested"] == 1
    assert body["funnel"]["rejected"] == 0
    assert body["telecaller"]["actioned"] == 0


def test_two_windows_do_not_share_a_cache_entry():
    # A cache key that ignored the window would serve last week's funnel as
    # today's, which is the failure nobody would notice.
    brand = PydanticObjectId()
    week = intake_analytics._cache_key("overview", brand, start="2026-09-01", end=None)
    day = intake_analytics._cache_key("overview", brand, start="2026-09-17", end=None)
    assert week != day


def test_two_brands_do_not_share_a_cache_entry():
    args = {"start": None, "end": None}
    assert intake_analytics._cache_key(
        "overview", PydanticObjectId(), **args
    ) != intake_analytics._cache_key("overview", PydanticObjectId(), **args)


# ── Lead list ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_admin_list_names_both_owners_and_flags_the_late_ones(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    recruiter = await _staff("rec", UserRole.employee)
    await _lead(
        status=IntakeLeadStatus.pending_recruiter,
        telecaller=caller,
        recruiter=recruiter,
        telecaller_hours_ago=40,
        recruiter_hours_ago=2,
    )

    row = (await http.get("/api/v1/intake/leads", headers=await _headers("boss"))).json()["items"][
        0
    ]

    assert row["telecaller_name"] == "Caller"
    assert row["recruiter_name"] == "Rec"
    # Waiting on the recruiter for 2 hours. The telecaller's 40 hours are spent
    # and belong to a leg that is closed.
    assert row["overdue"] is False


@pytest.mark.asyncio
async def test_the_overdue_filter_reads_the_leg_the_lead_is_waiting_on(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    recruiter = await _staff("rec", UserRole.employee)
    late_call = await _lead(telecaller=caller, telecaller_hours_ago=40)
    await _lead(telecaller=caller, telecaller_hours_ago=2)
    late_recruit = await _lead(
        status=IntakeLeadStatus.pending_recruiter, recruiter=recruiter, recruiter_hours_ago=40
    )
    # Finished long ago, so not anybody's problem now.
    await _lead(status=IntakeLeadStatus.actioned, recruiter=recruiter, recruiter_hours_ago=100)

    res = await http.get("/api/v1/intake/leads?overdue=true", headers=await _headers("boss"))

    assert {row["id"] for row in res.json()["items"]} == {str(late_call.id), str(late_recruit.id)}
    assert all(row["overdue"] for row in res.json()["items"])


@pytest.mark.asyncio
async def test_the_list_filters_by_status_and_by_person(http, boss):
    mine = await _staff("mine", UserRole.telecaller)
    theirs = await _staff("theirs", UserRole.telecaller)
    kept = await _lead(telecaller=mine, telecaller_hours_ago=1)
    await _lead(telecaller=theirs, telecaller_hours_ago=1)
    await _lead(telecaller=mine, status=IntakeLeadStatus.rejected)
    headers = await _headers("boss")

    res = await http.get(
        f"/api/v1/intake/leads?status=pending_telecaller&telecaller_id={mine.id}", headers=headers
    )

    assert [row["id"] for row in res.json()["items"]] == [str(kept.id)]


@pytest.mark.asyncio
async def test_the_list_paginates_newest_first(http, boss):
    for hours in range(1, 6):
        await _lead(ingested_hours_ago=hours)

    res = await http.get("/api/v1/intake/leads?limit=2&page=2", headers=await _headers("boss"))

    body = res.json()
    assert body["meta"] == {
        "page": 2,
        "limit": 2,
        "total": 5,
        "pages": 3,
        "has_next": True,
        "has_prev": True,
    }
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_one_lead_carries_its_whole_timing_trail(http, boss):
    caller = await _staff("caller", UserRole.telecaller)
    lead = await _lead(
        status=IntakeLeadStatus.actioned,
        telecaller=caller,
        telecaller_hours_ago=5,
        telecaller_seconds=2 * _HOUR,
        recruiter_hours_ago=3,
        recruiter_seconds=_HOUR,
        decision=IntakeDecision.accept,
    )

    row = (await http.get(f"/api/v1/intake/leads/{lead.id}", headers=await _headers("boss"))).json()

    assert row["telecaller_response_seconds"] == 2 * _HOUR
    assert row["recruiter_response_seconds"] == _HOUR
    assert row["telecaller_name"] == "Caller"


@pytest.mark.asyncio
async def test_the_queue_route_is_not_swallowed_by_the_lead_id_route(http, admin):
    """`/leads/mine` and `/leads/{id}` both match "mine"; order decides."""
    res = await http.get("/api/v1/intake/leads/mine", headers=await _headers("chief"))

    assert res.status_code == 200
    assert res.json() == []  # an admin's own queue, empty — not a 404 lead


# ── Who may look ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/intake/analytics/overview",
        "/api/v1/intake/analytics/telecallers",
        "/api/v1/intake/analytics/campaigns",
        "/api/v1/intake/leads",
        "/api/v1/intake/config",
    ],
)
async def test_a_telecaller_cannot_read_the_reports_about_themselves(http, path):
    await _staff("caller", UserRole.telecaller)

    res = await http.get(path, headers=await _headers("caller"))

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_a_recruiter_cannot_read_the_reports(http):
    await _staff("rec", UserRole.employee)

    res = await http.get("/api/v1/intake/analytics/overview", headers=await _headers("rec"))

    assert res.status_code == 403
