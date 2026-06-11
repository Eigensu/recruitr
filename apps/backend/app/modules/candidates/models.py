"""Beanie Document model for Candidates."""

from datetime import datetime
from typing import Any, Literal

from beanie import Document
from pydantic import Field, model_validator
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
    # ── Candidate management additions ────────────────────────────────────────
    tags: list[str] = Field(default_factory=list)
    source: Literal["internal", "external"] = "internal"
    cv_link: str | None = None  # externally hosted CV URL (optional)
    # ── Unified fields (absorbed from the former DashboardCandidate) ──────────
    previous_company: str | None = None
    experience: float = 0
    current_stage: str | None = None  # denormalised pipeline stage (string enum value)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="before")
    @classmethod
    def _backfill_legacy_fields(cls, data: Any) -> Any:
        """Tolerate legacy dashboard-shaped docs (full_name/skills/resume_link).

        Historically a parallel DashboardCandidate model wrote the same
        `candidates` collection with different field names. This normalises those
        documents on read so the unified model never fails to parse.
        """
        if isinstance(data, dict):
            if not data.get("name") and data.get("full_name"):
                data["name"] = data["full_name"]
            if not data.get("extracted_skills") and data.get("skills"):
                data["extracted_skills"] = data["skills"]
            if not data.get("cv_link") and data.get("resume_link"):
                data["cv_link"] = data["resume_link"]
        return data

    class Settings:
        name = "candidates"
        indexes = [
            IndexModel("email", unique=True),
            IndexModel("extracted_skills"),
            IndexModel("tags"),  # multikey — supports $all / $in queries
            IndexModel("source"),  # equality filter
        ]
