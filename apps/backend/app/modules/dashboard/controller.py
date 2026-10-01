"""Dashboard API routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_tenant, get_viewer
from app.modules.auth.models import UserRole
from app.modules.dashboard.schemas import (
    DashboardActivityPage,
    DashboardCandidatePage,
    DashboardClientPage,
    DashboardClientProfilePage,
    DashboardEmployeePage,
    DashboardFilters,
    DashboardMappingPage,
    DashboardOverviewResponse,
    DashboardPipelineResponse,
    DashboardSourcingResponse,
    DashboardStageTimingResponse,
)
from app.modules.dashboard.services import service
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.schemas import TenantScope

router = APIRouter()

# ── Annotated query-parameter aliases ─────────────────────────────────────────
# Per FastAPI rules, defaults must be set with = on the parameter, not inside Query().
# These aliases carry only the metadata (validation constraints, docs).

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
# Staff or client. Only on endpoints whose every query honours client_id —
# which rules out /activity (_activity_match ignores it, so a client would
# see the whole brand's feed) and the employee/client roster endpoints.
_Viewer = Annotated[TenantScope, Depends(get_viewer)]
_EmployeeId = Annotated[str | None, Query()]
_StartDate = Annotated[datetime | None, Query()]
_EndDate = Annotated[datetime | None, Query()]
_ClientId = Annotated[str | None, Query()]
_Stage = Annotated[PipelineStage | None, Query()]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]


async def _filters(
    tenant: TenantScope,
    employee_id: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    client_id: str | None,
    pipeline_stage: PipelineStage | None,
) -> DashboardFilters:
    # Every dashboard query is built from this one place, so pinning client_id
    # here scopes the whole dashboard rather than each endpoint separately. It
    # overrides the query parameter, not merges with it: a client asking for
    # another employer's numbers gets their own.
    if tenant.client_id is not None:
        client_id = str(tenant.client_id)
    filters = DashboardFilters(
        brand_id=str(tenant.brand_id),
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        pipeline_stage=pipeline_stage,
    )
    # A recruiter sees only what they are part of — the same override-not-merge
    # rule as client_id above: an employee_id in the query is ignored, so asking
    # for a colleague's numbers returns their own.
    if _is_recruiter(tenant):
        assigned, positions = await service.recruiter_scope(tenant.brand_id, tenant.employee_id)
        filters.employee_id = None
        filters.scope_employee_id = str(tenant.employee_id)
        filters.scope_assigned_position_ids = assigned
        filters.scope_position_ids = positions
    return filters


def _is_recruiter(tenant: TenantScope) -> bool:
    return tenant.role == UserRole.employee and tenant.employee_id is not None


def _not_for_recruiters(tenant: TenantScope) -> None:
    """Brand-wide reports — everyone's numbers — are closed to recruiters."""
    if _is_recruiter(tenant):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not available to recruiters")


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/overview")
async def get_overview(
    tenant: _Viewer,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
) -> DashboardOverviewResponse:
    return await service.get_overview(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage)
    )


@router.get("/pipeline")
async def get_pipeline(
    tenant: _Viewer,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
) -> DashboardPipelineResponse:
    return await service.get_pipeline(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage)
    )


@router.get("/stage-timing")
async def get_stage_timing(
    tenant: _Viewer,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
) -> DashboardStageTimingResponse:
    return await service.get_stage_timing(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage)
    )


@router.get("/sourcing")
async def get_sourcing(
    tenant: _Viewer,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
) -> DashboardSourcingResponse:
    _not_for_recruiters(tenant)
    return await service.get_sourcing(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage)
    )


@router.get("/employees")
async def get_employees(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
    page: _Page = 1,
    limit: _Limit = 50,
) -> DashboardEmployeePage:
    _not_for_recruiters(tenant)
    return await service.get_employees(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/clients")
async def get_clients(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
    page: _Page = 1,
    limit: _Limit = 50,
) -> DashboardClientPage:
    return await service.get_clients(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/candidates")
async def get_candidates(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
    page: _Page = 1,
    limit: _Limit = 50,
) -> DashboardCandidatePage:
    _not_for_recruiters(tenant)
    return await service.get_candidates(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/mappings")
async def get_mappings(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
    page: _Page = 1,
    limit: _Limit = 50,
) -> DashboardMappingPage:
    return await service.get_mappings(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/client-profiles")
async def get_client_profiles(
    tenant: _Tenant,
    page: _Page = 1,
    limit: _Limit = 20,
) -> DashboardClientProfilePage:
    """One row per client, aggregated across all their job openings."""
    _not_for_recruiters(tenant)
    return await service.get_client_profiles(str(tenant.brand_id), page, limit)


@router.get("/activity")
async def get_activity(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
    page: _Page = 1,
    limit: _Limit = 50,
) -> DashboardActivityPage:
    return await service.get_activities(
        await _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )
