"""Positions API router — Phase C.

Endpoints (registered in this order — static paths before dynamic):
  GET    /positions/filters                          dropdown data for the page
  GET    /positions                                  paginated list + search
  POST   /positions                                  create (atomic code generation)
  GET    /positions/{id}                             detail
  PATCH  /positions/{id}                             update fields
  DELETE /positions/{id}                             soft-delete
  GET    /positions/{id}/top-candidates              AI-ranked candidate matches
  GET    /positions/{id}/candidates                  already-mapped candidates
  POST   /positions/{id}/candidates                  map a candidate
  DELETE /positions/{id}/candidates/{candidate_id}   unmap
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.common.dtos.pagination import PaginationMeta
from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant
from app.modules.recruitment.matching import compute_single_score, top_candidates
from app.modules.recruitment.models import (
    Client,
    Mapping,
    Position,
)
from app.modules.recruitment.repository import (
    generate_position_code,
    get_candidate,
    get_position,
)
from app.modules.recruitment.schemas import (
    ClientOption,
    MapCandidateRequest,
    MapCandidateResponse,
    PositionCreate,
    PositionFiltersResponse,
    PositionListItem,
    PositionMappedCandidate,
    PositionPage,
    PositionUpdate,
    TenantScope,
    TopCandidateItem,
)
from app.modules.recruitment.service import map_candidate, unmap_candidate

router = APIRouter()

# ── Annotated query-parameter aliases ─────────────────────────────────────────

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_Search = Annotated[str | None, Query()]
_ClientId = Annotated[str | None, Query()]
_Status = Annotated[str | None, Query()]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]

# ── MongoDB operator constants ─────────────────────────────────────────────────

_MATCH = "$match"
_LOOKUP = "$lookup"
_ADD_FIELDS = "$addFields"
_UNSET = "$unset"
_SORT = "$sort"
_FACET = "$facet"
_SKIP = "$skip"
_LIMIT_OP = "$limit"
_COUNT = "$count"
_SIZE = "$size"
_TO_STR = "$toString"
_EXPR = "$expr"
_UNWIND = "$unwind"
_PROJECT = "$project"
_IF_NULL = "$ifNull"
_COND = "$cond"
_NE = "$ne"
_F_CAND_ID = "$candidate_id"
_F_EMP_ID = "$assigned_employee_id"


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


def _make_page(items: list, total: int, page: int, limit: int) -> PositionPage:
    pages = 0 if total == 0 else (total + limit - 1) // limit
    meta = PaginationMeta(
        page=page, limit=limit, total=total, pages=pages, has_next=page < pages, has_prev=page > 1
    )
    return PositionPage(items=[PositionListItem.model_validate(i) for i in items], meta=meta)


async def _get_or_404(scope: TenantScope, position_id: str) -> Position:
    return await get_position(scope, position_id)


# ── STATIC ROUTES (must precede /{position_id}) ───────────────────────────────


@router.get("/filters")
async def get_filters(tenant: _Tenant) -> PositionFiltersResponse:
    """Distinct clients and status values for the positions page dropdowns."""
    clients = (
        await Client.find({"brand_id": tenant.brand_id, "is_active": True}).sort("name").to_list()
    )

    client_options = [ClientOption(id=str(c.id), code=c.code, name=c.name) for c in clients]
    return PositionFiltersResponse(
        clients=client_options,
        statuses=["open", "on_hold", "closed"],
    )


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("")
async def list_positions(
    tenant: _Tenant,
    search: _Search = None,
    client_id: _ClientId = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: _Page = 1,
    limit: _Limit = 50,
) -> PositionPage:
    match: dict = {"brand_id": tenant.brand_id, "is_active": True}

    if search:
        rx = {"$regex": search, "$options": "i"}
        match["$or"] = [
            {"role": rx},
            {"client_name": rx},
            {"department": rx},
            {"city": rx},
        ]
    if client_id:
        match["client_id"] = to_object_id(client_id, "client_id")
    if status_filter:
        match["status"] = status_filter

    pipeline = [
        {_MATCH: match},
        # Mapped count + preview (top 5 with candidate names)
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"pos_id": "$_id"},
                "pipeline": [
                    {_MATCH: {_EXPR: {"$eq": ["$position_id", "$$pos_id"]}}},
                    {_SORT: {"mapped_at": -1}},
                    {_LIMIT_OP: 5},
                    {
                        _LOOKUP: {
                            "from": "candidates",
                            "let": {"cid": _F_CAND_ID},
                            "pipeline": [
                                {_MATCH: {_EXPR: {"$eq": ["$_id", "$$cid"]}}},
                                {_PROJECT: {"full_name": 1}},
                            ],
                            "as": "cand",
                        }
                    },
                    {_UNWIND: {"path": "$cand", "preserveNullAndEmptyArrays": True}},
                    {
                        _PROJECT: {
                            "id": {_TO_STR: _F_CAND_ID},
                            "full_name": {_IF_NULL: ["$cand.full_name", ""]},
                        }
                    },
                ],
                "as": "mapped_preview",
            }
        },
        # Total mapped count (separate lightweight lookup)
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"pos_id": "$_id"},
                "pipeline": [{_MATCH: {_EXPR: {"$eq": ["$position_id", "$$pos_id"]}}}],
                "as": "_all_maps",
            }
        },
        # Assigned employee name
        {
            _LOOKUP: {
                "from": "employees",
                "let": {"emp_id": "$assigned_employee_id"},
                "pipeline": [
                    {
                        _MATCH: {
                            _EXPR: {
                                "$and": [
                                    {_NE: ["$$emp_id", None]},
                                    {"$eq": ["$_id", "$$emp_id"]},
                                ]
                            }
                        }
                    },
                    {_PROJECT: {"name": 1}},
                ],
                "as": "_emp",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "mapped_count": {_SIZE: "$_all_maps"},
                "assigned_employee_id": {
                    _COND: [
                        {_IF_NULL: ["$assigned_employee_id", False]},
                        {_TO_STR: "$assigned_employee_id"},
                        None,
                    ]
                },
                "assigned_employee_name": {_IF_NULL: [{"$first": "$_emp.name"}, None]},
            }
        },
        {_UNSET: ["_all_maps", "_emp"]},
        {_SORT: {"created_at": -1, "client_name": 1}},
        _paginate(page, limit),
    ]

    result = await Position.get_motor_collection().aggregate(pipeline).to_list(length=None)
    items, total = _unpack(result)
    return _make_page(items, total, page, limit)


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_position(tenant: _Tenant, data: PositionCreate) -> PositionListItem:
    client_oid = to_object_id(data.client_id, "client_id")
    client_doc = await Client.find_one({"_id": client_oid, "brand_id": tenant.brand_id})
    if not client_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")

    code = await generate_position_code(tenant.brand_id, client_doc.code)

    pos = Position(
        brand_id=tenant.brand_id,
        code=code,
        client_id=client_oid,  # type: ignore[arg-type]
        client_name=client_doc.name,
        role=data.role,
        department=data.department,
        city=data.city,
        seniority=data.seniority,
        requirements=[r.lower().strip() for r in data.requirements],
        total_seats=data.total_seats,
        remaining_seats=data.total_seats,
        date_opened=data.date_opened or datetime.now(UTC),
        target_close=data.target_close,
        notes=data.notes,
    )
    try:
        await pos.insert()
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Position code conflict, retry") from None

    return PositionListItem(
        id=str(pos.id),
        code=pos.code,
        client_id=str(pos.client_id),
        client_name=pos.client_name,
        role=pos.role,
        department=pos.department,
        city=pos.city,
        seniority=pos.seniority,
        status=pos.status.value if hasattr(pos.status, "value") else pos.status,
        total_seats=pos.total_seats,
        filled_seats=pos.filled_seats,
        remaining_seats=pos.remaining_seats,
        date_opened=pos.date_opened,
        target_close=pos.target_close,
        notes=pos.notes,
    )


# ── DYNAMIC ROUTES ─────────────────────────────────────────────────────────────


@router.get("/{position_id}")
async def get_position_detail(tenant: _Tenant, position_id: str) -> PositionListItem:
    pos = await _get_or_404(tenant, position_id)
    pos_oid = to_object_id(position_id, "position_id")
    mapped_count = await Mapping.find({"position_id": pos_oid, "brand_id": tenant.brand_id}).count()

    return PositionListItem(
        id=str(pos.id),
        code=pos.code,
        client_id=str(pos.client_id),
        client_name=pos.client_name,
        role=pos.role,
        department=pos.department,
        city=pos.city,
        seniority=pos.seniority.value if hasattr(pos.seniority, "value") else pos.seniority,
        status=pos.status.value if hasattr(pos.status, "value") else pos.status,
        total_seats=pos.total_seats,
        filled_seats=pos.filled_seats,
        remaining_seats=pos.remaining_seats,
        mapped_count=mapped_count,
        date_opened=pos.date_opened,
        target_close=pos.target_close,
        notes=pos.notes,
    )


@router.patch("/{position_id}")
async def update_position(
    tenant: _Tenant, position_id: str, data: PositionUpdate
) -> PositionListItem:
    pos = await _get_or_404(tenant, position_id)
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
        update["requirements"] = [r.lower().strip() for r in data.requirements]
    if data.total_seats is not None:
        update["total_seats"] = data.total_seats
        update["remaining_seats"] = max(data.total_seats - pos.filled_seats, 0)
    if data.status is not None:
        update["status"] = data.status
    if data.assigned_employee_id is not None:
        update["assigned_employee_id"] = to_object_id(
            data.assigned_employee_id, "assigned_employee_id"
        )
    if data.target_close is not None:
        update["target_close"] = data.target_close
    if data.notes is not None:
        update["notes"] = data.notes
    if update:
        await pos.set(update)

    pos_oid = to_object_id(position_id, "position_id")
    mapped_count = await Mapping.find({"position_id": pos_oid, "brand_id": tenant.brand_id}).count()
    return PositionListItem(
        id=str(pos.id),
        code=pos.code,
        client_id=str(pos.client_id),
        client_name=pos.client_name,
        role=pos.role,
        department=pos.department,
        city=pos.city,
        seniority=pos.seniority.value if hasattr(pos.seniority, "value") else pos.seniority,
        status=pos.status.value if hasattr(pos.status, "value") else pos.status,
        total_seats=pos.total_seats,
        filled_seats=pos.filled_seats,
        remaining_seats=pos.remaining_seats,
        mapped_count=mapped_count,
        date_opened=pos.date_opened,
        target_close=pos.target_close,
        notes=pos.notes,
    )


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(tenant: _Tenant, position_id: str) -> None:
    pos = await _get_or_404(tenant, position_id)
    await pos.set({"is_active": False})


# ── Top candidates (AI ranked) ─────────────────────────────────────────────────


@router.get("/{position_id}/top-candidates")
async def get_top_candidates(
    tenant: _Tenant,
    position_id: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[TopCandidateItem]:
    pos = await _get_or_404(tenant, position_id)
    pos_oid = to_object_id(position_id, "position_id")

    # Collect already-mapped candidate ids so we can mark them
    mapped_docs = (
        await Mapping.find({"position_id": pos_oid, "brand_id": tenant.brand_id})
        .project({"candidate_id": 1})
        .to_list()
    )
    mapped_ids = {str(m.candidate_id) for m in mapped_docs}

    rows = await top_candidates(scope=tenant, position=pos, limit=limit)

    return [
        TopCandidateItem(
            id=row["id"],
            full_name=row["full_name"],
            email=row["email"],
            phone=row.get("phone"),
            previous_company=row.get("previous_company"),
            experience_years=row.get("experience_years", 0),
            skills=row.get("skills", []),
            resume_url=row.get("resume_url"),
            match_score=row.get("match_score"),
            is_mapped=row["id"] in mapped_ids,
        )
        for row in rows
    ]


# ── Mapped candidates ──────────────────────────────────────────────────────────


@router.get("/{position_id}/candidates")
async def get_position_candidates(
    tenant: _Tenant, position_id: str
) -> list[PositionMappedCandidate]:
    pos_oid = to_object_id(position_id, "position_id")
    # Verify position belongs to brand
    await _get_or_404(tenant, position_id)

    pipeline = [
        {_MATCH: {"position_id": pos_oid, "brand_id": tenant.brand_id}},
        {
            _LOOKUP: {
                "from": "candidates",
                "let": {"cid": _F_CAND_ID},
                "pipeline": [
                    {_MATCH: {_EXPR: {"$eq": ["$_id", "$$cid"]}}},
                    {
                        _PROJECT: {
                            "full_name": 1,
                            "email": 1,
                            "previous_company": 1,
                            "experience_years": 1,
                            "skills": 1,
                        }
                    },
                ],
                "as": "cand",
            }
        },
        {_UNWIND: "$cand"},
        {
            _ADD_FIELDS: {
                "mapping_id": {_TO_STR: "$_id"},
                "candidate_id": {_TO_STR: _F_CAND_ID},
                "full_name": "$cand.full_name",
                "email": "$cand.email",
                "previous_company": "$cand.previous_company",
                "experience_years": "$cand.experience_years",
                "skills": "$cand.skills",
            }
        },
        {
            _UNSET: [
                "_id",
                "cand",
                "position_id",
                "client_id",
                "employee_id",
                "decision",
                "history",
                "brand_id",
                "updated_at",
            ]
        },
        {_SORT: {"mapped_at": -1}},
    ]

    rows = await Mapping.get_motor_collection().aggregate(pipeline).to_list(length=None)
    return [PositionMappedCandidate.model_validate(r) for r in rows]


# ── Map candidate ──────────────────────────────────────────────────────────────


@router.post("/{position_id}/candidates", status_code=status.HTTP_201_CREATED)
async def map_candidate_to_position(
    tenant: _Tenant, position_id: str, body: MapCandidateRequest
) -> MapCandidateResponse:
    pos = await _get_or_404(tenant, position_id)
    cand = await get_candidate(tenant, body.candidate_id)

    score = compute_single_score(cand.skills_normalized, pos.requirements)

    mapping = await map_candidate(
        scope=tenant,
        candidate_id=cand.id,  # type: ignore[arg-type]
        position=pos,
        match_score=score,
    )

    return MapCandidateResponse(
        mapping_id=str(mapping.id),
        position_id=position_id,
        candidate_id=body.candidate_id,
        stage=mapping.stage.value if hasattr(mapping.stage, "value") else mapping.stage,
        match_score=score,
        recruiter_score_delta=4,
    )


# ── Unmap candidate ────────────────────────────────────────────────────────────


@router.delete("/{position_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unmap_candidate_from_position(
    tenant: _Tenant, position_id: str, candidate_id: str
) -> None:
    await _get_or_404(tenant, position_id)  # brand check
    pos_oid = to_object_id(position_id, "position_id")
    cand_oid = to_object_id(candidate_id, "candidate_id")

    mapping = await Mapping.find_one(
        {"position_id": pos_oid, "candidate_id": cand_oid, "brand_id": tenant.brand_id}
    )
    if not mapping:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mapping not found")

    await unmap_candidate(scope=tenant, mapping=mapping)
