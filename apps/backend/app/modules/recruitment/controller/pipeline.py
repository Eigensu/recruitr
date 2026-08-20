"""Pipeline/Kanban board API router — Phase D.

Endpoints:
  GET    /pipeline/board                    kanban board state (all stages + mappings)
  POST   /pipeline/mappings/{id}/move       move mapping to new stage (with activity logging)
  GET    /pipeline/filtered                 Kanban view filtered by position (frontend board)
  GET    /pipeline/top-candidates           keyword-scored candidate suggestions
  PATCH  /pipeline/match                    assign/move a candidate onto a position
"""

from __future__ import annotations

import contextlib
import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant, get_viewer
from app.modules.recruitment.enums import (
    KANBAN_STAGES,
    TERMINAL_STAGES,
    CandidateEventType,
    Decision,
    PipelineStage,
)
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    Mapping,
    Position,
    StageEvent,
)
from app.modules.recruitment.repository_impl import (
    move_stage,
    recompute_position_seats,
    record_candidate_event,
)
from app.modules.recruitment.schemas import (
    PipelineBoard,
    PipelineCandidateDroppedRequest,
    PipelineSetInterviewRequest,
    PipelineSetJoiningRequest,
    PipelineStageColumn,
    PipelineUploadOfferRequest,
    StageMappingItem,
    StageMoveRequest,
    StageMoveResponse,
    TenantScope,
)
from app.modules.recruitment.utils.cv_access import mask_cv_rows
from app.modules.recruitment.utils.scoping import scope_mapping_match

router = APIRouter()

# ── Annotated aliases ──────────────────────────────────────────────────────────

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
# Staff or client. Only for reads that narrow their query by the scope.
_Viewer = Annotated[TenantScope, Depends(get_viewer)]
_ERR_POSITION_NOT_FOUND = "Position not found"

# ── Frontend-facing DTOs (not part of the core recruitment schemas) ────────────


class FilteredCandidate(BaseModel):
    """Candidate row for the Kanban filtered view (3-column board)."""

    id: str
    name: str
    email: str
    phone: str | None = None
    resume_url: str | None = None
    extracted_skills: list[str] = []
    tags: list[str] = []
    source: str = "internal"
    cv_link: str | None = None
    created_by_id: str | None = None
    # True when the CV was withheld because another recruiter sourced this
    # candidate — see recruitment/utils/cv_access.py.
    cv_locked: bool = False
    status: Literal["pending", "accepted", "rejected"] = "pending"


class SuggestedCandidate(BaseModel):
    """Candidate row for the top-candidates suggestion panel."""

    id: str
    name: str
    email: str
    resume_url: str | None = None
    extracted_skills: list[str] = []
    tags: list[str] = []
    source: str = "internal"
    cv_link: str | None = None
    created_by_id: str | None = None
    cv_locked: bool = False
    match_score: float


class MatchRequest(BaseModel):
    position_id: str
    candidate_id: str
    target_status: Literal["pending", "accepted", "rejected"] = "pending"


class MatchResponse(BaseModel):
    position_id: str
    candidate_id: str
    status: str
    recruiter_daily_score: int = 0


# ── Stage labels (matching frontend expectations) ─────────────────────────────

