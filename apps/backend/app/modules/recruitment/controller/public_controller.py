"""Public APIs for Candidate Application Form.

Endpoints:
  POST   /apply                       Submit a candidate application (unauthenticated)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pymongo.errors import DuplicateKeyError, OperationFailure
from beanie import PydanticObjectId

from app.common.utils.object_id import to_object_id
from app.config import settings
from app.modules.brands.models import Brand
from app.modules.recruitment.enums import CandidateStatus
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import CandidateResponse
from app.modules.recruitment.utils.resume_parser import parse_resume
from app.modules.storage.service import extract_text_from_file, upload_bytes_to_cloudinary

_CLOUDINARY_HOST = f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/"

router = APIRouter()
_log = logging.getLogger(__name__)

@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def public_apply(
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    brand_id: Annotated[str | None, Query(description="Brand ID to apply to (optional if only one brand exists)")] = None,
    phone: Annotated[str | None, Form()] = None,
    current_role: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    education_level: Annotated[str | None, Form()] = None,
    resume: UploadFile | None = File(None, description="PDF or DOCX resume file"),
) -> CandidateResponse:
    """Submit a public application."""
    
    # Resolve brand
    target_brand_id: PydanticObjectId
    if brand_id:
        try:
            target_brand_id = to_object_id(brand_id, "brand_id")
        except Exception:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid brand_id format")
    else:
        # Default to first brand if none provided
        first_brand = await Brand.find_one({})
        if not first_brand:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No brands configured in the system")
        target_brand_id = first_brand.id

    raw_text = None
    resume_url = None
    resume_public_id = None
    parsed_skills = []
    parsed_tags = []
    parsed_exp = 0.0

    if resume:
        filename = resume.filename or "unknown"
        if not filename.lower().endswith((".pdf", ".docx")):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF and DOCX files are accepted")
            
        try:
            file_bytes = await resume.read()
            raw_text = extract_text_from_file(file_bytes)
            parsed = parse_resume(raw_text)
            parsed_skills = parsed.skills or []
            parsed_tags = parsed.tags or []
            parsed_exp = parsed.experience_years or 0.0
            
            cld = await asyncio.to_thread(upload_bytes_to_cloudinary, file_bytes, filename)
            resume_url = cld.get("secure_url")
            resume_public_id = cld.get("public_id")
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Resume extraction failed: {str(exc)}")
        except Exception as exc:
            _log.exception("Upload failed for public form")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Upload failed: {str(exc)}")

    from pydantic import ValidationError
    
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
            status=CandidateStatus.pending
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid application data: {str(e)}")
    
    try:
        await doc.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An application with this email already exists"
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
        source=doc.source,
        status=doc.status,
        created_at=doc.created_at,
    )
