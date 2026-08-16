"""Referee management endpoints.

GET    /referees               list referees for the brand
POST   /referees/invite        provision a referee — admin only
DELETE /referees/{id}          revoke a referee — admin only
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

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
from app.modules.recruitment.utils.connect_code import ensure_connect_code, generate_connect_code

router = APIRouter()

_MAX_CODE_ATTEMPTS = 5

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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email is required to invite a referee.")

    existing = await RefereeUser.find_one({"brand_id": tenant.brand_id, "email": email})
    if existing:
        if existing.is_active:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{email} is already authorized as a referee"
            )
        # Re-inviting a revoked address restores the original row rather than
        # tripping the unique index.
        await existing.set(_stamp({"is_active": True, "name": payload.name, "role": payload.role}))
        await ensure_connect_code(existing)
        return _to_user_response(existing)

    # Bounded, unlike an open `while True`: only a connect_code collision is
    # worth another draw, and anything else that keeps raising would spin here
    # forever holding the request open.
    for _ in range(_MAX_CODE_ATTEMPTS):
        doc = RefereeUser(
            brand_id=tenant.brand_id,
            email=email,
            name=payload.name,
            role=payload.role,
            connect_code=generate_connect_code(),
            invited_by_id=tenant.employee_id,
        )
        try:
            await doc.insert()
            return _to_user_response(doc)
        except DuplicateKeyError as exc:
            if "connect_code" not in str(exc):
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"{email} is already authorized as a referee"
                ) from None
            # Collided with a live code — draw again.

    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Could not allocate a connect code for this referee. Please try again.",
    )


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
