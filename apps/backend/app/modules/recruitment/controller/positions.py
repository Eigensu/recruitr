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
from app.modules.recruitment.models import Candidate, Client, Mapping, Position
from app.modules.recruitment.repository import generate_position_code
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
from app.modules.recruitment.utils.matching import _get_effective_requirements

router = APIRouter()

# ── Annotated aliases ──────────────────────────────────────────────────────────

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]
_ClientId = Annotated[str | None, Query()]
_Status = Annotated[str | None, Query(alias="status")]
_Search = Annotated[str | None, Query()]
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
_MULTIPLY = "$multiply"
_ADD_OP = "$add"
_SWITCH = "$switch"
_ABS = "$abs"
_F_CURRENT_STAGE = "$current_stage"
_F_EXP_YEARS = "$experience_years"

# ── Field references ───────────────────────────────────────────────────────────

_F_CANDIDATE_ID = "$candidate_id"
_F_POSITION_ID = "$position_id"
_VAR_CAND_ID = "$$cand_id"


# ── Scoring helpers ────────────────────────────────────────────────────────────

# Availability score: candidates deep in another pipeline are down-ranked.
_AVAIL_SCORE_EXPR: dict = {
    _SWITCH: {
        "branches": [
            {"case": {"$eq": [_F_CURRENT_STAGE, "sourced"]}, "then": 1.0},
            {"case": {"$eq": [_F_CURRENT_STAGE, "sent_to_client"]}, "then": 0.85},
            {"case": {"$eq": [_F_CURRENT_STAGE, "interview"]}, "then": 0.7},
            {"case": {"$eq": [_F_CURRENT_STAGE, "decision_pending"]}, "then": 0.5},
            {"case": {"$eq": [_F_CURRENT_STAGE, "offer"]}, "then": 0.3},
        ],
        "default": 0.0,
    }
}


def _edu_score(edu: str | None) -> float:
    if edu == "PhD":
        return 1.0
    if edu == "Masters":
        return 0.8
    if edu == "Bachelors":
        return 0.6
    if edu == "High School":
        return 0.4
    return 0.0


def _py_exp_score(seniority: str, years: float) -> float:
    """Python mirror of _exp_score_expr — used at map-time score snapshot."""
    s = seniority.lower()
    if s == "junior":
        return max(0.0, 1.0 - abs(years - 1.0) / 3.0)
    if s == "senior":
        return min(1.0, max(0.2, years / 8.0))
    # Mid: peak at 4y
    return max(0.0, 1.0 - abs(years - 4.0) / 4.0)


def _py_composite_score(
    pos_requirements: list[str],
    seniority: str,
    pos_train_line: str | None,
    skills_normalized: list[str],
    experience_years: float,
    edu_level: str | None,
    preferred_train_line: str | None,
) -> float:
    """Composite match score — mirrors the MongoDB aggregation in get_top_candidates."""
    has_reqs = bool(pos_requirements)
    req_lower = [s.lower() for s in pos_requirements]
    n_req = len(req_lower) or 1

    skill_score = sum(1 for s in skills_normalized if s in req_lower) / n_req if has_reqs else 0.0
    exp_score = _py_exp_score(seniority, experience_years)
    avail_score = 1.0  # new mappings always start at sourced
    if pos_train_line and pos_train_line == preferred_train_line or not pos_train_line:
        train_score = 1.0
    else:
        train_score = 0.0
    edu_score_val = _edu_score(edu_level)

    if has_reqs:
        return (
            0.4 * skill_score
            + 0.2 * exp_score
            + 0.2 * avail_score
            + 0.1 * train_score
            + 0.1 * edu_score_val
        )
    return 0.4 * exp_score + 0.4 * avail_score + 0.1 * train_score + 0.1 * edu_score_val


