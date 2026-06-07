"""Team management endpoints."""

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app.dependencies import get_tenant
from app.modules.recruitment.models import Employee, Team
from app.modules.recruitment.schemas import (
    BulkAssignEmployees,
    EmployeeTeamResponse,
    TeamCreate,
    TeamResponse,
    TenantScope,
)

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


@router.get("/employees", response_model=list[EmployeeTeamResponse])
async def list_employees(tenant: _Tenant):
    employees = await Employee.find({"brand_id": tenant.brand_id}).to_list(None)
    return employees


@router.put("/employees/assign")
async def bulk_assign_employees(tenant: _Tenant, payload: BulkAssignEmployees):
    target_team_id = PydanticObjectId(payload.team_id) if payload.team_id else None
    oids = [PydanticObjectId(eid) for eid in payload.employee_ids]

    await Employee.find({"_id": {"$in": oids}, "brand_id": tenant.brand_id}).update(
        {"$set": {"team_id": target_team_id}}
    )

    return {"status": "ok"}
