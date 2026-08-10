"""Beanie Document model for the Brand (employer organisation)."""

from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel


class Branding(BaseModel):
    logo_public_id: str | None = None  # Cloudinary public_id
    logo_url: str | None = None  # Cloudinary secure_url


class AutomationSettings(BaseModel):
    """Workspace-level switches for what happens automatically to a new resume.

    Both default to True so existing brands — whose documents predate this
    field and therefore fall back to these defaults on read — keep the
    behaviour they already had.
    """

    # Extract text from the file and infer skills / phone / experience /
    # education / previous company. Off means the resume is still stored and
    # attached to the candidate, it is just never read.
    resume_parsing_enabled: bool = True
    # Copy the top parsed skills onto the candidate as tags. Nested under
    # parsing: with parsing off there is nothing to tag from.
    auto_tagging_enabled: bool = True


class Brand(Document):
    owner_id: str
    name: str
    domain: str
    branding: Branding = Field(default_factory=Branding)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "brands"
        indexes = [
            IndexModel("owner_id"),
            IndexModel("domain", unique=True),
        ]