def _exp_score_expr(seniority: str) -> dict:
    """
    Continuous experience score — linear decay from the optimal point.
    Junior: peak 1.0 at 1y, zero at 4y+
    Mid:    peak 1.0 at 4y, zero at 0y and 8y
    Senior: linear 0.2 at 0y → 1.0 at 8y (capped)
    """
    s = seniority.lower()

    def _decay(optimal: float, spread: float) -> dict:
        return {
            "$max": [
                0.0,
                {
                    "$subtract": [
                        1.0,
                        {_DIVIDE: [{_ABS: {"$subtract": [_F_EXP_YEARS, optimal]}}, spread]},
                    ]
                },
            ]
        }

    if s == "junior":
        return _decay(1.0, 3.0)
    if s == "senior":
        return {"$min": [1.0, {"$max": [0.2, {_DIVIDE: [_F_EXP_YEARS, 8.0]}]}]}
    # Mid: peak at 4y
    return _decay(4.0, 4.0)


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


# ── Filters (static — must be registered before /{position_id}) ───────────────


@router.get("/filters")
async def get_position_filters(tenant: _Tenant) -> PositionFiltersResponse:
    clients = (
        await Client.find({"brand_id": tenant.brand_id, "is_active": True}).sort("name").to_list()
    )
    client_options = [ClientOption(id=str(c.id), code=c.code, name=c.name) for c in clients]
    return PositionFiltersResponse(clients=client_options, statuses=["open", "on_hold", "closed"])


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("")
async def list_positions(
    tenant: _Tenant,
    search: _Search = None,
    client_id: _ClientId = None,
    status_filter: _Status = None,
    page: _Page = 1,
    limit: _Limit = 30,
) -> PositionPage:
    match: dict = {"brand_id": tenant.brand_id, "is_active": True}

    if search:
        rx = {"$regex": search, "$options": "i"}
        match["$or"] = [{"role": rx}, {"client_name": rx}, {"department": rx}, {"city": rx}]

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
                "pipeline": [
                    {_MATCH: {_EXPR: {"$eq": [_F_POSITION_ID, "$$pos_id"]}}},
                    {
                        _LOOKUP: {
                            "from": "candidates",
                            "let": {"cand_id": "$candidate_id"},
                            "pipeline": [
                                {_MATCH: {_EXPR: {"$eq": ["$_id", _VAR_CAND_ID]}}},
                                {"$project": {"full_name": 1}},
                            ],
                            "as": "cand",
                        }
                    },
                    {"$unwind": {"path": "$cand", "preserveNullAndEmptyArrays": True}},
                ],
                "as": "pos_maps",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "client_id": {_TO_STR: "$client_id"},
                "assigned_employee_id": {
                    "$cond": {
                        "if": {"$gt": ["$assigned_employee_id", None]},
                        "then": {_TO_STR: "$assigned_employee_id"},
                        "else": None,
                    }
                },
                "mapped_count": {_SIZE: "$pos_maps"},
                "mapped_preview": {
                    "$map": {
                        "input": {"$slice": ["$pos_maps", 3]},
                        "as": "m",
                        "in": {
                            "id": {_TO_STR: "$$m.candidate_id"},
                            "full_name": {"$ifNull": ["$$m.cand.full_name", ""]},
                        },
                    }
                },
            }
        },
        {_UNSET: ["pos_maps"]},
        {_SORT: {"created_at": -1, "role": 1}},
        _paginate(page, limit),
    ]

    result = await (await Position.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    items, total = _unpack(result)
    return _make_page(items, total, page, limit, PositionListItem)


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_position(tenant: _Tenant, data: PositionCreate) -> PositionListItem:
    # Verify client belongs to tenant and get details
    client_oid = to_object_id(data.client_id, "client_id")
    if not client_oid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _ERR_INVALID_CLIENT_ID)

    client_doc = await Client.find_one(Client.id == client_oid, Client.brand_id == tenant.brand_id)
    if not client_doc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or unauthorized client")

    code = await generate_position_code(tenant.brand_id, client_doc.code)

    doc = Position(
        brand_id=tenant.brand_id,
        code=code,
        client_id=client_oid,
        client_name=client_doc.name,
        role=data.role,
        department=data.department,
        city=data.city,
        train_line=data.train_line,
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
        train_line=doc.train_line,
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
        train_line=doc.train_line,
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
    if data.train_line is not None:
        update["train_line"] = data.train_line
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
        train_line=doc.train_line,
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
    Rank candidates by a composite score:
      50% skill match (requirements ∩ skills / |requirements|)
      30% experience fit (years vs seniority bracket)
      20% pipeline availability (sourced=1.0 … offer=0.3 … closed=0.0)
    When no requirements are set, weights shift to 60% exp / 40% availability.
    """
    pos_oid = to_object_id(position_id, "position_id")
    pos = await Position.find_one({"_id": pos_oid, "brand_id": tenant.brand_id})
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_POSITION_NOT_FOUND)

    reqs = _get_effective_requirements(pos)
    has_reqs = bool(reqs)
    req_lower = [s.lower() for s in reqs]
    n_req = len(req_lower) or 1

    if has_reqs:
        w_skill, w_exp, w_avail, w_train, w_edu = 0.4, 0.2, 0.2, 0.1, 0.1
        skill_score_expr: dict = {
            _DIVIDE: [
                {_SIZE: {_SET_INTERSECTION: [{"$ifNull": ["$skills_normalized", []]}, req_lower]}},
                n_req,
            ]
        }
    else:
        w_skill, w_exp, w_avail, w_train, w_edu = 0.0, 0.4, 0.4, 0.1, 0.1
        skill_score_expr = {"$literal": 0.0}

    edu_score_expr: dict = {
        _SWITCH: {
            "branches": [
                {"case": {"$eq": ["$education_level", "PhD"]}, "then": 1.0},
                {"case": {"$eq": ["$education_level", "Masters"]}, "then": 0.8},
                {"case": {"$eq": ["$education_level", "Bachelors"]}, "then": 0.6},
                {"case": {"$eq": ["$education_level", "High School"]}, "then": 0.4},
            ],
            "default": 0.0,
        }
    }

    train_score_expr: dict = (
        {"$cond": [{"$eq": ["$preferred_train_line", pos.train_line]}, 1.0, 0.0]}
        if pos.train_line
        else {"$literal": 1.0}
    )

    pipeline = [
        {_MATCH: {"brand_id": tenant.brand_id, "is_active": True}},
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "skill_score": skill_score_expr,
                "exp_score": _exp_score_expr(pos.seniority.value),
                "avail_score": _AVAIL_SCORE_EXPR,
                "edu_score": edu_score_expr,
                "train_score": train_score_expr,
            }
        },
        {
            _ADD_FIELDS: {
                "match_score": {
                    _ADD_OP: [
                        {_MULTIPLY: ["$skill_score", w_skill]},
                        {_MULTIPLY: ["$exp_score", w_exp]},
                        {_MULTIPLY: ["$avail_score", w_avail]},
                        {_MULTIPLY: ["$edu_score", w_edu]},
                        {_MULTIPLY: ["$train_score", w_train]},
                    ]
                }
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
                                    {"$eq": [_F_CANDIDATE_ID, _VAR_CAND_ID]},
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
        {
            _UNSET: [
                "mapping",
                "skills_normalized",
                "skill_score",
                "exp_score",
                "avail_score",
                "edu_score",
                "train_score",
            ]
        },
        {_SORT: {"match_score": -1, "experience_years": -1}},
        {_LIMIT_OP: limit},
    ]

    results = await (await Candidate.get_motor_collection().aggregate(pipeline)).to_list(
        length=None
    )
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
                "pipeline": [{_MATCH: {_EXPR: {"$eq": ["$_id", _VAR_CAND_ID]}}}],
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

    rows = await (await Mapping.get_motor_collection().aggregate(pipeline)).to_list(length=None)
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

    match_score: float = _py_composite_score(
        pos.requirements,
        pos.seniority.value,
        pos.train_line,
        cand.skills_normalized or [],
        cand.experience_years,
        cand.education_level.value if cand.education_level else None,
        cand.preferred_train_line,
    )

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
