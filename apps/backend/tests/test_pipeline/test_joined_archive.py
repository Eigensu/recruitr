"""Joined cards leave the staff board 100 days after the move to Joined.

The clock is Mapping.joined_at, set and cleared by move_stage. The cut-off is
applied when the board is read, so it needs no job. Clients are never cut off:
their Joined column keeps every placement, and the archive is not theirs to ask
for. Rows that joined before joined_at existed get it from the backfill script.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient

from app.core.config import settings
from app.core.dependencies import get_viewer
from app.core.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import CandidateEventType, Decision, PipelineStage
from app.modules.recruitment.models import (
    Candidate,
    CandidateEvent,
    Client,
    Mapping,
    Position,
    StageEvent,
)
from app.modules.recruitment.repository import move_stage
from app.modules.recruitment.schemas import TenantScope
from scripts.backfill_joined_at import apply, joined_at_for, plan

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
_CLIENT_ID = PydanticObjectId()
_STAFF = TenantScope(brand_id=_BRAND, employee_id=_EMP, role=UserRole.maintainer)
_CLIENT = TenantScope(brand_id=_BRAND, employee_id=None, role=UserRole.client, client_id=_CLIENT_ID)
_URL = "/api/v1/pipeline/board"


def _days_ago(days: int) -> datetime:
    # Whole seconds: Mongo keeps milliseconds, and these are compared after a round trip.
    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0)


@pytest_asyncio.fixture
async def position(init_test_db) -> Position:
    await Client(id=_CLIENT_ID, brand_id=_BRAND, code="C1", name="Hunger Inc").insert()
    doc = Position(
        brand_id=_BRAND,
        code="P1",
        client_id=_CLIENT_ID,
        client_name="Hunger Inc",
        role="Captain",
        total_seats=5,
        remaining_seats=5,
    )
    await doc.insert()
    return doc


async def _mapping(position: Position, name: str, stage: PipelineStage, **fields) -> Mapping:
    candidate = Candidate(brand_id=_BRAND, full_name=name, phone=f"9{abs(hash(name)) % 10**9:09d}")
    await candidate.insert()
    doc = Mapping(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        position_id=position.id,
        client_id=_CLIENT_ID,
        employee_id=_EMP,
        stage=stage,
        **fields,
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def board(position):
    """Joined 101 days ago, joined 99 days ago, joined before joined_at existed, and sourced."""
    return {
        "old": await _mapping(
            position, "Old Joiner", PipelineStage.joined, joined_at=_days_ago(101)
        ),
        "recent": await _mapping(
            position, "Recent Joiner", PipelineStage.joined, joined_at=_days_ago(99)
        ),
        "legacy": await _mapping(position, "Legacy Joiner", PipelineStage.joined),
        "sourced": await _mapping(position, "Just Sourced", PipelineStage.sourced),
    }


async def _get(scope: TenantScope, **params):
    app.dependency_overrides[get_viewer] = lambda: scope
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            return await http.get(_URL, params=params)
    finally:
        app.dependency_overrides.pop(get_viewer, None)


def _names(res, stage: str = "joined") -> set[str]:
    assert res.status_code == 200, res.text
    [column] = [c for c in res.json()["stages"] if c["stage"] == stage]
    return {m["candidate_name"] for m in column["mappings"]}


# ── The board ──────────────────────────────────────────────────────────────────


async def test_staff_board_drops_cards_joined_over_100_days_ago(board):
    res = await _get(_STAFF)
    assert _names(res) == {"Recent Joiner", "Legacy Joiner"}
    assert _names(res, "sourced") == {"Just Sourced"}
    [joined] = [c for c in res.json()["stages"] if c["stage"] == "joined"]
    assert joined["count"] == 2


async def test_the_archive_holds_only_the_archived_cards(board):
    res = await _get(_STAFF, archived="true")
    assert _names(res) == {"Old Joiner"}
    assert all(not c["mappings"] for c in res.json()["stages"] if c["stage"] != "joined")


async def test_a_client_keeps_every_joined_card_and_has_no_archive(board):
    assert _names(await _get(_CLIENT)) == {"Old Joiner", "Recent Joiner", "Legacy Joiner"}
    res = await _get(_CLIENT, archived="true")
    assert res.status_code == 403


# ── The clock ──────────────────────────────────────────────────────────────────


async def _stored_joined_at(mapping: Mapping) -> datetime | None:
    return (await Mapping.get(mapping.id)).joined_at


async def test_moving_in_and_out_of_joined_starts_and_clears_the_clock(position):
    mapping = await _mapping(position, "Mover", PipelineStage.selected)
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)

    await move_stage(
        mapping=mapping, new_stage=PipelineStage.joined, decision=Decision.selected, scope=_STAFF
    )
    joined_at = await _stored_joined_at(mapping)
    assert joined_at is not None and joined_at >= before

    await move_stage(
        mapping=mapping, new_stage=PipelineStage.rejected, decision=Decision.rejected, scope=_STAFF
    )
    assert await _stored_joined_at(mapping) is None


async def test_coming_back_to_joined_restarts_the_100_days(board):
    old = board["old"]
    for stage, decision in (
        (PipelineStage.rejected, Decision.rejected),
        (PipelineStage.joined, Decision.selected),
    ):
        await move_stage(mapping=old, new_stage=stage, decision=decision, scope=_STAFF)

    assert (await _stored_joined_at(old)) > _days_ago(1).replace(tzinfo=None)
    assert "Old Joiner" in _names(await _get(_STAFF))
    assert _names(await _get(_STAFF, archived="true")) == set()


# ── Backfill ───────────────────────────────────────────────────────────────────


@pytest.mark.no_db
def test_backfill_prefers_history_then_the_event_log_then_updated_at():
    older, newer, logged, touched = (_days_ago(d) for d in (200, 150, 120, 110))
    history = [
        {"stage": "joined", "at": older},
        {"stage": "rejected", "at": older + timedelta(days=1)},
        {"stage": "joined", "at": newer},
    ]
    assert joined_at_for({"history": history, "updated_at": touched}, logged) == (newer, "history")
    assert joined_at_for({"history": [], "updated_at": touched}, logged) == (
        logged,
        "candidate_events",
    )
    assert joined_at_for({"updated_at": touched}, None) == (touched, "updated_at")
    assert joined_at_for({}, None) == (None, "none")


async def test_backfill_fills_only_joined_rows_without_a_date_and_is_idempotent(position):
    in_history, in_log, set_already = _days_ago(130), _days_ago(140), _days_ago(5)
    from_history = await _mapping(
        position,
        "From History",
        PipelineStage.joined,
        history=[StageEvent(stage=PipelineStage.joined, at=in_history)],
    )
    from_log = await _mapping(position, "From Log", PipelineStage.joined)
    await CandidateEvent(
        brand_id=_BRAND,
        candidate_id=from_log.candidate_id,
        position_id=position.id,
        event_type=CandidateEventType.stage_moved,
        to_stage=PipelineStage.joined,
        at=in_log,
    ).insert()
    already = await _mapping(position, "Already Set", PipelineStage.joined, joined_at=set_already)
    sourced = await _mapping(position, "Not Joined", PipelineStage.sourced)

    client = MongoClient(settings.MONGODB_URI)
    try:
        db = client[f"{settings.MONGODB_DB_NAME}_test"]
        planned, unexplained = plan(db)
        assert {oid for oid, _, _ in planned} == {from_history.id, from_log.id}
        assert unexplained == []
        assert apply(db.candidate_mappings, planned) == 2
        assert plan(db) == ([], [])  # a second run finds nothing
    finally:
        client.close()

    # Read back naive: Mongo stores UTC without the zone.
    assert await _stored_joined_at(from_history) == in_history.replace(tzinfo=None)
    assert await _stored_joined_at(from_log) == in_log.replace(tzinfo=None)
    assert await _stored_joined_at(already) == set_already.replace(tzinfo=None)
    assert await _stored_joined_at(sourced) is None
