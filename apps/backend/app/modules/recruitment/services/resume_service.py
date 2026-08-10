"""Resume ingestion — text extraction, field parsing, and storage upload.

Every entry point takes the brand's AutomationSettings and is the one place
those switches are honoured, so a workspace that has turned resume parsing off
gets the file stored and attached to the candidate without its contents ever
being read.
"""

import asyncio

from app.modules.brands.models import AutomationSettings
from app.modules.recruitment.utils.resume_parser import (
    ParsedResume,
    extract_email,
    parse_resume,
)
from app.modules.storage.service import extract_text_from_file, upload_bytes_to_cloudinary


def parse_resume_with(
    raw_text: str,
    automation: AutomationSettings,
    *,
    email_only: bool = False,
) -> ParsedResume:
    """Parse `raw_text` as far as the brand's automation settings allow."""
    if not automation.resume_parsing_enabled:
        # Bulk upload matches candidates by the email in the file, so it asks
        # for that one field even with parsing off — without it every file in
        # the batch fails and the feature is dead rather than merely disabled.
        return ParsedResume(email=extract_email(raw_text)) if email_only else ParsedResume()

    parsed = parse_resume(raw_text)
    if not automation.auto_tagging_enabled:
        parsed.tags = []
    return parsed


async def process_resume_bytes(
    file_bytes: bytes,
    filename: str,
    automation: AutomationSettings,
    *,
    email_only: bool = False,
):
    """
    Extracts text from the resume bytes, parses structured fields, and uploads the file to Cloudinary.

    Raises:
        ValueError: If text extraction fails due to invalid file content.
        Exception: If Cloudinary upload fails.

    Returns:
        A tuple of (raw_text, parsed_resume, resume_url, resume_public_id).
        `raw_text` is None when the brand has parsing off — the file is still
        uploaded, and `parsed` carries at most the email when `email_only`.
    """
    # 1. Extract text — only if something is going to read it
    text = (
        extract_text_from_file(file_bytes)
        if automation.resume_parsing_enabled or email_only
        else None
    )

    # 2. Parse structured fields
    parsed = (
        parse_resume_with(text, automation, email_only=email_only)
        if text is not None
        else ParsedResume()
    )

    # 3. Upload to Cloudinary (blocking SDK call -> thread pool)
    cld = await asyncio.to_thread(upload_bytes_to_cloudinary, file_bytes, filename)
    resume_url = cld.get("secure_url", "")
    resume_public_id = cld.get("public_id", "")

    # The stored raw text is a parsing artifact. With parsing off we may still
    # have read the file to recover the email, but none of it is kept.
    raw_text = text if automation.resume_parsing_enabled else None

    return raw_text, parsed, resume_url, resume_public_id


def build_candidate_resume_update(
    existing_doc,
    parsed: ParsedResume,
    raw_text: str | None,
    resume_url: str | None = None,
    resume_public_id: str | None = None,
) -> dict:
    """
    Build a MongoDB update dict to merge parsed resume fields into an existing candidate without
    overwriting fields the recruiter has set, except for skills/tags which always sync.

    With the brand's parsing switched off `parsed` is empty and `raw_text` is
    None, so this narrows to just the resume URL — the file is attached and
    nothing about the candidate is inferred.
    """
    update: dict = {}

    if raw_text is not None:
        update["resume_raw_text"] = raw_text

    if resume_url is not None:
        update["resume_url"] = resume_url
    if resume_public_id is not None:
        update["resume_public_id"] = resume_public_id

    if parsed.skills:
        update["skills"] = parsed.skills
        update["skills_normalized"] = [s.lower() for s in parsed.skills]

    if parsed.tags:
        update["tags"] = parsed.tags

    if parsed.phone and not existing_doc.phone:
        update["phone"] = parsed.phone

    if parsed.experience_years is not None and existing_doc.experience_years == 0:
        update["experience_years"] = parsed.experience_years

    if parsed.education_level is not None and existing_doc.education_level is None:
        update["education_level"] = parsed.education_level

    if parsed.previous_company and not existing_doc.previous_company:
        update["previous_company"] = parsed.previous_company

    return update
