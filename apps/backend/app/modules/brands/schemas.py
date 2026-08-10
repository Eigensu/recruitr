"""Pydantic schemas for the Brands API."""

from datetime import datetime

from pydantic import BaseModel


class BrandingSchema(BaseModel):
    logo_public_id: str | None = None
    logo_url: str | None = None


class AutomationSettingsSchema(BaseModel):
    resume_parsing_enabled: bool = True
    auto_tagging_enabled: bool = True

    model_config = {"from_attributes": True}


class AutomationSettingsUpdate(BaseModel):
    """PATCH body — an omitted switch is left as-is."""

    resume_parsing_enabled: bool | None = None
    auto_tagging_enabled: bool | None = None


class BrandCreate(BaseModel):
    name: str
    domain: str


class PublicBrandResponse(BaseModel):
    """Minimal brand fields safe to expose on unauthenticated surfaces.

    Deliberately excludes owner_id, domain and created_at: the public
    application form only needs enough to identify and visually brand itself.
    """

    id: str
    name: str
    logo_url: str | None = None


class BrandResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    domain: str
    branding: BrandingSchema
    automation: AutomationSettingsSchema = AutomationSettingsSchema()
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandSettingsResponse(BaseModel):
    """Workspace configuration, split out from BrandResponse.

    Kept separate so the settings screen — which every signed-in staff member
    loads — does not hand out owner_id and the rest of the tenant record.
    """

    automation: AutomationSettingsSchema


class BrandSettingsUpdate(BaseModel):
    """PATCH body, mirroring BrandSettingsResponse. An omitted group is untouched."""

    automation: AutomationSettingsUpdate | None = None
