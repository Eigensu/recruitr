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
    source: str | None = Query(default=None, description="Filter by source"),
    city: str | None = Query(default=None, description="Filter by city"),
    gender: str | None = Query(default=None, description="Filter by gender"),
    has_resume: bool | None = Query(default=None, description="Filter by resume existence"),
    has_cv_link: bool | None = Query(default=None, description="Filter by cv link existence"),
    tags: list[str] = Query(default_factory=list, description="Filter by tags"),
    page: _Page = 1,
    limit: _Limit = 30,
) -> CandidatePage:
    match: dict = {"brand_id": tenant.brand_id, "is_active": True}

    if source == "internal":
        match["source"] = {"$in": ["internal", None]}
    elif source == "external":
        match["source"] = "external"
    if city:
        match["city"] = {"$regex": f"^{city}$", "$options": "i"}
    if gender:
        match["gender"] = gender
    if has_resume is True:
        match["resume_url"] = {"$ne": None}
    elif has_resume is False:
        match["resume_url"] = None
    if has_cv_link is True:
        match["cv_link"] = {"$ne": None, "$ne": ""}
    elif has_cv_link is False:
        match["cv_link"] = {"$in": [None, ""]}
    if tags:
        match["tags"] = {"$in": tags}

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
    result = await (await Candidate.get_motor_collection().aggregate(pipeline)).to_list(length=None)
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
        education_level=data.education_level,
        city=data.city,
        area=data.area,
        gender=data.gender,
        age=data.age,
        skills=data.skills,
        skills_normalized=[s.lower() for s in data.skills],
        tags=data.tags,
        preferred_train_line=data.preferred_train_line,
        cv_link=data.cv_link,
        current_role=data.current_role,
        previous_role=data.previous_role,
        expected_salary=data.expected_salary,
        notice_period=data.notice_period,
        source=data.source,
        salary=data.salary,
        notes=data.notes,
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
        education_level=doc.education_level,
        city=doc.city,
        area=doc.area,
        gender=doc.gender,
        age=doc.age,
        skills=doc.skills,
        tags=doc.tags,
        preferred_train_line=doc.preferred_train_line,
        cv_link=doc.cv_link,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=0,
        current_role=doc.current_role,
        previous_role=doc.previous_role,
        expected_salary=doc.expected_salary,
        notice_period=doc.notice_period,
        source=doc.source,
        salary=doc.salary,
        notes=doc.notes,
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
        education_level=doc.education_level,
        city=doc.city,
        area=doc.area,
        gender=doc.gender,
        age=doc.age,
        skills=doc.skills,
        tags=doc.tags,
        preferred_train_line=doc.preferred_train_line,
        cv_link=doc.cv_link,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=count,
        current_role=doc.current_role,
        previous_role=doc.previous_role,
        expected_salary=doc.expected_salary,
        notice_period=doc.notice_period,
        source=doc.source,
        salary=doc.salary,
        notes=doc.notes,
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
    if data.education_level is not None:
        update["education_level"] = data.education_level
    if data.city is not None:
        update["city"] = data.city
    if data.area is not None:
        update["area"] = data.area
    if data.gender is not None:
        update["gender"] = data.gender
    if data.age is not None:
        update["age"] = data.age
    if data.skills is not None:
        update["skills"] = data.skills
        update["skills_normalized"] = [s.lower() for s in data.skills]
    if data.tags is not None:
        update["tags"] = data.tags
    if data.preferred_train_line is not None:
        update["preferred_train_line"] = data.preferred_train_line
    if data.cv_link is not None:
        update["cv_link"] = data.cv_link
    if data.current_role is not None:
        update["current_role"] = data.current_role
    if data.previous_role is not None:
        update["previous_role"] = data.previous_role
    if data.expected_salary is not None:
        update["expected_salary"] = data.expected_salary
    if data.notice_period is not None:
        update["notice_period"] = data.notice_period
    if data.source is not None:
        update["source"] = data.source
    if data.salary is not None:
        update["salary"] = data.salary
    if data.notes is not None:
        update["notes"] = data.notes

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
        education_level=doc.education_level,
        city=doc.city,
        area=doc.area,
        gender=doc.gender,
        age=doc.age,
        skills=doc.skills,
        tags=doc.tags,
        preferred_train_line=doc.preferred_train_line,
        cv_link=doc.cv_link,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=count,
        current_role=doc.current_role,
        previous_role=doc.previous_role,
        expected_salary=doc.expected_salary,
        notice_period=doc.notice_period,
        source=doc.source,
        salary=doc.salary,
        notes=doc.notes,
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
    rows = await (await Mapping.get_motor_collection().aggregate(pipeline)).to_list(length=None)
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
        education_level=doc.education_level,
        city=doc.city,
        area=doc.area,
        gender=doc.gender,
        age=doc.age,
        skills=doc.skills,
        tags=doc.tags,
        preferred_train_line=doc.preferred_train_line,
        cv_link=doc.cv_link,
        resume_url=doc.resume_url,
        current_stage=doc.current_stage,
        mappings_count=count,
        current_role=doc.current_role,
        previous_role=doc.previous_role,
        expected_salary=doc.expected_salary,
        notice_period=doc.notice_period,
        source=doc.source,
        salary=doc.salary,
        notes=doc.notes,
        created_at=doc.created_at,
    )
