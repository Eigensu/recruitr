"""Recruiter tag management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_tenant
from app.modules.recruitment.models import RecruiterTag
from app.modules.recruitment.schemas import RecruiterTagCreate, RecruiterTagResponse, TenantScope

router = APIRouter()
_Tenant = Annotated[TenantScope, Depends(get_tenant)]


@router.get("", response_model=list[RecruiterTagResponse])
async def list_tags(tenant: _Tenant):
    tags = await RecruiterTag.find({"brand_id": tenant.brand_id}).to_list(None)
    return tags


@router.post("", response_model=RecruiterTagResponse)
async def create_tag(tenant: _Tenant, payload: RecruiterTagCreate):
    tag = RecruiterTag(brand_id=tenant.brand_id, name=payload.name)
    await tag.insert()
    return tag
