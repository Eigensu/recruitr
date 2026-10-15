"""Telecaller metrics and the daily / weekly reports built on them.

Reads three permanent records, none of which expire: the call log (`LeadCall`),
the lead's own stamps for leads closed as unreachable (`IntakeLead`) and the
screening notes (`LeadNote`). It sits beside `intake_service` and
`intake_analytics` rather than inside them: import it by module path.

What is counted, and for whom:

* **calls** — every call a telecaller made, answered or not (a row in the call
  log). `connected` and `unanswered` split it.
* **forwarded / rejected** — the accepts and rejects a telecaller made, read off
  the call each ended (`LeadCall.decision`). A manager deciding on a telecaller's
  behalf is not a call and is not counted for them.
* **dead** — leads that ran out of calls and were closed as unreachable. Nobody
  *judged* those bad, so they are not in `rejected`, but they are bad leads, and
  they are in `bad_lead_rate`.

Days are cut in India Standard Time. The agency works a Mumbai day, and a call
made at 11pm belongs to that day, not to the next one in UTC. IST has no daylight
saving, so a fixed offset is exact and needs no timezone database.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, Literal

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import IntakeDecision
from app.modules.recruitment.models import (
    Employee,
    IntakeLead,
    LeadCall,
    LeadNote,
    TelecallerTarget,
)

IST = timezone(timedelta(hours=5, minutes=30))
_IST_OFFSET = "+05:30"  # the same offset, spelled the way Mongo's $dateToString wants it

# A report this long is one screen of days; longer is a different question, and
# a range of years would aggregate the whole call log for one click.
MAX_RANGE_DAYS = 92

Period = Literal["day", "week", "range"]

_COUNTS = ("calls", "unanswered", "connected", "forwarded", "rejected", "dead")


def today_ist(now: datetime | None = None) -> date:
    """Today's date on the agency's clock."""
    return (now or datetime.now(UTC)).astimezone(IST).date()


def period_dates(
    period: Period,
    *,
    anchor: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[date, date]:
    """The first and last date, inclusive, a report covers.

    A day is the anchor itself (today by default). A week is the Monday-to-Sunday
    week containing the anchor, so "this week" and "last week" are stable
    whichever day they are asked on. A range is the dates given.

    Dates that do not belong to the period are an error rather than ignored: a
    caller who sent `start` and `end` and forgot `period` would otherwise get
    today's single day back and read it as the range they asked for.
    """
    if period == "range":
        if anchor is not None:
            raise ValueError("A range takes start and end, not date.")
        if start is None or end is None:
            raise ValueError("A range needs a start and an end date.")
        if end < start:
            raise ValueError("The end date is before the start date.")
        if (end - start).days + 1 > MAX_RANGE_DAYS:
            raise ValueError(f"A range can be at most {MAX_RANGE_DAYS} days.")
        return start, end
    if start is not None or end is not None:
        raise ValueError(f"Use period=range with start and end; period={period} takes date.")
    day = anchor or today_ist()
    if period == "day":
        return day, day
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def utc_bounds(first: date, last: date) -> tuple[datetime, datetime]:
    """[start, end) in UTC for the IST dates first..last inclusive.

    Aware datetimes: the driver converts them to UTC for the comparison, whereas
    comparing against the naive values Mongo hands back is what intake_service.
    as_utc exists to guard.
    """
    start = datetime(first.year, first.month, first.day, tzinfo=IST).astimezone(UTC)
    after = last + timedelta(days=1)
    end = datetime(after.year, after.month, after.day, tzinfo=IST).astimezone(UTC)
    return start, end


async def _aggregate(model: Any, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run a pipeline on a model's collection, as intake_analytics does for leads.

    The async driver's `aggregate` is a coroutine that yields the cursor, which
    is why Beanie's own `.aggregate(...).to_list()` cannot be used here.
    """
    cursor = await model.get_motor_collection().aggregate(pipeline)
    return await cursor.to_list(length=None)


def _day(field: str) -> dict[str, Any]:
    return {"$dateToString": {"format": "%Y-%m-%d", "date": field, "timezone": _IST_OFFSET}}


def _count_if(condition: dict[str, Any]) -> dict[str, Any]:
    return {"$sum": {"$cond": [condition, 1, 0]}}


