"""Candidates API router — Phase B.

Endpoints:
  GET    /candidates                  list + search + filter (paginated)
  POST   /candidates                  create new candidate
  GET    /candidates/{id}             detail
  PATCH  /candidates/{id}             update profile fields
  GET    /candidates/{id}/mappings    positions this candidate is mapped to (for drawer)
  POST   /candidates/{id}/resume      confirm Cloudinary upload
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.common.dtos.pagination import PaginationMeta
from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.models import Candidate, Mapping
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateMappingItem,
    CandidatePage,
    CandidateResponse,
    CandidateUpdate,
    ExperienceFilter,
    ResumeConfirm,
    TenantScope,
)

router = APIRouter()

# ── Annotated aliases ──────────────────────────────────────────────────────────

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_Search = Annotated[str | None, Query(description="Search by name, email, company, or skill")]
_ExpFilter = Annotated[ExperienceFilter | None, Query(description="Experience band")]
_Stage = Annotated[PipelineStage | None, Query(description="Filter by pipeline stage")]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]

# ── Aggregation constants (avoid repeated literals) ───────────────────────────

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


def _make_page(items: list, total: int, page: int, limit: int, model: type) -> CandidatePage:
    pages = 0 if total == 0 else (total + limit - 1) // limit
    meta = PaginationMeta(
        page=page, limit=limit, total=total, pages=pages, has_next=page < pages, has_prev=page > 1
    )
    return CandidatePage(items=[model.model_validate(i) for i in items], meta=meta)


async def _get_or_404(scope: TenantScope, candidate_id: str) -> Candidate:
    oid = to_object_id(candidate_id, "candidate_id")
    doc = await Candidate.find_one({"_id": oid, "brand_id": scope.brand_id, "is_active": True})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return doc


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("")
async def list_candidates(
    tenant: _Tenant,
    search: _Search = None,
    experience: _ExpFilter = None,
    stage: _Stage = None,
    page: _Page = 1,
    limit: _Limit = 30,
) -> CandidatePage:
    match: dict = {"brand_id": tenant.brand_id, "is_active": True}

    if search:
        rx = {"$regex": search, "$options": "i"}
        match["$or"] = [
            {"full_name": rx},
            {"email": rx},
            {"previous_company": rx},
            {"skills": rx},
        ]

    if stage:
        match["current_stage"] = stage.value

    if experience == "lt2":
        match["experience_years"] = {"$lt": 2}
    elif experience == "2to5":
        match["experience_years"] = {"$gte": 2, "$lte": 5}
    elif experience == "gt5":
        match["experience_years"] = {"$gt": 5}

    pipeline = [
        {_MATCH: match},
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"cid": "$_id"},
                "pipeline": [{_MATCH: {_EXPR: {"$eq": ["$candidate_id", "$$cid"]}}}],
                "as": "cand_maps",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "mappings_count": {_SIZE: "$cand_maps"},
            }
        },
        {_UNSET: ["cand_maps"]},
        {_SORT: {"created_at": -1, "full_name": 1}},
        _paginate(page, limit),
    ]
    result = await Candidate.get_motor_collection().aggregate(pipeline).to_list(length=None)
    items, total = _unpack(result)
    return _make_page(items, total, page, limit, CandidateResponse)


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_candidate(tenant: _Tenant, data: CandidateCreate) -> CandidateResponse:
    doc = Candidate(
        brand_id=tenant.brand_id,
        full_name=data.full_name,
        email=data.email.lower(),
        phone=data.phone,
        previous_company=data.previous_company,
        experience_years=data.experience_years,
        skills=data.skills,
        skills_normalized=[s.lower() for s in data.skills],
    )
    try:
        await doc.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A candidate with this email already exists in this brand",
        ) from None
    return CandidateResponse(
        id=str(doc.id),
        full_name=doc.full_name,
        email=doc.email,
        phone=doc.phone,
        previous_company=doc.previous_company,
        experience_years=doc.experience_years,
        skills=doc.skills,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=0,
        created_at=doc.created_at,
    )


# ── Detail ─────────────────────────────────────────────────────────────────────


@router.get("/{candidate_id}")
async def get_candidate(tenant: _Tenant, candidate_id: str) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    cand_oid = to_object_id(candidate_id, "candidate_id")
    count = await Mapping.find({"candidate_id": cand_oid, "brand_id": tenant.brand_id}).count()
    return CandidateResponse(
        id=str(doc.id),
        full_name=doc.full_name,
        email=doc.email,
        phone=doc.phone,
        previous_company=doc.previous_company,
        experience_years=doc.experience_years,
        skills=doc.skills,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=count,
        created_at=doc.created_at,
    )


# ── Update ─────────────────────────────────────────────────────────────────────


@router.patch("/{candidate_id}")
async def update_candidate(
    tenant: _Tenant, candidate_id: str, data: CandidateUpdate
) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    update: dict = {}
    if data.full_name is not None:
        update["full_name"] = data.full_name
    if data.phone is not None:
        update["phone"] = data.phone
    if data.previous_company is not None:
        update["previous_company"] = data.previous_company
    if data.experience_years is not None:
        update["experience_years"] = data.experience_years
    if data.skills is not None:
        update["skills"] = data.skills
        update["skills_normalized"] = [s.lower() for s in data.skills]
    if update:
        await doc.set(update)
    cand_oid = to_object_id(candidate_id, "candidate_id")
    count = await Mapping.find({"candidate_id": cand_oid, "brand_id": tenant.brand_id}).count()
    return CandidateResponse(
        id=str(doc.id),
        full_name=doc.full_name,
        email=doc.email,
        phone=doc.phone,
        previous_company=doc.previous_company,
        experience_years=doc.experience_years,
        skills=doc.skills,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=count,
        created_at=doc.created_at,
    )


# ── Mappings (for drawer) ──────────────────────────────────────────────────────


@router.get("/{candidate_id}/mappings")
async def get_candidate_mappings(tenant: _Tenant, candidate_id: str) -> list[CandidateMappingItem]:
    cand_oid = to_object_id(candidate_id, "candidate_id")
    # Verify candidate belongs to this brand first
    exists = await Candidate.find_one(
        {"_id": cand_oid, "brand_id": tenant.brand_id, "is_active": True}
    )
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    pipeline = [
        {_MATCH: {"candidate_id": cand_oid, "brand_id": tenant.brand_id}},
        {
            _LOOKUP: {
                "from": "positions",
                "let": {"pos_id": "$position_id"},
                "pipeline": [{_MATCH: {_EXPR: {"$eq": ["$_id", "$$pos_id"]}}}],
                "as": "pos",
            }
        },
        {_UNWIND: "$pos"},
        {
            _ADD_FIELDS: {
                "mapping_id": {_TO_STR: "$_id"},
                "position_id": {_TO_STR: "$position_id"},
                "position_code": "$pos.code",
                "role": "$pos.role",
                "client_name": "$pos.client_name",
                "city": "$pos.city",
            }
        },
        {
            _UNSET: [
                "pos",
                "_id",
                "candidate_id",
                "employee_id",
                "history",
                "brand_id",
                "client_id",
                "decision",
                "feedback",
                "updated_at",
            ]
        },
        {_SORT: {"mapped_at": -1}},
    ]
    rows = await Mapping.get_motor_collection().aggregate(pipeline).to_list(length=None)
    return [CandidateMappingItem.model_validate(r) for r in rows]


# ── Resume confirm ─────────────────────────────────────────────────────────────


@router.post("/{candidate_id}/resume")
async def confirm_resume(
    tenant: _Tenant, candidate_id: str, data: ResumeConfirm
) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    await doc.set({"resume_public_id": data.resume_public_id, "resume_url": data.resume_url})
    cand_oid = to_object_id(candidate_id, "candidate_id")
    count = await Mapping.find({"candidate_id": cand_oid, "brand_id": tenant.brand_id}).count()
    return CandidateResponse(
        id=str(doc.id),
        full_name=doc.full_name,
        email=doc.email,
        phone=doc.phone,
        previous_company=doc.previous_company,
        experience_years=doc.experience_years,
        skills=doc.skills,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=count,
        created_at=doc.created_at,
    )
