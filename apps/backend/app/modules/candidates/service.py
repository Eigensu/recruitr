"""Business logic for Candidate management."""

import asyncio
import re
from typing import Any

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
from app.modules.storage.service import (
    extract_text_from_pdf,
    upload_bytes_to_cloudinary,
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


async def create_candidate(data: CandidateCreate) -> Candidate:
    email = data.email.lower()
    existing = await Candidate.find_one(Candidate.email == email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A candidate with this email already exists",
        )
    payload = data.model_dump()
    payload["email"] = email
    payload["tags"] = [t.lower() for t in payload.get("tags", [])]
    candidate = Candidate(**payload)
    await candidate.insert()
    return candidate


async def update_candidate(candidate_id: str, data: CandidateUpdate) -> Candidate:
    candidate = await get_candidate(candidate_id)
    update_data = data.model_dump(exclude_none=True)
    if "tags" in update_data:
        update_data["tags"] = [t.lower() for t in update_data["tags"]]
    if update_data:
        await candidate.set(update_data)
    return candidate


async def confirm_resume_upload(data: CandidateUploadConfirm) -> Candidate:
    """Attach Cloudinary public_id and URL to a candidate after upload."""
    candidate = await get_candidate(data.candidate_id)
    await candidate.set(
        {
            "resume_public_id": data.resume_public_id,
            "resume_url": data.resume_url,
        }
    )
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


def _extract_skills_from_text(text: str) -> list[str]:
    """Phase 1: naive keyword extraction — alpha tokens longer than 2 chars.

    Phase 2: replace with LLM-based extraction.
    """
    words = set(text.lower().split())
    return [w for w in words if len(w) > 2 and w.isalpha()][:50]


def _extract_email_from_text(text: str) -> str | None:
    match = _EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


async def bulk_upload_candidates(files: list[UploadFile]) -> BulkUploadResult:
    """For each PDF file: upload to Cloudinary, extract text/skills, upsert by email."""
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

            # Cloudinary SDK is blocking — run off the event loop
            upload_result = await asyncio.to_thread(upload_bytes_to_cloudinary, pdf_bytes, filename)
            resume_public_id = upload_result["public_id"]
            resume_url = upload_result["secure_url"]

            raw_text = _safe_extract_text(pdf_bytes)
            skills = _extract_skills_from_text(raw_text)
            email = _extract_email_from_text(raw_text)

            if email:
                existing = await Candidate.find_one(Candidate.email == email)
                if existing:
                    await existing.set(
                        {
                            "resume_public_id": resume_public_id,
                            "resume_url": resume_url,
                            "resume_raw_text": raw_text,
                            "extracted_skills": sorted(
                                set(existing.extracted_skills) | set(skills)
                            ),
                        }
                    )
                    updated += 1
                    continue

            candidate_name = (
                filename.removesuffix(".pdf").replace("_", " ").replace("-", " ").title()
            )
            placeholder_email = (
                email or f"unknown_{resume_public_id.split('/')[-1]}@placeholder.local"
            )
            candidate = Candidate(
                name=candidate_name,
                email=placeholder_email,
                resume_public_id=resume_public_id,
                resume_url=resume_url,
                resume_raw_text=raw_text,
                extracted_skills=skills,
                source="external",
            )
            await candidate.insert()
            created += 1

        except Exception as exc:  # noqa: BLE001 — report per-file, keep processing
            failed.append(BulkUploadFailure(filename=filename, reason=str(exc)))

    return BulkUploadResult(created=created, updated=updated, failed=failed)


def _safe_extract_text(pdf_bytes: bytes) -> str:
    try:
        return extract_text_from_pdf(pdf_bytes)
    except Exception:  # noqa: BLE001 — extraction failures shouldn't abort the upload
        return ""
