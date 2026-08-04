"""Brands API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_tenant
from app.modules.auth.schemas import TokenPayload
from app.modules.brands import service
from app.modules.brands.models import Brand
from app.modules.brands.schemas import BrandCreate, BrandResponse
from app.modules.recruitment.schemas import TenantScope

router = APIRouter()


@router.get("")
async def list_brands(
    _: Annotated[TokenPayload, Depends(get_current_user)],
) -> list[BrandResponse]:
    brands = await service.get_all_brands()
    return [BrandResponse(id=str(b.id), **b.model_dump(exclude={"id"})) for b in brands]


@router.get("/me")
async def my_brand(
    tenant: Annotated[TenantScope, Depends(get_tenant)],
) -> BrandResponse:
    """The signed-in user's own brand.

    Resolved through get_tenant so it uses the same employee→brand path as
    every other tenant-scoped route, rather than a second source of truth.
    """
    brand = await Brand.get(tenant.brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No brand for this user")
    return BrandResponse(id=str(brand.id), **brand.model_dump(exclude={"id"}))


@router.post("", status_code=201)
async def create_brand(
    data: BrandCreate,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> BrandResponse:
    brand = await service.create_brand(data, owner_id=current_user.sub)
    return BrandResponse(id=str(brand.id), **brand.model_dump(exclude={"id"}))
