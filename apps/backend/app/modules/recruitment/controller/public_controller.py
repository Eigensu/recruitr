"""Public APIs for Candidate Application Form.

Endpoints:
  GET    /brands/{domain}             Resolve an agency by its public domain (unauthenticated)
  POST   /apply                       Submit a candidate application (unauthenticated)
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.config import settings
from app.modules.brands.models import Brand
from app.modules.brands.schemas import PublicBrandResponse
from app.modules.recruitment.enums import CandidateStatus
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import CandidateResponse
from app.modules.storage.service import (
    delete_cloudinary_asset,
)

_CLOUDINARY_HOST = f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/"

router = APIRouter()
_log = logging.getLogger(__name__)


async def _find_brand_by_domain(domain: str) -> Brand | None:
    """Look up an agency by its public domain.

    Tries the exact stored value first so the unique index is used, then falls
    back to a case-insensitive match because domains are case-insensitive in
    practice and onboarding stores whatever casing the agency typed.
    """
    brand = await Brand.find_one(Brand.domain == domain)
    if brand is None:
        brand = await Brand.find_one(
            {"domain": {"$regex": f"^{re.escape(domain)}$", "$options": "i"}}
        )
    return brand


async def _resolve_target_brand(brand_id: str | None) -> PydanticObjectId:
    """Resolve which agency (tenant) an application belongs to."""
    if brand_id:
        try:
            target = to_object_id(brand_id, "brand_id")
        except Exception as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid brand_id format") from exc
        if not await Brand.find_one(Brand.id == target):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown brand")
        return target

    # No brand supplied: only safe to infer when the deployment has exactly one.
    brands = await Brand.find_all().to_list()
    if len(brands) == 1:
        return brands[0].id
    if not brands:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No brands configured in the system"
        )
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "This application link is missing its agency. Please use the full link you were given.",
    )


@router.get("/brands/{domain}")
async def public_brand_by_domain(domain: str) -> PublicBrandResponse:
    """Resolve an agency by domain so the public form can brand and target itself.

    Intentionally a single-item lookup with no list counterpart: enumerating
    agencies on an unauthenticated endpoint would expose the customer roster.
    """
    brand = await _find_brand_by_domain(domain)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown brand")
    return PublicBrandResponse(
        id=str(brand.id),
        name=brand.name,
        logo_url=brand.branding.logo_url,
    )


async def _process_resume_upload(
    resume: UploadFile | None,
) -> tuple[str | None, str | None, str | None, list[str], list[str], float]:
    """Process the resume upload, parse it, and upload to Cloudinary."""
    if not resume:
        return None, None, None, [], [], 0.0

    filename = resume.filename or "unknown"
    if not filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF and DOCX files are accepted")

    if resume.size is not None and resume.size > 10 * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Resume file too large (max 10MB)"
        )

    try:
        file_bytes = await resume.read()

        # Manually check size if resume.size was not provided by the server
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Resume file too large (max 10MB)"
            )

        from app.modules.recruitment.services.resume_service import process_resume_bytes

        raw_text, parsed, resume_url, resume_public_id = await process_resume_bytes(
            file_bytes, filename
        )

        parsed_skills = parsed.skills or []
        parsed_tags = parsed.tags or []
        parsed_exp = parsed.experience_years or 0.0

        return raw_text, resume_url, resume_public_id, parsed_skills, parsed_tags, parsed_exp
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Resume extraction failed due to invalid file content"
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _log.exception("Upload failed for public form")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred during upload"
        ) from exc


@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def public_apply(
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    # Must stay a Form field: the client submits multipart/form-data, and a
    # Query-declared param would be read from the URL only and silently ignored.
    brand_id: Annotated[
        str | None, Form(description="Agency to apply to (optional if only one exists)")
    ] = None,
    phone: Annotated[str | None, Form()] = None,
    current_role: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    education_level: Annotated[str | None, Form()] = None,
    resume: Annotated[UploadFile | None, File(description="PDF or DOCX resume file")] = None,
) -> CandidateResponse:
    """Submit a public application."""

    target_brand_id = await _resolve_target_brand(brand_id)
    (
        raw_text,
        resume_url,
        resume_public_id,
        parsed_skills,
        parsed_tags,
        parsed_exp,
    ) = await _process_resume_upload(resume)

    try:
        doc = Candidate(
            brand_id=target_brand_id,
            full_name=full_name,
            email=email.lower(),
            phone=phone,
            city=city,
            current_role=current_role,
            education_level=education_level,
            experience_years=parsed_exp,
            skills=parsed_skills,
            skills_normalized=[s.lower() for s in parsed_skills],
            tags=parsed_tags,
            resume_url=resume_url,
            resume_public_id=resume_public_id,
            resume_raw_text=raw_text,
            source="External",
            status=CandidateStatus.pending,
        )
    except ValidationError as e:
        if resume_public_id:
            await asyncio.to_thread(delete_cloudinary_asset, resume_public_id)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid application data format provided"
        ) from e

    try:
        await doc.insert()
    except DuplicateKeyError as exc:
        if resume_public_id:
            await asyncio.to_thread(delete_cloudinary_asset, resume_public_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An application with this email already exists"
        ) from exc

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
        source=doc.source,
        status=doc.status,
        created_at=doc.created_at,
    )
