"""Positions API router."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.positions import service
from app.modules.positions.schemas import PositionCreate, PositionResponse, PositionUpdate

router = APIRouter()


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    current_user: TokenPayload = Depends(get_current_user),
) -> list[PositionResponse]:
    brand_id = current_user.org_id or current_user.sub
    positions = await service.list_positions(brand_id)
    return [PositionResponse(id=str(p.id), brand_id=str(p.brand_id), **p.model_dump(exclude={"id", "brand_id"})) for p in positions]


@router.post("", response_model=PositionResponse, status_code=201)
async def create_position(
    data: PositionCreate,
    current_user: TokenPayload = Depends(get_current_user),
) -> PositionResponse:
    brand_id = current_user.org_id or current_user.sub
    position = await service.create_position(data, brand_id)
    return PositionResponse(id=str(position.id), brand_id=str(position.brand_id), **position.model_dump(exclude={"id", "brand_id"}))


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: str,
    _: TokenPayload = Depends(get_current_user),
) -> PositionResponse:
    position = await service.get_position(position_id)
    return PositionResponse(id=str(position.id), brand_id=str(position.brand_id), **position.model_dump(exclude={"id", "brand_id"}))


@router.patch("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: str,
    data: PositionUpdate,
    _: TokenPayload = Depends(get_current_user),
) -> PositionResponse:
    position = await service.update_position(position_id, data)
    return PositionResponse(id=str(position.id), brand_id=str(position.brand_id), **position.model_dump(exclude={"id", "brand_id"}))


@router.delete("/{position_id}", status_code=204)
async def delete_position(
    position_id: str,
    _: TokenPayload = Depends(get_current_user),
) -> None:
    await service.delete_position(position_id)
