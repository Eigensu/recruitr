"""Telling someone when a lead has been sitting too long.

Two jobs with deliberately different jobs to do:

  - `sweep_breaches` runs **hourly** and raises one in-app notification the
    moment a lead crosses its SLA. Hourly rather than daily because a daily
    sweep could let a breach wait another 24 hours before anyone heard about
    it, which would make a 24-hour SLA mean 48.
  - `build_digests` runs **once a day** and emails a summary of everything
    still overdue. It is the safety net for anything the sweep could not
    deliver, and it reports the current state rather than the moment of
    crossing.

The clock is 24 calendar hours, nights and weekends included: a lead assigned
at 6pm Friday breaches on Saturday evening and says so then. There is no
working-calendar configuration, and if weekend noise turns out to be a real
problem the cheap fix is to delay *delivery* until Monday morning while leaving
the measured times alone — a paused clock would quietly flatter the analytics.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from beanie import PydanticObjectId

from app.core.config import settings
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import IntakeLeadStatus, NotificationKind
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, Notification
from app.modules.recruitment.service.intake_analytics import (
    RECRUITER,
    TELECALLER,
    sla_hours,
)
from app.modules.recruitment.service.intake_service import as_utc

logger = logging.getLogger(__name__)

# Who hears about a breach: the people who can actually do something about it.
# Reassigning a stuck lead is maintainer-gated and so are the intake reports, so
# notifying exactly that set keeps the alert actionable — an alert sent to
# someone with no way to act on it is only noise.
_WATCHER_ROLES = (UserRole.admin.value, UserRole.maintainer.value)

_BREACH_KIND = {
    TELECALLER: NotificationKind.telecaller_sla_breach,
    RECRUITER: NotificationKind.recruiter_sla_breach,
}
_OPEN_STATUS = {
    TELECALLER: IntakeLeadStatus.pending_telecaller,
    RECRUITER: IntakeLeadStatus.pending_recruiter,
}
_LEG_LABEL = {TELECALLER: "telecaller", RECRUITER: "recruiter"}
_UNKNOWN_PERSON = "(unassigned)"


@dataclass
class SweepResult:
    """What one hourly sweep did."""

    breached: int = 0  # leads that crossed their SLA this run
    notified: int = 0  # notification rows written
    by_leg: dict[str, int] = field(default_factory=dict)


@dataclass
class OverdueLead:
    """One late lead, as both the notification and the digest describe it."""

    lead_id: PydanticObjectId
    brand_id: PydanticObjectId
    leg: str
    candidate_name: str
    owner_name: str
    owner_id: PydanticObjectId | None
    hours: int


def _hours_since(assigned: datetime | None, now: datetime) -> int:
    """Whole hours a lead has been waiting. 0 when it was never assigned.

    `as_utc` is not optional here: `assigned` comes straight out of Mongo, which
    returns naive datetimes, and subtracting it from an aware `now` raises
    TypeError rather than guessing a timezone.
    """
    assigned = as_utc(assigned)
    if assigned is None:
        return 0
    return max(0, int((now - assigned).total_seconds() // 3600))


async def _watchers(brand_id: PydanticObjectId) -> list[Employee]:
    return await Employee.find(
        {"brand_id": brand_id, "is_active": True, "role": {"$in": list(_WATCHER_ROLES)}}
    ).to_list()


async def _describe(leads: list[IntakeLead], *, leg: str, now: datetime) -> list[OverdueLead]:
    """Attach the candidate and owner names, in two queries for the whole batch."""
    if not leads:
        return []
    candidate_ids = {lead.candidate_id for lead in leads}
    owner_ids = {
        getattr(lead, f"{leg}_id") for lead in leads if getattr(lead, f"{leg}_id") is not None
    }
    candidates = {
        row.id: row for row in await Candidate.find({"_id": {"$in": list(candidate_ids)}}).to_list()
    }
    owners = {
        row.id: row for row in await Employee.find({"_id": {"$in": list(owner_ids)}}).to_list()
    }

    described = []
    for lead in leads:
        owner_id = getattr(lead, f"{leg}_id")
        owner = owners.get(owner_id)
        candidate = candidates.get(lead.candidate_id)
        described.append(
            OverdueLead(
                lead_id=lead.id,
                brand_id=lead.brand_id,
                leg=leg,
                candidate_name=candidate.full_name if candidate else "(candidate removed)",
                # A lead whose owner has left the company is exactly the one
                # nobody is going to call, so it must still be reportable.
                owner_name=owner.name if owner else _UNKNOWN_PERSON,
                owner_id=owner_id,
                hours=_hours_since(getattr(lead, f"{leg}_assigned_at"), now),
            )
        )
    return described


def _breach_message(item: OverdueLead) -> str:
    who = "a telecaller" if item.leg == TELECALLER else "a recruiter"
    owner = item.owner_name if item.owner_id else who
    action = "called" if item.leg == TELECALLER else "put forward"
    return (
        f"{item.candidate_name} has been waiting {item.hours}h to be {action} "
        f"— past the {sla_hours(item.leg)}h limit, with {owner}."
    )


# ── Hourly sweep ───────────────────────────────────────────────────────────────


async def sweep_breaches(*, now: datetime | None = None) -> SweepResult:
    """Alert on every lead that has just crossed its SLA, once each.

    `*_sla_breached_at` is the dedupe key and is stamped whether or not anyone
    was there to notify: it records that the lead breached, which is a fact
    about the lead rather than about the delivery. A brand with no admins yet
    is covered by the daily digest, which reports what is overdue *now* and so
    does not depend on having caught the moment.
    """
    now = now or datetime.now(UTC)
    result = SweepResult()

    for leg in (TELECALLER, RECRUITER):
        # Deliberately not filtered by brand: this runs on a schedule with no
        # tenant attached and must cover every brand. The cost is that it cannot
        # use the (brand_id, status, *_assigned_at) index, which is fine at this
        # volume — if the collection ever grows enough to matter, loop over the
        # brands and run this query inside the loop rather than adding an index.
        leads = await IntakeLead.find(
            {
                "status": _OPEN_STATUS[leg].value,
                f"{leg}_assigned_at": {"$lt": now - timedelta(hours=sla_hours(leg))},
                f"{leg}_sla_breached_at": None,
            }
        ).to_list()
        if not leads:
            continue

        described = await _describe(leads, leg=leg, now=now)
        rows: list[Notification] = []
        watchers_by_brand: dict[PydanticObjectId, list[Employee]] = {}

        for item in described:
            if item.brand_id not in watchers_by_brand:
                watchers_by_brand[item.brand_id] = await _watchers(item.brand_id)
            rows.extend(
                Notification(
                    brand_id=item.brand_id,
                    employee_id=watcher.id,
                    intake_lead_id=item.lead_id,
                    kind=_BREACH_KIND[leg],
                    message=_breach_message(item),
                )
                for watcher in watchers_by_brand[item.brand_id]
            )

        if rows:
            await Notification.insert_many(rows)
        await IntakeLead.find({"_id": {"$in": [item.lead_id for item in described]}}).update(
            {"$set": {f"{leg}_sla_breached_at": now}}
        )

        result.breached += len(described)
        result.notified += len(rows)
        result.by_leg[leg] = len(described)

    if result.breached:
        logger.info(
            "Intake SLA sweep: %d newly overdue leads, %d notifications",
            result.breached,
            result.notified,
        )
    return result


# ── Daily digest ───────────────────────────────────────────────────────────────


@dataclass
class BrandDigest:
    """One brand's overdue work, ready to be emailed to its admins."""

    brand_id: PydanticObjectId
    recipients: list[str]
    groups: list[dict]  # [{"name", "leg", "leads": [{"name", "hours"}]}]
    total: int
    unassigned: int


