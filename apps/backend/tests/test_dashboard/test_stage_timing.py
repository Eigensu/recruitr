"""Stage-timing analytics: how long candidates wait, and how fast they move.

The aggregation reads `Mapping.history`, which is uneven in real data — seeded
rows carry no events at all and migrated ones can carry events for stages the
mapping has since left — so the cases below pin the fallbacks as much as the
arithmetic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_viewer
from app.main import app
from app.modules.dashboard.repository import fetch_stage_timing
from app.modules.dashboard.schemas import DashboardFilters
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.models import Mapping, StageEvent
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
_OTHER_EMP = PydanticObjectId()
TENANT = TenantScope(brand_id=_BRAND, employee_id=_EMP)

FILTERS = DashboardFilters(brand_id=str(_BRAND))


def _ago(days: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


async def _mapping(
    *,
    stage: PipelineStage,
    history: list[tuple[PipelineStage, float]] | None = None,
    mapped_days_ago: float = 30.0,
    employee_id: PydanticObjectId = _EMP,
) -> Mapping:
    doc = Mapping(
        brand_id=_BRAND,
        candidate_id=PydanticObjectId(),
        position_id=PydanticObjectId(),
        employee_id=employee_id,
        stage=stage,
        mapped_at=_ago(mapped_days_ago),
        history=[StageEvent(stage=s, at=_ago(days)) for s, days in (history or [])],
    )
    await doc.insert()
    return doc


def _stage(payload: dict, stage: PipelineStage) -> dict:
    return next(item for item in payload["stages"] if item["stage"] == stage)


@pytest_asyncio.fixture
async def api():
    app.dependency_overrides[get_viewer] = lambda: TENANT
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_viewer, None)


@pytest.mark.asyncio
async def test_dwell_is_measured_from_the_current_stage_entry():
    await _mapping(
        stage=PipelineStage.interview,
        history=[(PipelineStage.sourced, 30), (PipelineStage.interview, 4)],
    )

    payload = await fetch_stage_timing(FILTERS)

    interview = _stage(payload, PipelineStage.interview)
    assert interview["count"] == 1
    assert interview["avg_days"] == pytest.approx(4, abs=0.1)
    # The stage it passed through is empty now, not credited with the 26 days.
    assert _stage(payload, PipelineStage.sourced) == {
        "stage": PipelineStage.sourced,
        "label": "Sourced",
        "avg_days": 0.0,
        "count": 0,
    }


@pytest.mark.asyncio
async def test_dwell_falls_back_to_mapped_at_without_a_matching_event():
    # Seeded rows land in a stage with no history event for it.
    await _mapping(stage=PipelineStage.sent_to_client, history=[], mapped_days_ago=3)

    payload = await fetch_stage_timing(FILTERS)

    assert _stage(payload, PipelineStage.sent_to_client)["avg_days"] == pytest.approx(3, abs=0.1)


@pytest.mark.asyncio
async def test_re_entering_a_stage_counts_from_the_latest_entry():
    await _mapping(
        stage=PipelineStage.interview,
        history=[
            (PipelineStage.interview, 20),
            (PipelineStage.on_hold, 12),
            (PipelineStage.interview, 2),
        ],
    )

    payload = await fetch_stage_timing(FILTERS)

    assert _stage(payload, PipelineStage.interview)["avg_days"] == pytest.approx(2, abs=0.1)


@pytest.mark.asyncio
async def test_terminal_stages_are_left_out_of_the_wait_times():
    await _mapping(stage=PipelineStage.joined, history=[(PipelineStage.joined, 5)])
    await _mapping(stage=PipelineStage.rejected, history=[(PipelineStage.rejected, 5)])
    await _mapping(stage=PipelineStage.candidate_dropped, history=[])

    payload = await fetch_stage_timing(FILTERS)

    reported = {item["stage"] for item in payload["stages"]}
    assert reported.isdisjoint(
        {PipelineStage.joined, PipelineStage.rejected, PipelineStage.candidate_dropped}
    )
    assert payload["candidates_waiting"] == 0
    assert payload["avg_days_in_stage"] == 0.0


@pytest.mark.asyncio
async def test_overall_average_weights_stages_by_how_many_are_waiting():
    await _mapping(stage=PipelineStage.sourced, history=[(PipelineStage.sourced, 2)])
    await _mapping(stage=PipelineStage.sourced, history=[(PipelineStage.sourced, 4)])
    await _mapping(stage=PipelineStage.interview, history=[(PipelineStage.interview, 12)])

    payload = await fetch_stage_timing(FILTERS)

    assert payload["candidates_waiting"] == 3
    # (2 + 4 + 12) / 3, not the unweighted (3 + 12) / 2.
    assert payload["avg_days_in_stage"] == pytest.approx(6, abs=0.1)


@pytest.mark.asyncio
async def test_stalled_counts_only_the_long_waits():
    await _mapping(stage=PipelineStage.sourced, history=[(PipelineStage.sourced, 9)])
    await _mapping(stage=PipelineStage.interview, history=[(PipelineStage.interview, 1)])

    payload = await fetch_stage_timing(FILTERS)

    assert payload["stalled_count"] == 1
    assert payload["stalled_after_days"] == 7


@pytest.mark.asyncio
async def test_time_to_action_averages_the_gaps_between_moves():
    await _mapping(
        stage=PipelineStage.interview,
        history=[
            (PipelineStage.sourced, 10),
            (PipelineStage.sent_to_client, 8),
            (PipelineStage.interview, 4),
        ],
    )

    payload = await fetch_stage_timing(FILTERS)

    assert payload["action_moves"] == 2
    assert payload["avg_days_to_action"] == pytest.approx(3, abs=0.1)  # (2 + 4) / 2


@pytest.mark.asyncio
async def test_time_to_action_ignores_mappings_that_never_moved():
    await _mapping(stage=PipelineStage.sourced, history=[(PipelineStage.sourced, 5)])
    await _mapping(stage=PipelineStage.sourced, history=[])

    payload = await fetch_stage_timing(FILTERS)

    assert payload["action_moves"] == 0
    assert payload["avg_days_to_action"] == 0.0


@pytest.mark.asyncio
async def test_recruiter_filter_narrows_both_measures():
    await _mapping(stage=PipelineStage.interview, history=[(PipelineStage.interview, 10)])
    await _mapping(
        stage=PipelineStage.sourced,
        history=[(PipelineStage.sourced, 2)],
        employee_id=_OTHER_EMP,
    )

    payload = await fetch_stage_timing(
        DashboardFilters(brand_id=str(_BRAND), employee_id=str(_OTHER_EMP))
    )

    assert payload["candidates_waiting"] == 1
    assert _stage(payload, PipelineStage.sourced)["count"] == 1
    assert _stage(payload, PipelineStage.interview)["count"] == 0


@pytest.mark.asyncio
async def test_another_brands_pipeline_is_not_counted():
    doc = await _mapping(stage=PipelineStage.interview, history=[(PipelineStage.interview, 3)])
    doc.brand_id = PydanticObjectId()
    await doc.save()

    payload = await fetch_stage_timing(FILTERS)

    assert payload["candidates_waiting"] == 0


@pytest.mark.asyncio
async def test_endpoint_returns_the_stage_timing_payload(api: AsyncClient):
    await _mapping(stage=PipelineStage.interview, history=[(PipelineStage.interview, 6)])

    response = await api.get("/api/v1/dashboard/stage-timing")

    assert response.status_code == 200
    body = response.json()
    assert body["candidates_waiting"] == 1
    assert next(s for s in body["stages"] if s["stage"] == "interview")[
        "avg_days"
    ] == pytest.approx(6, abs=0.1)
