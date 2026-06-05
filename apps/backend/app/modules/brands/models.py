"""Beanie Document model for the Brand (employer organisation)."""

from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel


class Branding(BaseModel):
    logo_public_id: str | None = None  # Cloudinary public_id
    logo_url: str | None = None  # Cloudinary secure_url


class Brand(Document):
    owner_id: str
    name: str
    domain: str
    branding: Branding = Field(default_factory=Branding)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "brands"
        indexes = [
            IndexModel("owner_id"),
            IndexModel("domain", unique=True),
        ]
