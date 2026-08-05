"""Narrowing queries to a single employer for the client role.

Mapping carries a denormalized client_id, but it is null on every document
written before that field existed — so filtering mappings on it directly would
silently hide a client's older pipeline. These helpers go through Position
instead, which has always had client_id, and are the only correct way to scope
mapping-shaped queries.
"""

from __future__ import annotations

from beanie import PydanticObjectId

from app.modules.recruitment.models import Position
from app.modules.recruitment.schemas import TenantScope


async def client_position_ids(scope: TenantScope) -> list[PydanticObjectId]:
    """Every position id belonging to the scoped client, archived ones included.

    Archived positions count: their mappings are still part of the pipeline the
    client worked through, and hiding them would make historical stages vanish.
    """
    return await Position.get_motor_collection().distinct(
        "_id", {"brand_id": scope.brand_id, "client_id": scope.client_id}
    )


async def scope_mapping_match(scope: TenantScope, match: dict) -> dict:
    """Restrict a mapping query to the scoped client, or leave it alone for staff.

    A client with no positions yet gets `position_id: {"$in": []}`, which matches
    nothing — the right answer, and never an unfiltered query.
    """
    if scope.client_id is None:
        return match
    match["position_id"] = {"$in": await client_position_ids(scope)}
    return match
