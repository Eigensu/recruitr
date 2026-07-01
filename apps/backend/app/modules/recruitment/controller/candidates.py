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

import asyncio
import logging
import re
from typing import Annotated

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pymongo.errors import DuplicateKeyError

from app.common.dtos.pagination import PaginationMeta
from app.common.utils.object_id import to_object_id
from app.config import settings
from app.dependencies import get_tenant, require_maintainer
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.models import Candidate, Mapping
from app.modules.recruitment.schemas import (
    BulkUploadFailure,
    BulkUploadResult,
    CandidateCreate,
    CandidateMappingItem,
    CandidatePage,
    CandidateResponse,
    CandidateUpdate,
    ExperienceFilter,
    ResumeConfirm,
    TenantScope,
)
from app.modules.recruitment.utils.resume_parser import parse_resume
from app.modules.storage.service import extract_text_from_file, upload_bytes_to_cloudinary

_CLOUDINARY_HOST = f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/"

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

_log = logging.getLogger(__name__)


# ── Background tasks ───────────────────────────────────────────────────────────


async def _parse_and_update_resume(candidate_id: str, resume_url: str) -> None:
    """Download resume PDF, parse it, and update candidate fields.

    Runs as a background task after confirm_resume returns. Failures are logged
    but never surface to the caller — the resume URL is already saved.
    Fields are only updated when the candidate currently has no value
    (skills are always refreshed since the resume is the source of truth).
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(resume_url)
            resp.raise_for_status()
        raw_text = extract_text_from_file(resp.content)
        parsed = parse_resume(raw_text)
    except Exception:
        _log.exception("Resume parse failed for candidate %s", candidate_id)
        return

    from app.common.utils.object_id import to_object_id

    try:
        oid = to_object_id(candidate_id, "candidate_id")
        doc = await Candidate.find_one({"_id": oid})
        if not doc:
            return

        update: dict = {"resume_raw_text": raw_text}
        if parsed.skills:
            update["skills"] = parsed.skills
            update["skills_normalized"] = [s.lower() for s in parsed.skills]
        if parsed.phone and not doc.phone:
            update["phone"] = parsed.phone
        if parsed.experience_years is not None and doc.experience_years == 0:
            update["experience_years"] = parsed.experience_years
        if parsed.education_level is not None and doc.education_level is None:
            update["education_level"] = parsed.education_level
        if parsed.tags:
            update["tags"] = parsed.tags
        if parsed.previous_company and not doc.previous_company:
            update["previous_company"] = parsed.previous_company

        await doc.set(update)
    except Exception:
        _log.exception("Resume DB update failed for candidate %s", candidate_id)


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


_NOISE_RE = re.compile(
    r"\b(resume|cv|curriculum|vitae|portfolio|application|profile|updated?)\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _name_from_filename(filename: str) -> str:
    """Derive a best-guess candidate name from a resume filename.

    e.g. "john_doe_resume_2024.pdf" → "John Doe"
         "CV - Jane Smith.docx"     → "Jane Smith"
    """
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    name = stem.replace("_", " ").replace("-", " ").replace(".", " ")
    name = _NOISE_RE.sub("", name)
    name = _YEAR_RE.sub("", name)
    words = [w.capitalize() for w in name.split() if w]
    return " ".join(words) if words else stem


async def _get_or_404(scope: TenantScope, candidate_id: str) -> Candidate:
    oid = to_object_id(candidate_id, "candidate_id")
    doc = await Candidate.find_one({"_id": oid, "brand_id": scope.brand_id, "is_active": True})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return doc


# ── Tags (must be before /{candidate_id} to avoid route conflict) ─────────────


@router.get("/tags")
async def list_candidate_tags(tenant: _Tenant) -> list[str]:
    """Return all distinct recruiter tags for candidates in this brand."""
    collection = Candidate.get_motor_collection()
    tags = await collection.distinct(
        "tags", {"brand_id": tenant.brand_id, "is_active": True}
    )
    return sorted(t for t in tags if t)


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("")
async def list_candidates(
    tenant: _Tenant,
    search: _Search = None,
    experience: _ExpFilter = None,
    stage: _Stage = None,
    source: Annotated[str | None, Query()] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    has_resume: Annotated[bool | None, Query()] = None,
    has_cv_link: Annotated[bool | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    gender: Annotated[str | None, Query()] = None,
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

    if source:
        match["source"] = source

    if city:
        match["city"] = city
        
    if gender:
        match["gender"] = gender

    if tags:
        match["tags"] = {"$in": tags}

    if has_resume is True:
        match["resume_url"] = {"$exists": True, "$nin": [None, ""]}
    elif has_resume is False:
        match["resume_url"] = {"$in": [None, ""]}

    if has_cv_link is True:
        match["cv_link"] = {"$exists": True, "$nin": [None, ""]}
    elif has_cv_link is False:
        match["cv_link"] = {"$in": [None, ""]}

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
        salary=doc.salary,
        notes=doc.notes,
        created_at=doc.created_at,
    )


# ── Bulk resume upload ─────────────────────────────────────────────────────────
# Route must appear before /{candidate_id} so FastAPI doesn't treat "bulk-upload"
# as a path parameter.

_BULK_MAX = 50


@router.post("/bulk-upload")
async def bulk_upload_resumes(
    tenant: _Tenant,
    files: list[UploadFile] = File(..., description="PDF or DOCX resume files (max 50)"),
) -> BulkUploadResult:
    """Upload multiple resume files and create or update candidate records.

    Per file:
    - Extracts text (PDF or DOCX) and parses structured fields
    - Requires an email address in the resume — files without one are skipped
    - Upserts by email: creates a new Candidate or refreshes an existing one's
      skills / resume URL without overwriting fields the recruiter has set
    - Uploads the file to Cloudinary and stores resume_url on the candidate
    """
    if len(files) > _BULK_MAX:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Maximum {_BULK_MAX} files per upload")

    created = 0
    updated = 0
    failed: list[BulkUploadFailure] = []

    for upload in files:
        filename = upload.filename or "unknown"
        try:
            file_bytes = await upload.read()

            # 1. Extract text
            try:
                raw_text = extract_text_from_file(file_bytes)
            except ValueError as exc:
                failed.append(BulkUploadFailure(filename=filename, reason=str(exc)))
                continue

            # 2. Parse structured fields
            parsed = parse_resume(raw_text)
            if not parsed.email:
                failed.append(
                    BulkUploadFailure(filename=filename, reason="No email address found in resume")
                )
                continue

            # 3. Upload to Cloudinary (blocking SDK call → thread pool)
            try:
                cld = await asyncio.to_thread(upload_bytes_to_cloudinary, file_bytes, filename)
            except Exception as exc:
                failed.append(
                    BulkUploadFailure(filename=filename, reason=f"Storage upload failed: {exc}")
                )
                continue

            resume_url: str = cld.get("secure_url", "")
            resume_public_id: str = cld.get("public_id", "")

            # 4. Upsert candidate by email
            email_lower = parsed.email.lower()
            existing = await Candidate.find_one({"email": email_lower, "brand_id": tenant.brand_id})

            if existing:
                patch: dict = {
                    "resume_url": resume_url,
                    "resume_public_id": resume_public_id,
                    "resume_raw_text": raw_text,
                }
                if parsed.skills:
                    patch["skills"] = parsed.skills
                    patch["skills_normalized"] = [s.lower() for s in parsed.skills]
                if parsed.ai_tags:
                    patch["ai_tags"] = parsed.ai_tags
                if parsed.phone and not existing.phone:
                    patch["phone"] = parsed.phone
                if parsed.experience_years is not None and existing.experience_years == 0:
                    patch["experience_years"] = parsed.experience_years
                if parsed.education_level is not None and existing.education_level is None:
                    patch["education_level"] = parsed.education_level
                if parsed.previous_company and not existing.previous_company:
                    patch["previous_company"] = parsed.previous_company
                await existing.set(patch)
                updated += 1
            else:
                doc = Candidate(
                    brand_id=tenant.brand_id,
                    full_name=_name_from_filename(filename),
                    email=email_lower,
                    phone=parsed.phone,
                    previous_company=parsed.previous_company,
                    experience_years=parsed.experience_years or 0,
                    education_level=parsed.education_level,
                    skills=parsed.skills,
                    skills_normalized=[s.lower() for s in parsed.skills],
                    ai_tags=parsed.ai_tags,
                    resume_url=resume_url,
                    resume_public_id=resume_public_id,
                    resume_raw_text=raw_text,
                )
                try:
                    await doc.insert()
                    created += 1
                except DuplicateKeyError:
                    failed.append(
                        BulkUploadFailure(
                            filename=filename,
                            reason="Candidate with this email already exists",
                        )
                    )

        except Exception:
            _log.exception("Bulk upload: unexpected error for %s", filename)
            failed.append(BulkUploadFailure(filename=filename, reason="Unexpected server error"))

    return BulkUploadResult(created=created, updated=updated, failed=failed)


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
    if data.skills is not None:
        update["skills"] = data.skills
        update["skills_normalized"] = [s.lower() for s in data.skills]
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
    if data.tags is not None:
        update["tags"] = data.tags
    if data.preferred_train_line is not None:
        update["preferred_train_line"] = data.preferred_train_line
    if data.cv_link is not None:
        update["cv_link"] = data.cv_link
    if data.current_role is not None:
        update["current_role"] = data.current_role
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
        salary=doc.salary,
        notes=doc.notes,
        created_at=doc.created_at,
    )


# ── Delete (soft) ─────────────────────────────────────────────────────────────


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    tenant: _Tenant,
    candidate_id: str,
    _: Annotated[object, Depends(require_maintainer)],
):
    """Soft-delete a candidate (sets is_active=False). Mappings are preserved."""
    doc = await _get_or_404(tenant, candidate_id)
    await doc.set({"is_active": False})


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
    tenant: _Tenant,
    candidate_id: str,
    data: ResumeConfirm,
    background_tasks: BackgroundTasks,
) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    if settings.CLOUDINARY_CLOUD_NAME and not data.resume_url.startswith(_CLOUDINARY_HOST):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "resume_url must be a Cloudinary URL")
    await doc.set({"resume_public_id": data.resume_public_id, "resume_url": data.resume_url})
    background_tasks.add_task(_parse_and_update_resume, candidate_id, data.resume_url)
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
        salary=doc.salary,
        notes=doc.notes,
        created_at=doc.created_at,
    )
