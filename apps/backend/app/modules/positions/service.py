"""Business logic for Position management."""

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.modules.positions.models import Position
from app.modules.positions.schemas import PositionCreate, PositionUpdate


async def create_position(data: PositionCreate, brand_id: str) -> Position:
    position = Position(
        brand_id=PydanticObjectId(brand_id),
        title=data.title,
        requirements=data.requirements,
    )
    await position.insert()
    return position


async def list_positions(brand_id: str) -> list[Position]:
    return await Position.find(Position.brand_id == PydanticObjectId(brand_id)).to_list()


async def get_position(position_id: str) -> Position:
    position = await Position.get(PydanticObjectId(position_id))
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    return position


async def update_position(position_id: str, data: PositionUpdate) -> Position:
    position = await get_position(position_id)
    update_data = data.model_dump(exclude_none=True)
    if update_data:
        await position.set(update_data)
    return position


async def delete_position(position_id: str) -> None:
    position = await get_position(position_id)
    await position.delete()
