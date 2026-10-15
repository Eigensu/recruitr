"""Telecaller metrics, the daily / weekly reports and the targets behind them.

Signed in with real tokens so the role guards are exercised. Calls, decisions and
notes are written straight to their collections with fixed timestamps: the
reports cut days in IST, and a test about where midnight falls must not depend
on what time it is when it runs.
"""

from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    MAX_CALL_ATTEMPTS,
    CandidateStatus,
    IntakeCallOutcome,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeNoteStage,
    IntakeRejectReason,
)
from app.modules.recruitment.models import (
    Candidate,
    Employee,
    IntakeLead,
    LeadCall,
    LeadNote,
    TelecallerTarget,
)
from app.modules.recruitment.service import telecaller_metrics
from tests.staff import auth_headers, make_staff

_BRAND = PydanticObjectId()
_URL = "/api/v1/intake/telecaller-report"
# Wednesday 14 Oct 2026, so the week is Mon 12 .. Sun 18.
_DAY = "2026-10-14"


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


async def _call(
    who: Employee,
    at: datetime,
    outcome: IntakeCallOutcome = IntakeCallOutcome.no_answer,
    decision: IntakeDecision | None = None,
    brand: PydanticObjectId = _BRAND,
) -> LeadCall:
    return await LeadCall(
        brand_id=brand,
        lead_id=PydanticObjectId(),
        candidate_id=PydanticObjectId(),
        telecaller_id=who.id,
        attempt=1,
        outcome=outcome,
        decision=decision,
        at=at,
    ).insert()


async def _connected(who: Employee, at: datetime, decision: IntakeDecision) -> LeadCall:
    return await _call(who, at, IntakeCallOutcome.connected, decision)


async def _lead(
    who: Employee,
    *,
    status: IntakeLeadStatus = IntakeLeadStatus.pending_telecaller,
    attempts: int = 0,
    decision: IntakeDecision | None = None,
    reason: IntakeRejectReason | None = None,
    actioned_at: datetime | None = None,
    closed_unreachable: bool = False,
) -> IntakeLead:
    candidate = Candidate(
        brand_id=_BRAND, full_name="Asha Rao", phone="9876543210", status=CandidateStatus.pending
    )
    await candidate.insert()
    return await IntakeLead(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        external_id=f"l_{PydanticObjectId()}",
        status=status,
        telecaller_id=who.id,
        telecaller_assigned_at=_utc(1, 0),
        call_attempts=attempts,
        telecaller_decision=decision,
        telecaller_reject_reason=reason,
        telecaller_actioned_at=actioned_at,
        closed_unreachable=closed_unreachable,
    ).insert()


@pytest_asyncio.fixture
async def ann() -> Employee:
    return await make_staff(_BRAND, "ann", UserRole.telecaller)


@pytest_asyncio.fixture
async def ben() -> Employee:
    return await make_staff(_BRAND, "ben", UserRole.telecaller)


@pytest_asyncio.fixture
async def boss() -> Employee:
    return await make_staff(_BRAND, "boss", UserRole.maintainer)


async def _report(http, params: dict | None = None, who: str = "boss"):
    return await http.get(_URL, params=params or {}, headers=await auth_headers(who))


def _row(body: dict, name: str) -> dict:
    return next(r for r in body["rows"] if r["telecaller_name"] == name)


# ── The numbers ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_day_counts_every_call_answered_or_not_and_the_decisions_they_ended(
    http, ann, boss
):
    await _call(ann, _utc(14, 5))
    await _call(ann, _utc(14, 6))
    await _connected(ann, _utc(14, 7), IntakeDecision.accept)
    await _connected(ann, _utc(14, 8), IntakeDecision.accept)
    await _connected(ann, _utc(14, 9), IntakeDecision.reject)

    res = await _report(http, {"period": "day", "date": _DAY})

    assert res.status_code == 200, res.text
    row = _row(res.json(), "ann")
    assert (row["calls"], row["unanswered"], row["connected"]) == (5, 2, 3)
    assert (row["forwarded"], row["rejected"], row["dead"]) == (2, 1, 0)
    assert row["bad_lead_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert res.json()["start_date"] == res.json()["end_date"] == _DAY


@pytest.mark.asyncio
async def test_a_managers_decision_is_not_counted_for_the_telecaller(http, ann, boss):
    """It has no row in the call log, which is what the counts read."""
    await _lead(
        ann,
        status=IntakeLeadStatus.rejected,
        decision=IntakeDecision.reject,
        reason=IntakeRejectReason.not_interested,
        actioned_at=_utc(14, 5),
    )

    row = _row((await _report(http, {"date": _DAY})).json(), "ann")

    assert (row["calls"], row["forwarded"], row["rejected"]) == (0, 0, 0)


@pytest.mark.asyncio
async def test_leads_closed_as_unreachable_are_dead_and_count_as_bad_leads(http, ann, boss):
    await _connected(ann, _utc(14, 5), IntakeDecision.accept)
    await _connected(ann, _utc(14, 6), IntakeDecision.accept)
    await _connected(ann, _utc(14, 7), IntakeDecision.accept)
    await _connected(ann, _utc(14, 8), IntakeDecision.reject)
    await _lead(
        ann,
        status=IntakeLeadStatus.rejected,
        attempts=MAX_CALL_ATTEMPTS,
        decision=IntakeDecision.reject,
        reason=IntakeRejectReason.not_reachable,
        actioned_at=_utc(14, 9),
        closed_unreachable=True,
    )
    # Rejected as unreachable by choice, before the calls ran out: not dead.
    await _lead(
        ann,
        status=IntakeLeadStatus.rejected,
        attempts=2,
        decision=IntakeDecision.reject,
        reason=IntakeRejectReason.not_reachable,
        actioned_at=_utc(14, 10),
    )

    row = _row((await _report(http, {"date": _DAY})).json(), "ann")

    assert (row["forwarded"], row["rejected"], row["dead"]) == (3, 1, 1)
    # 1 rejected + 1 dead of 5 finished.
    assert row["bad_lead_rate"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_a_manual_unreachable_reject_is_one_rejected_lead_never_also_dead(http, ann, boss):
    """Rejecting as "not reachable" on the way to the limit is a telecaller's own
    call: the decision call brings the count to 5, but the lead was not closed by it."""
    lead = await _lead(ann, attempts=4)
    headers = await auth_headers("ann")

    res = await http.post(
        f"/api/v1/intake/leads/{lead.id}/reject", json={"reason": "not_reachable"}, headers=headers
    )

    assert res.status_code == 200, res.text
    assert (await IntakeLead.get(lead.id)).call_attempts == MAX_CALL_ATTEMPTS
    today = telecaller_metrics.today_ist().isoformat()
    row = _row((await _report(http, {"date": today})).json(), "ann")
    assert (row["rejected"], row["dead"]) == (1, 0)
    assert row["bad_lead_rate"] == 1.0


@pytest.mark.asyncio
async def test_a_lead_the_call_limit_closes_is_dead_and_not_also_rejected(http, ann, boss):
    lead = await _lead(ann)
    headers = await auth_headers("ann")
    for _ in range(MAX_CALL_ATTEMPTS):
        await http.post(f"/api/v1/intake/leads/{lead.id}/calls", json={}, headers=headers)

    today = telecaller_metrics.today_ist().isoformat()
    row = _row((await _report(http, {"date": today})).json(), "ann")

    assert (row["calls"], row["unanswered"]) == (MAX_CALL_ATTEMPTS, MAX_CALL_ATTEMPTS)
    assert (row["rejected"], row["dead"], row["forwarded"]) == (0, 1, 0)
    assert row["bad_lead_rate"] == 1.0
    assert (await IntakeLead.get(lead.id)).closed_unreachable is True


@pytest.mark.asyncio
async def test_no_decisions_is_no_rate_not_zero(http, ann, boss):
    await _call(ann, _utc(14, 5))

    row = _row((await _report(http, {"date": _DAY})).json(), "ann")

    assert row["bad_lead_rate"] is None


@pytest.mark.asyncio
async def test_days_are_cut_in_ist_not_utc(http, ann, boss):
    # 18:00 UTC is 23:30 IST on the 14th; 19:00 UTC is 00:30 IST on the 15th.
    await _call(ann, _utc(14, 18))
    await _call(ann, _utc(14, 19))

    on_14 = _row((await _report(http, {"date": "2026-10-14"})).json(), "ann")
    on_15 = _row((await _report(http, {"date": "2026-10-15"})).json(), "ann")

    assert (on_14["calls"], on_15["calls"]) == (1, 1)


@pytest.mark.asyncio
async def test_a_week_is_monday_to_sunday_with_a_row_per_day(http, ann, boss):
    await _call(ann, _utc(12, 5))  # Monday
    await _call(ann, _utc(14, 5))  # Wednesday
    await _call(ann, _utc(14, 6))
    await _call(ann, _utc(19, 5))  # the next Monday: outside

    res = await _report(http, {"period": "week", "date": _DAY})

    body = res.json()
    assert (body["start_date"], body["end_date"]) == ("2026-10-12", "2026-10-18")
    row = _row(body, "ann")
    assert row["calls"] == 3
    assert [d["date"] for d in row["days"]] == [f"2026-10-{n}" for n in range(12, 19)]
    assert [d["calls"] for d in row["days"]] == [1, 0, 2, 0, 0, 0, 0]


@pytest.mark.asyncio
async def test_a_range_spans_the_dates_given(http, ann, boss):
    await _call(ann, _utc(10, 5))
    await _call(ann, _utc(14, 5))
    await _call(ann, _utc(20, 5))

    res = await _report(http, {"period": "range", "start": "2026-10-10", "end": "2026-10-14"})

    assert _row(res.json(), "ann")["calls"] == 2
    assert len(_row(res.json(), "ann")["days"]) == 5


@pytest.mark.asyncio
async def test_a_quiet_telecaller_is_listed_with_zeros_and_the_filter_narrows(http, ann, ben, boss):
    await _call(ann, _utc(14, 5))

    everyone = (await _report(http, {"date": _DAY})).json()
    only_ben = (await _report(http, {"date": _DAY, "telecaller_id": str(ben.id)})).json()

    assert [r["telecaller_name"] for r in everyone["rows"]] == ["ann", "ben"]
    assert _row(everyone, "ben")["calls"] == 0
    assert [r["telecaller_name"] for r in only_ben["rows"]] == ["ben"]
    assert everyone["totals"]["calls"] == 1


@pytest.mark.asyncio
async def test_someone_who_is_no_longer_a_telecaller_still_shows_under_their_name(http, ann, boss):
    await _call(ann, _utc(14, 5))
    await ann.set({"role": UserRole.employee.value})

    body = (await _report(http, {"date": _DAY})).json()

    assert _row(body, "ann")["calls"] == 1


@pytest.mark.asyncio
async def test_another_brands_activity_never_appears(http, ann, boss):
    stranger = await make_staff(PydanticObjectId(), "stranger", UserRole.telecaller)
    await _call(stranger, _utc(14, 5), brand=stranger.brand_id)

    body = (await _report(http, {"date": _DAY})).json()

    assert [r["telecaller_name"] for r in body["rows"]] == ["ann"]
    assert body["totals"]["calls"] == 0


@pytest.mark.asyncio
async def test_notes_written_counts_telecaller_authored_notes_in_the_period(http, ann, boss):
    def note(author: Employee, role: str, at: datetime) -> LeadNote:
        return LeadNote(
            brand_id=_BRAND,
            lead_id=PydanticObjectId(),
            candidate_id=PydanticObjectId(),
            stage=IntakeNoteStage.telecaller,
            body="n",
            author_id=author.id,
            author_name=author.name,
            author_role=role,
            created_at=at,
        )

    await note(ann, "telecaller", _utc(14, 5)).insert()
    await note(ann, "telecaller", _utc(14, 6)).insert()
    await note(ann, "telecaller", _utc(20, 6)).insert()  # another day
    await note(boss, "maintainer", _utc(14, 7)).insert()  # not a telecaller's

    body = (await _report(http, {"date": _DAY})).json()

    assert _row(body, "ann")["notes_written"] == 2
    assert body["totals"]["notes_written"] == 2


# ── Asking for a period ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"period": "range"},
        {"period": "range", "start": "2026-10-10"},
        {"period": "range", "start": "2026-10-14", "end": "2026-10-10"},
        {"period": "range", "start": "2026-01-01", "end": "2026-12-31"},
        {"period": "range", "start": "2026-10-10", "end": "2026-10-14", "date": _DAY},
        # `start` and `end` without `period=range` must not quietly become today.
        {"start": "2026-10-10", "end": "2026-10-14"},
        {"period": "week", "start": "2026-10-10"},
    ],
)
async def test_a_period_that_does_not_make_sense_is_refused(http, boss, params):
    res = await _report(http, params)

    assert res.status_code == 422, (params, res.text)


@pytest.mark.asyncio
async def test_with_no_date_a_day_report_is_todays_in_ist(http, boss):
    res = await _report(http, {"period": "day"})

    assert res.status_code == 200
    assert res.json()["start_date"] == telecaller_metrics.today_ist().isoformat()


# ── Targets ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_targets_set_the_yardstick_for_a_day_a_week_and_a_range(http, ann, boss):
    await TelecallerTarget(
        brand_id=_BRAND, telecaller_id=ann.id, daily_calls=10, weekly_calls=40
    ).insert()
    for hour in range(4):
        await _call(ann, _utc(14, 5 + hour))

    day = _row((await _report(http, {"date": _DAY})).json(), "ann")
    week = _row((await _report(http, {"period": "week", "date": _DAY})).json(), "ann")
    span = _row(
        (
            await _report(http, {"period": "range", "start": "2026-10-12", "end": "2026-10-14"})
        ).json(),
        "ann",
    )

    assert (day["target_calls"], day["target_pct"]) == (10, 0.4)
    assert (week["target_calls"], week["target_pct"]) == (40, 0.1)
    # The daily target for each of the three days.
    assert (span["target_calls"], span["target_pct"]) == (30, pytest.approx(0.1333, abs=1e-4))


@pytest.mark.asyncio
async def test_no_target_means_no_percentage(http, ann, boss):
    await _call(ann, _utc(14, 5))

    row = _row((await _report(http, {"date": _DAY})).json(), "ann")

    assert (row["target_calls"], row["target_pct"]) == (None, None)


