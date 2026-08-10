"""Candidates API router — Phase B.

Endpoints:
  GET    /candidates                  list + search + filter (paginated)
  POST   /candidates                  create new candidate
  GET    /candidates/{id}             detail
  PATCH  /candidates/{id}             update profile fields
  GET    /candidates/{id}/mappings    positions this candidate is mapped to (for drawer)
  GET    /candidates/{id}/history     permanent ATS timeline + placements
  POST   /candidates/{id}/resume      confirm Cloudinary upload
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
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
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.common.dtos.pagination import PaginationMeta
from app.common.utils.object_id import to_object_id
from app.config import settings
from app.dependencies import get_tenant, require_maintainer
from app.modules.brands.models import AutomationSettings
from app.modules.brands.service import get_automation_settings
from app.modules.recruitment.enums import (
    CandidateEventType,
    CandidateStatus,
    PipelineStage,
)
from app.modules.recruitment.models import Candidate, CandidateEvent, Employee, Mapping
from app.modules.recruitment.repository_impl import record_candidate_event
from app.modules.recruitment.schemas import (
    BulkUploadFailure,
    BulkUploadResult,
    CandidateCreate,
    CandidateHistoryEvent,
    CandidateHistoryResponse,
    CandidateMappingItem,
    CandidatePage,
    CandidatePlacement,
    CandidateResponse,
    CandidateUpdate,
    ExperienceFilter,
    ResumeConfirm,
    TenantScope,
)
from app.modules.recruitment.utils.cv_access import can_view_cv, mask_cv_rows
from app.modules.storage.service import extract_text_from_file

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

# Sentinel accepted by the created_by filter for candidates nobody owns.
_UNASSIGNED = "unassigned"

# Stages that mean the candidate actually landed the job. Not TERMINAL_STAGES,
# which also counts `rejected` — a rejection closes a mapping but is not a
# placement, and must never show up under "companies this person joined".
_PLACEMENT_STAGES = (PipelineStage.offer_accepted, PipelineStage.position_close)


# ── Background tasks ───────────────────────────────────────────────────────────


async def _parse_and_update_resume(
    candidate_id: str, resume_url: str, automation: AutomationSettings
) -> None:
    """Download resume PDF, parse it, and update candidate fields.

    Runs as a background task after confirm_resume returns, and only when the
    brand has resume parsing enabled. Failures are logged but never surface to
    the caller — the resume URL is already saved.
    Fields are only updated when the candidate currently has no value
    (skills are always refreshed since the resume is the source of truth).
    """
    from app.modules.recruitment.services.resume_service import parse_resume_with

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(resume_url)
            resp.raise_for_status()
        raw_text = extract_text_from_file(resp.content)
        parsed = parse_resume_with(raw_text, automation)
    except Exception:
        _log.exception("Resume parse failed for candidate %s", candidate_id)
        return

    from app.common.utils.object_id import to_object_id

    try:
        oid = to_object_id(candidate_id, "candidate_id")
        doc = await Candidate.find_one({"_id": oid})
        if not doc:
            return

        from app.modules.recruitment.services.resume_service import build_candidate_resume_update

        update = build_candidate_resume_update(doc, parsed, raw_text)
        if update:
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


async def _owner_name(candidate: Candidate) -> str | None:
    """Display name of the recruiter who added this candidate, if any."""
    if candidate.created_by_id is None:
        return None
    owner = await Employee.get(candidate.created_by_id)
    return owner.name if owner else None


async def _build_candidate_response(
    doc: Candidate, mappings_count: int = 0, scope: TenantScope | None = None
) -> CandidateResponse:
    """Shared builder — resolves the owner's name and applies the CV lock.

    `scope` is optional only so the public application form, which has no
    viewer, can reuse the shape; every authenticated call site passes it.
    """
    cv_locked = scope is not None and not can_view_cv(scope, doc.created_by_id)
    return CandidateResponse.from_document(
        doc,
        mappings_count,
        created_by_name=await _owner_name(doc),
        cv_locked=cv_locked,
    )


async def _mappings_count(scope: TenantScope, candidate_id: str) -> int:
    cand_oid = to_object_id(candidate_id, "candidate_id")
    return await Mapping.find({"candidate_id": cand_oid, "brand_id": scope.brand_id}).count()


# ── Tags (must be before /{candidate_id} to avoid route conflict) ─────────────


@router.get("/tags")
async def list_candidate_tags(tenant: _Tenant) -> list[str]:
    """Return all distinct recruiter tags for candidates in this brand."""
    collection = Candidate.get_motor_collection()
    tags = await collection.distinct("tags", {"brand_id": tenant.brand_id, "is_active": True})
    return sorted(t for t in tags if t)


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("")
async def list_candidates(
    tenant: _Tenant,
    search: _Search = None,
    experience: _ExpFilter = None,
    stage: _Stage = None,
    source: Annotated[str | None, Query()] = None,
    source_channel: Annotated[str | None, Query()] = None,
    created_by: Annotated[
        str | None,
        Query(description="Employee id of the recruiter who added them, or 'unassigned'"),
    ] = None,
    tags: Annotated[list[str] | None, Query()] = None,
    has_resume: Annotated[bool | None, Query()] = None,
    has_cv_link: Annotated[bool | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    gender: Annotated[str | None, Query()] = None,
    status: Annotated[CandidateStatus | None, Query()] = CandidateStatus.approved,
    page: _Page = 1,
    limit: _Limit = 30,
) -> CandidatePage:
    match: dict = {"brand_id": tenant.brand_id, "is_active": True}
    # Status and search each need their own $or, so they are collected as $and
    # clauses. Assigning both to match["$or"] let search overwrite status,
    # leaking unapproved candidates into the directory whenever anyone searched.
    and_clauses: list[dict] = []

    if status is not None:
        if status == CandidateStatus.approved:
            # Candidates created before `status` existed have no such field.
            and_clauses.append({"$or": [{"status": status.value}, {"status": {"$exists": False}}]})
        else:
            match["status"] = status.value

    if search:
        # Escaped: an unbalanced "(" or "[" typed into the search box would
        # otherwise be an invalid regex and fail the whole query.
        rx = {"$regex": re.escape(search), "$options": "i"}
        and_clauses.append(
            {
                "$or": [
                    {"full_name": rx},
                    {"email": rx},
                    {"previous_company": rx},
                    {"skills": rx},
                ]
            }
        )

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

    if source_channel:
        match["source_channel"] = source_channel

    if created_by == _UNASSIGNED:
        # Public-form applications and anything predating created_by_id. A null
        # equality match covers both: Mongo treats a missing field as null here.
        match["created_by_id"] = None
    elif created_by:
        match["created_by_id"] = to_object_id(created_by, "created_by")

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

    if and_clauses:
        match["$and"] = and_clauses

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
            _LOOKUP: {
                "from": "employees",
                "localField": "created_by_id",
                "foreignField": "_id",
                "as": "owner",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "mappings_count": {_SIZE: "$cand_maps"},
                "created_by_id": {_TO_STR: "$created_by_id"},
                "created_by_name": {"$arrayElemAt": ["$owner.name", 0]},
            }
        },
        {_UNSET: ["cand_maps", "owner"]},
        {_SORT: {"created_at": -1, "full_name": 1}},
        _paginate(page, limit),
    ]
    result = await (await Candidate.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    items, total = _unpack(result)
    # Masked here rather than in the projection: the lock depends on who is
    # asking, and the same row is public to its owner and withheld from the desk
    # next to them.
    return _make_page(mask_cv_rows(items, tenant), total, page, limit, CandidateResponse)


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_candidate(tenant: _Tenant, data: CandidateCreate) -> CandidateResponse:
    # Spread the whole DTO instead of naming each field: the hand-written list
    # this replaced had drifted from CandidateCreate and silently dropped
    # expected_salary, notice_period, source and source_channel.
    # Only email and skills need massaging on the way in.
    doc = Candidate(
        **data.model_dump(exclude={"email", "skills"}),
        brand_id=tenant.brand_id,
        email=data.email.lower() if data.email else None,
        skills=data.skills,
        skills_normalized=[s.lower() for s in data.skills],
        created_by_id=tenant.employee_id,
    )
    try:
        await doc.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A candidate with this email already exists in this brand",
        ) from None
    await record_candidate_event(
        scope=tenant,
        candidate_id=doc.id,
        event_type=CandidateEventType.created,
        note="Added to the talent pool",
    )
    return await _build_candidate_response(doc, 0, tenant)


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

    With the brand's resume parsing switched off, each file is still read for
    its email address — that is how a candidate is identified here — but no
    skills, tags or other fields are inferred from it.
    """
    if len(files) > _BULK_MAX:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Maximum {_BULK_MAX} files per upload")

    # Resolved once for the whole batch rather than per file: 50 identical
    # brand lookups, and a mid-batch toggle would split one upload's behaviour.
    automation = await get_automation_settings(tenant.brand_id)

    created = 0
    updated = 0
    failed: list[BulkUploadFailure] = []

    for upload in files:
        filename = upload.filename or "unknown"
        try:
            file_bytes = await upload.read()

            from app.modules.recruitment.services.resume_service import process_resume_bytes

            try:
                raw_text, parsed, resume_url, resume_public_id = await process_resume_bytes(
                    file_bytes, filename, automation, email_only=True
                )
            except ValueError as exc:
                failed.append(BulkUploadFailure(filename=filename, reason=str(exc)))
                continue
            except Exception as exc:
                failed.append(
                    BulkUploadFailure(filename=filename, reason=f"Storage upload failed: {exc}")
                )
                continue

            if not parsed.email:
                failed.append(
                    BulkUploadFailure(filename=filename, reason="No email address found in resume")
                )
                continue

            # 4. Upsert candidate by email
            email_lower = parsed.email.lower()
            existing = await Candidate.find_one({"email": email_lower, "brand_id": tenant.brand_id})

            if existing:
                from app.modules.recruitment.services.resume_service import (
                    build_candidate_resume_update,
                )

                patch = build_candidate_resume_update(
                    existing_doc=existing,
                    parsed=parsed,
                    raw_text=raw_text,
                    resume_url=resume_url,
                    resume_public_id=resume_public_id,
                )
                if patch:
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
                    tags=parsed.tags,
                    resume_url=resume_url,
                    resume_public_id=resume_public_id,
                    resume_raw_text=raw_text,
                    created_by_id=tenant.employee_id,
                )
                try:
                    await doc.insert()
                    created += 1
                    await record_candidate_event(
                        scope=tenant,
                        candidate_id=doc.id,
                        event_type=CandidateEventType.created,
                        note=f"Added by bulk resume upload ({filename})",
                    )
                except DuplicateKeyError:
                    failed.append(
                        BulkUploadFailure(
                            filename=filename,
                            reason="Candidate with this email already exists",
                        )
                    )

        except OperationFailure as exc:
            _log.exception("Bulk upload: MongoDB operation failed for %s", filename)
            failed.append(
                BulkUploadFailure(
                    filename=filename,
                    reason=f"Database write failed (Quota Exceeded?): {exc.details.get('errmsg', str(exc)) if hasattr(exc, 'details') and isinstance(exc.details, dict) else str(exc)}",
                )
            )
        except Exception as exc:
            _log.exception("Bulk upload: unexpected error for %s", filename)
            failed.append(
                BulkUploadFailure(filename=filename, reason=f"Unexpected server error: {exc}")
            )

    return BulkUploadResult(created=created, updated=updated, failed=failed)


# ── Detail ─────────────────────────────────────────────────────────────────────


@router.get("/{candidate_id}")
async def get_candidate(tenant: _Tenant, candidate_id: str) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    return await _build_candidate_response(doc, await _mappings_count(tenant, candidate_id), tenant)


# ── Update ─────────────────────────────────────────────────────────────────────


@router.patch("/{candidate_id}")
async def update_candidate(
    tenant: _Tenant, candidate_id: str, data: CandidateUpdate
) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    # Whole-DTO dump instead of a field-by-field if-chain: that chain had drifted
    # from CandidateUpdate and silently ignored expected_salary, notice_period,
    # source and source_channel on every save. exclude_none keeps
    # the established contract that an omitted (or null) field means "leave it".
    update: dict = data.model_dump(exclude_unset=True, exclude_none=True)
    if "skills" in update:
        update["skills_normalized"] = [s.lower() for s in update["skills"]]
    # A viewer who cannot see the CV was served nulls for these, so accepting
    # them back would let an edit of any other field quietly clear another
    # recruiter's CV off the record.
    if not can_view_cv(tenant, doc.created_by_id):
        update.pop("cv_link", None)
    if update:
        await doc.set(update)
    return await _build_candidate_response(doc, await _mappings_count(tenant, candidate_id), tenant)


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


# ── Status Update ─────────────────────────────────────────────────────────────


@router.post("/{candidate_id}/approve")
async def approve_candidate(
    tenant: _Tenant, candidate_id: str, _: Annotated[object, Depends(require_maintainer)]
) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    await doc.set({"status": CandidateStatus.approved})
    await record_candidate_event(
        scope=tenant,
        candidate_id=doc.id,
        event_type=CandidateEventType.approved,
        note="Application approved",
    )
    return await _build_candidate_response(doc, await _mappings_count(tenant, candidate_id), tenant)


@router.post("/{candidate_id}/reject")
async def reject_candidate(
    tenant: _Tenant, candidate_id: str, _: Annotated[object, Depends(require_maintainer)]
) -> CandidateResponse:
    doc = await _get_or_404(tenant, candidate_id)
    await doc.set({"status": CandidateStatus.rejected})
    await record_candidate_event(
        scope=tenant,
        candidate_id=doc.id,
        event_type=CandidateEventType.declined,
        note="Application declined at review",
    )
    return await _build_candidate_response(doc, await _mappings_count(tenant, candidate_id), tenant)


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


# ── History (ATS timeline + placements) ────────────────────────────────────────


def _event_to_dto(row: CandidateEvent) -> CandidateHistoryEvent:
    return CandidateHistoryEvent(
        id=str(row.id),
        at=row.at,
        event_type=row.event_type,
        employee_id=str(row.employee_id) if row.employee_id else None,
        employee_name=row.employee_name,
        position_id=str(row.position_id) if row.position_id else None,
        position_code=row.position_code,
        position_role=row.position_role,
        client_name=row.client_name,
        from_stage=row.from_stage,
        to_stage=row.to_stage,
        note=row.note,
    )


def _opening_event(candidate: Candidate, owner_name: str | None) -> CandidateHistoryEvent:
    """The "how this person got here" entry, derived from the candidate record.

    Synthesised rather than stored so that profiles created before history
    existed still open with something truthful instead of a gap.
    """
    applied = (candidate.source or "").lower() == "external" and candidate.created_by_id is None
    return CandidateHistoryEvent(
        at=candidate.created_at,
        event_type=CandidateEventType.applied if applied else CandidateEventType.created,
        employee_id=str(candidate.created_by_id) if candidate.created_by_id else None,
        employee_name=owner_name,
        note=(
            f"Applied through the public form ({candidate.source_channel})"
            if applied and candidate.source_channel
            else "Applied through the public form"
            if applied
            else "Added to the talent pool"
        ),
    )


async def _live_placements(
    scope: TenantScope, cand_oid, fallback_at: datetime
) -> list[CandidatePlacement]:
    """Placements read off the candidate's current mappings.

    The authoritative "where are they now": a mapping sitting in offer_accepted
    or position_close is a live placement even if its history was never recorded.

    `fallback_at` covers a raw Mongo document that predates both `updated_at`
    and `mapped_at` — Beanie always writes them now, but this reads the motor
    collection directly, so it cannot lean on that. Without it, a legacy
    document would leave `at` null and fail CandidatePlacement's validation,
    404ing this candidate's whole history instead of just guessing a date.
    """
    agg = [
        {
            _MATCH: {
                "brand_id": scope.brand_id,
                "candidate_id": cand_oid,
                "stage": {"$in": [s.value for s in _PLACEMENT_STAGES]},
            }
        },
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
            _LOOKUP: {
                "from": "employees",
                "localField": "employee_id",
                "foreignField": "_id",
                "as": "emp",
            }
        },
        {_SORT: {"updated_at": -1}},
    ]
    rows = await (await Mapping.get_motor_collection().aggregate(agg)).to_list(length=None)
    return [
        CandidatePlacement(
            position_id=str(r["position_id"]),
            position_code=r["pos"].get("code"),
            role=r["pos"].get("role"),
            client_name=r["pos"].get("client_name"),
            stage=PipelineStage(r["stage"]),
            at=r.get("updated_at") or r.get("mapped_at") or fallback_at,
            employee_name=(r["emp"][0].get("name") if r.get("emp") else None),
            is_current=True,
        )
        for r in rows
    ]


