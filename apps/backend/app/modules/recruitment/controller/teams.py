"""Team management endpoints.

Reads (list teams/employees) are available to any user in the brand.
Writes (create/edit team, assign employees) are restricted to maintainers
and admins via the require_maintainer guard.
"""

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_tenant, require_maintainer
from app.modules.auth.models import User, UserRole
from app.modules.recruitment.models import Employee, Team
from app.modules.recruitment.schemas import (
    BulkAssignEmployees,
    EmployeeTeamResponse,
    TeamCreate,
    TeamResponse,
    TeamUpdate,
    TenantScope,
)

router = APIRouter()
_Tenant = Annotated[TenantScope, Depends(get_tenant)]
# Gate that only lets maintainers/admins through; raises 403 otherwise.
_RequireMaintainer = Depends(require_maintainer)


async def _elevated_emails() -> set[str]:
    """Emails of maintainer/admin users — they are not recruiters and are hidden
    from employee listings."""
    elevated = await User.find(
        {"role": {"$in": [UserRole.maintainer.value, UserRole.admin.value]}}
    ).to_list(None)
    return {user.email.lower() for user in elevated}


@router.get("", response_model=list[TeamResponse])
async def list_teams(tenant: _Tenant):
    teams = await Team.find({"brand_id": tenant.brand_id}).to_list(None)
    return teams


@router.post("", response_model=TeamResponse, dependencies=[_RequireMaintainer])
async def create_team(tenant: _Tenant, payload: TeamCreate):
    team = Team(brand_id=tenant.brand_id, name=payload.name)
    await team.insert()
    return team


@router.put("/{team_id}", response_model=TeamResponse, dependencies=[_RequireMaintainer])
async def update_team(tenant: _Tenant, team_id: str, payload: TeamUpdate):
    team = await Team.find_one({"_id": PydanticObjectId(team_id), "brand_id": tenant.brand_id})
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    if payload.name is not None:
        team.name = payload.name
    if payload.is_active is not None:
        team.is_active = payload.is_active
    await team.save()
    return team


@router.get("/employees", response_model=list[EmployeeTeamResponse])
async def list_employees(tenant: _Tenant):
    employees = await Employee.find({"brand_id": tenant.brand_id}).to_list(None)
    hidden = await _elevated_emails()
    return [employee for employee in employees if employee.email.lower() not in hidden]


@router.put("/employees/assign", dependencies=[_RequireMaintainer])
async def bulk_assign_employees(tenant: _Tenant, payload: BulkAssignEmployees):
    target_team_id = None
    if payload.team_id:
        team = await Team.find_one(
            {"_id": PydanticObjectId(payload.team_id), "brand_id": tenant.brand_id}
        )
        if not team:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
        target_team_id = team.id
    oids = [PydanticObjectId(eid) for eid in payload.employee_ids]

    await Employee.find({"_id": {"$in": oids}, "brand_id": tenant.brand_id}).update(
        {"$set": {"team_id": target_team_id}}
    )

    return {"status": "ok"}