@pytest.mark.asyncio
async def test_setting_one_target_keeps_the_other_and_null_clears(http, ann, boss):
    headers = await auth_headers("boss")
    url = f"/api/v1/intake/telecaller-targets/{ann.id}"

    first = await http.put(url, json={"daily_calls": 30, "weekly_calls": 150}, headers=headers)
    only_daily = await http.put(url, json={"daily_calls": 40}, headers=headers)
    cleared = await http.put(url, json={"weekly_calls": None}, headers=headers)

    assert first.status_code == 200, first.text
    assert (only_daily.json()["daily_calls"], only_daily.json()["weekly_calls"]) == (40, 150)
    assert (cleared.json()["daily_calls"], cleared.json()["weekly_calls"]) == (40, None)
    assert await TelecallerTarget.find({"telecaller_id": ann.id}).count() == 1


@pytest.mark.asyncio
async def test_targets_are_listed_for_every_telecaller(http, ann, ben, boss):
    await TelecallerTarget(brand_id=_BRAND, telecaller_id=ann.id, daily_calls=25).insert()

    res = await http.get("/api/v1/intake/telecaller-targets", headers=await auth_headers("boss"))

    assert res.status_code == 200
    assert [(t["telecaller_name"], t["daily_calls"], t["weekly_calls"]) for t in res.json()] == [
        ("ann", 25, None),
        ("ben", None, None),
    ]


@pytest.mark.asyncio
async def test_a_target_needs_a_real_telecaller_in_the_brand(http, boss):
    recruiter = await make_staff(_BRAND, "rec", UserRole.employee)
    stranger = await make_staff(PydanticObjectId(), "stranger", UserRole.telecaller)
    headers = await auth_headers("boss")

    for employee_id in (recruiter.id, stranger.id, PydanticObjectId()):
        res = await http.put(
            f"/api/v1/intake/telecaller-targets/{employee_id}",
            json={"daily_calls": 10},
            headers=headers,
        )
        assert res.status_code == 404, (employee_id, res.text)


@pytest.mark.asyncio
async def test_a_negative_target_is_refused(http, ann, boss):
    res = await http.put(
        f"/api/v1/intake/telecaller-targets/{ann.id}",
        json={"daily_calls": -1},
        headers=await auth_headers("boss"),
    )

    assert res.status_code == 422


# ── Who may look ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_management_may_see_the_metrics_or_set_targets(http, ann):
    await make_staff(_BRAND, "rec", UserRole.employee)
    for who in ("ann", "rec"):
        headers = await auth_headers(who)
        assert (await http.get(_URL, headers=headers)).status_code == 403, who
        assert (
            await http.get("/api/v1/intake/telecaller-targets", headers=headers)
        ).status_code == 403, who
        assert (
            await http.put(
                f"/api/v1/intake/telecaller-targets/{ann.id}",
                json={"daily_calls": 1},
                headers=headers,
            )
        ).status_code == 403, who


@pytest.mark.asyncio
async def test_period_dates_helper_weeks_start_on_monday():
    assert telecaller_metrics.period_dates("week", anchor=date(2026, 10, 18)) == (
        date(2026, 10, 12),
        date(2026, 10, 18),
    )
    assert telecaller_metrics.period_dates("week", anchor=date(2026, 10, 12)) == (
        date(2026, 10, 12),
        date(2026, 10, 18),
    )
