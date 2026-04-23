"""Pydantic schemas for the Brands API."""

from datetime import datetime

from pydantic import BaseModel


class BrandingSchema(BaseModel):
    logo_public_id: str | None = None
    logo_url: str | None = None


class BrandCreate(BaseModel):
    name: str
    domain: str


class BrandResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    domain: str
    branding: BrandingSchema
    created_at: datetime

    model_config = {"from_attributes": True}
