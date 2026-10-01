"""The inbound lead queue.

    GET  /intake/leads/mine            the signed-in telecaller's queue
    GET  /intake/leads/{id}/candidate  what we hold on them, to prefill the form
    GET  /intake/role-catalog          department → roles, for the form's dropdowns
    POST /intake/leads/{id}/accept     save the form, send the lead to review
    POST /intake/leads/{id}/reject     turn the lead away, with a reason
    POST /intake/leads/assign-team     reviewed leads → a team's round-robin (maintainer+)
    GET  /intake/teams                 teams a reviewer can assign to     (maintainer+)
    POST /intake/leads/{id}/reassign   move a lead to someone else        (maintainer+)
    POST /intake/sync                  read the sheet now                 (admin)

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

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

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
from app.modules.brands.service import get_automation_settings
from app.modules.recruitment.enums import IntakeLeadStatus, IntakeSource
from app.modules.recruitment.models import (
    Candidate,
    Employee,
    IntakeLead,
    IntakeSourceConfig,
    Team,
)
from app.modules.recruitment.schemas import (
    IntakeAcceptRequest,
    IntakeAssignee,
    IntakeAssigneesResponse,
    IntakeAssignTeamRequest,
    IntakeAssignTeamResponse,
    IntakeCampaignResponse,
    IntakeCandidateDraft,
    IntakeConfigResponse,
    IntakeConfigUpdate,
    IntakeLeadPage,
    IntakeLeadResponse,
    IntakeOverviewResponse,
    IntakePersonStats,
    IntakeReassignRequest,
    IntakeRejectRequest,
    IntakeSyncResponse,
    IntakeTeamOption,
    ManualLeadsResponse,
    NaukriImportResponse,
    NaukriPreviewResponse,
    NaukriPreviewRow,
    NaukriSkippedRow,
    ResumeLeadDraft,
    TenantScope,
)
from app.modules.recruitment.service import intake_analytics
from app.modules.recruitment.service.intake_service import (
    LeadAlreadyDecided,
    TeamHasNoRecruiters,
    accept_lead,
    as_utc,
    assign_to_team,
    assignment_roster,
    ingest_leads,
    plan_ingest,
    poll_google_sheet,
    reassign_lead,
    reject_lead,
    team_roster,
    waiting_on_recruiter,
)
from app.modules.recruitment.service.lead_entry import (
    ResumeFile,
    add_manual_leads,
    check_resume,
    drafts_from_resumes,
)
from app.modules.recruitment.utils.constants import (
    RESUME_BATCH_MAX_FILES,
    RESUME_MAX_BYTES,
    ROLES_BY_CATEGORY,
)
from app.modules.recruitment.utils.naukri_sheet import (
    NaukriFileError,
    NaukriRows,
    parse_naukri_xlsx,
    warnings_for,
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


def _already_decided() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, "Someone else actioned this lead a moment ago. Reload to see it."
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
    team_name: str | None = None,
    now: datetime | None = None,
) -> IntakeLeadResponse:
    return IntakeLeadResponse(
        id=str(lead.id),
        status=lead.status,
        source=lead.source,
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
        team_id=str(lead.team_id) if lead.team_id else None,
        team_name=team_name,
        reviewed_at=lead.reviewed_at,
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


async def _team_names(brand_id) -> dict:
    """Every team in the brand by id. A brand has a handful, so one query for
    all of them beats a lookup per row."""
    return {team.id: team.name for team in await Team.find({"brand_id": brand_id}).to_list()}


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


@router.get("/leads/{lead_id}/candidate", response_model=IntakeCandidateDraft)
async def lead_candidate(tenant: _Telecaller, lead_id: str):
    """What we already hold on this person, to prefill the accept form.

    Through the telecaller door, not /candidates/{id}: that endpoint is refused
    to the role, and opening it would expose the whole directory. This returns
    one candidate, and only the one on a lead the caller owns.
    """
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    candidate = await Candidate.get(lead.candidate_id)
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    fields = IntakeCandidateDraft.model_fields.keys() - {"has_resume"}
    return IntakeCandidateDraft(
        **candidate.model_dump(include=set(fields), mode="json"),
        has_resume=bool(candidate.resume_url),
    )


@router.get("/role-catalog")
async def role_catalog(_: _Telecaller) -> dict[str, list[str]]:
    """Department → roles, for the accept form's role dropdown.

    The same data as GET /positions/role-catalog, which telecallers are refused
    along with the rest of the positions module.
    """
    return {dept.value: roles for dept, roles in ROLES_BY_CATEGORY.items()}


# ── Decisions ──────────────────────────────────────────────────────────────────


@router.post("/leads/{lead_id}/accept", response_model=IntakeLeadResponse)
async def accept(tenant: _Telecaller, lead_id: str, payload: IntakeAcceptRequest):
    """Accept a lead with the details from the call; it then waits for review."""
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    _pending_or_409(lead)

    try:
        await accept_lead(lead, details=payload.details, notes=payload.notes)
    except LeadAlreadyDecided:
        raise _already_decided() from None
    return await _fetch_response(lead)


@router.post("/leads/{lead_id}/reject", response_model=IntakeLeadResponse)
async def reject(tenant: _Telecaller, lead_id: str, payload: IntakeRejectRequest):
    """Reject a lead. The candidate stays on record, marked REJECTED."""
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    _pending_or_409(lead)

    try:
        await reject_lead(lead, reason=payload.reason, notes=payload.notes)
    except LeadAlreadyDecided:
        raise _already_decided() from None
    return await _fetch_response(lead)


# ── Review ─────────────────────────────────────────────────────────────────────


@router.get("/teams", response_model=list[IntakeTeamOption], dependencies=[_RequireMaintainer])
async def review_teams(tenant: _Staff):
    """Active teams a reviewer can assign to, with who is on them and how busy.

    A team with no recruiters is still listed, with zero, so the reviewer sees
    why it cannot take a lead rather than wondering where it went.
    """
    teams = await Team.find({"brand_id": tenant.brand_id, "is_active": True}).sort("name").to_list()
    load = await intake_analytics.open_leads_by_team(tenant.brand_id)
    return [
        IntakeTeamOption(
            id=str(team.id),
            name=team.name,
            recruiters=len(await team_roster(tenant.brand_id, team.id)),
            open_leads=load.get(team.id, 0),
        )
        for team in teams
    ]


@router.post(
    "/leads/assign-team",
    response_model=IntakeAssignTeamResponse,
    dependencies=[_RequireMaintainer],
)
async def assign_team(tenant: _Staff, payload: IntakeAssignTeamRequest):
    """Hand reviewed leads to a team; the team's round-robin picks each recruiter.

    Leads that are no longer awaiting review are reported back as skipped rather
    than failing the batch: with two reviewers on the same list, part of a
    selection being taken a moment earlier is normal.
    """
    team = await Team.find_one(
        {
            "_id": to_object_id(payload.team_id, "team_id"),
            "brand_id": tenant.brand_id,
            "is_active": True,
        }
    )
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    ids = list(dict.fromkeys(to_object_id(lead_id, "lead_id") for lead_id in payload.lead_ids))
    leads = await IntakeLead.find({"_id": {"$in": ids}, "brand_id": tenant.brand_id}).to_list()
    by_id = {lead.id: lead for lead in leads}
    ordered = [by_id[lead_id] for lead_id in ids if lead_id in by_id]

    try:
        assigned, skipped = await assign_to_team(ordered, team=team, reviewer_id=tenant.employee_id)
    except TeamHasNoRecruiters:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{team.name} has no active recruiters. Add someone to the team first.",
        ) from None

    candidates, employees = await intake_analytics.people_for(assigned)
    now = datetime.now(UTC)
    missing = [str(lead_id) for lead_id in ids if lead_id not in by_id]
    return IntakeAssignTeamResponse(
        assigned=[
            _to_response(
                lead,
                candidates.get(lead.candidate_id),
                telecaller=employees.get(lead.telecaller_id),
                recruiter=employees.get(lead.recruiter_id),
                team_name=team.name,
                now=now,
            )
            for lead in assigned
        ],
        skipped=[str(lead.id) for lead in skipped] + missing,
    )


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

    # The same roster the picker offers, for the leg this lead is waiting on:
    # any active employee would let a recruiter own a telecaller queue they
    # cannot open, or a telecaller own a recruiter's lead.
    roster = await assignment_roster(tenant.brand_id, telecallers=not waiting_on_recruiter(lead))
    target = to_object_id(payload.employee_id, "employee_id")
    assignee = next((person for person in roster if person.id == target), None)
    if assignee is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "That person cannot take this lead."
        )

    try:
        await reassign_lead(lead, assignee=assignee)
    except LeadAlreadyDecided:
        raise _already_decided() from None
    return await _fetch_response(lead)


@router.post("/sync", dependencies=[_RequireAdmin])
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


# ── Naukri import ──────────────────────────────────────────────────────────────
# Any staff member may import (recruiters included); telecallers and clients are
# refused by get_tenant like everywhere else. Imported people go through the
# same ingest as the Meta sheet, so they land in the telecaller queue.

_NAUKRI_MAX_BYTES = 5 * 1024 * 1024
_NaukriFile = Annotated[UploadFile, File(description="Naukri candidate export (.xlsx)")]


async def _read_naukri(upload: UploadFile) -> NaukriRows:
    if not (upload.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload the .xlsx file Naukri exported.")
    data = await upload.read(_NAUKRI_MAX_BYTES + 1)
    if len(data) > _NAUKRI_MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "That file is over 5 MB. Export fewer candidates at a time.",
        )
    try:
        return parse_naukri_xlsx(data)
    except NaukriFileError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


@router.post("/imports/naukri/preview", response_model=NaukriPreviewResponse)
async def preview_naukri_import(tenant: _Staff, file: _NaukriFile) -> NaukriPreviewResponse:
    """What importing this export would do, row by row. Writes nothing.

    Classified by plan_ingest — the same checks, in the same order, as the
    import itself — so the preview can't promise something the import won't do.
    """
    parsed = await _read_naukri(file)
    plan = await plan_ingest(parsed.leads, brand_id=tenant.brand_id)
    return NaukriPreviewResponse(
        rows=[
            NaukriPreviewRow(
                row_number=row_number,
                full_name=lead.full_name,
                phone=lead.phone,
                email=lead.email,
                city=lead.city,
                designation=lead.current_role,
                current_company=lead.previous_company,
                experience_years=lead.experience_years,
                salary=lead.salary,
                outcome=outcome,
                warnings=warnings_for(lead),
            )
            for row_number, lead, outcome in zip(
                parsed.lead_rows, parsed.leads, plan.outcomes, strict=True
            )
        ],
        skipped=[
            NaukriSkippedRow(row_number=s.row_number, reason=s.reason) for s in parsed.skipped
        ],
        new=plan.new,
        matched_existing=plan.matched_existing,
        already_ingested=plan.already_ingested,
        duplicate_in_sheet=plan.duplicate_in_sheet,
    )


@router.post("/imports/naukri", response_model=NaukriImportResponse)
async def import_naukri(tenant: _Staff, file: _NaukriFile) -> NaukriImportResponse:
    """Import the export: each new person becomes a lead in the telecaller queue.

    Idempotent: a row's lead id is its phone number, so uploading the same
    export twice, or a later one that repeats people, creates nothing new.
    Telecaller SLA clocks start now, for every lead created.
    """
    parsed = await _read_naukri(file)
    result = await ingest_leads(
        parsed.leads,
        brand_id=tenant.brand_id,
        source=IntakeSource.naukri_import,
        submitted_by_id=tenant.employee_id,
    )
    return NaukriImportResponse(
        rows_read=result.rows_read + len(parsed.skipped),
        created=result.created,
        assigned=result.assigned,
        unassigned=result.unassigned,
        matched_existing=result.matched_existing,
        already_ingested=result.already_ingested,
        repeated_in_file=result.repeated_in_batch,
        unusable=len(parsed.skipped),
        errors=result.errors,
    )


# ── Leads added by hand or from resumes ───────────────────────────────────────
# Same access as the Naukri import. Parsing stores nothing; submitting goes
# through the same ingest, so these leads also start in the telecaller queue.

_ResumeFiles = Annotated[list[UploadFile], File(description="PDF or Word resumes")]


def _too_many(count: int, what: str) -> None:
    if count > RESUME_BATCH_MAX_FILES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"At most {RESUME_BATCH_MAX_FILES} {what} at a time — you sent {count}.",
        )


async def _read_resumes(uploads: list[UploadFile]) -> list[ResumeFile]:
    """Each file read to one byte past the cap, so an oversize file fails alone."""
    _too_many(len(uploads), "resumes")
    return [
        check_resume(upload.filename or "resume", await upload.read(RESUME_MAX_BYTES + 1))
        for upload in uploads
    ]


@router.post("/leads/parse-resumes", response_model=list[ResumeLeadDraft])
async def parse_resumes(tenant: _Staff, files: _ResumeFiles) -> list[ResumeLeadDraft]:
    """Read resumes into lead drafts for a person to check. Saves and uploads nothing."""
    resumes = await _read_resumes(files)
    return await drafts_from_resumes(resumes, await get_automation_settings(tenant.brand_id))


@router.post("/leads/manual", response_model=ManualLeadsResponse)
async def add_leads(
    tenant: _Staff,
    drafts: Annotated[str, Form(description="JSON list of ManualLeadDraft")],
    files: Annotated[list[UploadFile] | None, File(description="Resumes, by resume_index")] = None,
) -> ManualLeadsResponse:
    """Add checked drafts as leads. Each draft succeeds or fails on its own.

    Multipart rather than JSON so the resumes travel with the drafts that name
    them; a draft's `resume_index` points into `files`.
    """
    try:
        raw = json.loads(drafts)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "drafts must be a JSON list.") from None
    if not isinstance(raw, list) or not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "drafts must be a non-empty JSON list.")
    _too_many(len(raw), "leads")
    resumes = await _read_resumes(files or [])
    return await add_manual_leads(
        raw,
        resumes,
        brand_id=tenant.brand_id,
        submitted_by_id=tenant.employee_id,
        automation=await get_automation_settings(tenant.brand_id),
    )


# Declared before /leads/{lead_id}, which would otherwise swallow "submitted".
@router.get("/leads/submitted", response_model=list[IntakeLeadResponse])
async def my_submitted_leads(
    tenant: _Staff, limit: Annotated[int, Query(ge=1, le=500)] = 200
) -> list[IntakeLeadResponse]:
    """Leads the caller put in themselves, newest first, and where each one is now."""
    leads = (
        await IntakeLead.find({"brand_id": tenant.brand_id, "submitted_by_id": tenant.employee_id})
        .sort("-ingested_at")
        .limit(limit)
        .to_list()
    )
    candidates, employees = await intake_analytics.people_for(leads)
    teams = await _team_names(tenant.brand_id)
    now = datetime.now(UTC)
    return [
        _to_response(
            lead,
            candidates.get(lead.candidate_id),
            telecaller=employees.get(lead.telecaller_id),
            recruiter=employees.get(lead.recruiter_id),
            team_name=teams.get(lead.team_id),
            now=now,
        )
        for lead in leads
    ]


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
    teams = await _team_names(tenant.brand_id)
    now = datetime.now(UTC)
    pages = 0 if total == 0 else (total + limit - 1) // limit
    return IntakeLeadPage(
        items=[
            _to_response(
                lead,
                candidates.get(lead.candidate_id),
                telecaller=employees.get(lead.telecaller_id),
                recruiter=employees.get(lead.recruiter_id),
                team_name=teams.get(lead.team_id),
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
    teams = await _team_names(tenant.brand_id)
    return _to_response(
        lead,
        candidates.get(lead.candidate_id),
        telecaller=employees.get(lead.telecaller_id),
        recruiter=employees.get(lead.recruiter_id),
        team_name=teams.get(lead.team_id),
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
