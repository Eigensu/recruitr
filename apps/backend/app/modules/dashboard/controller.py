"""Dashboard API routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_tenant
from app.modules.dashboard import service
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
)
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.schemas import TenantScope

router = APIRouter()

# ── Annotated query-parameter aliases ─────────────────────────────────────────
# Per FastAPI rules, defaults must be set with = on the parameter, not inside Query().
# These aliases carry only the metadata (validation constraints, docs).

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_EmployeeId = Annotated[str | None, Query()]
_StartDate = Annotated[datetime | None, Query()]
_EndDate = Annotated[datetime | None, Query()]
_ClientId = Annotated[str | None, Query()]
_Stage = Annotated[PipelineStage | None, Query()]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]


def _filters(
    tenant: TenantScope,
    employee_id: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    client_id: str | None,
    pipeline_stage: PipelineStage | None,
) -> DashboardFilters:
    return DashboardFilters(
        brand_id=str(tenant.brand_id),
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        pipeline_stage=pipeline_stage,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/overview")
async def get_overview(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
) -> DashboardOverviewResponse:
    return await service.get_overview(
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage)
    )


@router.get("/pipeline")
async def get_pipeline(
    tenant: _Tenant,
    employee_id: _EmployeeId = None,
    start_date: _StartDate = None,
    end_date: _EndDate = None,
    client_id: _ClientId = None,
    pipeline_stage: _Stage = None,
) -> DashboardPipelineResponse:
    return await service.get_pipeline(
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage)
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
    return await service.get_employees(
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
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
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
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
    return await service.get_candidates(
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
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
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
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
        _filters(tenant, employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )
