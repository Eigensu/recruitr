# Implementation Spec — Recruitr Feature Additions

**Date:** 2026-06-10  
**Spec version:** 1.0  
**Based on:** Tech Spec (2026-06-10) + open questions resolved as "keep all options"

---

## Open Questions — Resolved Decisions

| Question                      | Decision                                                                                                                                            |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tags scope                    | **Global** — `GET /candidates/tags` returns all distinct tags across all candidates. No brand-scoping for now.                                      |
| Bulk upload duplicates        | **Upsert** — if parsed email matches an existing candidate, update their record (merge skills, overwrite resume). If no match, create new.          |
| CV link vs resume exclusivity | **Allow both simultaneously** — neither field clears the other. Recruiter can have a Cloudinary resume AND an external link.                        |
| Client Profiles "Status"      | **Computed** — "active" if ≥1 job opening for the client is `open`, "on_hold" if none are `open` but ≥1 is `on_hold`, "closed" if all are `closed`. |
| Kanban filter scope           | **Per-position board only** — filters apply within the current position's Kanban view. No positions-list-page filtering in this phase.              |

---

## Phase Overview & Dependency Order

```
Phase 1A  Candidate model + indexes
Phase 1B  Candidate schemas
Phase 1C  Candidate service (filter logic)
Phase 1D  Candidate router (new endpoints)
Phase 1E  JobOpening model extension
Phase 1F  Pipeline service (last_activity_at update)
Phase 1G  Pipeline router (new filtered endpoint)
Phase 1H  Dashboard repository (client-profiles query)
Phase 1I  Dashboard schemas (new response types)
Phase 1J  Dashboard service (new function)
Phase 1K  Dashboard controller (new route)
          ↓
Phase 2A  Frontend: candidate types
Phase 2B  Frontend: candidate API client
Phase 2C  Frontend: CandidateFilterBar component
Phase 2D  Frontend: AddCandidateForm component
Phase 2E  Frontend: BulkUploadDrawer component
Phase 2F  Frontend: CandidateTable component
Phase 2G  Frontend: candidates page.tsx (wire everything)
          ↓
Phase 3A  Frontend: KanbanFilterBar component
Phase 3B  Frontend: usePipelineStore (extend for filters)
Phase 3C  Frontend: Board.tsx (wire filter bar)
Phase 3D  Frontend: pipeline API client (new filtered fetch)
          ↓
Phase 4A  Frontend: dashboard types (ClientProfileRow)
Phase 4B  Frontend: dashboard API client (fetchClientProfiles)
Phase 4C  Frontend: ClientProfilesTable component
Phase 4D  Frontend: dashboard-data.ts (fetchClientProfiles)
Phase 4E  Frontend: page.tsx (swap component)
```

---

## Phase 1 — Backend

### 1A — Extend `Candidate` Model

**File:** `apps/backend/app/modules/candidates/models.py`

**Current state:** 7 fields — `name`, `email`, `phone`, `resume_public_id`, `resume_url`, `resume_raw_text`, `extracted_skills[]`.

**Change:** Add `tags`, `source`, `cv_link`. Add two new indexes.

```python
# Full file replacement:

"""Beanie Document model for Candidates."""

from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class Candidate(Document):
    name: str
    email: str
    phone: str | None = None
    resume_public_id: str | None = None
    resume_url: str | None = None
    resume_raw_text: str | None = None
    extracted_skills: list[str] = Field(default_factory=list)
    # ── New fields ────────────────────────────────────────────────────────────
    tags: list[str] = Field(default_factory=list)
    source: Literal["internal", "external"] = "internal"
    cv_link: str | None = None

    class Settings:
        name = "candidates"
        indexes = [
            IndexModel("email", unique=True),
            IndexModel("extracted_skills"),
            IndexModel("tags"),      # multikey — supports $all / $in queries
            IndexModel("source"),    # equality filter
        ]
```

**Why no migration script:** Beanie reads missing fields as their Python default. All existing documents will get `tags=[]`, `source="internal"`, `cv_link=None` transparently.

---

### 1B — Extend `Candidate` Schemas

**File:** `apps/backend/app/modules/candidates/schemas.py`

**Full replacement:**

```python
"""Pydantic schemas for the Candidates API."""

from typing import Literal

from pydantic import BaseModel, EmailStr, HttpUrl


class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    extracted_skills: list[str] = []
    # ── New ───────────────────────────────────────────────────────────────────
    cv_link: str | None = None
    source: Literal["internal", "external"] = "internal"
    tags: list[str] = []


class CandidateUpdate(BaseModel):
    """Partial update — all fields optional."""
    name: str | None = None
    phone: str | None = None
    cv_link: str | None = None
    source: Literal["internal", "external"] | None = None
    tags: list[str] | None = None


class CandidateListFilters(BaseModel):
    """Query parameters for GET /candidates."""
    search: str | None = None
    source: Literal["internal", "external"] | None = None
    tags: list[str] | None = None        # ?tags=python&tags=senior  (AND semantics)
    has_resume: bool | None = None
    has_cv_link: bool | None = None
    page: int = 1
    limit: int = 50


class CandidateUploadConfirm(BaseModel):
    """Sent after a successful Cloudinary upload to register the asset."""
    candidate_id: str
    resume_public_id: str
    resume_url: str


class CandidateResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None = None
    resume_url: str | None = None
    extracted_skills: list[str]
    # ── New ───────────────────────────────────────────────────────────────────
    tags: list[str] = []
    source: Literal["internal", "external"] = "internal"
    cv_link: str | None = None

    model_config = {"from_attributes": True}


class CandidateMatchScore(CandidateResponse):
    """Candidate with a computed keyword match score (from aggregation)."""
    match_score: float


class BulkUploadFailure(BaseModel):
    filename: str
    reason: str


class BulkUploadResult(BaseModel):
    created: int
    updated: int
    failed: list[BulkUploadFailure]
```

---

### 1C — Extend `Candidate` Service

**File:** `apps/backend/app/modules/candidates/service.py`

**Full replacement:**

```python
"""Business logic for Candidate management."""

import io
from typing import Any

import fitz  # PyMuPDF
from beanie import PydanticObjectId
from fastapi import HTTPException, UploadFile, status

from app.modules.candidates.models import Candidate
from app.modules.candidates.schemas import (
    BulkUploadFailure,
    BulkUploadResult,
    CandidateCreate,
    CandidateListFilters,
    CandidateUpdate,
    CandidateUploadConfirm,
)
from app.modules.storage.service import upload_bytes_to_cloudinary


async def create_candidate(data: CandidateCreate) -> Candidate:
    existing = await Candidate.find_one(Candidate.email == data.email.lower())
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A candidate with this email already exists",
        )
    candidate = Candidate(**data.model_dump())
    candidate.email = candidate.email.lower()
    await candidate.insert()
    return candidate


async def update_candidate(candidate_id: str, data: CandidateUpdate) -> Candidate:
    candidate = await get_candidate(candidate_id)
    update_data = data.model_dump(exclude_none=True)
    if update_data:
        await candidate.set(update_data)
    return candidate


async def confirm_resume_upload(data: CandidateUploadConfirm) -> Candidate:
    candidate = await get_candidate(data.candidate_id)
    await candidate.set({
        "resume_public_id": data.resume_public_id,
        "resume_url": data.resume_url,
    })
    return candidate


async def get_candidate(candidate_id: str) -> Candidate:
    candidate = await Candidate.get(PydanticObjectId(candidate_id))
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


async def list_candidates(filters: CandidateListFilters) -> list[Candidate]:
    match: dict[str, Any] = {}

    if filters.search:
        match["$or"] = [
            {"name": {"$regex": filters.search, "$options": "i"}},
            {"email": {"$regex": filters.search, "$options": "i"}},
            {"extracted_skills": {"$in": [filters.search.lower()]}},
            {"tags": {"$in": [filters.search.lower()]}},
        ]
    if filters.source:
        match["source"] = filters.source
    if filters.tags:
        # AND semantics: candidate must have ALL requested tags
        match["tags"] = {"$all": [t.lower() for t in filters.tags]}
    if filters.has_resume is True:
        match["resume_url"] = {"$ne": None}
    elif filters.has_resume is False:
        match["resume_url"] = None
    if filters.has_cv_link is True:
        match["cv_link"] = {"$ne": None}
    elif filters.has_cv_link is False:
        match["cv_link"] = None

    skip = (filters.page - 1) * filters.limit
    return await Candidate.find(match).skip(skip).limit(filters.limit).to_list()


async def get_distinct_tags() -> list[str]:
    """Return all distinct tags across all candidate documents, sorted."""
    collection = Candidate.get_motor_collection()
    tags = await collection.distinct("tags")
    return sorted(t for t in tags if t)


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def _extract_skills_from_text(text: str) -> list[str]:
    """
    Phase 1: naive keyword extraction — lower-case tokens longer than 2 chars.
    Phase 2: replace with LLM-based extraction.
    """
    words = set(text.lower().split())
    return [w for w in words if len(w) > 2 and w.isalpha()][:50]


def _extract_email_from_text(text: str) -> str | None:
    import re
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0).lower() if match else None


async def bulk_upload_candidates(files: list[UploadFile]) -> BulkUploadResult:
    """
    For each PDF file:
      1. Upload to Cloudinary
      2. Extract text + skills
      3. Upsert Candidate (match on email, create if no email found)
    """
    created = 0
    updated = 0
    failed: list[BulkUploadFailure] = []

    for file in files:
        filename = file.filename or "unknown.pdf"
        try:
            pdf_bytes = await file.read()
            if not pdf_bytes:
                failed.append(BulkUploadFailure(filename=filename, reason="Empty file"))
                continue

            # Upload to Cloudinary
            upload_result = await upload_bytes_to_cloudinary(pdf_bytes, filename)
            resume_public_id = upload_result["public_id"]
            resume_url = upload_result["secure_url"]

            # Extract content
            raw_text = _extract_text_from_pdf(pdf_bytes)
            skills = _extract_skills_from_text(raw_text)
            email = _extract_email_from_text(raw_text)

            if email:
                existing = await Candidate.find_one(Candidate.email == email)
                if existing:
                    await existing.set({
                        "resume_public_id": resume_public_id,
                        "resume_url": resume_url,
                        "resume_raw_text": raw_text,
                        "extracted_skills": list(set(existing.extracted_skills + skills)),
                    })
                    updated += 1
                    continue

            # No email match — create new candidate with placeholder name from filename
            candidate_name = filename.replace(".pdf", "").replace("_", " ").replace("-", " ").title()
            candidate = Candidate(
                name=candidate_name,
                email=email or f"unknown_{resume_public_id.split('/')[-1]}@placeholder.local",
                resume_public_id=resume_public_id,
                resume_url=resume_url,
                resume_raw_text=raw_text,
                extracted_skills=skills,
                source="external",
            )
            await candidate.insert()
            created += 1

        except Exception as exc:
            failed.append(BulkUploadFailure(filename=filename, reason=str(exc)))

    return BulkUploadResult(created=created, updated=updated, failed=failed)
```

**Note:** The `upload_bytes_to_cloudinary` helper is added to the storage service in step 1D below.

---

### 1D — Extend `Candidate` Router

**File:** `apps/backend/app/modules/candidates/router.py`

**Full replacement:**

```python
"""Candidates API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.candidates import service
from app.modules.candidates.schemas import (
    BulkUploadResult,
    CandidateCreate,
    CandidateListFilters,
    CandidateResponse,
    CandidateUpdate,
    CandidateUploadConfirm,
)

router = APIRouter()


@router.get("/tags", response_model=list[str])
async def list_tags(
    _: TokenPayload = Depends(get_current_user),
) -> list[str]:
    """Return all distinct candidate tags (global, not brand-scoped)."""
    return await service.get_distinct_tags()


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    search: str | None = Query(None),
    source: str | None = Query(None),
    tags: list[str] | None = Query(None),
    has_resume: bool | None = Query(None),
    has_cv_link: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _: TokenPayload = Depends(get_current_user),
) -> list[CandidateResponse]:
    filters = CandidateListFilters(
        search=search,
        source=source,
        tags=tags,
        has_resume=has_resume,
        has_cv_link=has_cv_link,
        page=page,
        limit=limit,
    )
    candidates = await service.list_candidates(filters)
    return [CandidateResponse(id=str(c.id), **c.model_dump(exclude={"id"})) for c in candidates]


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    data: CandidateCreate,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    candidate = await service.create_candidate(data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.post("/bulk-upload", response_model=BulkUploadResult)
async def bulk_upload(
    files: Annotated[list[UploadFile], File(description="PDF files to upload")],
    _: TokenPayload = Depends(get_current_user),
) -> BulkUploadResult:
    """Upload multiple PDF resumes. Upserts on matched email."""
    if len(files) > 50:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Maximum 50 files per request")
    return await service.bulk_upload_candidates(files)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    candidate = await service.get_candidate(candidate_id)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: str,
    data: CandidateUpdate,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    candidate = await service.update_candidate(candidate_id, data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.patch("/{candidate_id}/resume", response_model=CandidateResponse)
async def confirm_resume(
    candidate_id: str,
    data: CandidateUploadConfirm,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    data.candidate_id = candidate_id
    candidate = await service.confirm_resume_upload(data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))
```

**Router ordering note:** `GET /tags` MUST be declared before `GET /{candidate_id}`. FastAPI matches routes top-down — if `/{candidate_id}` comes first, the string `"tags"` would be interpreted as a candidate ID.

---

### 1D-i — Add `upload_bytes_to_cloudinary` to Storage Service

**File:** `apps/backend/app/modules/storage/service.py`

Add one new function (do not touch the existing `generate_upload_signature` and `verify_cloudinary_webhook`):

```python
import cloudinary
import cloudinary.uploader


async def upload_bytes_to_cloudinary(pdf_bytes: bytes, filename: str) -> dict:
    """
    Upload raw bytes directly to Cloudinary from the backend.
    Used by bulk-upload — does NOT use the signed-upload flow.
    Returns the Cloudinary upload result dict.
    """
    result = cloudinary.uploader.upload(
        pdf_bytes,
        resource_type="raw",
        folder="eigensu/resumes",
        public_id=filename.replace(".pdf", ""),
        overwrite=False,
        use_filename=True,
    )
    return result
```

Import `cloudinary` and `cloudinary.uploader` at the top of the file if not already present.

---

### 1E — Extend `JobOpening` Model

**File:** `apps/backend/app/modules/dashboard/models.py`

Locate the `JobOpening` class (lines 79–102) and add two fields:

```python
class JobOpening(Document):
    client_name: str
    role: str
    total_seats: int = 0
    filled_seats: int = 0
    remaining_seats: int = 0
    status: JobStatus = JobStatus.open
    # ── New ───────────────────────────────────────────────────────────────────
    recruiter_ids: list[PydanticObjectId] = Field(default_factory=list)
    last_activity_at: datetime | None = None
    # ─────────────────────────────────────────────────────────────────────────
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch_updated_at(self)

    class Settings:
        name = "job_openings"
        indexes = [
            IndexModel("client_name"),
            IndexModel("status"),
            IndexModel("is_active"),
            IndexModel("created_at"),
            IndexModel("updated_at"),
            IndexModel("last_activity_at"),  # new — for sorting in client profiles
        ]
```

---

### 1F — Update Pipeline Service to Set `last_activity_at`

**File:** `apps/backend/app/modules/pipeline/service.py`

In `match_candidate_to_position`, the existing transaction writes to `positions` and `recruiters`. Add a third write that updates `JobOpening.last_activity_at`.

The pipeline service currently doesn't know about `JobOpening`. We need to import it and add the write inside the transaction.

**Add import at top of file:**

```python
from datetime import datetime, UTC
from app.modules.dashboard.models import JobOpening
```

**Inside the `async with session.start_transaction():` block, after the two existing writes, add:**

```python
# 3. Stamp last_activity_at on the linked job opening (if one shares this position's brand)
#    Best-effort — if no job opening is found, skip silently.
job_opening = await JobOpening.find_one(
    JobOpening.client_name != None,  # any opening
    session=session,
)
# More precisely: find a JobOpening tied to the position's brand context.
# For now, update ANY open job opening matching the brand_id via recruiter_ids.
# This is a best-effort stamp — full linkage requires position↔job_opening foreign key.
await JobOpening.find(
    {"recruiter_ids": PydanticObjectId(recruiter_id)},
    session=session,
).update(
    {"$set": {"last_activity_at": datetime.now(UTC)}},
    session=session,
)
```

**Note on the linkage gap:** The `Position` model (recruiter module) and `JobOpening` model (dashboard module) are parallel representations of the same real-world concept but have no FK relationship yet. The `last_activity_at` update via `recruiter_ids` is the bridge. Until `recruiter_ids` are populated on `JobOpening` records, this write is a no-op (which is safe — it won't break anything). Full linkage is tracked as a future data-model unification task.

---

### 1G — Add `GET /pipeline/filtered` Endpoint

**File:** `apps/backend/app/modules/pipeline/router.py`

Add the new endpoint at the bottom of the router:

```python
from datetime import datetime
from app.modules.dashboard.models import CandidateMapping
from app.modules.candidates.models import Candidate as PipelineCandidate
from app.modules.candidates.schemas import CandidateResponse


@router.get("/filtered", response_model=list[CandidateResponse])
async def get_filtered_pipeline(
    position_id: str = Query(...),
    recruiter_id: str | None = Query(None),
    source: str | None = Query(None),
    tags: list[str] | None = Query(None),
    stage: str | None = Query(None),
    mapped_after: datetime | None = Query(None),
    mapped_before: datetime | None = Query(None),
    _: TokenPayload = Depends(get_current_user),
) -> list[CandidateResponse]:
    """
    Return candidates for a position filtered by recruiter, source, tags,
    stage, and date range. Uses CandidateMapping + Candidate join.
    """
    results = await service.find_filtered_candidates(
        position_id=position_id,
        recruiter_id=recruiter_id,
        source=source,
        tags=tags,
        stage=stage,
        mapped_after=mapped_after,
        mapped_before=mapped_before,
    )
    return results
```

**File:** `apps/backend/app/modules/pipeline/service.py`

Add the new service function:

```python
async def find_filtered_candidates(
    position_id: str,
    recruiter_id: str | None,
    source: str | None,
    tags: list[str] | None,
    stage: str | None,
    mapped_after: datetime | None,
    mapped_before: datetime | None,
) -> list[dict]:
    """
    Join CandidateMapping → Candidate with applied filters.
    Returns CandidateResponse-compatible dicts.
    """
    from datetime import datetime
    from app.modules.dashboard.models import CandidateMapping
    from beanie import PydanticObjectId as ObjId

    # Build the mapping match stage
    mapping_match: dict = {}
    if recruiter_id:
        mapping_match["employee_id"] = ObjId(recruiter_id)
    if stage:
        mapping_match["pipeline_stage"] = stage
    if mapped_after or mapped_before:
        date_filter: dict = {}
        if mapped_after:
            date_filter["$gte"] = mapped_after
        if mapped_before:
            date_filter["$lte"] = mapped_before
        mapping_match["mapped_at"] = date_filter

    # Build the candidate match stage (applied after lookup)
    candidate_match: dict = {}
    if source:
        candidate_match["source"] = source
    if tags:
        candidate_match["tags"] = {"$all": [t.lower() for t in tags]}

    pipeline = [
        {"$match": mapping_match},
        {
            "$lookup": {
                "from": "candidates",
                "localField": "candidate_id",
                "foreignField": "_id",
                "as": "candidate",
            }
        },
        {"$unwind": "$candidate"},
    ]

    if candidate_match:
        pipeline.append({"$match": {f"candidate.{k}": v for k, v in candidate_match.items()}})

    pipeline.append({
        "$project": {
            "id": {"$toString": "$candidate._id"},
            "name": "$candidate.name",
            "email": "$candidate.email",
            "phone": "$candidate.phone",
            "resume_url": "$candidate.resume_url",
            "extracted_skills": "$candidate.extracted_skills",
            "tags": "$candidate.tags",
            "source": "$candidate.source",
            "cv_link": "$candidate.cv_link",
            "status": "$pipeline_stage",
        }
    })

    collection = CandidateMapping.get_motor_collection()
    return await (await collection.aggregate(pipeline)).to_list(length=None)
```

---

### 1H — Add `fetch_client_profiles` to Dashboard Repository

**File:** `apps/backend/app/modules/dashboard/repository.py`

Add at the end of the file:

```python
async def fetch_client_profiles(page: int, limit: int) -> dict[str, Any]:
    """
    Aggregate job_openings grouped by client_name.
    Computes derived status: "active" if any opening is open,
    "on_hold" if none open but some on_hold, "closed" otherwise.
    """
    pipeline = [
        {"$match": {"is_active": True}},
        {
            "$lookup": {
                "from": "candidate_mappings",
                "localField": "_id",
                "foreignField": "job_opening_id",
                "as": "mappings",
            }
        },
        {
            "$group": {
                "_id": "$client_name",
                "total_open_positions": {
                    "$sum": {"$cond": [{"$eq": ["$status", JobStatus.open.value]}, 1, 0]}
                },
                "total_on_hold": {
                    "$sum": {"$cond": [{"$eq": ["$status", JobStatus.on_hold.value]}, 1, 0]}
                },
                "total_candidates": {"$sum": {"$size": "$mappings"}},
                # Flatten recruiter_ids arrays across all openings for this client
                "all_recruiter_ids": {"$push": "$recruiter_ids"},
                "last_activity_at": {"$max": "$last_activity_at"},
            }
        },
        {
            "$addFields": {
                "client_name": "$_id",
                # Flatten nested array of arrays into a single set
                "recruiter_id_set": {
                    "$reduce": {
                        "input": "$all_recruiter_ids",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]},
                    }
                },
                # Computed status: active > on_hold > closed
                "status": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {"$gt": ["$total_open_positions", 0]},
                                "then": "active",
                            },
                            {
                                "case": {"$gt": ["$total_on_hold", 0]},
                                "then": "on_hold",
                            },
                        ],
                        "default": "closed",
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "client_name": 1,
                "total_open_positions": 1,
                "total_candidates": 1,
                "active_recruiters": {"$size": "$recruiter_id_set"},
                "last_activity": "$last_activity_at",
                "status": 1,
            }
        },
        {"$sort": {"last_activity": -1, "client_name": 1}},
        {
            "$facet": {
                "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                "meta": [{"$count": "total"}],
            }
        },
    ]

    result = await (await JobOpening.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return {"items": items, "total": total, "page": page, "limit": limit}
```

---

### 1I — Add `ClientProfileRow` to Dashboard Schemas

**File:** `apps/backend/app/modules/dashboard/schemas.py`

Add at the end (before the paginated response classes):

```python
class ClientProfileRow(BaseModel):
    client_name: str
    total_open_positions: int
    total_candidates: int
    active_recruiters: int
    last_activity: datetime | None = None
    status: str  # "active" | "on_hold" | "closed"


class DashboardClientProfilePage(PaginatedResponse[ClientProfileRow]):
    pass
```

---

### 1J — Add `get_client_profiles` to Dashboard Service

**File:** `apps/backend/app/modules/dashboard/service.py`

Add the import at the top of the file:

```python
from app.modules.dashboard.repository import (
    ...existing imports...,
    fetch_client_profiles,  # add this
)
```

Add the new function at the end:

```python
async def get_client_profiles(page: int, limit: int) -> DashboardClientProfilePage:
    from app.modules.dashboard.schemas import ClientProfileRow, DashboardClientProfilePage

    cache_key = dashboard_cache.build_key("client_profiles", f"p{page}_l{limit}")
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardClientProfilePage.model_validate(cached)

    payload = await fetch_client_profiles(page, limit)
    items = [ClientProfileRow.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardClientProfilePage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response
```

Also update the imports in `service.py` for `DashboardClientProfilePage`:

```python
from app.modules.dashboard.schemas import (
    ...existing...,
    DashboardClientProfilePage,
)
```

---

### 1K — Add `GET /dashboard/client-profiles` Endpoint

**File:** `apps/backend/app/modules/dashboard/controller.py`

Add import and new route:

```python
from app.modules.dashboard.schemas import (
    ...existing...,
    DashboardClientProfilePage,
)
```

Add at the end of the router:

```python
@router.get("/client-profiles", response_model=DashboardClientProfilePage)
async def get_client_profiles(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardClientProfilePage:
    return await service.get_client_profiles(page, limit)
```

**Note:** This endpoint does not accept the common `DashboardFilters` params — the aggregation is client-centric, not employee/date-range filtered. Filtering can be added in a future iteration.

---

## Phase 2 — Frontend: Candidate Management

### 2A — Add Candidate TypeScript Types

**File:** `apps/frontend/src/types/index.ts`

Add after the existing `Candidate` interface:

```typescript
export type CandidateSource = "internal" | "external";

export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  resume_url: string | null;
  extracted_skills: string[];
  // New fields
  tags: string[];
  source: CandidateSource;
  cv_link: string | null;
}

export interface CandidateFilters {
  search?: string;
  source?: CandidateSource;
  tags?: string[];
  has_resume?: boolean;
  has_cv_link?: boolean;
  page: number;
  limit: number;
}

export interface BulkUploadFailure {
  filename: string;
  reason: string;
}

export interface BulkUploadResult {
  created: number;
  updated: number;
  failed: BulkUploadFailure[];
}
```

---

### 2B — Extend Candidate API Client

**File:** `apps/frontend/src/lib/api/candidates.ts`

**Full replacement:**

```typescript
import { cookies } from "next/headers";
import type { Candidate, CandidateFilters, BulkUploadResult } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function serverFetch<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
    },
    cache: "no-store",
  });

  if (!res.ok) throw new Error(`Candidates API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

function buildQuery(filters: Partial<CandidateFilters>): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.source) params.set("source", filters.source);
  if (filters.tags) filters.tags.forEach((t) => params.append("tags", t));
  if (filters.has_resume !== undefined)
    params.set("has_resume", String(filters.has_resume));
  if (filters.has_cv_link !== undefined)
    params.set("has_cv_link", String(filters.has_cv_link));
  if (filters.page) params.set("page", String(filters.page));
  if (filters.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function getCandidates(filters: Partial<CandidateFilters> = {}) {
  return serverFetch<Candidate[]>(`/api/v1/candidates${buildQuery(filters)}`);
}

export function getCandidateTags() {
  return serverFetch<string[]>("/api/v1/candidates/tags");
}

// Client-side fetch helpers (used in interactive components)
export async function clientFetchCandidates(
  filters: Partial<CandidateFilters>,
  cookieStr?: string,
): Promise<Candidate[]> {
  const res = await fetch(
    `${API_URL}/api/v1/candidates${buildQuery(filters)}`,
    {
      credentials: "include",
    },
  );
  if (!res.ok) throw new Error(`Candidates fetch failed: ${res.status}`);
  return res.json();
}

export async function clientCreateCandidate(data: {
  name: string;
  email: string;
  phone?: string;
  source: "internal" | "external";
  tags?: string[];
  cv_link?: string;
}): Promise<Candidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientUpdateCandidate(
  id: string,
  data: Partial<{
    name: string;
    phone: string;
    cv_link: string;
    source: string;
    tags: string[];
  }>,
): Promise<Candidate> {
  const res = await fetch(`${API_URL}/api/v1/candidates/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clientBulkUpload(
  files: File[],
): Promise<BulkUploadResult> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const res = await fetch(`${API_URL}/api/v1/candidates/bulk-upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Used by dashboard-data.ts
export async function getCandidateMappingsForDashboard() {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  const res = await fetch(`${API_URL}/api/v1/dashboard/mappings?limit=100`, {
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
    },
    cache: "no-store",
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.items ?? [];
}
```

---

### 2C — Create `CandidateFilterBar` Component

**New file:** `apps/frontend/src/components/candidates/CandidateFilterBar.tsx`

```tsx
"use client";

import { useState } from "react";
import type { CandidateFilters, CandidateSource } from "@/types";

interface Props {
  availableTags: string[];
  onFilterChange: (filters: Partial<CandidateFilters>) => void;
}

export default function CandidateFilterBar({
  availableTags,
  onFilterChange,
}: Props) {
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<CandidateSource | "">("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [hasResume, setHasResume] = useState<boolean | undefined>(undefined);
  const [hasCvLink, setHasCvLink] = useState<boolean | undefined>(undefined);
  const [tagsOpen, setTagsOpen] = useState(false);

  function emit(
    overrides: Partial<{
      search: string;
      source: CandidateSource | "";
      selectedTags: string[];
      hasResume: boolean | undefined;
      hasCvLink: boolean | undefined;
    }> = {},
  ) {
    const s = overrides.search ?? search;
    const src = overrides.source ?? source;
    const tags = overrides.selectedTags ?? selectedTags;
    const resume =
      overrides.hasResume !== undefined ? overrides.hasResume : hasResume;
    const cv =
      overrides.hasCvLink !== undefined ? overrides.hasCvLink : hasCvLink;
    onFilterChange({
      search: s || undefined,
      source: (src as CandidateSource) || undefined,
      tags: tags.length > 0 ? tags : undefined,
      has_resume: resume,
      has_cv_link: cv,
      page: 1,
      limit: 50,
    });
  }

  function toggleTag(tag: string) {
    const next = selectedTags.includes(tag)
      ? selectedTags.filter((t) => t !== tag)
      : [...selectedTags, tag];
    setSelectedTags(next);
    emit({ selectedTags: next });
  }

  function clearAll() {
    setSearch("");
    setSource("");
    setSelectedTags([]);
    setHasResume(undefined);
    setHasCvLink(undefined);
    onFilterChange({ page: 1, limit: 50 });
  }

  const hasActiveFilters =
    search ||
    source ||
    selectedTags.length > 0 ||
    hasResume !== undefined ||
    hasCvLink !== undefined;

  return (
    <div
      className="flex flex-wrap items-center gap-3 p-3 rounded-xl border"
      style={{
        background: "var(--color-surface)",
        borderColor: "var(--color-border-val)",
      }}
    >
      {/* Text search */}
      <input
        type="text"
        placeholder="Search by name, email, skill..."
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          emit({ search: e.target.value });
        }}
        className="flex-1 min-w-[180px] rounded-lg px-3 py-1.5 text-sm"
        style={{
          background: "var(--color-canvas)",
          color: "var(--color-text-primary)",
          border: "1px solid var(--color-border-val)",
        }}
      />

      {/* Source dropdown */}
      <select
        value={source}
        onChange={(e) => {
          const v = e.target.value as CandidateSource | "";
          setSource(v);
          emit({ source: v });
        }}
        className="rounded-lg px-3 py-1.5 text-sm"
        style={{
          background: "var(--color-canvas)",
          color: "var(--color-text-primary)",
          border: "1px solid var(--color-border-val)",
        }}
      >
        <option value="">All Sources</option>
        <option value="internal">Internal</option>
        <option value="external">External</option>
      </select>

      {/* Tags popover */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setTagsOpen((o) => !o)}
          className="rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
          style={{
            background:
              selectedTags.length > 0
                ? "var(--color-accent)"
                : "var(--color-canvas)",
            color: "var(--color-text-primary)",
            border: "1px solid var(--color-border-val)",
          }}
        >
          Tags {selectedTags.length > 0 && `(${selectedTags.length})`}
          <span>{tagsOpen ? "▲" : "▼"}</span>
        </button>
        {tagsOpen && (
          <div
            className="absolute top-full mt-1 z-20 rounded-xl shadow-xl p-2 min-w-[180px] max-h-48 overflow-y-auto"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border-val)",
            }}
          >
            {availableTags.length === 0 && (
              <p
                className="text-xs px-2 py-1"
                style={{ color: "var(--color-text-secondary)" }}
              >
                No tags yet
              </p>
            )}
            {availableTags.map((tag) => (
              <label
                key={tag}
                className="flex items-center gap-2 px-2 py-1 cursor-pointer rounded hover:bg-black/10"
              >
                <input
                  type="checkbox"
                  checked={selectedTags.includes(tag)}
                  onChange={() => toggleTag(tag)}
                />
                <span
                  className="text-sm"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {tag}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Has Resume toggle */}
      <button
        type="button"
        onClick={() => {
          const next = hasResume === true ? undefined : true;
          setHasResume(next);
          emit({ hasResume: next });
        }}
        className={`rounded-lg px-3 py-1.5 text-sm border transition-colors ${
          hasResume === true ? "opacity-100" : "opacity-60"
        }`}
        style={{
          background:
            hasResume === true
              ? "var(--color-success-subtle)"
              : "var(--color-canvas)",
          borderColor: "var(--color-border-val)",
          color: "var(--color-text-primary)",
        }}
      >
        Has Resume
      </button>

      {/* Has CV Link toggle */}
      <button
        type="button"
        onClick={() => {
          const next = hasCvLink === true ? undefined : true;
          setHasCvLink(next);
          emit({ hasCvLink: next });
        }}
        className={`rounded-lg px-3 py-1.5 text-sm border transition-colors ${
          hasCvLink === true ? "opacity-100" : "opacity-60"
        }`}
        style={{
          background:
            hasCvLink === true
              ? "var(--color-success-subtle)"
              : "var(--color-canvas)",
          borderColor: "var(--color-border-val)",
          color: "var(--color-text-primary)",
        }}
      >
        Has CV Link
      </button>

      {/* Clear */}
      {hasActiveFilters && (
        <button
          type="button"
          onClick={clearAll}
          className="text-sm underline"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Clear all
        </button>
      )}
    </div>
  );
}
```

---

### 2D — Create `AddCandidateForm` Component

**New file:** `apps/frontend/src/components/candidates/AddCandidateForm.tsx`

```tsx
"use client";

import { useState } from "react";
import { z } from "zod";
import { clientCreateCandidate } from "@/lib/api/candidates";
import type { Candidate } from "@/types";

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  source: z.enum(["internal", "external"]),
  tags: z.array(z.string()),
  cv_link: z.string().url("Must be a valid URL").optional().or(z.literal("")),
});

interface Props {
  onSuccess: (candidate: Candidate) => void;
  onCancel: () => void;
}

export default function AddCandidateForm({ onSuccess, onCancel }: Props) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    source: "internal" as "internal" | "external",
    tagInput: "",
    tags: [] as string[],
    cv_link: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function addTag() {
    const raw = form.tagInput.trim().toLowerCase();
    if (!raw || form.tags.includes(raw)) return;
    setForm((f) => ({ ...f, tags: [...f.tags, raw], tagInput: "" }));
  }

  function removeTag(tag: string) {
    setForm((f) => ({ ...f, tags: f.tags.filter((t) => t !== tag) }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse({
      name: form.name,
      email: form.email,
      phone: form.phone || undefined,
      source: form.source,
      tags: form.tags,
      cv_link: form.cv_link || undefined,
    });

    if (!parsed.success) {
      const fieldErrors: Record<string, string> = {};
      parsed.error.errors.forEach((err) => {
        if (err.path[0]) fieldErrors[err.path[0] as string] = err.message;
      });
      setErrors(fieldErrors);
      return;
    }

    setLoading(true);
    setErrors({});
    try {
      const candidate = await clientCreateCandidate({
        name: parsed.data.name,
        email: parsed.data.email,
        phone: parsed.data.phone,
        source: parsed.data.source,
        tags: parsed.data.tags,
        cv_link: parsed.data.cv_link || undefined,
      });
      onSuccess(candidate);
    } catch (err: unknown) {
      setErrors({
        _root:
          err instanceof Error ? err.message : "Failed to create candidate",
      });
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full rounded-lg px-3 py-2 text-sm border outline-none focus:ring-1";
  const inputStyle = {
    background: "var(--color-canvas)",
    color: "var(--color-text-primary)",
    borderColor: "var(--color-border-val)",
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-4">
      <h2
        className="text-lg font-semibold"
        style={{ color: "var(--color-text-primary)" }}
      >
        Add Candidate
      </h2>

      {errors._root && (
        <p className="text-sm text-red-500 rounded-lg px-3 py-2 bg-red-500/10">
          {errors._root}
        </p>
      )}

      {/* Name */}
      <div>
        <label
          className="text-xs font-medium mb-1 block"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Name *
        </label>
        <input
          className={inputCls}
          style={inputStyle}
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        />
        {errors.name && (
          <p className="text-xs text-red-400 mt-0.5">{errors.name}</p>
        )}
      </div>

      {/* Email */}
      <div>
        <label
          className="text-xs font-medium mb-1 block"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Email *
        </label>
        <input
          type="email"
          className={inputCls}
          style={inputStyle}
          value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
        />
        {errors.email && (
          <p className="text-xs text-red-400 mt-0.5">{errors.email}</p>
        )}
      </div>

      {/* Phone */}
      <div>
        <label
          className="text-xs font-medium mb-1 block"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Phone
        </label>
        <input
          type="tel"
          className={inputCls}
          style={inputStyle}
          value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
        />
      </div>

      {/* Source */}
      <div>
        <label
          className="text-xs font-medium mb-1 block"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Source *
        </label>
        <div className="flex gap-3">
          {(["internal", "external"] as const).map((s) => (
            <label key={s} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="source"
                value={s}
                checked={form.source === s}
                onChange={() => setForm((f) => ({ ...f, source: s }))}
              />
              <span
                className="text-sm font-medium"
                style={{
                  color:
                    s === "internal"
                      ? "var(--color-success)"
                      : "var(--color-danger)",
                }}
              >
                {s === "internal" ? "● Internal" : "● External"}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Tags */}
      <div>
        <label
          className="text-xs font-medium mb-1 block"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Tags
        </label>
        <div className="flex gap-2">
          <input
            className={`${inputCls} flex-1`}
            style={inputStyle}
            placeholder="e.g. senior, python"
            value={form.tagInput}
            onChange={(e) =>
              setForm((f) => ({ ...f, tagInput: e.target.value }))
            }
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                addTag();
              }
            }}
          />
          <button
            type="button"
            onClick={addTag}
            className="px-3 py-1.5 rounded-lg text-sm font-medium"
            style={{
              background: "var(--color-surface)",
              color: "var(--color-text-primary)",
              border: "1px solid var(--color-border-val)",
            }}
          >
            Add
          </button>
        </div>
        {form.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {form.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "var(--color-surface)",
                  color: "var(--color-text-primary)",
                  border: "1px solid var(--color-border-val)",
                }}
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="opacity-60 hover:opacity-100"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* CV Link */}
      <div>
        <label
          className="text-xs font-medium mb-1 block"
          style={{ color: "var(--color-text-secondary)" }}
        >
          CV Link
        </label>
        <input
          type="url"
          className={inputCls}
          style={inputStyle}
          placeholder="https://..."
          value={form.cv_link}
          onChange={(e) => setForm((f) => ({ ...f, cv_link: e.target.value }))}
        />
        {errors.cv_link && (
          <p className="text-xs text-red-400 mt-0.5">{errors.cv_link}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={loading}
          className="flex-1 rounded-lg py-2 text-sm font-semibold disabled:opacity-50"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-text-on-accent)",
          }}
        >
          {loading ? "Saving…" : "Add Candidate"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-4 py-2 text-sm"
          style={{
            background: "var(--color-surface)",
            color: "var(--color-text-primary)",
            border: "1px solid var(--color-border-val)",
          }}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
```

---

### 2E — Create `BulkUploadDrawer` Component

**New file:** `apps/frontend/src/components/candidates/BulkUploadDrawer.tsx`

```tsx
"use client";

import { useRef, useState } from "react";
import { clientBulkUpload } from "@/lib/api/candidates";
import type { BulkUploadResult } from "@/types";

interface Props {
  onComplete: (result: BulkUploadResult) => void;
  onClose: () => void;
}

type FileStatus = "pending" | "uploading" | "done" | "failed";

interface FileEntry {
  file: File;
  status: FileStatus;
  error?: string;
}

export default function BulkUploadDrawer({ onComplete, onClose }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<BulkUploadResult | null>(null);

  function handleFileSelect(files: FileList | null) {
    if (!files) return;
    const pdfs = Array.from(files).filter(
      (f) => f.type === "application/pdf" || f.name.endsWith(".pdf"),
    );
    if (pdfs.length + entries.length > 50) {
      alert("Maximum 50 files per upload.");
      return;
    }
    setEntries((prev) => [
      ...prev,
      ...pdfs.map((f) => ({ file: f, status: "pending" as FileStatus })),
    ]);
  }

  function removeFile(idx: number) {
    setEntries((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleUpload() {
    if (entries.length === 0 || uploading) return;
    setUploading(true);
    setEntries((prev) =>
      prev.map((e) => ({ ...e, status: "uploading" as FileStatus })),
    );

    try {
      const res = await clientBulkUpload(entries.map((e) => e.file));
      // Mark all as done (failed ones are in res.failed)
      const failedSet = new Set(res.failed.map((f) => f.filename));
      setEntries((prev) =>
        prev.map((e) => ({
          ...e,
          status: failedSet.has(e.file.name) ? "failed" : "done",
          error: res.failed.find((f) => f.filename === e.file.name)?.reason,
        })),
      );
      setResult(res);
      onComplete(res);
    } catch {
      setEntries((prev) =>
        prev.map((e) => ({ ...e, status: "failed", error: "Upload failed" })),
      );
    } finally {
      setUploading(false);
    }
  }

  const statusColor: Record<FileStatus, string> = {
    pending: "var(--color-text-secondary)",
    uploading: "var(--color-warning)",
    done: "var(--color-success)",
    failed: "var(--color-danger)",
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2
          className="text-lg font-semibold"
          style={{ color: "var(--color-text-primary)" }}
        >
          Bulk Resume Upload
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="text-sm opacity-60 hover:opacity-100"
        >
          Close
        </button>
      </div>

      {/* Drop zone */}
      <div
        className="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer"
        style={{ borderColor: "var(--color-border-val)" }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFileSelect(e.dataTransfer.files);
        }}
      >
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Drop PDF files here or click to browse (max 50)
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
        />
      </div>

      {/* File list */}
      {entries.length > 0 && (
        <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
          {entries.map((entry, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between text-sm px-2 py-1 rounded-lg"
              style={{ background: "var(--color-surface)" }}
            >
              <span
                className="truncate flex-1"
                style={{ color: "var(--color-text-primary)" }}
              >
                {entry.file.name}
              </span>
              <span
                className="ml-2 shrink-0 text-xs font-medium"
                style={{ color: statusColor[entry.status] }}
              >
                {entry.status === "failed"
                  ? `✗ ${entry.error ?? "failed"}`
                  : entry.status}
              </span>
              {entry.status === "pending" && (
                <button
                  type="button"
                  onClick={() => removeFile(idx)}
                  className="ml-2 opacity-50 hover:opacity-100 text-xs"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Result summary */}
      {result && (
        <div
          className="rounded-xl p-3 text-sm"
          style={{ background: "var(--color-surface)" }}
        >
          <p style={{ color: "var(--color-success)" }}>
            Created: {result.created}
          </p>
          <p style={{ color: "var(--color-text-primary)" }}>
            Updated: {result.updated}
          </p>
          {result.failed.length > 0 && (
            <p style={{ color: "var(--color-danger)" }}>
              Failed: {result.failed.length}
            </p>
          )}
        </div>
      )}

      {/* Upload button */}
      {!result && (
        <button
          type="button"
          disabled={entries.length === 0 || uploading}
          onClick={handleUpload}
          className="rounded-lg py-2 text-sm font-semibold disabled:opacity-50"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-text-on-accent)",
          }}
        >
          {uploading
            ? "Uploading…"
            : `Upload ${entries.length} file${entries.length !== 1 ? "s" : ""}`}
        </button>
      )}
    </div>
  );
}
```

---

### 2F — Create `CandidateTable` Component

**New file:** `apps/frontend/src/components/candidates/CandidateTable.tsx`

```tsx
import type { Candidate } from "@/types";

interface Props {
  candidates: Candidate[];
}

const SOURCE_STYLES = {
  internal: { color: "var(--color-success)", label: "Internal" },
  external: { color: "var(--color-danger)", label: "External" },
};

export default function CandidateTable({ candidates }: Props) {
  if (candidates.length === 0) {
    return (
      <div
        className="text-center py-12"
        style={{ color: "var(--color-text-secondary)" }}
      >
        No candidates found. Adjust your filters or add a new candidate.
      </div>
    );
  }

  return (
    <div
      className="overflow-x-auto rounded-xl border"
      style={{ borderColor: "var(--color-border-val)" }}
    >
      <table className="w-full text-sm">
        <thead>
          <tr
            style={{
              background: "var(--color-surface)",
              borderBottom: "1px solid var(--color-border-val)",
            }}
          >
            {["Name", "Email", "Source", "Tags", "CV", "Skills"].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr
              key={c.id}
              className="border-b last:border-0 hover:bg-black/5 transition-colors"
              style={{ borderColor: "var(--color-border-val)" }}
            >
              {/* Name */}
              <td
                className="px-4 py-3 font-medium"
                style={{ color: "var(--color-text-primary)" }}
              >
                {c.name}
              </td>

              {/* Email */}
              <td
                className="px-4 py-3"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {c.email}
              </td>

              {/* Source */}
              <td className="px-4 py-3">
                <span
                  className="inline-flex items-center gap-1.5 text-xs font-medium"
                  style={{ color: SOURCE_STYLES[c.source].color }}
                >
                  <span className="text-[8px]">●</span>
                  {SOURCE_STYLES[c.source].label}
                </span>
              </td>

              {/* Tags */}
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {c.tags.slice(0, 4).map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-1.5 py-0.5 rounded-full"
                      style={{
                        background: "var(--color-surface)",
                        color: "var(--color-text-secondary)",
                        border: "1px solid var(--color-border-val)",
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                  {c.tags.length > 4 && (
                    <span
                      className="text-[10px]"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      +{c.tags.length - 4}
                    </span>
                  )}
                </div>
              </td>

              {/* CV */}
              <td className="px-4 py-3">
                {c.cv_link || c.resume_url ? (
                  <a
                    href={(c.cv_link || c.resume_url)!}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs underline"
                    style={{ color: "var(--color-accent)" }}
                  >
                    {c.cv_link ? "CV Link ↗" : "Resume ↗"}
                  </a>
                ) : (
                  <span
                    className="text-xs"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    —
                  </span>
                )}
              </td>

              {/* Skills */}
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {c.extracted_skills.slice(0, 3).map((skill) => (
                    <span
                      key={skill}
                      className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{
                        background: "var(--color-surface)",
                        color: "var(--color-text-secondary)",
                        border: "1px solid var(--color-border-val)",
                      }}
                    >
                      {skill}
                    </span>
                  ))}
                  {c.extracted_skills.length > 3 && (
                    <span
                      className="text-[10px]"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      +{c.extracted_skills.length - 3}
                    </span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

### 2G — Replace `candidates/page.tsx`

**File:** `apps/frontend/src/app/(dashboard)/candidates/page.tsx`

**Full replacement:**

```tsx
import { Suspense } from "react";
import { getCandidates, getCandidateTags } from "@/lib/api/candidates";
import CandidatesClient from "@/components/candidates/CandidatesClient";
import { PanelSkeleton } from "@/components/dashboard";

export default async function CandidatesPage() {
  const [initialCandidates, availableTags] = await Promise.all([
    getCandidates({ page: 1, limit: 50 }),
    getCandidateTags(),
  ]);

  return (
    <div
      className="min-h-full px-4 py-5 sm:px-6 lg:px-8"
      style={{
        background: "var(--color-canvas)",
        color: "var(--color-text-primary)",
      }}
    >
      <div className="mx-auto flex w-full max-w-400 flex-col gap-5">
        <header
          className="pb-4"
          style={{ borderBottom: "1px solid var(--color-border-val)" }}
        >
          <p
            className="text-xs font-bold uppercase tracking-normal"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Talent Pool
          </p>
          <h1
            className="mt-2 font-heading text-4xl leading-tight sm:text-5xl"
            style={{ color: "var(--color-text-primary)" }}
          >
            Candidate Directory
          </h1>
        </header>

        <Suspense fallback={<PanelSkeleton rows={8} />}>
          <CandidatesClient
            initialCandidates={initialCandidates}
            availableTags={availableTags}
          />
        </Suspense>
      </div>
    </div>
  );
}
```

**New file:** `apps/frontend/src/components/candidates/CandidatesClient.tsx`

```tsx
"use client";

import { useState } from "react";
import type { Candidate, CandidateFilters, BulkUploadResult } from "@/types";
import { clientFetchCandidates } from "@/lib/api/candidates";
import CandidateFilterBar from "./CandidateFilterBar";
import CandidateTable from "./CandidateTable";
import AddCandidateForm from "./AddCandidateForm";
import BulkUploadDrawer from "./BulkUploadDrawer";

interface Props {
  initialCandidates: Candidate[];
  availableTags: string[];
}

export default function CandidatesClient({
  initialCandidates,
  availableTags,
}: Props) {
  const [candidates, setCandidates] = useState<Candidate[]>(initialCandidates);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkUpload, setShowBulkUpload] = useState(false);

  async function handleFilterChange(filters: Partial<CandidateFilters>) {
    setLoading(true);
    try {
      const results = await clientFetchCandidates(filters);
      setCandidates(results);
    } finally {
      setLoading(false);
    }
  }

  function handleCandidateAdded(candidate: Candidate) {
    setCandidates((prev) => [candidate, ...prev]);
    setShowAddForm(false);
  }

  function handleBulkComplete(_result: BulkUploadResult) {
    // Refresh list after bulk upload
    clientFetchCandidates({ page: 1, limit: 50 }).then(setCandidates);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Action bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span
          className="text-sm"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setShowBulkUpload(true)}
            className="rounded-lg px-3 py-1.5 text-sm font-medium border"
            style={{
              background: "var(--color-surface)",
              color: "var(--color-text-primary)",
              borderColor: "var(--color-border-val)",
            }}
          >
            Bulk Upload
          </button>
          <button
            type="button"
            onClick={() => setShowAddForm(true)}
            className="rounded-lg px-3 py-1.5 text-sm font-semibold"
            style={{
              background: "var(--color-accent)",
              color: "var(--color-text-on-accent)",
            }}
          >
            + Add Candidate
          </button>
        </div>
      </div>

      <CandidateFilterBar
        availableTags={availableTags}
        onFilterChange={handleFilterChange}
      />

      {/* Inline Add Candidate drawer */}
      {showAddForm && (
        <div
          className="rounded-xl border"
          style={{
            borderColor: "var(--color-border-val)",
            background: "var(--color-surface)",
          }}
        >
          <AddCandidateForm
            onSuccess={handleCandidateAdded}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}

      {/* Inline Bulk Upload drawer */}
      {showBulkUpload && (
        <div
          className="rounded-xl border"
          style={{
            borderColor: "var(--color-border-val)",
            background: "var(--color-surface)",
          }}
        >
          <BulkUploadDrawer
            onComplete={handleBulkComplete}
            onClose={() => setShowBulkUpload(false)}
          />
        </div>
      )}

      {loading ? (
        <div
          className="py-8 text-center text-sm"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Loading…
        </div>
      ) : (
        <CandidateTable candidates={candidates} />
      )}
    </div>
  );
}
```

---

## Phase 3 — Frontend: Kanban Filters

### 3A — Create `KanbanFilterBar` Component

**New file:** `apps/frontend/src/components/kanban/KanbanFilterBar.tsx`

```tsx
"use client";

import { useState } from "react";

export interface KanbanFilters {
  recruiter_id?: string;
  source?: "internal" | "external";
  tags?: string[];
  stage?: string;
  mapped_after?: string;
  mapped_before?: string;
}

interface Employee {
  id: string;
  name: string;
}
const PIPELINE_STAGES = [
  "added",
  "shortlisted",
  "sent_to_client",
  "rejected",
  "hold",
  "offer_sent",
  "offer_accepted",
  "joined",
  "dropped",
];
const STAGE_LABELS: Record<string, string> = {
  added: "Added",
  shortlisted: "Shortlisted",
  sent_to_client: "Sent to Client",
  rejected: "Rejected",
  hold: "Hold",
  offer_sent: "Offer Sent",
  offer_accepted: "Offer Accepted",
  joined: "Joined",
  dropped: "Dropped",
};

interface Props {
  employees: Employee[];
  availableTags: string[];
  onFilterChange: (filters: KanbanFilters) => void;
}

export default function KanbanFilterBar({
  employees,
  availableTags,
  onFilterChange,
}: Props) {
  const [f, setF] = useState<KanbanFilters>({});

  function update<K extends keyof KanbanFilters>(
    key: K,
    value: KanbanFilters[K],
  ) {
    const next = { ...f, [key]: value };
    // Remove undefined/empty values
    Object.keys(next).forEach((k) => {
      const v = next[k as keyof KanbanFilters];
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
        delete next[k as keyof KanbanFilters];
      }
    });
    setF(next);
    onFilterChange(next);
  }

  function clear() {
    setF({});
    onFilterChange({});
  }

  const hasFilters = Object.keys(f).length > 0;
  const selectCls = "rounded-lg px-2 py-1.5 text-xs border";
  const selectStyle = {
    background: "var(--color-canvas)",
    color: "var(--color-text-primary)",
    borderColor: "var(--color-border-val)",
  };

  return (
    <div className="flex flex-wrap items-center gap-2 pb-3">
      {/* Recruiter */}
      <select
        value={f.recruiter_id ?? ""}
        onChange={(e) => update("recruiter_id", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
      >
        <option value="">All Recruiters</option>
        {employees.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
          </option>
        ))}
      </select>

      {/* Source */}
      <select
        value={f.source ?? ""}
        onChange={(e) =>
          update(
            "source",
            (e.target.value as "internal" | "external") || undefined,
          )
        }
        className={selectCls}
        style={selectStyle}
      >
        <option value="">All Sources</option>
        <option value="internal">Internal</option>
        <option value="external">External</option>
      </select>

      {/* Stage */}
      <select
        value={f.stage ?? ""}
        onChange={(e) => update("stage", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
      >
        <option value="">All Stages</option>
        {PIPELINE_STAGES.map((s) => (
          <option key={s} value={s}>
            {STAGE_LABELS[s]}
          </option>
        ))}
      </select>

      {/* Tags */}
      {availableTags.length > 0 && (
        <select
          value=""
          onChange={(e) => {
            const tag = e.target.value;
            if (!tag) return;
            const current = f.tags ?? [];
            if (!current.includes(tag)) update("tags", [...current, tag]);
          }}
          className={selectCls}
          style={selectStyle}
        >
          <option value="">+ Tag filter</option>
          {availableTags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      )}

      {/* Active tag pills */}
      {(f.tags ?? []).map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
          style={{
            background: "var(--color-surface)",
            color: "var(--color-text-primary)",
            border: "1px solid var(--color-border-val)",
          }}
        >
          {tag}
          <button
            type="button"
            onClick={() =>
              update(
                "tags",
                (f.tags ?? []).filter((t) => t !== tag),
              )
            }
            className="opacity-60 hover:opacity-100"
          >
            ×
          </button>
        </span>
      ))}

      {/* Date range */}
      <input
        type="date"
        value={f.mapped_after ?? ""}
        onChange={(e) => update("mapped_after", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
        title="Mapped after"
      />
      <input
        type="date"
        value={f.mapped_before ?? ""}
        onChange={(e) => update("mapped_before", e.target.value || undefined)}
        className={selectCls}
        style={selectStyle}
        title="Mapped before"
      />

      {hasFilters && (
        <button
          type="button"
          onClick={clear}
          className="text-xs underline"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
```

---

### 3B — Extend `usePipelineStore`

**File:** `apps/frontend/src/stores/usePipelineStore.ts`

Add `activeFilters` and `isFiltered` to the store:

```typescript
import { create } from "zustand";
import type { CandidateCard, CandidateStatus } from "@/types";
import type { KanbanFilters } from "@/components/kanban/KanbanFilterBar";

interface PipelineState {
  columns: Record<CandidateStatus, CandidateCard[]>;
  setColumns: (columns: Record<CandidateStatus, CandidateCard[]>) => void;
  moveCard: (
    cardId: string,
    from: CandidateStatus,
    to: CandidateStatus,
  ) => void;
  activeCardId: string | null;
  setActiveCardId: (id: string | null) => void;
  // New: filter state
  activeFilters: KanbanFilters;
  setActiveFilters: (filters: KanbanFilters) => void;
  isFiltered: boolean;
}

const EMPTY_COLUMNS: Record<CandidateStatus, CandidateCard[]> = {
  pending: [],
  accepted: [],
  rejected: [],
};

export const usePipelineStore = create<PipelineState>((set) => ({
  columns: EMPTY_COLUMNS,
  setColumns: (columns) => set({ columns }),
  moveCard: (cardId, from, to) =>
    set((state) => {
      if (from === to) return state;
      const card = state.columns[from].find((c) => c.id === cardId);
      if (!card) return state;
      return {
        columns: {
          ...state.columns,
          [from]: state.columns[from].filter((c) => c.id !== cardId),
          [to]: [...state.columns[to], { ...card, status: to }],
        },
      };
    }),
  activeCardId: null,
  setActiveCardId: (id) => set({ activeCardId: id }),
  // New
  activeFilters: {},
  setActiveFilters: (filters) =>
    set({
      activeFilters: filters,
      isFiltered: Object.keys(filters).length > 0,
    }),
  isFiltered: false,
}));

export const selectColumn =
  (status: CandidateStatus) => (state: PipelineState) =>
    state.columns[status];
export const selectAllCards = (state: PipelineState) =>
  Object.values(state.columns).flat();
```

---

### 3C — Add Pipeline Filtered Fetch

**File:** `apps/frontend/src/lib/api/` — create new file `pipeline.ts`

```typescript
"use client";

import type { CandidateCard, CandidateStatus } from "@/types";
import type { KanbanFilters } from "@/components/kanban/KanbanFilterBar";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchFilteredPipeline(
  positionId: string,
  filters: KanbanFilters,
): Promise<Record<CandidateStatus, CandidateCard[]>> {
  const params = new URLSearchParams({ position_id: positionId });
  if (filters.recruiter_id) params.set("recruiter_id", filters.recruiter_id);
  if (filters.source) params.set("source", filters.source);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.mapped_after) params.set("mapped_after", filters.mapped_after);
  if (filters.mapped_before) params.set("mapped_before", filters.mapped_before);
  if (filters.tags) filters.tags.forEach((t) => params.append("tags", t));

  const res = await fetch(
    `${API_URL}/api/v1/pipeline/filtered?${params.toString()}`,
    {
      credentials: "include",
    },
  );
  if (!res.ok) throw new Error(`Pipeline filtered fetch failed: ${res.status}`);
  const cards: (CandidateCard & { status: CandidateStatus })[] =
    await res.json();

  return {
    pending: cards.filter((c) => c.status === "pending"),
    accepted: cards.filter((c) => c.status === "accepted"),
    rejected: cards.filter((c) => c.status === "rejected"),
  };
}
```

---

### 3D — Wire Filter Bar into `Board.tsx`

**File:** `apps/frontend/src/components/kanban/Board.tsx`

Add filter bar rendering, filtered-fetch logic, and filter count badges on column headers. Replace the current file:

```tsx
"use client";

import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useCallback, useEffect, useState } from "react";
import type { CandidateStatus } from "@/types";
import { usePipelineStore } from "@/stores/usePipelineStore";
import { useApiFetch } from "@/lib/api";
import { fetchFilteredPipeline } from "@/lib/api/pipeline";
import KanbanColumn from "./Column";
import CandidateCardComponent from "./CandidateCard";
import KanbanFilterBar, { type KanbanFilters } from "./KanbanFilterBar";

const COLUMNS: { id: CandidateStatus; label: string; color: string }[] = [
  { id: "pending", label: "Pending Review", color: "shadow-amber-500/20" },
  { id: "accepted", label: "Accepted", color: "shadow-emerald-500/20" },
  { id: "rejected", label: "Rejected", color: "shadow-red-500/20" },
];

interface Props {
  positionId: string;
  employees?: { id: string; name: string }[];
  availableTags?: string[];
}

export default function KanbanBoard({
  positionId,
  employees = [],
  availableTags = [],
}: Props) {
  const {
    columns,
    moveCard,
    activeCardId,
    setActiveCardId,
    setColumns,
    setActiveFilters,
    isFiltered,
  } = usePipelineStore();
  const apiFetch = useApiFetch();
  const [filterLoading, setFilterLoading] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const findCardColumn = useCallback(
    (cardId: string): CandidateStatus | null => {
      for (const [colId, cards] of Object.entries(columns)) {
        if (cards.some((c) => c.id === cardId)) return colId as CandidateStatus;
      }
      return null;
    },
    [columns],
  );

  async function handleFilterChange(filters: KanbanFilters) {
    setActiveFilters(filters);
    const hasFilters = Object.keys(filters).length > 0;

    if (!hasFilters) {
      // Reset to unfiltered — reload full board
      await loadUnfiltered();
      return;
    }

    setFilterLoading(true);
    try {
      const filtered = await fetchFilteredPipeline(positionId, filters);
      setColumns(filtered);
    } catch (err) {
      console.error("Filter failed:", err);
    } finally {
      setFilterLoading(false);
    }
  }

  async function loadUnfiltered() {
    try {
      const data = await apiFetch<
        Array<{
          id: string;
          name: string;
          email: string;
          extracted_skills: string[];
          resume_url: string | null;
          match_score?: number;
          status: CandidateStatus;
        }>
      >(`/api/v1/pipeline/top-candidates?position_id=${positionId}&limit=50`);
      setColumns({
        pending: data.filter((c) => c.status === "pending"),
        accepted: data.filter((c) => c.status === "accepted"),
        rejected: data.filter((c) => c.status === "rejected"),
      });
    } catch (err) {
      console.error("Failed to load pipeline:", err);
    }
  }

  useEffect(() => {
    loadUnfiltered();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionId]);

  function handleDragStart(event: DragStartEvent) {
    setActiveCardId(event.active.id as string);
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (!over) return;
    const from = findCardColumn(active.id as string);
    const to = over.id as CandidateStatus;
    if (from && to && from !== to && COLUMNS.some((c) => c.id === to)) {
      moveCard(active.id as string, from, to);
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveCardId(null);
    if (!over) return;
    const to = over.id as CandidateStatus;
    if (!COLUMNS.some((c) => c.id === to)) return;

    try {
      await apiFetch("/api/v1/pipeline/match", {
        method: "PATCH",
        body: JSON.stringify({
          position_id: positionId,
          candidate_id: active.id,
          target_status: to,
        }),
      });
    } catch (err) {
      console.error("Failed to sync match:", err);
      // TODO: rollback optimistic update on error
    }
  }

  const activeCard = activeCardId
    ? Object.values(columns)
        .flat()
        .find((c) => c.id === activeCardId)
    : null;

  const totalCards = Object.values(columns).reduce(
    (sum, col) => sum + col.length,
    0,
  );

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Filter bar */}
      <KanbanFilterBar
        employees={employees}
        availableTags={availableTags}
        onFilterChange={handleFilterChange}
      />

      {isFiltered && (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Showing {totalCards} filtered candidate{totalCards !== 1 ? "s" : ""}
        </p>
      )}

      {filterLoading ? (
        <div
          className="flex-1 flex items-center justify-center text-sm"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Filtering…
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <div className="grid grid-cols-3 gap-4 flex-1">
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.id}
                id={col.id}
                label={
                  isFiltered
                    ? `${col.label} (${columns[col.id].length})`
                    : col.label
                }
                color={col.color}
                cards={columns[col.id]}
              />
            ))}
          </div>

          <DragOverlay>
            {activeCard && (
              <CandidateCardComponent card={activeCard} isDragging />
            )}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}
```

**Update `pipeline/page.tsx`** to pass `employees` and `availableTags` props to `KanbanBoard`. Since this page is a Server Component, fetch data server-side:

```tsx
import KanbanBoard from "@/components/kanban/Board";
import { getDashboardOverview } from "@/lib/api/dashboard";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function PipelinePage({ params }: PageProps) {
  const { id } = await params;
  // Fetch employees for the filter bar (best-effort — empty array on failure)
  let employees: { id: string; name: string }[] = [];
  try {
    const { items } = await (
      await import("@/lib/api/dashboard")
    ).getDashboardEmployees({ limit: 100 });
    employees = items.map((e) => ({ id: e.id, name: e.name }));
  } catch {
    /* non-critical */
  }

  let availableTags: string[] = [];
  try {
    availableTags = await (
      await import("@/lib/api/candidates")
    ).getCandidateTags();
  } catch {
    /* non-critical */
  }

  return (
    <div className="flex flex-col h-screen p-6 gap-4">
      <div>
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--color-text-primary)" }}
        >
          Candidate Pipeline
        </h1>
        <p
          className="text-sm mt-1"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Drag candidates between columns to update their status.
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <KanbanBoard
          positionId={id}
          employees={employees}
          availableTags={availableTags}
        />
      </div>
    </div>
  );
}
```

---

## Phase 4 — Frontend: Dashboard Client Profiles

### 4A — Add `ClientProfileRow` Type

**File:** `apps/frontend/src/types/dashboard.ts`

Add at the end:

```typescript
export interface ClientProfileRow {
  client_name: string;
  total_open_positions: number;
  total_candidates: number;
  active_recruiters: number;
  last_activity: string | null; // ISO datetime string
  status: "active" | "on_hold" | "closed";
}

export interface ClientProfilesPage {
  items: ClientProfileRow[];
  meta: {
    page: number;
    limit: number;
    total: number;
    pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}
```

---

### 4B — Add `getClientProfiles` to Dashboard API Client

**File:** `apps/frontend/src/lib/api/dashboard.ts`

Add at the end:

```typescript
export interface ApiClientProfileRow {
  client_name: string;
  total_open_positions: number;
  total_candidates: number;
  active_recruiters: number;
  last_activity: string | null;
  status: "active" | "on_hold" | "closed";
}

export function getClientProfiles(query: Record<string, QueryValue> = {}) {
  return dashboardFetch<ApiPaginatedResponse<ApiClientProfileRow>>(
    "/api/v1/dashboard/client-profiles",
    query,
  );
}
```

---

### 4C — Create `ClientProfilesTable` Component

**New file:** `apps/frontend/src/components/dashboard/organisms/ClientProfilesTable.tsx`

```tsx
import type { ClientProfileRow } from "@/types/dashboard";

interface Props {
  rows: ClientProfileRow[];
}

const STATUS_STYLES = {
  active: {
    label: "Active",
    bg: "var(--color-success-subtle)",
    color: "var(--color-success)",
  },
  on_hold: {
    label: "On Hold",
    bg: "var(--color-warning-subtle)",
    color: "var(--color-warning)",
  },
  closed: {
    label: "Closed",
    bg: "var(--color-surface)",
    color: "var(--color-text-secondary)",
  },
};

function formatTimeAgo(isoDate: string | null): string {
  if (!isoDate) return "—";
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return `${months} month${months > 1 ? "s" : ""} ago`;
}

export default function ClientProfilesTable({ rows }: Props) {
  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{
        borderColor: "var(--color-border-val)",
        background: "var(--color-surface)",
      }}
    >
      <div
        className="px-5 py-4 border-b"
        style={{ borderColor: "var(--color-border-val)" }}
      >
        <h2
          className="text-base font-semibold"
          style={{ color: "var(--color-text-primary)" }}
        >
          Client Profiles
        </h2>
        <p
          className="text-xs mt-0.5"
          style={{ color: "var(--color-text-secondary)" }}
        >
          One row per client — aggregated across all their open positions.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--color-border-val)" }}>
              {[
                "Client",
                "Open Positions",
                "Candidates",
                "Active Recruiters",
                "Last Activity",
                "Status",
              ].map((h) => (
                <th
                  key={h}
                  className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-5 py-8 text-center text-sm"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  No client data available.
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const st = STATUS_STYLES[row.status] ?? STATUS_STYLES.closed;
                return (
                  <tr
                    key={row.client_name}
                    className="border-b last:border-0 hover:bg-black/5 transition-colors"
                    style={{ borderColor: "var(--color-border-val)" }}
                  >
                    <td
                      className="px-5 py-3 font-semibold"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {row.client_name}
                    </td>
                    <td
                      className="px-5 py-3 tabular-nums"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {row.total_open_positions}
                    </td>
                    <td
                      className="px-5 py-3 tabular-nums"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {row.total_candidates}
                    </td>
                    <td
                      className="px-5 py-3 tabular-nums"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {row.active_recruiters}
                    </td>
                    <td
                      className="px-5 py-3"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {formatTimeAgo(row.last_activity)}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className="inline-block text-xs font-medium px-2.5 py-0.5 rounded-full"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

### 4D — Add `fetchClientProfilesData` to `dashboard-data.ts`

**File:** `apps/frontend/src/lib/dashboard-data.ts`

Add import:

```typescript
import { getClientProfiles } from "@/lib/api/dashboard";
```

Add function at the end of the file:

```typescript
export async function getClientProfilesData(): Promise<ClientProfileRow[]> {
  try {
    const { items } = await getClientProfiles({ page: 1, limit: 20 });
    return items.map((item) => ({
      client_name: item.client_name,
      total_open_positions: item.total_open_positions,
      total_candidates: item.total_candidates,
      active_recruiters: item.active_recruiters,
      last_activity: item.last_activity,
      status: item.status,
    }));
  } catch {
    return [];
  }
}
```

Also add to the `ClientProfileRow` import from `@/types/dashboard`.

---

### 4E — Swap Component in `page.tsx`

**File:** `apps/frontend/src/app/(dashboard)/page.tsx`

1. Replace the `ClientActivitySection` async component and its `Suspense` block:

```tsx
// Remove:
import { ClientActivityTable } from "@/components/dashboard";
// ... and:
async function ClientActivitySection() {
  const clients = await getClientActivityData();
  return <ClientActivityTable rows={clients} />;
}
// ... and:
<Suspense fallback={<PanelSkeleton rows={8} />}>
  <ClientActivitySection />
</Suspense>;

// Add:
import ClientProfilesTable from "@/components/dashboard/organisms/ClientProfilesTable";
import { getClientProfilesData } from "@/lib/dashboard-data";

async function ClientProfilesSection() {
  const rows = await getClientProfilesData();
  return <ClientProfilesTable rows={rows} />;
}

// In JSX:
<Suspense fallback={<PanelSkeleton rows={8} />}>
  <ClientProfilesSection />
</Suspense>;
```

1. Update the `dashboard` barrel export to add the new component (if the barrel exists at `@/components/dashboard/index.ts`):

```typescript
// Do NOT remove ClientActivityTable export — it stays for reference.
// Just add:
export { default as ClientProfilesTable } from "./organisms/ClientProfilesTable";
```

---

## Checklist — Before Marking Complete

### Backend

- [ ] `1A` — `Candidate` model updated with `tags`, `source`, `cv_link`, new indexes
- [ ] `1B` — Schemas: `CandidateCreate`, `CandidateUpdate`, `CandidateListFilters`, `BulkUploadResult` added
- [ ] `1C` — Service: `list_candidates` accepts `CandidateListFilters`, `update_candidate`, `get_distinct_tags`, `bulk_upload_candidates` added
- [ ] `1D` — Router: `GET /tags`, `PATCH /{id}`, `POST /bulk-upload` added; `GET /` extended; route order correct (`/tags` before `/{id}`)
- [ ] `1D-i` — Storage service: `upload_bytes_to_cloudinary` added
- [ ] `1E` — `JobOpening` model: `recruiter_ids`, `last_activity_at`, new index added
- [ ] `1F` — Pipeline service: `last_activity_at` stamped inside transaction
- [ ] `1G` — Pipeline router + service: `GET /filtered` and `find_filtered_candidates` added
- [ ] `1H` — Dashboard repository: `fetch_client_profiles` added
- [ ] `1I` — Dashboard schemas: `ClientProfileRow`, `DashboardClientProfilePage` added
- [ ] `1J` — Dashboard service: `get_client_profiles` added
- [ ] `1K` — Dashboard controller: `GET /client-profiles` route added

### Frontend

- [ ] `2A` — Types: `Candidate` interface updated; `CandidateFilters`, `BulkUploadResult` added
- [ ] `2B` — `lib/api/candidates.ts` replaced with new multi-function version
- [ ] `2C` — `CandidateFilterBar` component created
- [ ] `2D` — `AddCandidateForm` component created
- [ ] `2E` — `BulkUploadDrawer` component created
- [ ] `2F` — `CandidateTable` component created
- [ ] `2G` — `candidates/page.tsx` and `CandidatesClient.tsx` created
- [ ] `3A` — `KanbanFilterBar` component created
- [ ] `3B` — `usePipelineStore` extended with `activeFilters`, `isFiltered`, `setActiveFilters`
- [ ] `3C` — `lib/api/pipeline.ts` created with `fetchFilteredPipeline`
- [ ] `3D` — `Board.tsx` rewritten to include filter bar + useEffect initial load + filtered fetch
- [ ] `3D-i` — `pipeline/page.tsx` updated to fetch and pass `employees` and `availableTags`
- [ ] `4A` — `types/dashboard.ts`: `ClientProfileRow`, `ClientProfilesPage` added
- [ ] `4B` — `lib/api/dashboard.ts`: `ApiClientProfileRow`, `getClientProfiles` added
- [ ] `4C` — `ClientProfilesTable` component created
- [ ] `4D` — `dashboard-data.ts`: `getClientProfilesData` added
- [ ] `4E` — `page.tsx`: `ClientActivitySection` replaced with `ClientProfilesSection`

---

## Edge Cases & Gotchas

| Area                                    | Issue                                                                      | Handling                                                                                                 |
| --------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Bulk upload — email collision           | Two PDFs have the same email                                               | Second file upserts over the first                                                                       |
| Bulk upload — no email in PDF           | Can't extract email from scanned/image PDFs                                | Creates with placeholder email `unknown_<cloudinary_id>@placeholder.local`                               |
| `/candidates/tags` route order          | FastAPI will match `"tags"` as a candidate_id if `/{id}` is declared first | `GET /tags` MUST come before `GET /{candidate_id}` in router.py                                          |
| Tags — case normalization               | Frontend stores lowercase, backend queries lowercase                       | `service.py` lowercases all tags on write and on filter                                                  |
| Pipeline filtered view + drag           | User filters board, then drags a card                                      | Drag still calls `PATCH /match` with correct `target_status` — filter view is display-only, not blocking |
| `last_activity_at` nulls                | New job openings have `last_activity_at=None`                              | Aggregation uses `$max` which returns null for all-null sets; `formatTimeAgo(null)` returns "—"          |
| `active_recruiters` count               | `recruiter_ids` is empty on existing `JobOpening` records                  | `active_recruiters` will be 0 until recruiters are linked to job openings via the `recruiter_ids` field  |
| Redis cache invalidation                | Client profiles cache is not invalidated when `CandidateMapping` changes   | Cache TTL is 5 min; acceptable for now. Future: invalidate on pipeline PATCH.                            |
| `CandidateResponse` includes new fields | Old consumers of this schema get unexpected fields                         | All new fields have defaults (`tags=[]`, `source="internal"`, `cv_link=null`) — non-breaking             |
