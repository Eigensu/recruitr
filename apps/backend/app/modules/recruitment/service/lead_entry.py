"""Leads a staff member adds from the Leads page — typed in, or read from resumes.

Two steps. Reading uploaded resumes into editable drafts stores nothing and
uploads nothing, so a dialog closed half way leaves no orphan files behind.
Submitting the drafts a person has checked turns each one into a lead through
ingest_leads — the same duplicate checks, telecaller round-robin and review as
every other source — and only then uploads the resume of each person actually
created, so a duplicate's existing record is never touched.

Sits beside intake_service rather than in it: this is the HTTP-shaped edge of
manual entry (files, per-draft errors), and ingest stays the one write path.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from beanie import PydanticObjectId
from pydantic import ValidationError

from app.modules.brands.models import AutomationSettings
from app.modules.recruitment.enums import IntakeSource
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import (
    ManualLeadDraft,
    ManualLeadResult,
    ManualLeadsResponse,
    ResumeLeadDraft,
)
from app.modules.recruitment.service.intake_service import LeadOutcome, ingest_leads
from app.modules.recruitment.service.resume_service import (
    build_candidate_resume_update,
    parse_resume_with,
    process_resume_bytes,
)
from app.modules.recruitment.utils.constants import RESUME_MAX_BYTES
from app.modules.recruitment.utils.lead_sheet import ParsedLead, parse_email
from app.modules.recruitment.utils.phone import normalize_phone
from app.modules.storage.service import extract_text_from_file

_log = logging.getLogger(__name__)

SOURCE_CHANNEL = "Added by recruiter"
_PARSING_OFF = "Reading resumes is switched off for this workspace — fill the details in."


@dataclass(frozen=True)
class ResumeFile:
    """An uploaded resume as read off the request, or why it can't be used."""

    filename: str
    data: bytes | None = None
    error: str | None = None


def check_resume(filename: str, data: bytes) -> ResumeFile:
    """Accept a PDF or Word resume of at most RESUME_MAX_BYTES; say why not otherwise.

    Checked by content, not by name: a renamed file is caught here rather than
    failing later inside the PDF reader.
    """
    if len(data) > RESUME_MAX_BYTES:
        return ResumeFile(filename, error="Over 5 MB — use a smaller file.")
    if not (data.startswith(b"%PDF-") or data[:2] == b"PK"):
        return ResumeFile(filename, error="Only PDF and Word (.docx) resumes can be used.")
    return ResumeFile(filename, data=data)


async def drafts_from_resumes(
    files: list[ResumeFile], automation: AutomationSettings
) -> list[ResumeLeadDraft]:
    """One draft per file, in upload order. Reads text; stores and uploads nothing."""
    drafts: list[ResumeLeadDraft] = []
    for file in files:
        if file.error or file.data is None:
            drafts.append(ResumeLeadDraft(filename=file.filename, error=file.error))
            continue
        if not automation.resume_parsing_enabled:
            drafts.append(ResumeLeadDraft(filename=file.filename, notice=_PARSING_OFF))
            continue
        try:
            # CPU-bound PDF/DOCX decoding and regex passes: off the event loop.
            text = await asyncio.to_thread(extract_text_from_file, file.data)
            parsed = await asyncio.to_thread(parse_resume_with, text, automation)
        except ValueError:
            drafts.append(
                ResumeLeadDraft(
                    filename=file.filename,
                    error="Couldn't read any text in this file — is it a scanned image?",
                )
            )
            continue
        drafts.append(
            ResumeLeadDraft(
                filename=file.filename,
                full_name=parsed.full_name,
                phone=parsed.phone,
                email=parsed.email,
                city=parsed.city,
                current_role=parsed.current_role,
                department=parsed.department,
                current_company=parsed.previous_company,
                experience_years=parsed.experience_years,
            )
        )
    return drafts


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    field = ".".join(str(part) for part in err.get("loc", ())) or "draft"
    return f"{field.replace('_', ' ')}: {err.get('msg', 'invalid')}"


def _lead_from(draft: ManualLeadDraft, phone_normalized: str, email: str | None) -> ParsedLead:
    return ParsedLead(
        # Unique per submission. Re-adding the same person is caught as a
        # duplicate by phone/email in ingest, not by this id.
        external_id=f"manual:{uuid.uuid4().hex}",
        full_name=draft.full_name,
        phone=draft.phone,
        phone_normalized=phone_normalized,
        email=email,
        city=draft.city,
        current_role=draft.current_role,
        # Becomes the candidate's specialization, as the Naukri designation
        # does, so a department picked here comes with one when a role is given.
        role_interest=draft.current_role,
        department=draft.department,
        experience_years=draft.experience_years,
        previous_company=draft.current_company,
        salary=draft.salary,
        expected_salary=draft.expected_salary,
        source_channel=SOURCE_CHANNEL,
    )


