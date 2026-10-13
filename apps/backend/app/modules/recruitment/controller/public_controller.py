"""Public APIs for Candidate Application Form.

Endpoints:
  GET    /brands/{domain}             Resolve an agency by its public domain (unauthenticated)
  POST   /apply                       Submit a candidate application (unauthenticated)
  GET    /cv-upload/{token}           What a CV upload link is for (unauthenticated)
  POST   /cv-upload/{token}           Upload a CV through that link (unauthenticated)
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
from app.core.config import settings
from app.modules.brands.models import AutomationSettings, Brand
from app.modules.brands.schemas import PublicBrandResponse
from app.modules.brands.service import get_automation_settings
from app.modules.recruitment.enums import CandidateEventType, CandidateStatus
from app.modules.recruitment.models import Candidate, IntakeLead, RefereeUser
from app.modules.recruitment.repository import record_candidate_event
from app.modules.recruitment.schemas import CandidateResponse, CvUploadLinkInfo, TenantScope
from app.modules.recruitment.service.cv_requests import attach_cv, lead_for_token
from app.modules.recruitment.service.intake_service import open_lead_for_application
from app.modules.recruitment.service.intake_sla import alert_unqueued_application
from app.modules.recruitment.service.resume_service import process_resume_bytes
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
    automation: AutomationSettings,
) -> tuple[str | None, str | None, str | None, list[str], list[str], float]:
    """Process the resume upload, parse it, and upload to Cloudinary.

    Honours the target brand's automation settings: with parsing off the file is
    still stored and linked, and the applicant lands with no inferred skills,
    tags or experience.
    """
    if not resume:
        return None, None, None, [], [], 0.0
    raw_text, parsed, resume_url, resume_public_id = await _store_resume(resume, automation)
    return (
        raw_text,
        resume_url,
        resume_public_id,
        parsed.skills or [],
        parsed.tags or [],
        parsed.experience_years or 0.0,
    )


async def _store_resume(resume: UploadFile, automation: AutomationSettings) -> tuple:
    """Check one uploaded resume, read and parse it, and put it in Cloudinary.

    Returns process_resume_bytes' (raw_text, parsed, resume_url, resume_public_id),
    or raises the error to show whoever sent it.
    """
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

        return await process_resume_bytes(file_bytes, filename, automation)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Resume extraction failed due to invalid file content"
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _log.exception("Resume upload failed on a public page")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred during upload"
        ) from exc


@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def public_apply(
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    phone: Annotated[str, Form(min_length=1)],
    # Must stay a Form field: the client submits multipart/form-data, and a
    # Query-declared param would be read from the URL only and silently ignored.
    brand_id: Annotated[
        str | None, Form(description="Agency to apply to (optional if only one exists)")
    ] = None,
    current_role: Annotated[str | None, Form()] = None,
    city: Annotated[str | None, Form()] = None,
    education_level: Annotated[str | None, Form()] = None,
    source_channel: Annotated[str | None, Form(description="How the applicant found us")] = None,
    # ₹ per month, like every candidate salary. Both are optional.
    current_salary: Annotated[float | None, Form(ge=0)] = None,
    expected_salary: Annotated[float | None, Form(ge=0)] = None,
    connect_code: Annotated[
        str | None, Form(description="Optional connect code for referrals")
    ] = None,
    resume: Annotated[UploadFile | None, File(description="PDF or DOCX resume file")] = None,
) -> CandidateResponse:
    """Submit a public application."""

    target_brand_id = await _resolve_target_brand(brand_id)

    # Codes are minted uppercase but typed by hand off a message or a screen, so
    # match on the normalized form — a lowercased or padded code is the right
    # code, and failing it silently costs the referee their attribution.
    normalized_code = (connect_code or "").strip().upper() or None

    referee_id = None
    if normalized_code:
        referee = await RefereeUser.find_one(
            {"brand_id": target_brand_id, "connect_code": normalized_code, "is_active": True}
        )
        # Refused rather than stored: an unmatched code credits nobody, and only
        # the applicant can tell a typo from the code they were given. Checked
        # before the resume upload so a refusal leaves nothing in Cloudinary.
        # Matched within the brand being applied to: another agency's referee
        # must not be credited with, or see, this brand's candidate.
        if referee is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "That connect code isn't recognised. Check it with whoever gave it to "
                "you, or clear it to apply without one.",
            )
        referee_id = referee.id

    automation = await get_automation_settings(target_brand_id)
    (
        raw_text,
        resume_url,
        resume_public_id,
        parsed_skills,
        parsed_tags,
        parsed_exp,
    ) = await _process_resume_upload(resume, automation)

    try:
        doc = Candidate(
            brand_id=target_brand_id,
            full_name=full_name,
            email=email.lower(),
            phone=phone,
            city=city,
            current_role=current_role,
            # Stamped salary_period="monthly" by Candidate's Insert hook.
            salary=current_salary,
            expected_salary=expected_salary,
            education_level=education_level,
            experience_years=parsed_exp,
            skills=parsed_skills,
            skills_normalized=[s.lower() for s in parsed_skills],
            tags=parsed_tags,
            resume_url=resume_url,
            resume_public_id=resume_public_id,
            resume_raw_text=raw_text,
            # Lowercase to match every other writer (and the source filter's
            # options) — "External" was invisible to the directory's filter.
            source="external",
            source_channel=source_channel,
            connect_code=normalized_code,
            referee_id=referee_id,
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

    # Opens the candidate's permanent history. There is no employee behind a
    # public application, so the scope carries the brand only.
    await record_candidate_event(
        scope=TenantScope(brand_id=target_brand_id),
        candidate_id=doc.id,
        event_type=CandidateEventType.applied,
        note=(
            f"Applied through the public form ({source_channel})"
            if source_channel
            else "Applied through the public form"
        ),
    )

    # Every external applicant — referrals included — is screened by a
    # telecaller before a recruiter sees them.
    await _queue_for_screening(doc)

    return CandidateResponse.from_document(doc)


async def _queue_for_screening(candidate: Candidate) -> None:
    """Open the applicant's lead, or make sure somebody hears that it failed.

    The application is already saved, so nothing here may fail the request.
    Opening is idempotent — the lead is keyed on the candidate id — so a second
    attempt cannot double it, and rides out a momentary blip. If both fail the
    candidate is PENDING with no lead, which no page in the app shows; the
    alert is what tells anyone they exist.
    """
    for attempt in (1, 2):
        try:
            await open_lead_for_application(candidate)
            return
        except Exception:
            _log.exception(
                "Could not open an intake lead for applicant %s (attempt %d)",
                candidate.id,
                attempt,
            )
    try:
        await alert_unqueued_application(candidate)
    except Exception:
        _log.exception("Could not alert anyone about unqueued applicant %s", candidate.id)


# ── CV upload links ────────────────────────────────────────────────────────────

_LINK_GONE = "This link has expired or been replaced. Ask whoever sent it to you for a new one."


async def _live_link(token: str) -> tuple[IntakeLead, Candidate]:
    lead = await lead_for_token(token)
    candidate = (
        await Candidate.find_one({"_id": lead.candidate_id, "brand_id": lead.brand_id})
        if lead is not None
        else None
    )
    if lead is None or candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _LINK_GONE)
    return lead, candidate


async def _link_info(lead: IntakeLead, candidate: Candidate, *, uploaded: bool) -> CvUploadLinkInfo:
    brand = await Brand.get(lead.brand_id)
    return CvUploadLinkInfo(
        first_name=(candidate.full_name or "").split(" ")[0],
        brand_name=brand.name if brand else "",
        brand_logo_url=brand.branding.logo_url if brand else None,
        expires_at=lead.cv_upload_expires_at,
        uploaded=uploaded,
    )


@router.get("/cv-upload/{token}", response_model=CvUploadLinkInfo)
async def cv_upload_page(token: str) -> CvUploadLinkInfo:
    """Who a CV upload link is for, to greet them. 404 once it no longer works."""
    lead, candidate = await _live_link(token)
    return await _link_info(lead, candidate, uploaded=lead.cv_uploaded_at is not None)


@router.post("/cv-upload/{token}", response_model=CvUploadLinkInfo)
async def upload_cv_through_link(
    token: str, resume: Annotated[UploadFile, File()]
) -> CvUploadLinkInfo:
    """Put the candidate's CV on their record, replacing any earlier one.

    The token is the whole credential: it was made for one lead by whoever
    holds it, and only its hash is stored (service/cv_requests.py).
    """
    lead, _ = await _live_link(token)
    automation = await get_automation_settings(lead.brand_id)
    raw_text, parsed, resume_url, resume_public_id = await _store_resume(resume, automation)
    candidate = await attach_cv(
        lead,
        parsed=parsed,
        raw_text=raw_text,
        resume_url=resume_url,
        resume_public_id=resume_public_id,
    )
    if candidate is None:
        if resume_public_id:
            await asyncio.to_thread(delete_cloudinary_asset, resume_public_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, _LINK_GONE)
    return await _link_info(lead, candidate, uploaded=True)