async def _calls(
    brand_id: PydanticObjectId,
    start: datetime,
    end: datetime,
    telecaller_id: PydanticObjectId | None,
) -> list[dict[str, Any]]:
    """Calls, and the decisions they ended, by telecaller and IST day."""
    match: dict[str, Any] = {"brand_id": brand_id, "at": {"$gte": start, "$lt": end}}
    if telecaller_id:
        match["telecaller_id"] = telecaller_id
    return await _aggregate(
        LeadCall,
        [
            {"$match": match},
            {
                "$group": {
                    "_id": {"t": "$telecaller_id", "d": _day("$at")},
                    "calls": {"$sum": 1},
                    "unanswered": _count_if({"$eq": ["$outcome", "no_answer"]}),
                    "connected": _count_if({"$eq": ["$outcome", "connected"]}),
                    "forwarded": _count_if({"$eq": ["$decision", IntakeDecision.accept.value]}),
                    "rejected": _count_if({"$eq": ["$decision", IntakeDecision.reject.value]}),
                }
            },
        ],
    )


async def _dead_leads(
    brand_id: PydanticObjectId,
    start: datetime,
    end: datetime,
    telecaller_id: PydanticObjectId | None,
) -> list[dict[str, Any]]:
    """Leads closed as unreachable after the full set of calls, by day closed.

    Read off the lead because the closing is the system's, not a call: it has no
    row in the call log of its own (the fifth unanswered call does, but a call
    that merely brought the count to the limit is not the closure).
    """
    match: dict[str, Any] = {
        "brand_id": brand_id,
        # Set only by the call limit's own close, never by a telecaller rejecting
        # as "not reachable": that one is a rejected lead, counted once, there.
        "closed_unreachable": True,
        "telecaller_actioned_at": {"$gte": start, "$lt": end},
        "telecaller_id": {"$ne": None},
    }
    if telecaller_id:
        match["telecaller_id"] = telecaller_id
    return await _aggregate(
        IntakeLead,
        [
            {"$match": match},
            {
                "$group": {
                    "_id": {"t": "$telecaller_id", "d": _day("$telecaller_actioned_at")},
                    "dead": {"$sum": 1},
                }
            },
        ],
    )


async def _notes(
    brand_id: PydanticObjectId,
    start: datetime,
    end: datetime,
    telecaller_id: PydanticObjectId | None,
) -> dict[PydanticObjectId, int]:
    match: dict[str, Any] = {
        "brand_id": brand_id,
        "author_role": UserRole.telecaller.value,
        "created_at": {"$gte": start, "$lt": end},
    }
    if telecaller_id:
        match["author_id"] = telecaller_id
    rows = await _aggregate(
        LeadNote, [{"$match": match}, {"$group": {"_id": "$author_id", "n": {"$sum": 1}}}]
    )
    return {row["_id"]: int(row["n"]) for row in rows}


def _rate(numerator: int, denominator: int) -> float | None:
    """None, not zero, when there was nothing to rate: no decisions is not a 0% rate."""
    return round(numerator / denominator, 4) if denominator else None


def bad_lead_rate(forwarded: int, rejected: int, dead: int) -> float | None:
    """Of the leads a telecaller finished with, the share that were not forwarded.

    Rejected and dead both count: a lead nobody could reach is as much a bad lead
    as one turned away on the call. Null when they finished with none.
    """
    return _rate(rejected + dead, forwarded + rejected + dead)


def _target_for(period: Period, days: int, target: TelecallerTarget | None) -> int | None:
    """The calls target that applies to this period, or None when there is none.

    A week is judged against the whole weekly target even part-way through, so
    the percentage reads as progress towards it. A range is the daily target for
    each day in it, weekends included: set the daily figure with that in mind.
    """
    if target is None:
        return None
    if period == "week":
        return target.weekly_calls
    if period == "day":
        return target.daily_calls
    return target.daily_calls * days if target.daily_calls is not None else None