async def _attach_resume(
    candidate_id: PydanticObjectId, file: ResumeFile, automation: AutomationSettings
) -> bool:
    """Upload a newly created candidate's resume and fill in what it adds.

    build_candidate_resume_update never overwrites a field already set, so what
    the person typed in the draft wins over anything parsed from the file.
    """
    candidate = await Candidate.get(candidate_id)
    if candidate is None or file.data is None:
        return False
    try:
        raw_text, parsed, url, public_id = await process_resume_bytes(
            file.data, file.filename, automation
        )
    except Exception:
        # The filename is client-supplied; it stays out of the log line.
        _log.exception("Resume upload failed for a manually added lead")
        return False
    update = build_candidate_resume_update(
        existing_doc=candidate,
        parsed=parsed,
        raw_text=raw_text,
        resume_url=url,
        resume_public_id=public_id,
    )
    if update:
        await candidate.set(update)
    return True


def _result_for(index: int, name: str, outcome: LeadOutcome) -> ManualLeadResult:
    if outcome.outcome == "created":
        if outcome.assigned:
            return ManualLeadResult(
                index=index, full_name=name, status="queued", detail="Sent to a telecaller."
            )
        return ManualLeadResult(
            index=index,
            full_name=name,
            status="waiting",
            detail="Added, but no telecaller is active to call them yet.",
        )
    if outcome.outcome == "matched_existing":
        return ManualLeadResult(
            index=index,
            full_name=name,
            status="duplicate",
            detail="Already in the candidate pool — filed as a duplicate, not called again.",
        )
    return ManualLeadResult(
        index=index, full_name=name, status="error", detail="Couldn't be added. Try again."
    )


async def add_manual_leads(
    raw_drafts: list,
    files: list[ResumeFile],
    *,
    brand_id: PydanticObjectId,
    submitted_by_id: PydanticObjectId | None,
    automation: AutomationSettings,
) -> ManualLeadsResponse:
    """Turn checked drafts into leads. Each draft succeeds or fails on its own."""
    results: list[ManualLeadResult | None] = [None] * len(raw_drafts)
    pending: list[tuple[int, ManualLeadDraft, ParsedLead]] = []

    for index, raw in enumerate(raw_drafts):
        name = raw.get("full_name") if isinstance(raw, dict) else None
        try:
            draft = ManualLeadDraft.model_validate(raw)
        except ValidationError as exc:
            results[index] = ManualLeadResult(
                index=index, full_name=name, status="error", detail=_first_error(exc)
            )
            continue

        phone_normalized = normalize_phone(draft.phone)
        email = parse_email(draft.email)
        problem = None
        if not phone_normalized:
            problem = "Phone: needs a 10-digit number the telecaller can call."
        elif draft.email and not email:
            problem = "Email: doesn't look like an email address."
        elif draft.resume_index is not None:
            if draft.resume_index >= len(files):
                problem = "Resume: no file was uploaded for this draft."
            elif files[draft.resume_index].error:
                problem = f"Resume: {files[draft.resume_index].error}"
        if problem:
            results[index] = ManualLeadResult(
                index=index, full_name=draft.full_name, status="error", detail=problem
            )
            continue
        pending.append((index, draft, _lead_from(draft, phone_normalized, email)))  # type: ignore[arg-type]

    ingest = await ingest_leads(
        [lead for _, _, lead in pending],
        brand_id=brand_id,
        source=IntakeSource.recruiter_manual,
        submitted_by_id=submitted_by_id,
    )

    for index, draft, lead in pending:
        outcome = ingest.outcomes.get(lead.external_id, LeadOutcome("error"))
        result = _result_for(index, draft.full_name, outcome)
        if (
            outcome.outcome == "created"
            and outcome.candidate_id is not None
            and draft.resume_index is not None
            and not await _attach_resume(
                outcome.candidate_id, files[draft.resume_index], automation
            )
        ):
            result.detail += " The resume couldn't be attached — add it from their profile."
        results[index] = result

    final = [r for r in results if r is not None]
    return ManualLeadsResponse(
        results=final,
        queued=sum(r.status == "queued" for r in final),
        waiting=sum(r.status == "waiting" for r in final),
        duplicate=sum(r.status == "duplicate" for r in final),
        error=sum(r.status == "error" for r in final),
    )
