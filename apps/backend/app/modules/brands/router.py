"""Brands API router."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.brands import service
from app.modules.brands.schemas import BrandCreate, BrandResponse

router = APIRouter()


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    _: TokenPayload = Depends(get_current_user),
) -> list[BrandResponse]:
    brands = await service.list_brands()
    return [BrandResponse(id=str(b.id), **b.model_dump(exclude={"id"})) for b in brands]


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(
    data: BrandCreate,
    current_user: TokenPayload = Depends(get_current_user),
) -> BrandResponse:
    brand = await service.create_brand(data, owner_id=current_user.sub)
    return BrandResponse(id=str(brand.id), **brand.model_dump(exclude={"id"}))
