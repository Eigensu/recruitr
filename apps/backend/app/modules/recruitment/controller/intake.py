"""The inbound lead queue.

    GET  /intake/leads/mine          the signed-in telecaller's queue
    POST /intake/leads/{id}/accept   approve the candidate, hand them to a recruiter
    POST /intake/leads/{id}/reject   turn the lead away, with a reason
    POST /intake/leads/{id}/reassign move a lead to someone else  (maintainer+)
    POST /intake/sync                read the sheet now            (admin)

    GET  /intake/analytics/overview     funnel + both SLA clocks   (maintainer+)
    GET  /intake/analytics/telecallers  per-telecaller table       (maintainer+)
    GET  /intake/analytics/recruiters   per-recruiter table        (maintainer+)
    GET  /intake/analytics/campaigns    what the ad spend produced (maintainer+)
    GET  /intake/leads                  every lead, filtered       (maintainer+)
    GET  /intake/leads/{id}             one lead and its timings   (maintainer+)
    GET  /intake/assignees              who a lead can be given to (maintainer+)
    GET  /intake/config                 sheet connection + health  (maintainer+)
    PUT  /intake/config                 point it at a sheet        (admin)

Two dependencies, on purpose. The queue routes take `get_telecaller_tenant`,
which is the only door open to the role: `get_tenant` refuses telecallers
everywhere else, so nothing outside this module has been reviewed for one, and
the decision routes therefore check ownership explicitly — a telecaller may act
only on a lead assigned to them. Everything under the second heading takes plain
`get_tenant` instead, so the same refusal that protects the rest of the app
keeps a telecaller out of the reports about their own response times.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.common.dtos.pagination import PaginationMeta
from app.common.utils.object_id import to_object_id
from app.core.config import settings
from app.core.dependencies import (
    get_telecaller_tenant,
    get_tenant,
    require_admin,
    require_maintainer,
)
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import IntakeLeadStatus
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, IntakeSourceConfig
from app.modules.recruitment.schemas import (
    IntakeAcceptRequest,
    IntakeAssignee,
    IntakeAssigneesResponse,
    IntakeCampaignResponse,
    IntakeConfigResponse,
    IntakeConfigUpdate,
    IntakeLeadPage,
    IntakeLeadResponse,
    IntakeOverviewResponse,
    IntakePersonStats,
    IntakeReassignRequest,
    IntakeRejectRequest,
    IntakeSyncResponse,
    TenantScope,
)
from app.modules.recruitment.service import intake_analytics
from app.modules.recruitment.service.intake_service import (
    accept_lead,
    as_utc,
    assignment_roster,
    poll_google_sheet,
    reassign_lead,
    reject_lead,
)

router = APIRouter()

_Telecaller = Annotated[TenantScope, Depends(get_telecaller_tenant)]
# Plain get_tenant for the admin half: it refuses the telecaller role outright,
# so the reports about a telecaller's response times are closed to them by the
# same rule that closes the rest of the app, not by a second one written here.
_Staff = Annotated[TenantScope, Depends(get_tenant)]
_RequireAdmin = Depends(require_admin)
_RequireMaintainer = Depends(require_maintainer)

_ERR_NOT_FOUND = "Lead not found"

_Since = Annotated[datetime | None, Query(description="Leads ingested on or after this")]
_Until = Annotated[datetime | None, Query(description="Leads ingested on or before this")]


async def _lead_or_404(tenant: TenantScope, lead_id: str) -> IntakeLead:
    lead = await IntakeLead.find_one(
        {"_id": to_object_id(lead_id, "lead_id"), "brand_id": tenant.brand_id}
    )
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_NOT_FOUND)
    return lead


def _own_lead_or_403(tenant: TenantScope, lead: IntakeLead) -> None:
    """A telecaller may only act on their own lead; management may act on any.

    Not folded into the 404 above: an admin working a queue needs to reach every
    lead, and a telecaller reaching for someone else's should hear that it is
    not theirs rather than that it does not exist.
    """
    if tenant.role != UserRole.telecaller:
        return
    if lead.telecaller_id != tenant.employee_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This lead is assigned to another telecaller."
        )


def _pending_or_409(lead: IntakeLead) -> None:
    if lead.status != IntakeLeadStatus.pending_telecaller:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This lead is {lead.status.value.replace('_', ' ')} and cannot be actioned again.",
        )


def _is_overdue(lead: IntakeLead, now: datetime) -> bool:
    """Whether the leg this lead is waiting on has run past its SLA.

    Only the waiting leg counts: a lead with a recruiter is not overdue because
    the telecaller once took two days over it, and a finished lead is never
    overdue however long it took.
    """
    if lead.status == IntakeLeadStatus.pending_telecaller:
        assigned, hours = lead.telecaller_assigned_at, settings.TELECALLER_SLA_HOURS
    elif lead.status == IntakeLeadStatus.pending_recruiter:
        assigned, hours = lead.recruiter_assigned_at, settings.RECRUITER_SLA_HOURS
    else:
        return False
    assigned = as_utc(assigned)  # naive out of Mongo; see intake_service.as_utc
    return assigned is not None and now - assigned > timedelta(hours=hours)


def _to_response(
    lead: IntakeLead,
    candidate: Candidate | None,
    *,
    telecaller: Employee | None = None,
    recruiter: Employee | None = None,
    now: datetime | None = None,
) -> IntakeLeadResponse:
    return IntakeLeadResponse(
        id=str(lead.id),
        status=lead.status,
        candidate_id=str(lead.candidate_id),
        full_name=candidate.full_name if candidate else "(candidate removed)",
        phone=candidate.phone if candidate else None,
        email=candidate.email if candidate else None,
        city=candidate.city if candidate else None,
        current_role=candidate.current_role if candidate else None,
        experience_years=candidate.experience_years if candidate else 0,
        role_interest=candidate.specialization if candidate else None,
        education=candidate.education if candidate else None,
        source_channel=lead.source_channel,
        campaign_name=lead.attribution.campaign_name,
        external_created_at=lead.external_created_at,
        ingested_at=lead.ingested_at,
        telecaller_id=str(lead.telecaller_id) if lead.telecaller_id else None,
        telecaller_assigned_at=lead.telecaller_assigned_at,
        telecaller_actioned_at=lead.telecaller_actioned_at,
        telecaller_decision=lead.telecaller_decision,
        telecaller_reject_reason=lead.telecaller_reject_reason,
        telecaller_notes=lead.telecaller_notes,
        telecaller_response_seconds=lead.telecaller_response_seconds,
        recruiter_id=str(lead.recruiter_id) if lead.recruiter_id else None,
        recruiter_assigned_at=lead.recruiter_assigned_at,
        recruiter_actioned_at=lead.recruiter_actioned_at,
        recruiter_response_seconds=lead.recruiter_response_seconds,
        reassignment_count=lead.reassignment_count,
        telecaller_name=telecaller.name if telecaller else None,
        recruiter_name=recruiter.name if recruiter else None,
        overdue=_is_overdue(lead, now or datetime.now(UTC)),
    )


async def _fetch_response(lead: IntakeLead) -> IntakeLeadResponse:
    """One lead with its candidate fetched. Fine for a single row; the list
    endpoints batch instead, rather than doing this once per row."""
    return _to_response(lead, await Candidate.get(lead.candidate_id))


# ── Queue ──────────────────────────────────────────────────────────────────────


@router.get("/leads/mine", response_model=list[IntakeLeadResponse])
async def my_leads(
    tenant: _Telecaller,
    include_actioned: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    """The signed-in telecaller's queue, oldest assignment first.

    Oldest first because the SLA is measured from assignment: working the list
    top to bottom is then the same thing as working it in the order that keeps
    people inside the day.
    """
    match: dict = {"brand_id": tenant.brand_id, "telecaller_id": tenant.employee_id}
    if not include_actioned:
        match["status"] = IntakeLeadStatus.pending_telecaller.value
    leads = await IntakeLead.find(match).sort("telecaller_assigned_at").limit(limit).to_list()
    candidates, _ = await intake_analytics.people_for(leads)
    now = datetime.now(UTC)
    return [_to_response(lead, candidates.get(lead.candidate_id), now=now) for lead in leads]


# ── Decisions ──────────────────────────────────────────────────────────────────


@router.post("/leads/{lead_id}/accept", response_model=IntakeLeadResponse)
async def accept(tenant: _Telecaller, lead_id: str, payload: IntakeAcceptRequest):
    """Accept a lead: the candidate is approved and passed to a recruiter."""
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    _pending_or_409(lead)

    await accept_lead(lead, notes=payload.notes)
    return await _fetch_response(lead)


@router.post("/leads/{lead_id}/reject", response_model=IntakeLeadResponse)
async def reject(tenant: _Telecaller, lead_id: str, payload: IntakeRejectRequest):
    """Reject a lead. The candidate stays on record, marked REJECTED."""
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    _pending_or_409(lead)

    await reject_lead(lead, reason=payload.reason, notes=payload.notes)
    return await _fetch_response(lead)


# ── Management ─────────────────────────────────────────────────────────────────


@router.post(
    "/leads/{lead_id}/reassign",
    response_model=IntakeLeadResponse,
    dependencies=[_RequireMaintainer],
)
async def reassign(tenant: _Telecaller, lead_id: str, payload: IntakeReassignRequest):
    """Hand a waiting lead to someone else, restarting their SLA clock."""
    lead = await _lead_or_404(tenant, lead_id)
    if lead.status not in (
        IntakeLeadStatus.pending_telecaller,
        IntakeLeadStatus.pending_recruiter,
        IntakeLeadStatus.unassigned,
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This lead is {lead.status.value.replace('_', ' ')} and is nobody's to do.",
        )

    assignee = await Employee.find_one(
        {
            "_id": to_object_id(payload.employee_id, "employee_id"),
            "brand_id": tenant.brand_id,
            "is_active": True,
        }
    )
    if assignee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")

    await reassign_lead(lead, assignee=assignee)
    return await _fetch_response(lead)


@router.post("/sync", response_model=IntakeSyncResponse, dependencies=[_RequireAdmin])
async def sync_now(tenant: _Telecaller) -> IntakeSyncResponse:
    """Read the sheet now instead of waiting for the next scheduled poll.

    Runs inline rather than queueing onto Celery so the caller sees the result,
    including the reason when nothing happened. Ingest is idempotent, so a sync
    racing the scheduled poll duplicates nothing.
    """
    result = await poll_google_sheet()
    if result is None:
        return IntakeSyncResponse(
            ran=False,
            detail=(
                "Lead intake is switched off or not configured. Check "
                "GOOGLE_SHEETS_ENABLED and the intake source configuration."
            ),
        )
    return IntakeSyncResponse(
        ran=True,
        detail=f"Read {result.rows_read} rows.",
        created=result.created,
        matched_existing=result.matched_existing,
        already_ingested=result.already_ingested,
        unusable=result.unusable,
    )


# ── Observability ──────────────────────────────────────────────────────────────


@router.get(
    "/analytics/overview",
    response_model=IntakeOverviewResponse,
    dependencies=[_RequireMaintainer],
)
async def analytics_overview(tenant: _Staff, start_date: _Since = None, end_date: _Until = None):
    """The funnel and both SLA clocks for the leads that arrived in the window.

    A window describes *arrivals*, not activity: these are the leads received
    between the two dates, followed wherever they got to. Counting each leg by
    its own assignment date instead would let a lead be rejected in a window it
    never entered, and the funnel would stop adding up.
    """
    start, end = as_utc(start_date), as_utc(end_date)
    payload = await intake_analytics.cached(
        "overview",
        tenant.brand_id,
        lambda: intake_analytics.overview(tenant.brand_id, start=start, end=end),
        start=start,
        end=end,
    )
    return IntakeOverviewResponse.model_validate(payload)


async def _leg_table(
    tenant: TenantScope, leg: str, start: datetime | None, end: datetime | None
) -> list[IntakePersonStats]:
    rows = await intake_analytics.cached(
        f"{leg}s",
        tenant.brand_id,
        lambda: intake_analytics.leg_by_person(tenant.brand_id, leg=leg, start=start, end=end),
        start=start,
        end=end,
    )
    return [IntakePersonStats.model_validate(row) for row in rows]


@router.get(
    "/analytics/telecallers",
    response_model=list[IntakePersonStats],
    dependencies=[_RequireMaintainer],
)
async def analytics_telecallers(tenant: _Staff, start_date: _Since = None, end_date: _Until = None):
    """Per-telecaller time-to-action, busiest first."""
    return await _leg_table(
        tenant, intake_analytics.TELECALLER, as_utc(start_date), as_utc(end_date)
    )


@router.get(
    "/analytics/recruiters",
    response_model=list[IntakePersonStats],
    dependencies=[_RequireMaintainer],
)
async def analytics_recruiters(tenant: _Staff, start_date: _Since = None, end_date: _Until = None):
    """Per-recruiter time from being handed an accepted lead to first mapping it."""
    return await _leg_table(
        tenant, intake_analytics.RECRUITER, as_utc(start_date), as_utc(end_date)
    )


@router.get(
    "/analytics/campaigns",
    response_model=IntakeCampaignResponse,
    dependencies=[_RequireMaintainer],
)
async def analytics_campaigns(
    tenant: _Staff,
    group_by: Annotated[Literal["campaign", "ad", "form", "channel"], Query()] = "campaign",
    start_date: _Since = None,
    end_date: _Until = None,
):
    """What the ad spend actually produced, grouped however you want to read it.

    The attribution is already on every lead, so this costs one aggregation and
    is the only view that joins "which ad we paid for" to "who got hired".
    """
    start, end = as_utc(start_date), as_utc(end_date)
    rows = await intake_analytics.cached(
        "campaigns",
        tenant.brand_id,
        lambda: intake_analytics.campaigns(
            tenant.brand_id, group_by=group_by, start=start, end=end
        ),
        group_by=group_by,
        start=start,
        end=end,
    )
    return IntakeCampaignResponse(group_by=group_by, rows=rows)


@router.get("/leads", response_model=IntakeLeadPage, dependencies=[_RequireMaintainer])
async def all_leads(
    tenant: _Staff,
    status_filter: Annotated[IntakeLeadStatus | None, Query(alias="status")] = None,
    telecaller_id: Annotated[str | None, Query()] = None,
    recruiter_id: Annotated[str | None, Query()] = None,
    campaign: Annotated[str | None, Query()] = None,
    overdue: Annotated[bool, Query()] = False,
    start_date: _Since = None,
    end_date: _Until = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """Every lead in the brand, newest arrival first.

    Uncached, unlike the aggregations above: this is a working list read with a
    dozen filter combinations, and a five-minute-old answer to "what is overdue
    right now" is worse than making the query.
    """
    leads, total = await intake_analytics.lead_page(
        tenant.brand_id,
        status=status_filter,
        telecaller_id=to_object_id(telecaller_id, "telecaller_id") if telecaller_id else None,
        recruiter_id=to_object_id(recruiter_id, "recruiter_id") if recruiter_id else None,
        campaign=campaign,
        overdue=overdue,
        start=as_utc(start_date),
        end=as_utc(end_date),
        page=page,
        limit=limit,
    )
    candidates, employees = await intake_analytics.people_for(leads)
    now = datetime.now(UTC)
    pages = 0 if total == 0 else (total + limit - 1) // limit
    return IntakeLeadPage(
        items=[
            _to_response(
                lead,
                candidates.get(lead.candidate_id),
                telecaller=employees.get(lead.telecaller_id),
                recruiter=employees.get(lead.recruiter_id),
                now=now,
            )
            for lead in leads
        ],
        meta=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        ),
    )


@router.get(
    "/leads/{lead_id}", response_model=IntakeLeadResponse, dependencies=[_RequireMaintainer]
)
async def one_lead(tenant: _Staff, lead_id: str):
    """One lead with its full timing trail — declared after /leads/mine, which
    would otherwise be swallowed by this path parameter."""
    lead = await _lead_or_404(tenant, lead_id)
    candidates, employees = await intake_analytics.people_for([lead])
    return _to_response(
        lead,
        candidates.get(lead.candidate_id),
        telecaller=employees.get(lead.telecaller_id),
        recruiter=employees.get(lead.recruiter_id),
    )


@router.get("/assignees", response_model=IntakeAssigneesResponse, dependencies=[_RequireMaintainer])
async def assignees(tenant: _Staff):
    """Who a waiting lead can be handed to, and what each of them already holds.

    Drawn from the same roster the round-robin uses, so the picker cannot offer
    somebody the assignment would then refuse. The open-lead count is there
    because handing a stuck lead to whoever already has the longest queue is the
    one move guaranteed not to help.
    """

    async def roster(*, telecallers: bool) -> list[IntakeAssignee]:
        leg = intake_analytics.TELECALLER if telecallers else intake_analytics.RECRUITER
        people = await assignment_roster(tenant.brand_id, telecallers=telecallers)
        load = await intake_analytics.open_lead_counts(tenant.brand_id, leg=leg)
        return [
            IntakeAssignee(
                id=str(person.id),
                name=person.name,
                email=person.email,
                open_leads=load.get(person.id, 0),
            )
            for person in people
        ]

    return IntakeAssigneesResponse(
        telecallers=await roster(telecallers=True),
        recruiters=await roster(telecallers=False),
    )


# ── Configuration ──────────────────────────────────────────────────────────────


def _config_response(config: IntakeSourceConfig | None) -> IntakeConfigResponse:
    """The stored configuration, or what the environment would seed it with.

    An unconfigured brand gets the environment defaults rather than a 404, so
    the settings screen shows what switching the integration on would use
    instead of an empty form.
    """
    common = {
        "credentials_configured": bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON),
        "poll_minutes": settings.INTAKE_POLL_MINUTES,
        "telecaller_sla_hours": settings.TELECALLER_SLA_HOURS,
        "recruiter_sla_hours": settings.RECRUITER_SLA_HOURS,
    }
    if config is None:
        return IntakeConfigResponse(
            configured=False,
            spreadsheet_id=settings.INTAKE_SPREADSHEET_ID,
            sheet_range=settings.INTAKE_SHEET_RANGE,
            default_source_channel="Instagram",
            enabled=settings.GOOGLE_SHEETS_ENABLED,
            **common,
        )
    return IntakeConfigResponse(
        configured=True,
        brand_id=str(config.brand_id),
        spreadsheet_id=config.spreadsheet_id,
        sheet_range=config.sheet_range,
        default_source_channel=config.default_source_channel,
        enabled=config.enabled,
        activated_at=config.activated_at,
        last_synced_at=config.last_synced_at,
        last_success_at=config.last_success_at,
        last_row_count=config.last_row_count,
        last_ingested_count=config.last_ingested_count,
        last_skipped_count=config.last_skipped_count,
        last_error=config.last_error,
        consecutive_failures=config.consecutive_failures,
        **common,
    )


@router.get("/config", response_model=IntakeConfigResponse, dependencies=[_RequireMaintainer])
async def read_config(tenant: _Staff):
    """Which sheet is connected, and how the last read went."""
    return _config_response(await IntakeSourceConfig.find_one({"brand_id": tenant.brand_id}))


@router.put("/config", response_model=IntakeConfigResponse, dependencies=[_RequireAdmin])
async def update_config(tenant: _Staff, payload: IntakeConfigUpdate):
    """Point the integration at a sheet, or switch it on and off.

    Turning it on for the first time stamps `activated_at`, and that stamp is
    never moved again. It is the line between "leads that arrived while we were
    connected", which get assigned and start an SLA clock, and the sheet's
    history, which goes through scripts/backfill_intake_leads.py on purpose.
    Re-stamping on every re-enable would silently skip everything that arrived
    during the outage — exactly the leads someone still has to call.
    """
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    config = await IntakeSourceConfig.find_one({"brand_id": tenant.brand_id})

    if config is None:
        spreadsheet_id = updates.get("spreadsheet_id") or settings.INTAKE_SPREADSHEET_ID
        if not spreadsheet_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A spreadsheet id (or its URL) is required to connect the sheet.",
            )
        config = IntakeSourceConfig(
            brand_id=tenant.brand_id,
            spreadsheet_id=spreadsheet_id,
            sheet_range=updates.get("sheet_range", settings.INTAKE_SHEET_RANGE),
            default_source_channel=updates.get("default_source_channel", "Instagram"),
            enabled=updates.get("enabled", False),
        )
        if config.enabled:
            config.activated_at = datetime.now(UTC)
        await config.insert()
        return _config_response(config)

    if updates.get("enabled") and config.activated_at is None:
        updates["activated_at"] = datetime.now(UTC)
    if updates:
        await config.set(updates)
    return _config_response(config)
