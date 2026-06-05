"""Beanie Document model for Candidates."""

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class Candidate(Document):
    name: str
    email: str
    phone: str | None = None
    # Cloudinary fields (replaces S3)
    resume_public_id: str | None = None  # Cloudinary public_id of the uploaded PDF
    resume_url: str | None = None  # Cloudinary secure_url for download
    resume_raw_text: str | None = None  # Extracted plain text (Phase 1 stub)
    extracted_skills: list[str] = Field(default_factory=list)

    class Settings:
        name = "candidates"
        indexes = [
            IndexModel("email", unique=True),
            IndexModel("extracted_skills"),
        ]
