"""Business logic for Brand management."""

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.modules.brands.models import Brand, Branding
from app.modules.brands.schemas import BrandCreate


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
