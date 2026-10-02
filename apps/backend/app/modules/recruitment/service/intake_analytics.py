"""Read models for the admin intake dashboard: the funnel and both SLA clocks.

Answers four questions, each of which an admin asked for directly: how many
leads came in and where did they end up, how long is each telecaller taking to
call them, how long is each recruiter taking to act on the ones that were
accepted, and which ad spend produced them.

Three conventions, all borrowed from `dashboard/repository.py` rather than
invented here:

  - every pipeline starts with `$match` on `brand_id`;
  - results are cached in the dashboard Redis namespace and dropped on any
    lead write, so an accept is visible on the next refresh rather than up to
    five minutes later;
  - a window filters on `ingested_at`, so a range describes **the leads that
    arrived in it** and follows them wherever they got to. Filtering each leg
    on its own assignment date instead would let a lead leave the funnel it
    entered, and "we received 40 and rejected 45" is not a report anyone can
    act on.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from beanie import PydanticObjectId

from app.common.extras.redis_cache import dashboard_cache
from app.core.config import settings
from app.modules.recruitment.enums import IntakeDecision, IntakeLeadStatus
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, IntakeSourceConfig
from app.modules.recruitment.service.intake_service import as_utc

logger = logging.getLogger(__name__)

_MATCH = "$match"
_GROUP = "$group"
_SORT = "$sort"
_SUM = "$sum"
_COND = "$cond"
_CACHE_PREFIX = "intake"

_F_STATUS = "$status"
_F_DECISION = "$telecaller_decision"

# The two legs, named by their field prefix on IntakeLead. Everything below is
# written once and parameterised by this rather than twice, because the second
# copy is where the two would quietly drift apart.
TELECALLER = "telecaller"
RECRUITER = "recruiter"

_OPEN_STATUS = {
    TELECALLER: IntakeLeadStatus.pending_telecaller.value,
    RECRUITER: IntakeLeadStatus.pending_recruiter.value,
}

_SLA_HOURS = {
    TELECALLER: settings.TELECALLER_SLA_HOURS,
    RECRUITER: settings.RECRUITER_SLA_HOURS,
}

# What a campaign table can be grouped by, and the field behind each label.
CAMPAIGN_GROUPS = {
    "campaign": "$attribution.campaign_name",
    "ad": "$attribution.ad_name",
    "form": "$attribution.form_name",
    "channel": "$source_channel",
}
_UNATTRIBUTED = "(unattributed)"


# ── Small helpers ──────────────────────────────────────────────────────────────


def sla_hours(leg: str) -> int:
    return _SLA_HOURS[leg]


def _percentile(values: list[int], q: float) -> float | None:
    """Linear-interpolated percentile, in seconds. None for an empty sample.

    Computed here rather than with Mongo's `$percentile` accumulator: that needs
    server 7.0, and this has to run against whatever version the cluster happens
    to be on. The cost is pulling one integer per actioned lead into memory,
    which at this volume is a few hundred kilobytes.
    """
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = q * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[low])
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _hours(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds / 3600, 2)


def _rate(numerator: int, denominator: int) -> float | None:
    """A proportion, or None when nothing has happened yet.

    None rather than 0.0 on purpose: a telecaller who has not yet actioned
    anything has an *unknown* accept rate, and showing 0% would read as a person
    rejecting everyone.
    """
    return None if denominator <= 0 else round(numerator / denominator, 4)


def _window(
    brand_id: PydanticObjectId, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    match: dict[str, Any] = {"brand_id": brand_id}
    bounds = {}
    if start is not None:
        bounds["$gte"] = start
    if end is not None:
        bounds["$lte"] = end
    if bounds:
        match["ingested_at"] = bounds
    return match


async def _aggregate(pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cursor = await IntakeLead.get_motor_collection().aggregate(pipeline)
    return await cursor.to_list(length=None)


# ── Cache ──────────────────────────────────────────────────────────────────────


def _cache_key(name: str, brand_id: PydanticObjectId, **parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return dashboard_cache.build_key(brand_id, _CACHE_PREFIX, name, digest)


async def invalidate(brand_id: PydanticObjectId) -> None:
    """Drop this brand's cached intake analytics. Best effort, never raises.

    Called after every lead write. A stale funnel is not worth failing an accept
    that already succeeded, which is why this swallows everything.
    """
    try:
        await dashboard_cache.delete_pattern(
            dashboard_cache.build_key(brand_id, _CACHE_PREFIX, "*")
        )
    except Exception:  # noqa: BLE001
        logger.debug("Intake analytics cache invalidation failed", exc_info=True)


async def cached(name: str, brand_id: PydanticObjectId, builder, **parts: Any) -> Any:
    key = _cache_key(name, brand_id, **parts)
    hit = await dashboard_cache.get_json(key)
    if hit is not None:
        return hit
    payload = await builder()
    await dashboard_cache.set_json(key, payload, settings.REDIS_CACHE_TTL_SECONDS)
    return payload


# ── One leg of the journey ─────────────────────────────────────────────────────


def _leg_group(leg: str, *, per_person: bool, cutoff: datetime, sla_seconds: int) -> dict[str, Any]:
    """The `$group` stage that measures one leg, for one person or for everyone.

    The same accumulators either way, so the team totals and the per-person rows
    cannot disagree about what "overdue" means.
    """
    assigned_at = f"${leg}_assigned_at"
    actioned_at = f"${leg}_actioned_at"
    seconds = f"${leg}_response_seconds"
    still_open = {"$eq": [_F_STATUS, _OPEN_STATUS[leg]]}

    group: dict[str, Any] = {
        "_id": f"${leg}_id" if per_person else None,
        "assigned": {_SUM: 1},
        "actioned": {_SUM: {_COND: [{"$ne": [actioned_at, None]}, 1, 0]}},
        "pending": {_SUM: {_COND: [still_open, 1, 0]}},
        "overdue": {_SUM: {_COND: [{"$and": [still_open, {"$lt": [assigned_at, cutoff]}]}, 1, 0]}},
        "within_sla": {
            _SUM: {
                _COND: [
                    {"$and": [{"$ne": [seconds, None]}, {"$lte": [seconds, sla_seconds]}]},
                    1,
                    0,
                ]
            }
        },
        # $min ignores the nulls this $cond produces for actioned leads, so it
        # is the oldest assignment still waiting rather than the oldest overall.
        "oldest_pending_at": {"$min": {_COND: [still_open, assigned_at, None]}},
        "seconds": {"$push": seconds},
    }
    if leg == TELECALLER:
        group["accepted"] = {
            _SUM: {_COND: [{"$eq": [_F_DECISION, IntakeDecision.accept.value]}, 1, 0]}
        }
        group["rejected"] = {
            _SUM: {_COND: [{"$eq": [_F_DECISION, IntakeDecision.reject.value]}, 1, 0]}
        }
    return group


def _leg_stats(row: dict[str, Any], *, leg: str, now: datetime) -> dict[str, Any]:
    """One grouped row turned into the numbers the dashboard shows."""
    samples = [int(value) for value in row.get("seconds", []) if value is not None]
    actioned = int(row.get("actioned", 0))
    oldest = as_utc(row.get("oldest_pending_at"))
    stats: dict[str, Any] = {
        "assigned": int(row.get("assigned", 0)),
        "actioned": actioned,
        "pending": int(row.get("pending", 0)),
        "overdue": int(row.get("overdue", 0)),
        "avg_hours": _hours(sum(samples) / len(samples)) if samples else None,
        "median_hours": _hours(_percentile(samples, 0.5)),
        "p90_hours": _hours(_percentile(samples, 0.9)),
        "within_sla": int(row.get("within_sla", 0)),
        "sla_hours": sla_hours(leg),
        "sla_compliance": _rate(int(row.get("within_sla", 0)), actioned),
        "oldest_pending_hours": (
            None if oldest is None else round((now - oldest).total_seconds() / 3600, 2)
        ),
    }
    if leg == TELECALLER:
        accepted, rejected = int(row.get("accepted", 0)), int(row.get("rejected", 0))
        stats |= {
            "accepted": accepted,
            "rejected": rejected,
            # Of the decisions actually made — pending leads have no verdict yet,
            # so counting them in the denominator would make a full queue look
            # like a low accept rate.
            "accept_rate": _rate(accepted, accepted + rejected),
        }
    return stats


def _empty_leg(leg: str) -> dict[str, Any]:
    return _leg_stats({}, leg=leg, now=datetime.now(UTC))


async def _leg_rows(
    brand_id: PydanticObjectId,
    *,
    leg: str,
    per_person: bool,
    start: datetime | None,
    end: datetime | None,
    now: datetime,
) -> list[dict[str, Any]]:
    """The one pipeline behind both the team total and the per-person table.

    Leads with nobody on this leg are excluded: an unassigned lead is nobody's
    slow response, and counting it against the team would make an empty roster
    look like a late one.
    """
    hours = sla_hours(leg)
    pipeline: list[dict[str, Any]] = [
        {_MATCH: {**_window(brand_id, start, end), f"{leg}_id": {"$ne": None}}},
        {
            _GROUP: _leg_group(
                leg,
                per_person=per_person,
                cutoff=now - timedelta(hours=hours),
                sla_seconds=hours * 3600,
            )
        },
    ]
    if per_person:
        pipeline.append({_SORT: {"assigned": -1}})
    return await _aggregate(pipeline)


async def leg_totals(
    brand_id: PydanticObjectId,
    *,
    leg: str,
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    rows = await _leg_rows(brand_id, leg=leg, per_person=False, start=start, end=end, now=now)
    return _leg_stats(rows[0], leg=leg, now=now) if rows else _empty_leg(leg)


async def leg_by_person(
    brand_id: PydanticObjectId,
    *,
    leg: str,
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Per-person rows, busiest first, with names resolved in one extra query."""
    now = now or datetime.now(UTC)
    rows = await _leg_rows(brand_id, leg=leg, per_person=True, start=start, end=end, now=now)

    # One query for the names rather than a $lookup per row: the roster is a
    # handful of people, and joining the whole employees collection to read two
    # fields is more work than fetching them.
    ids = [row["_id"] for row in rows if row.get("_id") is not None]
    people = {
        employee.id: employee
        for employee in await Employee.find({"_id": {"$in": ids}, "brand_id": brand_id}).to_list()
    }

    table = []
    for row in rows:
        employee = people.get(row.get("_id"))
        table.append(
            {
                "employee_id": str(row["_id"]) if row.get("_id") else None,
                "name": employee.name if employee else "(removed)",
                "email": employee.email if employee else None,
                **_leg_stats(row, leg=leg, now=now),
            }
        )
    return table