_STAGE_LABELS = {
    PipelineStage.sourced: "Sourced",
    PipelineStage.sent_to_client: "Sent to Client",
    PipelineStage.interview: "Interview",
    PipelineStage.selected: "Selected",
    PipelineStage.joined: "Joined",
    PipelineStage.rejected: "Rejected",
    PipelineStage.on_hold: "On Hold",
    PipelineStage.candidate_dropped: "Candidate Dropped",
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
    from app.modules.recruitment.utils.scoping import scope_mapping_match

    oid = to_object_id(mapping_id, "mapping_id")
    match = await scope_mapping_match(scope, {"_id": oid, "brand_id": scope.brand_id})
    doc = await Mapping.find_one(match)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mapping not found")
    return doc


def _score_for_stage(stage: PipelineStage) -> int:
    """Return recruiter score delta for transitioning to a stage."""
    match stage:
        case PipelineStage.selected:
            return _SCORE_OFFER_ACCEPTED
        case PipelineStage.joined:
            return _SCORE_JOINED
        case PipelineStage.rejected:
            return _SCORE_REJECTED
        case _:
            return _SCORE_MOVED


def _activity_type_for_stage(stage: PipelineStage) -> str:
    """Return activity type for logging stage transitions."""
    match stage:
        case PipelineStage.selected:
            return _ACTIVITY_OFFER_ACCEPTED
        case PipelineStage.joined:
            return _ACTIVITY_JOINED
        case PipelineStage.rejected:
            return _ACTIVITY_REJECTED
        case _:
            return _ACTIVITY_STAGE_MOVED


# ── Board ──────────────────────────────────────────────────────────────────────


@router.get("/board")
async def get_pipeline_board(viewer: _Viewer) -> PipelineBoard:
    """
    Fetch the Kanban board state for this brand.
    Uses a single aggregation with $lookup to avoid N+1 queries.

    A client sees only their own employer's cards.
    """
    kanban_stage_values = [s.value for s in KANBAN_STAGES]

    board_match = await scope_mapping_match(
        viewer, {"brand_id": viewer.brand_id, "stage": {"$in": kanban_stage_values}}
    )

    agg = [
        {_MATCH: board_match},
        {
            _LOOKUP: {
                "from": "candidates",
                "localField": "candidate_id",
                "foreignField": "_id",
                "as": "cand",
            }
        },
        {_UNWIND: "$cand"},
        {
            _LOOKUP: {
                "from": "positions",
                "localField": "position_id",
                "foreignField": "_id",
                "as": "pos",
            }
        },
        {_UNWIND: "$pos"},
        {
            _PROJECT: {
                "mapping_id": {_TO_STR: "$_id"},
                "candidate_id": {_TO_STR: "$candidate_id"},
                "candidate_name": "$cand.full_name",
                "candidate_email": "$cand.email",
                "position_id": {_TO_STR: "$position_id"},
                "position_code": "$pos.code",
                "position_role": "$pos.role",
                "position_client": "$pos.client_name",
                "employee_id": {_TO_STR: "$employee_id"},
                "stage": 1,
                "match_score": 1,
                "decision": 1,
                "mapped_at": 1,
                "history": 1,
                "interview_date": 1,
                "joining_date": 1,
                "offer_letter_url": 1,
                "salary_offered": 1,
                "dropped_notes": 1,
            }
        },
    ]

    rows = await (await Mapping.get_motor_collection().aggregate(agg)).to_list(length=None)

    # Group rows into stage columns
    stage_map: dict[str, list[StageMappingItem]] = {s.value: [] for s in KANBAN_STAGES}
    for row in rows:
        stage_val = row.get("stage")
        if stage_val not in stage_map:
            continue
        stage_map[stage_val].append(
            StageMappingItem(
                mapping_id=row["mapping_id"],
                candidate_id=row["candidate_id"],
                candidate_name=row["candidate_name"],
                candidate_email=row["candidate_email"],
                position_id=row["position_id"],
                position_code=row["position_code"],
                position_role=row["position_role"],
                position_client=row["position_client"],
                employee_id=row.get("employee_id"),
                stage=PipelineStage(stage_val),
                match_score=row.get("match_score"),
                decision=row.get("decision", "pending"),
                mapped_at=row.get("mapped_at", row["_id"].generation_time),
                stage_entered_at=row.get("history")[-1].get("at")
                if row.get("history")
                else row.get("mapped_at", row["_id"].generation_time),
                interview_date=row.get("interview_date"),
                joining_date=row.get("joining_date"),
                offer_letter_url=row.get("offer_letter_url"),
                salary_offered=row.get("salary_offered"),
                dropped_notes=row.get("dropped_notes"),
            )
        )

    return PipelineBoard(
        stages=[
            PipelineStageColumn(
                stage=stage,
                label=_STAGE_LABELS[stage],
                count=len(stage_map[stage.value]),
                mappings=stage_map[stage.value],
            )
            for stage in KANBAN_STAGES
        ]
    )


# ── Move mapping ───────────────────────────────────────────────────────────────


@router.post("/mappings/{mapping_id}/move")
async def move_mapping_to_stage(
    viewer: _Viewer, mapping_id: str, req: StageMoveRequest
) -> StageMoveResponse:
    """
    Move a mapping to a new stage (Kanban drag-drop).
    Logs activity and awards recruiter points based on stage transition.
    """
    mapping = await _get_or_404(viewer, mapping_id)
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

    from app.modules.auth.models import UserRole

    if viewer.role == UserRole.client:
        allowed_transitions = {
            PipelineStage.sent_to_client.value: [PipelineStage.interview, PipelineStage.rejected],
            PipelineStage.interview.value: [PipelineStage.selected, PipelineStage.rejected],
        }
        if req.new_stage not in allowed_transitions.get(old_stage, []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid stage transition for client")

    # Through the repository rather than a bare mapping.set(): that shortcut
    # skipped the mapping's own stage history, the permanent candidate history,
    # and the denormalized candidate.current_stage, so a card dragged across the
    # board left no trace anywhere once the board was next re-arranged.
    await move_stage(
        mapping=mapping,
        new_stage=req.new_stage,
        decision=Decision.pending,
        scope=viewer,
    )

    # move_stage already recomputes seats on the way *into* a terminal stage;
    # this covers dragging a card back out of one.
    if req.new_stage not in TERMINAL_STAGES and old_stage in TERMINAL_STAGES:
        await recompute_position_seats(mapping.position_id)

    # Calculate recruiter score
    score_delta = _score_for_stage(req.new_stage)

    # Log activity (fire-and-forget, idempotent)
    activity = ActivityLog(
        brand_id=viewer.brand_id,
        employee_id=viewer.employee_id,
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


# ── Aggregation helpers ────────────────────────────────────────────────────────

_MATCH = "$match"
_IF_NULL = "$ifNull"
_LOOKUP = "$lookup"
_UNWIND = "$unwind"
_PROJECT = "$project"
_TO_STR = "$toString"

# ── Filtered pipeline (Kanban board for a position) ────────────────────────────

_PosId = Annotated[str, Query(...)]
_OptStr = Annotated[str | None, Query()]
_OptStrList = Annotated[list[str] | None, Query()]
_OptDt = Annotated[datetime | None, Query()]
_LimitQ = Annotated[int, Query(ge=1, le=50)]


@router.get("/filtered")
async def get_filtered_pipeline(
    viewer: _Viewer,
    position_id: _PosId,
    recruiter_id: _OptStr = None,
    client_id: _OptStr = None,
    tags: _OptStrList = None,
    stage: _OptStr = None,
    mapped_after: _OptDt = None,
    mapped_before: _OptDt = None,
) -> list[FilteredCandidate]:
    """Return all mapped candidates for a position grouped into 3 Kanban columns."""
    pos_oid = to_object_id(position_id, "position_id")

    # Confirm the position is one the caller may see before reading its
    # pipeline; for staff this is the brand check, for a client also the
    # employer check.
    owns = await Position.find_one(viewer.scoped({"_id": pos_oid, "brand_id": viewer.brand_id}))
    if not owns:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_POSITION_NOT_FOUND)

    mapping_match: dict = {"brand_id": viewer.brand_id, "position_id": pos_oid}
    if recruiter_id:
        mapping_match["employee_id"] = to_object_id(recruiter_id, "recruiter_id")
    if client_id:
        mapping_match["client_id"] = to_object_id(client_id, "client_id")
    if stage:
        mapping_match["stage"] = stage
    if mapped_after or mapped_before:
        date_filter: dict = {}
        if mapped_after:
            date_filter["$gte"] = mapped_after
        if mapped_before:
            date_filter["$lte"] = mapped_before
        mapping_match["mapped_at"] = date_filter

    agg: list[dict] = [
        {_MATCH: mapping_match},
        {
            _LOOKUP: {
                "from": "candidates",
                "localField": "candidate_id",
                "foreignField": "_id",
                "as": "candidate",
            }
        },
        {_UNWIND: "$candidate"},
    ]

    if tags:
        # Stored tags keep their canonical casing, so match case-insensitively.
        patterns = [re.compile(f"^{re.escape(t)}$", re.IGNORECASE) for t in tags]
        agg.append({_MATCH: {"candidate.tags": {"$all": patterns}}})

    agg.append(
        {
            _PROJECT: {
                "_id": 0,
                "id": {_TO_STR: "$candidate._id"},
                "name": "$candidate.full_name",
                "email": "$candidate.email",
                "phone": "$candidate.phone",
                "resume_url": "$candidate.resume_url",
                "extracted_skills": {"$ifNull": ["$candidate.skills", []]},
                "tags": {"$ifNull": ["$candidate.tags", []]},
                "source": {"$ifNull": ["$candidate.source", "internal"]},
                "cv_link": "$candidate.cv_link",
                "created_by_id": {_TO_STR: "$candidate.created_by_id"},
                "status": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {
                                    "$in": [
                                        "$stage",
                                        [
                                            PipelineStage.selected.value,
                                            PipelineStage.joined.value,
                                        ],
                                    ]
                                },
                                "then": "accepted",
                            },
                            {
                                "case": {"$in": ["$stage", [PipelineStage.rejected.value]]},
                                "then": "rejected",
                            },
                        ],
                        "default": "pending",
                    }
                },
            }
        }
    )

    rows = await (await Mapping.get_motor_collection().aggregate(agg)).to_list(length=None)
    return [FilteredCandidate(**r) for r in mask_cv_rows(rows, viewer)]


