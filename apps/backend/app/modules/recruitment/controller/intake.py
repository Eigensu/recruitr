"""The inbound lead queue.

    GET  /intake/leads/mine          the signed-in telecaller's queue
    POST /intake/leads/{id}/accept   approve the candidate, hand them to a recruiter
    POST /intake/leads/{id}/reject   turn the lead away, with a reason
    POST /intake/leads/{id}/reassign move a lead to someone else  (maintainer+)
    POST /intake/sync                read the sheet now            (admin)

Every route here is reachable by a telecaller, which makes this the one place
that has to be careful about it: `get_tenant` refuses the role everywhere else,
so nothing outside this module has been reviewed for a telecaller caller.
The decision routes therefore check ownership explicitly — a telecaller may act
only on a lead assigned to them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.common.utils.object_id import to_object_id
from app.core.dependencies import get_telecaller_tenant, require_admin, require_maintainer
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import IntakeLeadStatus
from app.modules.recruitment.models import Candidate, Employee, IntakeLead
from app.modules.recruitment.schemas import (
    IntakeAcceptRequest,
    IntakeLeadResponse,
    IntakeReassignRequest,
    IntakeRejectRequest,
    IntakeSyncResponse,
    TenantScope,
)
from app.modules.recruitment.service.intake_service import (
    accept_lead,
    poll_google_sheet,
    reassign_lead,
    reject_lead,
)

router = APIRouter()

_Telecaller = Annotated[TenantScope, Depends(get_telecaller_tenant)]
_RequireAdmin = Depends(require_admin)
_RequireMaintainer = Depends(require_maintainer)

_ERR_NOT_FOUND = "Lead not found"


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


async def _to_response(lead: IntakeLead) -> IntakeLeadResponse:
    candidate = await Candidate.get(lead.candidate_id)
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
    )


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
    return [await _to_response(lead) for lead in leads]


# ── Decisions ──────────────────────────────────────────────────────────────────


@router.post("/leads/{lead_id}/accept", response_model=IntakeLeadResponse)
async def accept(tenant: _Telecaller, lead_id: str, payload: IntakeAcceptRequest):
    """Accept a lead: the candidate is approved and passed to a recruiter."""
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    _pending_or_409(lead)

    await accept_lead(lead, notes=payload.notes)
    return await _to_response(lead)


@router.post("/leads/{lead_id}/reject", response_model=IntakeLeadResponse)
async def reject(tenant: _Telecaller, lead_id: str, payload: IntakeRejectRequest):
    """Reject a lead. The candidate stays on record, marked REJECTED."""
    lead = await _lead_or_404(tenant, lead_id)
    _own_lead_or_403(tenant, lead)
    _pending_or_409(lead)

    await reject_lead(lead, reason=payload.reason, notes=payload.notes)
    return await _to_response(lead)


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
    return await _to_response(lead)


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
