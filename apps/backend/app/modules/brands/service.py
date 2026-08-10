"""Business logic for Brand management."""

from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.modules.brands.models import AutomationSettings, Brand, Branding
from app.modules.brands.schemas import AutomationSettingsUpdate, BrandCreate


async def create_brand_from_org(
    owner_id: str,
    name: str,
    domain: str,
) -> Brand:
    """Create a Brand document for a user."""
    existing = await Brand.find_one(Brand.owner_id == owner_id)
    if existing:
        return existing  # idempotent

    existing_domain = await Brand.find_one(Brand.domain == domain)
    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A brand with this domain already exists.",
        )

    brand = Brand(
        owner_id=owner_id,
        name=name,
        domain=domain,
        branding=Branding(),
    )
    try:
        await brand.insert()
    except DuplicateKeyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A brand with this domain already exists.",
        ) from err
    return brand


# ── Automation settings ────────────────────────────────────────────────────────


async def get_automation_settings(brand_id: PydanticObjectId) -> AutomationSettings:
    """Resume automation switches for a brand.

    Falls back to the defaults (everything on, i.e. the behaviour that predates
    this setting) when the brand row is missing, so a dangling brand_id degrades
    into the old behaviour rather than silently turning parsing off everywhere.
    """
    brand = await Brand.get(brand_id)
    return brand.automation if brand else AutomationSettings()


async def update_automation_settings(
    brand_id: PydanticObjectId, data: AutomationSettingsUpdate
) -> AutomationSettings:
    brand = await Brand.get(brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    current = brand.automation
    updated = AutomationSettings(
        resume_parsing_enabled=(
            current.resume_parsing_enabled
            if data.resume_parsing_enabled is None
            else data.resume_parsing_enabled
        ),
        auto_tagging_enabled=(
            current.auto_tagging_enabled
            if data.auto_tagging_enabled is None
            else data.auto_tagging_enabled
        ),
    )
    # Auto-tagging is sourced from parsed skills, so leaving it "on" while
    # parsing is off would show a switch that does nothing.
    if not updated.resume_parsing_enabled:
        updated.auto_tagging_enabled = False

    await brand.set({"automation": updated.model_dump()})
    return updated


async def get_brand_by_org(owner_id: str) -> Brand | None:
    return await Brand.find_one(Brand.owner_id == owner_id)


async def get_all_brands() -> list[Brand]:
    return await Brand.find_all().to_list()


async def create_brand(data: BrandCreate, owner_id: str) -> Brand:
    # One workspace per owner. Re-running onboarding returns the existing brand
    # rather than minting a second tenant — unbounded brand creation is what
    # broke the public application form, which can only infer the agency when
    # exactly one exists.
    existing = await Brand.find_one(Brand.owner_id == owner_id)
    if existing:
        return existing

    # Check if a brand with this domain already exists
    existing_domain = await Brand.find_one(Brand.domain == data.domain)
    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A brand with this domain already exists.",
        )

    brand = Brand(
        owner_id=owner_id,
        name=data.name,
        domain=data.domain,
        branding=Branding(),
    )
    try:
        await brand.insert()
    except DuplicateKeyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A brand with this domain already exists.",
        ) from err
    return brand
