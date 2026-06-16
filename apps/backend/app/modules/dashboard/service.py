"""Business logic for dashboard analytics and supporting writes."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from app.common.dtos.pagination import PaginationMeta
from app.common.extras.redis_cache import dashboard_cache
from app.config import settings
from app.modules.dashboard.repository import (
    fetch_activities,
    fetch_candidates,
    fetch_client_profiles,
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
    ClientProfileRow,
    DashboardActivityPage,
    DashboardCandidatePage,
    DashboardClientPage,
    DashboardClientProfilePage,
    DashboardEmployeePage,
    DashboardFilters,
    DashboardMappingPage,
    DashboardOverviewResponse,
    DashboardPipelineResponse,
    EmployeeAnalyticsItem,
    MappingAnalyticsItem,
    PipelineStageMetric,
)


def _cache_key(
    prefix: str,
    filters: DashboardFilters,
    page: int | None = None,
    limit: int | None = None,
) -> str:
    payload = filters.model_dump(mode="json", exclude_none=True)
    raw = json.dumps(
        {"filters": payload, "page": page, "limit": limit}, sort_keys=True, default=str
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    # brand_id is already inside `payload` (via filters.brand_id), so the digest
    # is implicitly brand-scoped. The namespace prefix makes pattern-delete easy.
    brand_prefix = filters.brand_id or "unknown"
    return dashboard_cache.build_key(brand_prefix, prefix, digest)


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
        pipeline=[
            PipelineStageMetric.model_validate(stage) for stage in pipeline_payload["stages"]
        ],
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


async def get_candidates(
    filters: DashboardFilters, page: int, limit: int
) -> DashboardCandidatePage:
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


async def get_client_profiles(brand_id: str, page: int, limit: int) -> DashboardClientProfilePage:
    cache_key = dashboard_cache.build_key(brand_id, "client_profiles", f"p{page}_l{limit}")
    cached = await dashboard_cache.get_json(cache_key)
    if cached is not None:
        return DashboardClientProfilePage.model_validate(cached)

    payload = await fetch_client_profiles(brand_id, page, limit)
    items = [ClientProfileRow.model_validate(item) for item in payload["items"]]
    response = _make_paginated_response(payload, items, DashboardClientProfilePage)
    await dashboard_cache.set_json(
        cache_key, response.model_dump(mode="json"), settings.REDIS_CACHE_TTL_SECONDS
    )
    return response


# Activity logging and mapping writes are now owned by app.modules.recruitment.service.
# Those helpers have been removed from this module to keep dashboard read-only.