async def open_lead_counts(brand_id: PydanticObjectId, *, leg: str) -> dict[Any, int]:
    """How many leads each person is currently holding on this leg.

    Shown next to every name in the reassign picker: handing a stuck lead to
    whoever already has the longest queue is the one move guaranteed not to
    help, and the number is the only thing that makes that visible.
    """
    rows = await _aggregate(
        [
            {_MATCH: {"brand_id": brand_id, "status": _OPEN_STATUS[leg]}},
            {_GROUP: {"_id": f"${leg}_id", "count": {_SUM: 1}}},
        ]
    )
    return {row["_id"]: int(row["count"]) for row in rows if row.get("_id")}


# ── Funnel ─────────────────────────────────────────────────────────────────────


async def funnel(
    brand_id: PydanticObjectId, *, start: datetime | None = None, end: datetime | None = None
) -> dict[str, int]:
    """Every lead in the window, counted by where it ended up.

    Statuses are enumerated from the enum so a new one appears as a zero rather
    than silently vanishing from a total that no longer adds up.
    """
    rows = await _aggregate(
        [{_MATCH: _window(brand_id, start, end)}, {_GROUP: {"_id": _F_STATUS, "count": {_SUM: 1}}}]
    )
    counts = {status.value: 0 for status in IntakeLeadStatus}
    for row in rows:
        if row["_id"] in counts:
            counts[row["_id"]] = int(row["count"])
    counts["ingested"] = sum(int(row["count"]) for row in rows)
    return counts