# ── Top candidates (keyword match scoring) ─────────────────────────────────────


@router.get("/top-candidates")
async def get_top_candidates(
    tenant: _Tenant,
    position_id: str = Query(...),
    limit: int = Query(10, ge=1, le=50),
) -> list[SuggestedCandidate]:
    """Return top N candidates scored by skill overlap with a position's requirements."""
    pos_oid = to_object_id(position_id, "position_id")
    position = await Position.find_one({"_id": pos_oid, "brand_id": tenant.brand_id})
    if not position:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")

    job_keywords = position.requirements  # already stored lowercased

    agg: list[dict] = [
        {_MATCH: {"brand_id": tenant.brand_id, "is_active": True}},
        {
            "$addFields": {
                "match_score": {
                    "$cond": {
                        "if": {"$gt": [len(job_keywords), 0]},
                        "then": {
                            "$divide": [
                                {
                                    "$size": {
                                        "$setIntersection": ["$skills_normalized", job_keywords]
                                    }
                                },
                                len(job_keywords),
                            ]
                        },
                        "else": 0,
                    }
                }
            }
        },
        {"$sort": {"match_score": -1}},
        {"$limit": limit},
        {
            _PROJECT: {
                "id": {_TO_STR: "$_id"},
                "name": "$full_name",
                "email": 1,
                "resume_url": 1,
                "extracted_skills": {"$ifNull": ["$skills", []]},
                "tags": {"$ifNull": ["$tags", []]},
                "source": "internal",
                "cv_link": None,
                "created_by_id": {_TO_STR: "$created_by_id"},
                "match_score": 1,
            }
        },
    ]

    rows = await (await Candidate.get_motor_collection().aggregate(agg)).to_list(length=None)
    return [SuggestedCandidate(**r) for r in mask_cv_rows(rows, tenant)]


