"""Tests for the Brand service logic."""

import pytest
from fastapi import HTTPException

from app.modules.brands import service
from app.modules.brands.models import Brand
from app.modules.brands.schemas import BrandCreate


@pytest.mark.asyncio
async def test_create_brand_success() -> None:
    data = BrandCreate(name="Eigensu", domain="eigensu.in")
    brand = await service.create_brand(data, owner_id="user_123")

    assert brand.name == "Eigensu"
    assert brand.domain == "eigensu.in"
    assert brand.owner_id == "user_123"

    # Verify it exists in DB
    db_brand = await Brand.find_one(Brand.domain == "eigensu.in")
    assert db_brand is not None
    assert db_brand.id == brand.id


@pytest.mark.asyncio
async def test_create_brand_duplicate_domain_raises_conflict() -> None:
    data1 = BrandCreate(name="Eigensu", domain="eigensu.in")
    await service.create_brand(data1, owner_id="user_123")

    # Try creating with same domain but different owner/name
    data2 = BrandCreate(name="Another Eigensu", domain="eigensu.in")
    with pytest.raises(HTTPException) as exc_info:
        await service.create_brand(data2, owner_id="user_456")

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_brand_from_org_idempotent_success() -> None:
    # First creation
    brand = await service.create_brand_from_org(
        owner_id="user_123", name="Eigensu", domain="eigensu.in"
    )
    assert brand.owner_id == "user_123"

    # Second creation with same owner should return the existing brand
    brand2 = await service.create_brand_from_org(
        owner_id="user_123", name="Eigensu Renamed", domain="eigensu.in"
    )
    assert brand2.id == brand.id


@pytest.mark.asyncio
async def test_create_brand_from_org_duplicate_domain_raises_conflict() -> None:
    # First creation by user_123
    await service.create_brand_from_org(owner_id="user_123", name="Eigensu", domain="eigensu.in")

    # Second creation by user_456 with same domain should raise 409
    with pytest.raises(HTTPException) as exc_info:
        await service.create_brand_from_org(
            owner_id="user_456", name="Another Company", domain="eigensu.in"
        )

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail
