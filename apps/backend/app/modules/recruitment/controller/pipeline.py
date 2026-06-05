"""Pipeline/Kanban board API router — Phase D.

Endpoints:
  GET    /pipeline/board                    kanban board state (all stages + mappings)
  POST   /pipeline/mappings/{id}/move       move mapping to new stage (with activity logging)
"""

from __future__ import annotations

import contextlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant
from app.modules.recruitment.enums import KANBAN_STAGES, PipelineStage
from app.modules.recruitment.models import ActivityLog, Candidate, Mapping, Position
from app.modules.recruitment.schemas import (
    PipelineBoard,
    PipelineStageColumn,
    StageMappingItem,
    StageMoveRequest,
    StageMoveResponse,
    TenantScope,
)

router = APIRouter()

# ── Annotated aliases ──────────────────────────────────────────────────────────

_Tenant = Annotated[TenantScope, Depends(get_tenant)]

# ── Stage labels (matching frontend expectations) ─────────────────────────────

_STAGE_LABELS = {
    PipelineStage.sourced: "Sourced",
    PipelineStage.sent_to_client: "Sent to Client",
    PipelineStage.interview: "Interview",
    PipelineStage.decision_pending: "Decision Pending",
    PipelineStage.offer: "Offer",
    PipelineStage.offer_accepted: "Offer Accepted",
    PipelineStage.position_close: "Joined",
    PipelineStage.rejected: "Rejected",
    PipelineStage.on_hold: "On Hold",
}

# ── Activity type constants ────────────────────────────────────────────────────

_ACTIVITY_STAGE_MOVED = "stage_moved"
_ACTIVITY_OFFER_SENT = "offer_sent"
_ACTIVITY_OFFER_ACCEPTED = "offer_accepted"
_ACTIVITY_JOINED = "joined"
_ACTIVITY_REJECTED = "rejected"

# ── Gamification scoring ───────────────────────────────────────────────────────

_SCORE_MOVED = 0  # No points for moving through stages
_SCORE_OFFER_SENT = (
    0  # Offer sending is tracked separately (POST /positions/{id}/map-candidate = +4)
)
_SCORE_OFFER_ACCEPTED = 8  # Offer accepted = +8
_SCORE_JOINED = 15  # Position closed/joined = +15
_SCORE_REJECTED = -2  # Rejected = -2


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _get_or_404(scope: TenantScope, mapping_id: str) -> Mapping:
    oid = to_object_id(mapping_id, "mapping_id")
    doc = await Mapping.find_one({"_id": oid, "brand_id": scope.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mapping not found")
    return doc


def _score_for_stage(stage: PipelineStage) -> int:
    """Return recruiter score delta for transitioning to a stage."""
    match stage:
        case PipelineStage.offer:
            return _SCORE_OFFER_SENT
        case PipelineStage.offer_accepted:
            return _SCORE_OFFER_ACCEPTED
        case PipelineStage.position_close:
            return _SCORE_JOINED
        case PipelineStage.rejected:
            return _SCORE_REJECTED
        case _:
            return _SCORE_MOVED


def _activity_type_for_stage(stage: PipelineStage) -> str:
    """Return activity type for logging stage transitions."""
    match stage:
        case PipelineStage.offer:
            return _ACTIVITY_OFFER_SENT
        case PipelineStage.offer_accepted:
            return _ACTIVITY_OFFER_ACCEPTED
        case PipelineStage.position_close:
            return _ACTIVITY_JOINED
        case PipelineStage.rejected:
            return _ACTIVITY_REJECTED
        case _:
            return _ACTIVITY_STAGE_MOVED


# ── Board ──────────────────────────────────────────────────────────────────────


@router.get("/board")
async def get_pipeline_board(tenant: _Tenant) -> PipelineBoard:
    """
    Fetch the Kanban board state for this brand.
    Returns all KANBAN_STAGES with their mappings (excludes sourced + terminal stages).
    """
    stages = []

    for stage in KANBAN_STAGES:
        mappings_docs = await Mapping.find(
            {"brand_id": tenant.brand_id, "stage": stage.value}
        ).to_list(None)

        stage_mappings = []
        for m in mappings_docs:
            # Fetch candidate and position details
            cand = await Candidate.find_one({"_id": m.candidate_id})
            pos = await Position.find_one({"_id": m.position_id})

            if cand and pos:
                stage_mappings.append(
                    StageMappingItem(
                        mapping_id=str(m.id),
                        candidate_id=str(cand.id),
                        candidate_name=cand.full_name,
                        candidate_email=cand.email,
                        position_id=str(pos.id),
                        position_code=pos.code,
                        position_role=pos.role,
                        position_client=pos.client_name,
                        stage=stage,
                        match_score=m.match_score,
                        decision=m.decision or "pending",
                        mapped_at=m.mapped_at,
                    )
                )

        stages.append(
            PipelineStageColumn(
                stage=stage,
                label=_STAGE_LABELS[stage],
                count=len(stage_mappings),
                mappings=stage_mappings,
            )
        )

    return PipelineBoard(stages=stages)


# ── Move mapping ───────────────────────────────────────────────────────────────


@router.post("/mappings/{mapping_id}/move")
async def move_mapping_to_stage(
    tenant: _Tenant, mapping_id: str, req: StageMoveRequest
) -> StageMoveResponse:
    """
    Move a mapping to a new stage (Kanban drag-drop).
    Logs activity and awards recruiter points based on stage transition.
    """
    mapping = await _get_or_404(tenant, mapping_id)
    old_stage = mapping.stage

    if old_stage == req.new_stage.value:
        # No-op: already in that stage
        return StageMoveResponse(
            mapping_id=str(mapping.id),
            candidate_id=str(mapping.candidate_id),
            position_id=str(mapping.position_id),
            old_stage=PipelineStage(old_stage),
            new_stage=req.new_stage,
            recruiter_score_delta=0,
        )

    # Update mapping
    await mapping.set({"stage": req.new_stage.value, "decision": "pending"})

    # Calculate recruiter score
    score_delta = _score_for_stage(req.new_stage)

    # Log activity (fire-and-forget, idempotent)
    activity = ActivityLog(
        brand_id=tenant.brand_id,
        employee_id=tenant.employee_id,
        activity_type=_activity_type_for_stage(req.new_stage),
        target_entity_type="mapping",
        target_entity_id=str(mapping.id),
        description=(f"Moved to {_STAGE_LABELS[req.new_stage]}"),
    )
    # Best-effort activity log: if this fails, the stage move still succeeds
    with contextlib.suppress(Exception):
        await activity.insert()

    return StageMoveResponse(
        mapping_id=str(mapping.id),
        candidate_id=str(mapping.candidate_id),
        position_id=str(mapping.position_id),
        old_stage=PipelineStage(old_stage),
        new_stage=req.new_stage,
        decision=mapping.decision or "pending",
        recruiter_score_delta=score_delta,
        activity_id=str(activity.id) if activity else None,
    )