async def build_report(
    brand_id: PydanticObjectId,
    *,
    period: Period,
    first: date,
    last: date,
    telecaller_id: PydanticObjectId | None = None,
) -> dict[str, Any]:
    """Every telecaller's numbers for first..last (IST dates, inclusive).

    Telecallers with no activity are listed with zeros so a quiet day shows who
    was quiet. Someone who made calls and has since been removed or changed role
    still appears, under their name, since the numbers are theirs.
    """
    start, end = utc_bounds(first, last)
    calls, dead, notes, telecallers, target_rows = await asyncio.gather(
        _calls(brand_id, start, end, telecaller_id),
        _dead_leads(brand_id, start, end, telecaller_id),
        _notes(brand_id, start, end, telecaller_id),
        Employee.find({"brand_id": brand_id, "role": UserRole.telecaller.value}).to_list(),
        TelecallerTarget.find({"brand_id": brand_id}).to_list(),
    )

    people = {e.id: e for e in telecallers}
    seen = {r["_id"]["t"] for r in calls} | {r["_id"]["t"] for r in dead} | set(notes)
    absent = list(seen - people.keys())
    if absent:
        # One query, scoped to the brand: activity from someone no longer a
        # telecaller still shows, and an id from another brand never does.
        for employee in await Employee.find(
            {"_id": {"$in": absent}, "brand_id": brand_id}
        ).to_list():
            people[employee.id] = employee
    if telecaller_id:
        people = {k: v for k, v in people.items() if k == telecaller_id}

    targets = {t.telecaller_id: t for t in target_rows}
    dates = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    per: dict[PydanticObjectId, dict[str, dict[str, int]]] = {
        pid: {d.isoformat(): dict.fromkeys(_COUNTS, 0) for d in dates} for pid in people
    }
    for source in (calls, dead):
        for row in source:
            cell = per.get(row["_id"]["t"], {}).get(row["_id"]["d"])
            if cell is not None:
                for key in _COUNTS:
                    cell[key] += row.get(key, 0)

    rows: list[dict[str, Any]] = []
    for pid, employee in people.items():
        days = per[pid]
        total = {k: sum(day[k] for day in days.values()) for k in _COUNTS}
        target_calls = _target_for(period, len(dates), targets.get(pid))
        rows.append(
            {
                "telecaller_id": str(pid),
                "telecaller_name": employee.name,
                "active": employee.is_active,
                **total,
                "bad_lead_rate": bad_lead_rate(
                    total["forwarded"], total["rejected"], total["dead"]
                ),
                "notes_written": notes.get(pid, 0),
                "target_calls": target_calls,
                "target_pct": _rate(total["calls"], target_calls) if target_calls else None,
                "days": [{"date": d, **cell} for d, cell in days.items()],
            }
        )
    # Busiest first, then by name, so the ordering is stable between refreshes.
    rows.sort(key=lambda r: (-r["calls"], r["telecaller_name"].lower()))

    totals: dict[str, Any] = {k: sum(r[k] for r in rows) for k in _COUNTS}
    totals["bad_lead_rate"] = bad_lead_rate(totals["forwarded"], totals["rejected"], totals["dead"])
    totals["notes_written"] = sum(r["notes_written"] for r in rows)
    return {
        "period": period,
        "start_date": first,
        "end_date": last,
        "rows": rows,
        "totals": totals,
    }


def target_row(employee: Employee, target: TelecallerTarget | None) -> dict[str, Any]:
    """A telecaller with their targets, as the API shows them (null where unset)."""
    return {
        "telecaller_id": str(employee.id),
        "telecaller_name": employee.name,
        "active": employee.is_active,
        "daily_calls": target.daily_calls if target else None,
        "weekly_calls": target.weekly_calls if target else None,
    }


async def list_targets(brand_id: PydanticObjectId) -> list[dict[str, Any]]:
    """Every telecaller with their targets, none where unset."""
    targets = {
        t.telecaller_id: t for t in await TelecallerTarget.find({"brand_id": brand_id}).to_list()
    }
    people = (
        await Employee.find({"brand_id": brand_id, "role": UserRole.telecaller.value})
        .sort("name")
        .to_list()
    )
    return [target_row(p, targets.get(p.id)) for p in people]


async def set_target(
    brand_id: PydanticObjectId,
    telecaller: Employee,
    *,
    changes: dict[str, int | None],
    updated_by_id: PydanticObjectId | None,
) -> TelecallerTarget:
    """Change a telecaller's targets: only the keys in `changes`, null clearing one.

    A key left out keeps what is stored, so setting the daily target does not
    wipe the weekly one. Two admins setting a first target at once is not an
    error: the loser of the insert race applies its change to the winner's row.
    """
    now = datetime.now(UTC)
    key = {"brand_id": brand_id, "telecaller_id": telecaller.id}
    stamp = {"updated_by_id": updated_by_id, "updated_at": now}
    existing = await TelecallerTarget.find_one(key)
    if existing is None:
        try:
            return await TelecallerTarget(**key, **changes, **stamp).insert()
        except DuplicateKeyError:
            existing = await TelecallerTarget.find_one(key)
            if existing is None:
                raise
    await existing.set({**changes, **stamp})
    return existing