async def build_digests(*, now: datetime | None = None) -> list[BrandDigest]:
    """Everything currently overdue, grouped by the person who owes the call.

    Built separately from the sending so the grouping is testable without a
    mail provider, and so a failure to send one brand's mail cannot lose
    another's.
    """
    now = now or datetime.now(UTC)
    overdue: dict[PydanticObjectId, list[OverdueLead]] = defaultdict(list)

    for leg in (TELECALLER, RECRUITER):
        leads = await IntakeLead.find(
            {
                "status": _OPEN_STATUS[leg].value,
                f"{leg}_assigned_at": {"$lt": now - timedelta(hours=sla_hours(leg))},
            }
        ).to_list()
        for item in await _describe(leads, leg=leg, now=now):
            overdue[item.brand_id].append(item)

    digests = []
    for brand_id, items in overdue.items():
        watchers = await _watchers(brand_id)
        if not watchers:
            logger.warning("Intake SLA digest: brand %s has overdue leads and no admins", brand_id)
            continue

        grouped: dict[tuple[str, str], list[OverdueLead]] = defaultdict(list)
        for item in items:
            grouped[(item.owner_name, item.leg)].append(item)

        digests.append(
            BrandDigest(
                brand_id=brand_id,
                recipients=[watcher.email for watcher in watchers if watcher.email],
                groups=[
                    {
                        "name": name,
                        "leg": _LEG_LABEL[leg],
                        # Longest wait first: that is the one to chase.
                        "leads": [
                            {"name": row.candidate_name, "hours": row.hours}
                            for row in sorted(rows, key=lambda row: -row.hours)
                        ],
                    }
                    for (name, leg), rows in sorted(grouped.items(), key=lambda pair: -len(pair[1]))
                ],
                total=len(items),
                unassigned=await IntakeLead.find(
                    {"brand_id": brand_id, "status": IntakeLeadStatus.unassigned.value}
                ).count(),
            )
        )
    return digests


async def send_digests(*, now: datetime | None = None) -> int:
    """Email each brand's admins their overdue list. Returns emails sent.

    Nothing is sent when nothing is overdue. A daily "all clear" is the fastest
    way to teach people to filter the alert away, and then the one that matters
    goes unread too.
    """
    from app.modules.dashboard.services.email_service import EmailService

    sent = 0
    for digest in await build_digests(now=now):
        for email in digest.recipients:
            EmailService.send_intake_sla_digest(
                email=email,
                total=digest.total,
                unassigned=digest.unassigned,
                groups=digest.groups,
                portal_url=f"{settings.FRONTEND_URL}/leads?overdue=true",
            )
            sent += 1
    return sent