# ── Match / assign candidate to position ───────────────────────────────────────

_STATUS_TO_STAGE: dict[str, PipelineStage] = {
    "pending": PipelineStage.sourced,
    "accepted": PipelineStage.selected,
    "rejected": PipelineStage.rejected,
}


@router.patch("/match")
async def match_candidate(tenant: _Tenant, req: MatchRequest) -> MatchResponse:
    """Assign a candidate to a position (or update their stage). Upserts the Mapping."""
    pos_oid = to_object_id(req.position_id, "position_id")
    cand_oid = to_object_id(req.candidate_id, "candidate_id")

    position = await Position.find_one({"_id": pos_oid, "brand_id": tenant.brand_id})
    if not position:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")

    candidate = await Candidate.find_one({"_id": cand_oid, "brand_id": tenant.brand_id})
    if not candidate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    target_stage = _STATUS_TO_STAGE.get(req.target_status, PipelineStage.sourced)

    mapping = await Mapping.find_one(
        {"candidate_id": cand_oid, "position_id": pos_oid, "brand_id": tenant.brand_id}
    )
    prev_stage = mapping.stage if mapping else None

    if mapping is None:
        # New mappings always open at `sourced`, then move — even when the
        # recruiter accepted or rejected in one click. Writing the final stage
        # straight onto the insert would leave a candidate whose history says
        # they were rejected without ever having been put forward.
        mapping = Mapping(
            brand_id=tenant.brand_id,
            candidate_id=cand_oid,
            position_id=pos_oid,
            client_id=position.client_id,
            employee_id=tenant.employee_id,
            stage=PipelineStage.sourced,
            history=[
                StageEvent(
                    stage=PipelineStage.sourced,
                    by_employee_id=tenant.employee_id,
                )
            ],
        )
        try:
            await mapping.insert()
        except DuplicateKeyError:
            # Race condition: another request inserted between find_one and insert.
            mapping = await Mapping.find_one(
                {"brand_id": tenant.brand_id, "candidate_id": cand_oid, "position_id": pos_oid}
            )
            if mapping is None:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create mapping"
                ) from None
            prev_stage = mapping.stage
        else:
            prev_stage = PipelineStage.sourced.value
            await record_candidate_event(
                scope=tenant,
                candidate_id=cand_oid,
                event_type=CandidateEventType.mapped,
                position=position,
                to_stage=PipelineStage.sourced,
            )

    if mapping.stage != target_stage.value:
        await move_stage(
            mapping=mapping,
            new_stage=target_stage,
            decision=Decision.pending,
            scope=tenant,
        )

    if target_stage in TERMINAL_STAGES or prev_stage in TERMINAL_STAGES:
        await recompute_position_seats(pos_oid)

    return MatchResponse(
        position_id=req.position_id,
        candidate_id=req.candidate_id,
        status=req.target_status,
        recruiter_daily_score=0,
    )