async def reject_reasons(
    brand_id: PydanticObjectId, *, start: datetime | None = None, end: datetime | None = None
) -> list[dict[str, Any]]:
    """Why leads were turned away, commonest first.

    `wrong_number` dominating this list is a data-quality problem with the ad
    form, not a telecaller problem — which is the distinction it exists to make.
    """
    rows = await _aggregate(
        [
            {
                _MATCH: {
                    **_window(brand_id, start, end),
                    "telecaller_decision": IntakeDecision.reject.value,
                }
            },
            {_GROUP: {"_id": "$telecaller_reject_reason", "count": {_SUM: 1}}},
            {_SORT: {"count": -1}},
        ]
    )
    return [{"reason": row["_id"] or "unspecified", "count": int(row["count"])} for row in rows]


# ── Campaigns ──────────────────────────────────────────────────────────────────


async def campaigns(
    brand_id: PydanticObjectId,
    *,
    group_by: str = "campaign",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Leads, accept-rate and actioned-rate per campaign / ad / form / channel.

    Effectively free: Meta's attribution is already stored on every lead, and
    this is the only view that connects "what we paid for" to "who we hired".
    """
    field = CAMPAIGN_GROUPS[group_by]
    rows = await _aggregate(
        [
            {_MATCH: _window(brand_id, start, end)},
            {
                _GROUP: {
                    "_id": field,
                    "leads": {_SUM: 1},
                    "accepted": {
                        _SUM: {
                            _COND: [
                                {"$eq": [_F_DECISION, IntakeDecision.accept.value]},
                                1,
                                0,
                            ]
                        }
                    },
                    "rejected": {
                        _SUM: {
                            _COND: [
                                {"$eq": [_F_DECISION, IntakeDecision.reject.value]},
                                1,
                                0,
                            ]
                        }
                    },
                    "actioned": {
                        _SUM: {
                            _COND: [
                                {"$eq": [_F_STATUS, IntakeLeadStatus.actioned.value]},
                                1,
                                0,
                            ]
                        }
                    },
                    "duplicate": {
                        _SUM: {
                            _COND: [
                                {"$eq": [_F_STATUS, IntakeLeadStatus.duplicate.value]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {_SORT: {"leads": -1}},
            {"$limit": limit},
        ]
    )
    return [
        {
            "label": row["_id"] or _UNATTRIBUTED,
            "leads": int(row["leads"]),
            "accepted": int(row["accepted"]),
            "rejected": int(row["rejected"]),
            "actioned": int(row["actioned"]),
            "duplicate": int(row["duplicate"]),
            "accept_rate": _rate(int(row["accepted"]), int(row["accepted"]) + int(row["rejected"])),
            "actioned_rate": _rate(int(row["actioned"]), int(row["leads"])),
        }
        for row in rows
    ]


# ── Overview ───────────────────────────────────────────────────────────────────


async def overview(
    brand_id: PydanticObjectId, *, start: datetime | None = None, end: datetime | None = None
) -> dict[str, Any]:
    now = datetime.now(UTC)
    counts, telecaller, recruiter, reasons, config = await asyncio.gather(
        funnel(brand_id, start=start, end=end),
        leg_totals(brand_id, leg=TELECALLER, start=start, end=end, now=now),
        leg_totals(brand_id, leg=RECRUITER, start=start, end=end, now=now),
        reject_reasons(brand_id, start=start, end=end),
        IntakeSourceConfig.find_one({"brand_id": brand_id}),
    )
    return {
        "start_date": start,
        "end_date": end,
        "funnel": counts,
        "telecaller": telecaller,
        "recruiter": recruiter,
        "reject_reasons": reasons,
        "source": _source_status(config),
    }


def _source_status(config: IntakeSourceConfig | None) -> dict[str, Any]:
    if config is None:
        return {"configured": False, "enabled": False, "consecutive_failures": 0}
    return {
        "configured": True,
        "enabled": config.enabled,
        "last_synced_at": config.last_synced_at,
        "last_success_at": config.last_success_at,
        "last_error": config.last_error,
        "consecutive_failures": config.consecutive_failures,
    }


# ── Lead list ──────────────────────────────────────────────────────────────────


def overdue_clause(now: datetime) -> dict[str, Any]:
    """Leads past their SLA on whichever leg they are actually waiting on.

    Two clauses, not one: the legs have separate clocks and separate limits, and
    a lead waiting on a recruiter is not late because its telecaller was slow.
    """
    return {
        "$or": [
            {
                "status": IntakeLeadStatus.pending_telecaller.value,
                "telecaller_assigned_at": {"$lt": now - timedelta(hours=sla_hours(TELECALLER))},
            },
            {
                "status": IntakeLeadStatus.pending_recruiter.value,
                "recruiter_assigned_at": {"$lt": now - timedelta(hours=sla_hours(RECRUITER))},
            },
        ]
    }


async def lead_page(
    brand_id: PydanticObjectId,
    *,
    status: IntakeLeadStatus | None = None,
    telecaller_id: PydanticObjectId | None = None,
    recruiter_id: PydanticObjectId | None = None,
    campaign: str | None = None,
    overdue: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[IntakeLead], int]:
    """One page of leads for the admin list, newest arrival first.

    Not cached: this is a working list read with a dozen filter combinations,
    and a five-minute-old answer to "show me what is overdue right now" is
    worse than no answer.
    """
    match: dict[str, Any] = _window(brand_id, start, end)
    if status is not None:
        match["status"] = status.value
    if telecaller_id is not None:
        match["telecaller_id"] = telecaller_id
    if recruiter_id is not None:
        match["recruiter_id"] = recruiter_id
    if campaign is not None:
        match["attribution.campaign_name"] = campaign
    if overdue:
        match.update(overdue_clause(datetime.now(UTC)))

    total = await IntakeLead.find(match).count()
    rows = (
        await IntakeLead.find(match)
        .sort("-ingested_at")
        .skip((page - 1) * limit)
        .limit(limit)
        .to_list()
    )
    return rows, total


async def people_for(leads: list[IntakeLead]) -> tuple[dict, dict]:
    """The candidates and employees named by a page of leads, in two queries.

    Batched rather than resolved per row: an admin page of 50 leads would
    otherwise be 150 round-trips to print names next to them.
    """
    candidate_ids = {lead.candidate_id for lead in leads}
    employee_ids = {
        employee_id
        for lead in leads
        for employee_id in (lead.telecaller_id, lead.recruiter_id)
        if employee_id is not None
    }
    candidates, employees = await asyncio.gather(
        Candidate.find({"_id": {"$in": list(candidate_ids)}}).to_list(),
        Employee.find({"_id": {"$in": list(employee_ids)}}).to_list(),
    )
    return (
        {candidate.id: candidate for candidate in candidates},
        {employee.id: employee for employee in employees},
    )
