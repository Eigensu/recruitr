"""Business logic for Brand management."""

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

    brand = Brand(
        owner_id=owner_id,
        name=name,
        domain=domain,
        branding=Branding(),
    )
    await brand.insert()
    return brand


async def get_brand_by_org(owner_id: str) -> Brand | None:
    return await Brand.find_one(Brand.owner_id == owner_id)


async def get_all_brands() -> list[Brand]:
    return await Brand.find_all().to_list()


async def create_brand(data: BrandCreate, owner_id: str) -> Brand:
    brand = Brand(
        owner_id=owner_id,
        name=data.name,
        domain=data.domain,
        branding=Branding(),
    )
    await brand.insert()
    return brand
