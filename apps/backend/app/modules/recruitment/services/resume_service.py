import asyncio

from app.modules.storage.service import extract_text_from_file, upload_bytes_to_cloudinary
from app.modules.recruitment.utils.resume_parser import parse_resume

async def process_resume_bytes(file_bytes: bytes, filename: str):
    """
    Extracts text from the resume bytes, parses structured fields, and uploads the file to Cloudinary.

    Raises:
        ValueError: If text extraction fails due to invalid file content.
        Exception: If Cloudinary upload fails.
        
    Returns:
        A tuple of (raw_text, parsed_resume, resume_url, resume_public_id).
    """
    # 1. Extract text
    raw_text = extract_text_from_file(file_bytes)

    # 2. Parse structured fields
    parsed = parse_resume(raw_text)

    # 3. Upload to Cloudinary (blocking SDK call -> thread pool)
    cld = await asyncio.to_thread(upload_bytes_to_cloudinary, file_bytes, filename)
    resume_url = cld.get("secure_url", "")
    resume_public_id = cld.get("public_id", "")

    return raw_text, parsed, resume_url, resume_public_id

def build_candidate_resume_update(
    existing_doc, 
    parsed: ParsedResume, 
    raw_text: str, 
    resume_url: str | None = None, 
    resume_public_id: str | None = None
) -> dict:
    """
    Build a MongoDB update dict to merge parsed resume fields into an existing candidate without 
    overwriting fields the recruiter has set, except for skills/tags which always sync.
    """
    update: dict = {"resume_raw_text": raw_text}
    
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
