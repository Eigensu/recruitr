"""Dashboard API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.dashboard import service
from app.modules.dashboard.enums import PipelineStage
from app.modules.dashboard.schemas import (
    DashboardActivityPage,
    DashboardCandidatePage,
    DashboardClientPage,
    DashboardEmployeePage,
    DashboardFilters,
    DashboardMappingPage,
    DashboardOverviewResponse,
    DashboardPipelineResponse,
)

router = APIRouter()


def _filters(
    employee_id: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    client_id: str | None,
    pipeline_stage: PipelineStage | None,
) -> DashboardFilters:
    return DashboardFilters(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        pipeline_stage=pipeline_stage,
    )


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_overview(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardOverviewResponse:
    return await service.get_overview(_filters(employee_id, start_date, end_date, client_id, pipeline_stage))


@router.get("/pipeline", response_model=DashboardPipelineResponse)
async def get_pipeline(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardPipelineResponse:
    return await service.get_pipeline(_filters(employee_id, start_date, end_date, client_id, pipeline_stage))


@router.get("/employees", response_model=DashboardEmployeePage)
async def get_employees(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardEmployeePage:
    return await service.get_employees(
        _filters(employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/clients", response_model=DashboardClientPage)
async def get_clients(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardClientPage:
    return await service.get_clients(
        _filters(employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/candidates", response_model=DashboardCandidatePage)
async def get_candidates(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardCandidatePage:
    return await service.get_candidates(
        _filters(employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/mappings", response_model=DashboardMappingPage)
async def get_mappings(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardMappingPage:
    return await service.get_mappings(
        _filters(employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )


@router.get("/activity", response_model=DashboardActivityPage)
async def get_activity(
    employee_id: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    client_id: str | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    _: TokenPayload = Depends(get_current_user),
) -> DashboardActivityPage:
    return await service.get_activities(
        _filters(employee_id, start_date, end_date, client_id, pipeline_stage),
        page,
        limit,
    )
