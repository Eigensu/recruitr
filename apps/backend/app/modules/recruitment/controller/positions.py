"""Positions API router — Phase C.

Endpoints:
  GET    /positions                    list + filter (paginated)
  POST   /positions                    create new position
  GET    /positions/{id}               detail
  PATCH  /positions/{id}               update fields
  DELETE /positions/{id}               soft-delete (set is_active=false)
  GET    /positions/{id}/top-candidates  ranked candidates with match scores
  GET    /positions/{id}/candidates     already mapped candidates
  POST   /positions/{id}/map-candidate   map a candidate to this position
  POST   /positions/{id}/unmap-candidate unmap a candidate
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.common.dtos.pagination import PaginationMeta
from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant
from app.modules.recruitment.models import Candidate, Mapping, Position
from app.modules.recruitment.schemas import (
    MapCandidateRequest,
    MapCandidateResponse,
    PositionCreate,
    PositionListItem,
    PositionMappedCandidate,
    PositionPage,
    PositionUpdate,
    TenantScope,
    TopCandidateItem,
)

router = APIRouter()

# ── Annotated aliases ──────────────────────────────────────────────────────────

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]
_ClientId = Annotated[str | None, Query()]
_Status = Annotated[str | None, Query(alias="status")]
_PositionLimit = Annotated[int, Query(ge=1, le=50)]
_CandidateId = Annotated[str, Query()]

# ── Error messages ─────────────────────────────────────────────────────────────

_ERR_POSITION_NOT_FOUND = "Position not found"
_ERR_INVALID_CLIENT_ID = "Invalid client_id"
_ERR_CANDIDATE_NOT_FOUND = "Candidate not found"
_ERR_ALREADY_MAPPED = "Candidate already mapped to this position"
_ERR_MAPPING_NOT_FOUND = "Mapping not found"

# ── Aggregation constants ──────────────────────────────────────────────────────

_MATCH = "$match"
_LOOKUP = "$lookup"
_ADD_FIELDS = "$addFields"
_UNSET = "$unset"
_UNWIND = "$unwind"
_SORT = "$sort"
_FACET = "$facet"
_SKIP = "$skip"
_LIMIT_OP = "$limit"
_COUNT = "$count"
_SIZE = "$size"
_TO_STR = "$toString"
_EXPR = "$expr"
_GROUP = "$group"
_SET_INTERSECTION = "$setIntersection"
_DIVIDE = "$divide"

# ── Field references ───────────────────────────────────────────────────────────

_F_CANDIDATE_ID = "$candidate_id"
_F_POSITION_ID = "$position_id"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _paginate(page: int, limit: int) -> dict:
    return {
        _FACET: {
            "items": [{_SKIP: (page - 1) * limit}, {_LIMIT_OP: limit}],
            "meta": [{_COUNT: "total"}],
        }
    }


def _unpack(result: list) -> tuple[list, int]:
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return items, total


def _make_page(items: list, total: int, page: int, limit: int, model: type) -> PositionPage:
    pages = 0 if total == 0 else (total + limit - 1) // limit
    meta = PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )
    return PositionPage(items=[model.model_validate(i) for i in items], meta=meta)


async def _get_or_404(scope: TenantScope, position_id: str) -> Position:
    oid = to_object_id(position_id, "position_id")
    doc = await Position.find_one({"_id": oid, "brand_id": scope.brand_id, "is_active": True})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_POSITION_NOT_FOUND)
    return doc


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("")
async def list_positions(
    tenant: _Tenant,
    client_id: _ClientId = None,
    status_filter: _Status = None,
    page: _Page = 1,
    limit: _Limit = 30,
) -> PositionPage:
    match: dict = {"brand_id": tenant.brand_id, "is_active": True}

    if client_id:
        client_oid = to_object_id(client_id, "client_id")
        if client_oid:
            match["client_id"] = client_oid

    if status_filter:
        match["status"] = status_filter

    pipeline = [
        {_MATCH: match},
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"pos_id": "$_id"},
                "pipeline": [{_MATCH: {_EXPR: {"$eq": [_F_POSITION_ID, "$$pos_id"]}}}],
                "as": "pos_maps",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "mapped_count": {_SIZE: "$pos_maps"},
                "mapped_preview": {
                    "$map": {
                        "input": {
                            "$slice": ["$pos_maps", 3]  # First 3 mappings for preview
                        },
                        "as": "m",
                        "in": {
                            "$mergeObjects": [
                                {"$literal": {"id": "", "full_name": ""}},
                                {
                                    "id": {_TO_STR: "$$m.candidate_id"},
                                    "full_name": "$$m.candidate_id",  # Will be populated via join
                                },
                            ]
                        },
                    }
                },
            }
        },
        {_UNSET: ["pos_maps"]},
        {_SORT: {"created_at": -1, "role": 1}},
        _paginate(page, limit),
    ]

    result = await Position.get_motor_collection().aggregate(pipeline).to_list(None)
    items, total = _unpack(result)
    return _make_page(items, total, page, limit, PositionListItem)


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_position(tenant: _Tenant, data: PositionCreate) -> PositionListItem:
    # Generate position code (Phase C: will be moved to service layer)
    # Format: CLI-NNN-POS-NNN (handled by service in full implementation)
    client_oid = to_object_id(data.client_id, "client_id")
    if not client_oid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _ERR_INVALID_CLIENT_ID)

    doc = Position(
        brand_id=tenant.brand_id,
        code="TBD",  # Will be set by service
        client_id=client_oid,
        client_name=data.client_id,  # Will be populated from client lookup
        role=data.role,
        department=data.department,
        city=data.city,
        seniority=data.seniority,
        requirements=data.requirements,
        total_seats=data.total_seats,
        filled_seats=0,
        remaining_seats=data.total_seats,
        status="open",
        date_opened=data.date_opened,
        target_close=data.target_close,
        notes=data.notes,
    )
    try:
        await doc.insert()
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Position code already exists") from None

    return PositionListItem(
        id=str(doc.id),
        code=doc.code,
        client_id=str(doc.client_id),
        client_name=doc.client_name,
        role=doc.role,
        department=doc.department,
        city=doc.city,
        seniority=doc.seniority,
        status=doc.status,
        total_seats=doc.total_seats,
        filled_seats=doc.filled_seats,
        remaining_seats=doc.remaining_seats,
        mapped_count=0,
        mapped_preview=[],
        assigned_employee_id=None,
        assigned_employee_name=None,
        date_opened=doc.date_opened,
        target_close=doc.target_close,
        notes=doc.notes,
    )


# ── Detail ─────────────────────────────────────────────────────────────────────


@router.get("/{position_id}")
async def get_position(tenant: _Tenant, position_id: str) -> PositionListItem:
    doc = await _get_or_404(tenant, position_id)
    pos_oid = to_object_id(position_id, "position_id")
    count = await Mapping.find({"position_id": pos_oid, "brand_id": tenant.brand_id}).count()

    return PositionListItem(
        id=str(doc.id),
        code=doc.code,
        client_id=str(doc.client_id),
        client_name=doc.client_name,
        role=doc.role,
        department=doc.department,
        city=doc.city,
        seniority=doc.seniority,
        status=doc.status,
        total_seats=doc.total_seats,
        filled_seats=doc.filled_seats,
        remaining_seats=doc.remaining_seats,
        mapped_count=count,
        mapped_preview=[],
        assigned_employee_id=None,
        assigned_employee_name=None,
        date_opened=doc.date_opened,
        target_close=doc.target_close,
        notes=doc.notes,
    )


# ── Update ─────────────────────────────────────────────────────────────────────


@router.patch("/{position_id}")
async def update_position(
    tenant: _Tenant, position_id: str, data: PositionUpdate
) -> PositionListItem:
    doc = await _get_or_404(tenant, position_id)
    update: dict = {}

    if data.role is not None:
        update["role"] = data.role
    if data.department is not None:
        update["department"] = data.department
    if data.city is not None:
        update["city"] = data.city
    if data.seniority is not None:
        update["seniority"] = data.seniority
    if data.requirements is not None:
        update["requirements"] = data.requirements
    if data.total_seats is not None:
        update["total_seats"] = data.total_seats
        # Recalculate remaining_seats
        filled = doc.filled_seats or 0
        update["remaining_seats"] = max(data.total_seats - filled, 0)
    if data.status is not None:
        update["status"] = data.status
    if data.assigned_employee_id is not None:
        emp_oid = to_object_id(data.assigned_employee_id, "assigned_employee_id")
        update["assigned_employee_id"] = emp_oid if emp_oid else None
    if data.target_close is not None:
        update["target_close"] = data.target_close
    if data.notes is not None:
        update["notes"] = data.notes

    if update:
        await doc.set(update)

    pos_oid = to_object_id(position_id, "position_id")
    count = await Mapping.find({"position_id": pos_oid, "brand_id": tenant.brand_id}).count()

    return PositionListItem(
        id=str(doc.id),
        code=doc.code,
        client_id=str(doc.client_id),
        client_name=doc.client_name,
        role=doc.role,
        department=doc.department,
        city=doc.city,
        seniority=doc.seniority,
        status=doc.status,
        total_seats=doc.total_seats,
        filled_seats=doc.filled_seats,
        remaining_seats=doc.remaining_seats,
        mapped_count=count,
        mapped_preview=[],
        assigned_employee_id=None,
        assigned_employee_name=None,
        date_opened=doc.date_opened,
        target_close=doc.target_close,
        notes=doc.notes,
    )


# ── Delete (soft) ──────────────────────────────────────────────────────────────


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(tenant: _Tenant, position_id: str):
    doc = await _get_or_404(tenant, position_id)
    await doc.set({"is_active": False})


# ── Top candidates (with match scoring) ────────────────────────────────────────


@router.get("/{position_id}/top-candidates")
async def get_top_candidates(
    tenant: _Tenant, position_id: str, limit: _PositionLimit = 10
) -> list[TopCandidateItem]:
    """
    Return top matching candidates for this position using $setIntersection scoring.
    Score is (matched_skills / total_position_requirements).
    Returns null score if position has no requirements.
    """
    pos_oid = to_object_id(position_id, "position_id")
    pos = await Position.find_one({"_id": pos_oid, "brand_id": tenant.brand_id})
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_POSITION_NOT_FOUND)

    # If no requirements, return candidates without scores
    if not pos.requirements:
        candidates = (
            await Candidate.find({"brand_id": tenant.brand_id, "is_active": True})
            .sort("-experience_years")
            .limit(limit)
            .to_list(None)
        )
        return [
            TopCandidateItem(
                id=str(c.id),
                full_name=c.full_name,
                email=c.email,
                phone=c.phone,
                previous_company=c.previous_company,
                experience_years=c.experience_years,
                skills=c.skills,
                resume_url=c.resume_url,
                match_score=None,
                is_mapped=False,
            )
            for c in candidates
        ]

    # Aggregation with $setIntersection scoring
    pipeline = [
        {_MATCH: {"brand_id": tenant.brand_id, "is_active": True}},
        {
            _ADD_FIELDS: {
                "matched_skills_count": {
                    _SIZE: {
                        _SET_INTERSECTION: [
                            "$skills_normalized",
                            [s.lower() for s in pos.requirements],
                        ]
                    }
                },
                "match_score": {
                    _DIVIDE: [
                        {
                            _SIZE: {
                                _SET_INTERSECTION: [
                                    "$skills_normalized",
                                    [s.lower() for s in pos.requirements],
                                ]
                            }
                        },
                        len(pos.requirements) if pos.requirements else 1,
                    ]
                },
            }
        },
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"cand_id": "$_id"},
                "pipeline": [
                    {
                        _MATCH: {
                            _EXPR: {
                                "$and": [
                                    {"$eq": [_F_CANDIDATE_ID, "$$cand_id"]},
                                    {"$eq": [_F_POSITION_ID, pos_oid]},
                                ]
                            }
                        }
                    }
                ],
                "as": "mapping",
            }
        },
        {_ADD_FIELDS: {"is_mapped": {_SIZE: "$mapping"}}},
        {_UNSET: ["mapping", "skills_normalized"]},
        {_SORT: {"match_score": -1, "experience_years": -1}},
        {_LIMIT_OP: limit},
    ]

    results = await Candidate.get_motor_collection().aggregate(pipeline).to_list(None)
    return [TopCandidateItem.model_validate(r) for r in results]


# ── Mapped candidates ──────────────────────────────────────────────────────────


@router.get("/{position_id}/candidates")
async def get_position_candidates(
    tenant: _Tenant, position_id: str
) -> list[PositionMappedCandidate]:
    """Return all candidates mapped to this position."""
    pos_oid = to_object_id(position_id, "position_id")
    exists = await Position.find_one(
        {"_id": pos_oid, "brand_id": tenant.brand_id, "is_active": True}
    )
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_POSITION_NOT_FOUND)

    pipeline = [
        {_MATCH: {"position_id": pos_oid, "brand_id": tenant.brand_id}},
        {
            _LOOKUP: {
                "from": "candidates",
                "let": {"cand_id": _F_CANDIDATE_ID},
                "pipeline": [{_MATCH: {_EXPR: {"$eq": ["$_id", "$$cand_id"]}}}],
                "as": "candidate",
            }
        },
        {_UNWIND: "$candidate"},
        {
            _ADD_FIELDS: {
                "mapping_id": {_TO_STR: "$_id"},
                "candidate_id": {_TO_STR: _F_CANDIDATE_ID},
                "full_name": "$candidate.full_name",
                "email": "$candidate.email",
                "previous_company": "$candidate.previous_company",
                "experience_years": "$candidate.experience_years",
                "skills": "$candidate.skills",
            }
        },
        {_UNSET: ["_id", "candidate", "brand_id", "client_id", "employee_id", "history"]},
        {_SORT: {"stage": 1, "mapped_at": -1}},
    ]

    rows = await Mapping.get_motor_collection().aggregate(pipeline).to_list(None)
    return [PositionMappedCandidate.model_validate(r) for r in rows]


# ── Map candidate ──────────────────────────────────────────────────────────────


@router.post("/{position_id}/map-candidate")
async def map_candidate_to_position(
    tenant: _Tenant, position_id: str, req: MapCandidateRequest
) -> MapCandidateResponse:
    """Map a candidate to this position (create a mapping)."""
    pos_oid = to_object_id(position_id, "position_id")
    cand_oid = to_object_id(req.candidate_id, "candidate_id")

    pos = await Position.find_one({"_id": pos_oid, "brand_id": tenant.brand_id, "is_active": True})
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_POSITION_NOT_FOUND)

    cand = await Candidate.find_one(
        {"_id": cand_oid, "brand_id": tenant.brand_id, "is_active": True}
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_CANDIDATE_NOT_FOUND)

    # Check if already mapped
    existing = await Mapping.find_one(
        {
            "position_id": pos_oid,
            "candidate_id": cand_oid,
            "brand_id": tenant.brand_id,
        }
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, _ERR_ALREADY_MAPPED)

    # Calculate match score
    match_score = None
    if pos.requirements:
        pos_reqs_lower = [s.lower() for s in pos.requirements]
        matched_skills = sum(
            1 for skill in (cand.skills_normalized or []) if skill in pos_reqs_lower
        )
        match_score = matched_skills / len(pos.requirements)

    # Create mapping
    mapping = Mapping(
        brand_id=tenant.brand_id,
        candidate_id=cand_oid,
        position_id=pos_oid,
        client_id=pos.client_id,
        employee_id=tenant.employee_id,
        stage="sourced",
        decision="pending",
        match_score=match_score,
        mapped_at=None,  # Beanie will set to now
    )
    await mapping.insert()

    return MapCandidateResponse(
        mapping_id=str(mapping.id),
        position_id=str(pos.id),
        candidate_id=str(cand.id),
        stage=mapping.stage,
        match_score=match_score,
        recruiter_score_delta=4,
    )


# ── Unmap candidate ────────────────────────────────────────────────────────────


@router.post("/{position_id}/unmap-candidate")
async def unmap_candidate_from_position(
    tenant: _Tenant, position_id: str, candidate_id: _CandidateId
) -> dict:
    """Unmap a candidate from this position (delete mapping)."""
    pos_oid = to_object_id(position_id, "position_id")
    cand_oid = to_object_id(candidate_id, "candidate_id")

    mapping = await Mapping.find_one(
        {
            "position_id": pos_oid,
            "candidate_id": cand_oid,
            "brand_id": tenant.brand_id,
        }
    )
    if not mapping:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_MAPPING_NOT_FOUND)

    await mapping.delete()
    return {"success": True, "message": "Candidate unmapped"}
