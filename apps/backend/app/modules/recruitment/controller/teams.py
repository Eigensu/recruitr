"""Team management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_tenant
from app.modules.recruitment.models import Team
from app.modules.recruitment.schemas import TeamCreate, TeamResponse, TenantScope

router = APIRouter()
_Tenant = Annotated[TenantScope, Depends(get_tenant)]


@router.get("", response_model=list[TeamResponse])
async def list_teams(tenant: _Tenant):
    teams = await Team.find({"brand_id": tenant.brand_id}).to_list(None)
    return teams


@router.post("", response_model=TeamResponse)
async def create_team(tenant: _Tenant, payload: TeamCreate):
    team = Team(brand_id=tenant.brand_id, name=payload.name)
    await team.insert()
    return team
