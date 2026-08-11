from datetime import UTC, datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_tenant, get_viewer
from app.modules.recruitment.models import ClientMessage
from app.modules.recruitment.schemas import TenantScope
from app.modules.recruitment.schemas.client_messaging import (
    ClientMessageBase,
    ClientMessageCreate,
    ClientMessageOut,
    ClientMessagePublicOut,
    ClientMessageUpdate,
)

router = APIRouter()


class ClientMessageListOut(BaseModel):
    items: list[ClientMessageOut]
    total: int


@router.get("", response_model=ClientMessageListOut)
async def list_messages(
    scope: TenantScope = Depends(get_tenant),
) -> ClientMessageListOut:
    """Internal admin endpoint to list all client messages."""
    query = {"brand_id": scope.brand_id}
    messages = await ClientMessage.find(query).sort("-created_at").to_list()
    return ClientMessageListOut(
        items=[ClientMessageOut.model_validate(m) for m in messages],
        total=len(messages),
    )


@router.post("", response_model=ClientMessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: ClientMessageCreate,
    scope: TenantScope = Depends(get_tenant),
) -> ClientMessageOut:
    """Internal admin endpoint to create a client message."""
    msg = ClientMessage(
        brand_id=scope.brand_id,
        created_by_id=scope.employee_id,
        message_text=payload.message_text,
        target_type=payload.target_type,
        target_client_ids=payload.target_client_ids,
        start_at=payload.start_at,
        end_at=payload.end_at,
        type=payload.type,
        cta_url=payload.cta_url,
    )
    await msg.insert()
    return ClientMessageOut.model_validate(msg)


@router.patch("/{msg_id}", response_model=ClientMessageOut)
async def update_message(
    msg_id: PydanticObjectId,
    payload: ClientMessageUpdate,
    scope: TenantScope = Depends(get_tenant),
) -> ClientMessageOut:
    """Internal admin endpoint to update a client message."""
    msg = await ClientMessage.find_one({"_id": msg_id, "brand_id": scope.brand_id})
    if not msg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return ClientMessageOut.model_validate(msg)

    # Apply updates
    for k, v in update_data.items():
        setattr(msg, k, v)

    # Validate resulting complete state
    try:
        # ClientMessageBase has a model_validator that checks start_at < end_at,
        # and target_client_ids logic.
        validated = ClientMessageBase(
            message_text=msg.message_text,
            target_type=msg.target_type,
            target_client_ids=msg.target_client_ids,
            start_at=msg.start_at,
            end_at=msg.end_at,
            type=msg.type,
            cta_url=msg.cta_url,
        )
        # Update msg with normalized values (like cleared target_client_ids for "all")
        msg.target_client_ids = validated.target_client_ids
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e

    await msg.save()
    return ClientMessageOut.model_validate(msg)


@router.delete("/{msg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    msg_id: PydanticObjectId,
    scope: TenantScope = Depends(get_tenant),
) -> None:
    """Internal admin endpoint to delete a client message."""
    msg = await ClientMessage.find_one({"_id": msg_id, "brand_id": scope.brand_id})
    if not msg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    await msg.delete()


class ClientMessagePublicListOut(BaseModel):
    items: list[ClientMessagePublicOut]


@router.get("/active", response_model=ClientMessagePublicListOut)
async def get_active_messages(
    scope: TenantScope = Depends(get_viewer),
) -> ClientMessagePublicListOut:
    """Client-facing endpoint to fetch currently active applicable messages."""
    now = datetime.now(UTC)

    query = {
        "brand_id": scope.brand_id,
        "start_at": {"$lte": now},
        "end_at": {"$gt": now},
    }

    # Scoping: if client, they can only see "all" or specific to their ID
    if scope.client_id:
        query["$or"] = [
            {"target_type": "all"},
            {"target_type": "specific", "target_client_ids": scope.client_id},
        ]

    messages = await ClientMessage.find(query).sort("-created_at").to_list()
    return ClientMessagePublicListOut(
        items=[ClientMessagePublicOut.model_validate(m) for m in messages]
    )
