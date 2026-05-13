"""Business logic for dashboard analytics and supporting writes."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from app.common.dtos.pagination import PaginationMeta
from app.common.extras.redis_cache import dashboard_cache
from app.config import settings
from app.modules.dashboard.enums import ActivityType, PipelineStage, TargetEntityType
from app.modules.dashboard.models import ActivityLog, CandidateMapping
from app.modules.dashboard.repository import (
    create_activity_log,
    create_candidate_mapping,
    fetch_activities,
    fetch_candidates,
    fetch_clients,
    fetch_employees,
    fetch_mappings,
    fetch_overview,
    fetch_pipeline,
)
from app.modules.dashboard.schemas import (
    ActivityAnalyticsItem,
    CandidateAnalyticsItem,
    ClientAnalyticsItem,
    DashboardActivityPage,
    DashboardCandidatePage,
    DashboardClientPage,
    DashboardEmployeePage,
    DashboardFilters,
    DashboardMappingPage,
    DashboardOverviewResponse,
    DashboardPipelineResponse,
    EmployeeAnalyticsItem,
    MappingAnalyticsItem,
    PipelineStageMetric,
)


def _cache_key(prefix: str, filters: DashboardFilters, page: int | None = None, limit: int | None = None) -> str:
    payload = filters.model_dump(mode="json", exclude_none=True)
    raw = json.dumps({"filters": payload, "page": page, "limit": limit}, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return dashboard_cache.build_key(prefix, digest)


def _make_paginated_response(payload: dict[str, Any], items: list[Any], page_cls: type) -> Any:
    total = int(payload["total"])
    page = int(payload["page"])
    limit = int(payload["limit"])
    pages = 0 if total == 0 else (total + limit - 1) // limit
    meta = PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )
    return page_cls(items=items, meta=meta)


async def get_overview(filters: DashboardFilters) -> DashboardOverviewResponse:
    cache_key = _cache_key("overview", filters)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardOverviewResponse.model_validate(cached)

    payload, pipeline_payload = await asyncio.gather(
        fetch_overview(filters),
        fetch_pipeline(filters),
    )
    response = DashboardOverviewResponse(
        summary=payload["summary"],
        pipeline=[PipelineStageMetric.model_validate(stage) for stage in pipeline_payload["stages"]],
    )
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def get_pipeline(filters: DashboardFilters) -> DashboardPipelineResponse:
    cache_key = _cache_key("pipeline", filters)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardPipelineResponse.model_validate(cached)

    payload = await fetch_pipeline(filters)
    response = DashboardPipelineResponse(
        stages=[PipelineStageMetric.model_validate(stage) for stage in payload["stages"]],
        total_candidates=payload["total_candidates"],
    )
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def get_employees(filters: DashboardFilters, page: int, limit: int) -> DashboardEmployeePage:
    cache_key = _cache_key("employees", filters, page, limit)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardEmployeePage.model_validate(cached)

    payload = await fetch_employees(filters, page, limit)
    items = [EmployeeAnalyticsItem.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardEmployeePage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def get_clients(filters: DashboardFilters, page: int, limit: int) -> DashboardClientPage:
    cache_key = _cache_key("clients", filters, page, limit)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardClientPage.model_validate(cached)

    payload = await fetch_clients(filters, page, limit)
    items = [ClientAnalyticsItem.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardClientPage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def get_candidates(filters: DashboardFilters, page: int, limit: int) -> DashboardCandidatePage:
    cache_key = _cache_key("candidates", filters, page, limit)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardCandidatePage.model_validate(cached)

    payload = await fetch_candidates(filters, page, limit)
    items = [CandidateAnalyticsItem.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardCandidatePage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def get_mappings(filters: DashboardFilters, page: int, limit: int) -> DashboardMappingPage:
    cache_key = _cache_key("mappings", filters, page, limit)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardMappingPage.model_validate(cached)

    payload = await fetch_mappings(filters, page, limit)
    items = [MappingAnalyticsItem.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardMappingPage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def get_activities(filters: DashboardFilters, page: int, limit: int) -> DashboardActivityPage:
    cache_key = _cache_key("activities", filters, page, limit)
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardActivityPage.model_validate(cached)

    payload = await fetch_activities(filters, page, limit)
    items = [ActivityAnalyticsItem.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardActivityPage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


async def log_dashboard_activity(
    *,
    employee_id: str | None,
    activity_type: ActivityType,
    target_entity_type: TargetEntityType,
    target_entity_id: str,
    description: str,
) -> ActivityLog:
    return await create_activity_log(
        employee_id=employee_id,
        activity_type=activity_type,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        description=description,
    )


async def create_mapping(
    *,
    employee_id: str,
    candidate_id: str,
    job_opening_id: str,
    pipeline_stage: PipelineStage,
) -> CandidateMapping:
    return await create_candidate_mapping(
        employee_id=employee_id,
        candidate_id=candidate_id,
        job_opening_id=job_opening_id,
        pipeline_stage=pipeline_stage,
    )