def _historic_placements(events: list[CandidateEvent]) -> list[CandidatePlacement]:
    """Placements that happened at some point, read off the permanent history.

    Keeps a past placement on the profile after the candidate was moved on or
    taken off the board entirely — the whole point of recording history.
    """
    latest: dict[tuple[str, str], CandidateEvent] = {}
    for event in events:
        if event.to_stage not in _PLACEMENT_STAGES:
            continue
        key = (str(event.position_id or ""), event.to_stage.value)
        if key not in latest or event.at > latest[key].at:
            latest[key] = event
    return [
        CandidatePlacement(
            position_id=str(e.position_id) if e.position_id else None,
            position_code=e.position_code,
            role=e.position_role,
            client_name=e.client_name,
            stage=e.to_stage,  # type: ignore[arg-type]  # filtered above
            at=e.at,
            employee_name=e.employee_name,
            is_current=False,
        )
        for e in latest.values()
    ]


@router.get("/{candidate_id}/history")
async def get_candidate_history(tenant: _Tenant, candidate_id: str) -> CandidateHistoryResponse:
    """Everything that has happened to this candidate, oldest first.

    Reads the permanent candidate_events collection rather than the activity
    feed: activities carry a 90-day TTL, so anything older has already been
    deleted, and a placement made last year still belongs on the profile.
    """
    candidate = await _get_or_404(tenant, candidate_id)

    # _id breaks ties on `at`: BSON stores datetimes at millisecond resolution,
    # so two events recorded in the same request (a move that also closes a
    # mapping, say) can carry an identical timestamp and come back in either
    # order. ObjectIds ascend with insertion, which is the order that happened.
    rows = (
        await CandidateEvent.find({"brand_id": tenant.brand_id, "candidate_id": candidate.id})
        .sort("+at", "+_id")
        .to_list()
    )

    events = [_event_to_dto(r) for r in rows]
    if not any(
        e.event_type in (CandidateEventType.created, CandidateEventType.applied) for e in events
    ):
        events.insert(0, _opening_event(candidate, await _owner_name(candidate)))

    live = await _live_placements(tenant, candidate.id, candidate.created_at)
    live_keys = {(p.position_id, p.stage.value) for p in live}
    placements = live + [
        p for p in _historic_placements(rows) if (p.position_id, p.stage.value) not in live_keys
    ]
    placements.sort(key=lambda p: p.at, reverse=True)

    return CandidateHistoryResponse(events=events, placements=placements)


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
    # Nothing is scheduled at all when the brand has parsing off — the resume is
    # attached and left unread.
    automation = await get_automation_settings(tenant.brand_id)
    if automation.resume_parsing_enabled:
        background_tasks.add_task(
            _parse_and_update_resume, candidate_id, data.resume_url, automation
        )
    return await _build_candidate_response(doc, await _mappings_count(tenant, candidate_id), tenant)