@router.put("/mappings/{mapping_id}/interview-date")
async def set_interview_date(
    mapping_id: str,
    req: PipelineSetInterviewRequest,
    viewer: _Viewer,
):
    mapping = await _get_or_404(viewer, mapping_id)

    mapping.interview_date = req.interview_date
    await mapping.save()
    return {"success": True}


@router.put("/mappings/{mapping_id}/offer-letter")
async def upload_offer_letter(
    mapping_id: str,
    req: PipelineUploadOfferRequest,
    viewer: _Viewer,
):
    from app.modules.auth.models import UserRole

    mapping = await _get_or_404(viewer, mapping_id)

    if viewer.role == UserRole.client and mapping.stage != PipelineStage.selected.value:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Offer letter can only be uploaded when candidate is selected",
        )

    mapping.offer_letter_url = req.offer_letter_url
    mapping.salary_offered = req.salary_offered
    await mapping.save()
    return {"success": True}


@router.put("/mappings/{mapping_id}/joining-date")
async def set_joining_date(
    mapping_id: str,
    req: PipelineSetJoiningRequest,
    viewer: _Viewer,
):
    from app.modules.auth.models import UserRole

    mapping = await _get_or_404(viewer, mapping_id)

    if viewer.role == UserRole.client and not mapping.offer_letter_url:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Joining date can only be set after offer letter is uploaded"
        )

    mapping.joining_date = req.joining_date
    await mapping.save()
    return {"success": True}


@router.put("/mappings/{mapping_id}/dropped")
async def drop_candidate(
    mapping_id: str,
    req: PipelineCandidateDroppedRequest,
    viewer: _Viewer,
):
    from app.modules.recruitment.enums import Decision, PipelineStage
    from app.modules.recruitment.repository_impl import move_stage

    mapping = await _get_or_404(viewer, mapping_id)

    mapping.dropped_notes = req.dropped_notes
    await mapping.save()

    if mapping.stage != PipelineStage.candidate_dropped.value:
        await move_stage(
            mapping=mapping,
            new_stage=PipelineStage.candidate_dropped,
            decision=Decision.rejected,
            scope=viewer,
        )

    return {"success": True}
