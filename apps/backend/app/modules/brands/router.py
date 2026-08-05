"""Brands API router.

Deliberately minimal. A brand is the tenant (one recruitment agency's
workspace) and is created once during onboarding, so there is no CRUD surface
around it:

  - Reading your own brand goes through GET /auth/me, which already resolves
    employee -> brand and is fetched on every page load.
  - There is no list endpoint. With one agency per deployment it would return a
    single row, and it would hand every signed-in user the full agency roster.
"""

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.modules.auth.access import NOT_AUTHORIZED, may_hold_staff_account
from app.modules.auth.models import User
from app.modules.auth.schemas import TokenPayload
from app.modules.brands import service
from app.modules.brands.schemas import BrandCreate, BrandResponse

router = APIRouter()


@router.post("", status_code=201)
async def create_brand(
    data: BrandCreate,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> BrandResponse:
    """Create the caller's workspace, or return it if they already have one.

    Restricted to agency addresses. An unauthorized caller could otherwise mint
    a tenant of their own — which is both a junk row and an outage: the public
    application form can only infer the agency when exactly one brand exists.
    """
    user = await User.get(PydanticObjectId(current_user.sub))
    if not user or not await may_hold_staff_account(user.email):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_AUTHORIZED)

    brand = await service.create_brand(data, owner_id=current_user.sub)
    return BrandResponse(id=str(brand.id), **brand.model_dump(exclude={"id"}))
