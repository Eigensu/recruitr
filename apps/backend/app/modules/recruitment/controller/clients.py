"""Client management endpoints.

  GET    /clients                list clients for the brand (+ active position counts)
  POST   /clients                create a client — any brand user, so a recruiter can
                                 add a missing client inline while creating a position
  PATCH  /clients/{id}           rename / re-city / archive-restore — admin only
  DELETE /clients/{id}           archive (soft-delete) — admin only

Renaming a client fans the new name out to Position.client_name, which is
denormalized for list rendering and would otherwise go stale.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant, require_admin
from app.modules.recruitment.models import Client, Position
from app.modules.recruitment.repository import generate_client_code
from app.modules.recruitment.schemas import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    TenantScope,
)

router = APIRouter()

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_IncludeArchived = Annotated[bool, Query()]
# Gate that only lets admins through; raises 403 otherwise.
_RequireAdmin = Depends(require_admin)

_ERR_NOT_FOUND = "Client not found"
_CODE_RETRIES = 5


def _name_regex(name: str) -> dict:
    """Case-insensitive exact match on a client name."""
    return {"$regex": f"^{re.escape(name)}$", "$options": "i"}


async def _count_active_positions(brand_id, client_id) -> int:
    return await Position.find(
        {"brand_id": brand_id, "client_id": client_id, "is_active": True}
    ).count()


def _to_response(client: Client, position_count: int) -> ClientResponse:
    return ClientResponse(
        id=str(client.id),
        code=client.code,
        name=client.name,
        city=client.city,
        is_active=client.is_active,
        position_count=position_count,
    )


async def _get_or_404(tenant: TenantScope, client_id: str) -> Client:
    oid = to_object_id(client_id, "client_id")
    doc = await Client.find_one({"_id": oid, "brand_id": tenant.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_NOT_FOUND)
    return doc


# ── List ───────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ClientResponse])
async def list_clients(tenant: _Tenant, include_archived: _IncludeArchived = False):
    """Clients for the brand, alphabetical, each with its active position count."""
    match: dict = {"brand_id": tenant.brand_id}
    if not include_archived:
        match["is_active"] = True

    pipeline = [
        {"$match": match},
        {
            "$lookup": {
                "from": "positions",
                "let": {"cid": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$client_id", "$$cid"]},
                            "is_active": True,
                        }
                    },
                    {"$count": "n"},
                ],
                "as": "pos_count",
            }
        },
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
                "position_count": {"$ifNull": [{"$first": "$pos_count.n"}, 0]},
            }
        },
        {"$unset": ["pos_count"]},
        {"$sort": {"name": 1}},
    ]

    rows = await (await Client.get_motor_collection().aggregate(pipeline)).to_list(length=None)  # type: ignore[misc]
    return [ClientResponse.model_validate(r) for r in rows]


# ── Create ─────────────────────────────────────────────────────────────────────


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(tenant: _Tenant, payload: ClientCreate):
    """Add a client to the brand's list.

    Not admin-gated: creating a position requires picking a client, so a recruiter
    who hits a client that isn't in the list yet has to be able to add it.
    """
    existing = await Client.find_one(
        {"brand_id": tenant.brand_id, "name": _name_regex(payload.name)}
    )
    if existing:
        if existing.is_active:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f'A client named "{existing.name}" already exists'
            )
        # Reviving an archived client keeps its code and its position history
        # instead of creating a second row for the same real-world client.
        await existing.set({"is_active": True, "city": payload.city or existing.city})
        return _to_response(existing, await _count_active_positions(tenant.brand_id, existing.id))

    doc = Client(
        brand_id=tenant.brand_id,
        code=await generate_client_code(tenant.brand_id),
        name=payload.name,
        city=payload.city or None,
    )
    # The client counter can lag behind the codes already in the collection
    # (migrations write codes without touching it), so a fresh code may collide.
    # Each retry increments the counter, which walks past any existing code.
    for attempt in range(_CODE_RETRIES):
        try:
            await doc.insert()
            break
        except DuplicateKeyError:
            if attempt == _CODE_RETRIES - 1:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Could not allocate a client code — please retry"
                ) from None
            doc.code = await generate_client_code(tenant.brand_id)

    return _to_response(doc, 0)


# ── Update ─────────────────────────────────────────────────────────────────────


@router.patch("/{client_id}", response_model=ClientResponse, dependencies=[_RequireAdmin])
async def update_client(tenant: _Tenant, client_id: str, payload: ClientUpdate):
    doc = await _get_or_404(tenant, client_id)
    update: dict = {}

    if payload.name is not None and payload.name != doc.name:
        clash = await Client.find_one(
            {
                "brand_id": tenant.brand_id,
                "name": _name_regex(payload.name),
                "_id": {"$ne": doc.id},
            }
        )
        if clash:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f'A client named "{clash.name}" already exists'
            )
        update["name"] = payload.name

    if payload.city is not None:
        update["city"] = payload.city or None
    if payload.is_active is not None:
        update["is_active"] = payload.is_active

    if update:
        await doc.set(update)

    # client_name is denormalized onto every position for list rendering — a
    # rename that skipped this would leave the old name on screen forever.
    if "name" in update:
        await Position.get_motor_collection().update_many(
            {"brand_id": tenant.brand_id, "client_id": doc.id},
            {"$set": {"client_name": update["name"], "updated_at": datetime.now(UTC)}},
        )

    return _to_response(doc, await _count_active_positions(tenant.brand_id, doc.id))


# ── Archive (soft delete) ──────────────────────────────────────────────────────


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_RequireAdmin])
async def archive_client(tenant: _Tenant, client_id: str):
    """Remove a client from the dropdowns.

    Refused while the client still has open positions: those positions would stay
    live with no client left to filter them by.
    """
    doc = await _get_or_404(tenant, client_id)

    open_positions = await _count_active_positions(tenant.brand_id, doc.id)
    if open_positions:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{doc.name} still has {open_positions} active position"
            f"{'s' if open_positions != 1 else ''}. Delete those first.",
        )

    await doc.set({"is_active": False})
