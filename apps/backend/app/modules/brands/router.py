"""Brands API router.

Deliberately minimal. A brand is the tenant (one recruitment agency's
workspace) and is created once during onboarding, so there is no CRUD surface
around it:

  - Reading your own brand goes through GET /auth/me, which already resolves
    employee -> brand and is fetched on every page load.
  - There is no list endpoint. With one agency per deployment it would return a
    single row, and it would hand every signed-in user the full agency roster.

The exception is /settings, which is workspace configuration rather than brand
identity: it is read by any staff member and written only by a maintainer.
"""

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_tenant, require_maintainer
from app.modules.auth.access import NOT_AUTHORIZED, may_hold_staff_account
from app.modules.auth.models import User
from app.modules.auth.schemas import TokenPayload
from app.modules.brands import service
from app.modules.brands.schemas import (
    AutomationSettingsSchema,
    AutomationSettingsUpdate,
    BrandCreate,
    BrandResponse,
    BrandSettingsResponse,
    BrandSettingsUpdate,
)
from app.modules.recruitment.schemas import TenantScope

router = APIRouter()

_Tenant = Annotated[TenantScope, Depends(get_tenant)]


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


@router.get("/settings")
async def read_brand_settings(tenant: _Tenant) -> BrandSettingsResponse:
    """Workspace configuration for the caller's brand.

    Readable by any staff member — the settings screen shows the switches to
    everyone so recruiters can see why a resume was or was not parsed, but only
    a maintainer can change them.
    """
    automation = await service.get_automation_settings(tenant.brand_id)
    return BrandSettingsResponse(automation=AutomationSettingsSchema.model_validate(automation))


@router.patch("/settings", dependencies=[Depends(require_maintainer)])
async def update_brand_settings(
    tenant: _Tenant, data: BrandSettingsUpdate
) -> BrandSettingsResponse:
    """Update the caller's workspace automation switches. Maintainers only."""
    automation = await service.update_automation_settings(
        tenant.brand_id, data.automation or AutomationSettingsUpdate()
    )
    return BrandSettingsResponse(automation=AutomationSettingsSchema.model_validate(automation))
