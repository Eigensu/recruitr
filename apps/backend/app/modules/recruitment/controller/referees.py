"""Referee management endpoints.

GET    /referees               list referees for the brand
POST   /referees/invite        provision a referee — admin only
DELETE /referees/{id}          revoke a referee — admin only
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.dependencies import get_tenant, require_admin
from app.modules.recruitment.models import RefereeUser
from app.modules.recruitment.schemas import (
    RefereeUserInvite,
    RefereeUserResponse,
    TenantScope,
)

router = APIRouter()

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
# Gate that only lets admins through; raises 403 otherwise.
_RequireAdmin = Depends(require_admin)

_ERR_USER_NOT_FOUND = "Referee user not found"


def _stamp(updates: dict) -> dict:
    return {**updates, "updated_at": datetime.now(UTC)}


def _to_user_response(doc: RefereeUser) -> RefereeUserResponse:
    return RefereeUserResponse(
        _id=str(doc.id),
        brand_id=str(doc.brand_id),
        email=doc.email,
        name=doc.name,
        role=doc.role,
        is_active=doc.is_active,
        connect_code=doc.connect_code,
        last_login=doc.last_login,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _generate_connect_code() -> str:
    # 8 characters, uppercase alphanumeric, exclude O, 0, I, 1, L
    allowed_chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(allowed_chars) for _ in range(8))


@router.get("", response_model=list[RefereeUserResponse])
async def list_referees(tenant: _Tenant):
    """List all referees provisioned for this brand."""
    docs = await RefereeUser.find({"brand_id": tenant.brand_id}).sort("email").to_list()
    return [_to_user_response(d) for d in docs]


@router.post(
    "/invite",
    status_code=status.HTTP_201_CREATED,
    response_model=RefereeUserResponse,
    dependencies=[_RequireAdmin],
)
async def invite_referee(tenant: _Tenant, payload: RefereeUserInvite):
    """Provision a referee email address.

    This records an authorization, not a login. See RefereeUser for why creating
    a User here would hand the address full agency access.
    """
    email = payload.email.strip().lower()
    if not email:
        # TODO(aagam): email is being made optional for referees; until that's
        # properly modeled (nullable field + partial index), fall back to a
        # unique placeholder so blank invites don't collide on the unique
        # (brand_id, email) index.
        email = f"referee-{uuid4().hex[:12]}@placeholder.eigensu.test"

    existing = await RefereeUser.find_one({"brand_id": tenant.brand_id, "email": email})
    if existing:
        if existing.is_active:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{email} is already authorized as a referee"
            )
        # Re-inviting a revoked address restores the original row rather than
        # tripping the unique index.
        await existing.set(_stamp({"is_active": True, "name": payload.name, "role": payload.role}))
        return _to_user_response(existing)

    while True:
        doc = RefereeUser(
            brand_id=tenant.brand_id,
            email=email,
            name=payload.name,
            role=payload.role,
            connect_code=_generate_connect_code(),
            invited_by_id=tenant.employee_id,
        )
        try:
            await doc.insert()
            break
        except DuplicateKeyError as exc:
            if (
                "email_1" in str(exc)
                or "brand_id_1_email_1" in str(exc)
                or f"'{email}'" in str(exc)
            ):
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"{email} is already authorized as a referee"
                ) from None
            # If the duplicate key is on connect_code, it will loop and try again.

    return _to_user_response(doc)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_RequireAdmin],
)
async def remove_referee(tenant: _Tenant, user_id: str):
    """Revoke a referee's access.

    Does not delete the row, so we preserve the history of who was authorized
    and any foreign keys (e.g., if they referred a candidate).
    Sets is_active=False which prevents them signing in.
    """
    oid = to_object_id(user_id)
    if not oid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_USER_NOT_FOUND)

    doc = await RefereeUser.find_one({"_id": oid, "brand_id": tenant.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_USER_NOT_FOUND)

    if doc.is_active:
        await doc.set(_stamp({"is_active": False}))
