"""Contract cover for the pipeline endpoints the frontend calls but nothing tested.

Before this, interview-date, dropped, match, board and filtered had no test at
all while every one of them is called from the UI. That is the same gap the
offer-letter 422 lived in: an endpoint the frontend depends on, with nothing
asserting the shape it actually receives.

Each request body here is the one the frontend really sends — see
apps/frontend/src/lib/api/pipeline.ts — so a schema change that breaks the UI
breaks a test rather than a user.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_doc, get_tenant, get_viewer
from app.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.models import Candidate, Client, Mapping, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_OTHER_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
_CLIENT_1 = PydanticObjectId()
_CLIENT_2 = PydanticObjectId()

_STAFF = TenantScope(brand_id=_BRAND, employee_id=_EMP, role=UserRole.employee)
_CLIENT_SCOPE_1 = TenantScope(
    brand_id=_BRAND, employee_id=None, role=UserRole.client, client_id=_CLIENT_1
)

_EMP_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.employee, email="emp@test.com")
_CLIENT_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.client, email="cli@test.com")


def _staff_overrides():
    app.dependency_overrides[get_tenant] = lambda: _STAFF
    app.dependency_overrides[get_viewer] = lambda: _STAFF
    app.dependency_overrides[get_current_user_doc] = lambda: _EMP_USER


@pytest_asyncio.fixture
async def staff():
    _staff_overrides()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_1():
    from fastapi import HTTPException

    def denied():
        raise HTTPException(403, "This area is not available to client accounts.")

    app.dependency_overrides[get_tenant] = denied
    app.dependency_overrides[get_viewer] = lambda: _CLIENT_SCOPE_1
    app.dependency_overrides[get_current_user_doc] = lambda: _CLIENT_USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def seeded(init_test_db):
    """One mapping per client, plus one in a different brand entirely."""
    for cid, name, code in ((_CLIENT_1, "Client 1", "C1"), (_CLIENT_2, "Client 2", "C2")):
        await Client(id=cid, brand_id=_BRAND, code=code, name=name).insert()

    made: dict = {}
    for key, cid in (("mine", _CLIENT_1), ("theirs", _CLIENT_2)):
        cand = await Candidate(
            brand_id=_BRAND, email=f"{key}@test.com", full_name=f"Cand {key}", source="internal"
        ).insert()
        pos = await Position(
            brand_id=_BRAND,
            code=f"P-{key}",
            client_id=cid,
            client_name=f"Client {key}",
            role="Sous Chef",
            total_seats=1,
            remaining_seats=1,
        ).insert()
        made[key] = await Mapping(
            brand_id=_BRAND,
            candidate_id=cand.id,
            position_id=pos.id,
            employee_id=_EMP,
            stage=PipelineStage.sent_to_client,
        ).insert()

    foreign_cand = await Candidate(
        brand_id=_OTHER_BRAND, email="f@test.com", full_name="Foreign", source="internal"
    ).insert()
    foreign_pos = await Position(
        brand_id=_OTHER_BRAND,
        code="P-F",
        client_id=PydanticObjectId(),
        client_name="Foreign Co",
        role="Sous Chef",
        total_seats=1,
        remaining_seats=1,
    ).insert()
    made["foreign"] = await Mapping(
        brand_id=_OTHER_BRAND,
        candidate_id=foreign_cand.id,
        position_id=foreign_pos.id,
        employee_id=PydanticObjectId(),
        stage=PipelineStage.sent_to_client,
    ).insert()

    return made


# ── PUT /mappings/{id}/interview-date ──────────────────────────────────────────

_INTERVIEW_DATE = "2026-09-01T10:30:00Z"


@pytest.mark.asyncio
async def test_interview_date_is_persisted(staff: AsyncClient, seeded) -> None:
    mapping = seeded["mine"]

    res = await staff.put(
        f"/api/v1/pipeline/mappings/{mapping.id}/interview-date",
        json={"interview_date": _INTERVIEW_DATE},
    )
    assert res.status_code == 200, res.text

    refreshed = await Mapping.get(mapping.id)
    assert refreshed.interview_date is not None
    assert refreshed.interview_date.year == 2026
    assert refreshed.interview_date.month == 9


@pytest.mark.asyncio
async def test_interview_date_rejects_a_non_date(staff: AsyncClient, seeded) -> None:
    res = await staff.put(
        f"/api/v1/pipeline/mappings/{seeded['mine'].id}/interview-date",
        json={"interview_date": "next tuesday"},
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_interview_date_refused_on_another_brands_mapping(staff: AsyncClient, seeded) -> None:
    res = await staff.put(
        f"/api/v1/pipeline/mappings/{seeded['foreign'].id}/interview-date",
        json={"interview_date": _INTERVIEW_DATE},
    )
    assert res.status_code == 404, res.text
    assert (await Mapping.get(seeded["foreign"].id)).interview_date is None


@pytest.mark.asyncio
async def test_client_cannot_set_interview_date_on_another_clients_mapping(
    client_1: AsyncClient, seeded
) -> None:
    # Same brand, different employer. scope_mapping_match narrows by position,
    # and this is the only thing standing between the two clients.
    res = await client_1.put(
        f"/api/v1/pipeline/mappings/{seeded['theirs'].id}/interview-date",
        json={"interview_date": _INTERVIEW_DATE},
    )
    assert res.status_code == 404, res.text
    assert (await Mapping.get(seeded["theirs"].id)).interview_date is None


# ── PUT /mappings/{id}/dropped ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dropping_records_the_note_and_moves_the_stage(staff: AsyncClient, seeded) -> None:
    mapping = seeded["mine"]

    res = await staff.put(
        f"/api/v1/pipeline/mappings/{mapping.id}/dropped",
        json={"dropped_notes": "Took a competing offer closer to home."},
    )
    assert res.status_code == 200, res.text

    refreshed = await Mapping.get(mapping.id)
    assert refreshed.dropped_notes == "Took a competing offer closer to home."
    assert refreshed.stage == PipelineStage.candidate_dropped
    # The move must leave a trail, or the board cannot say when they dropped.
    assert any(e.stage == PipelineStage.candidate_dropped for e in refreshed.history)


@pytest.mark.asyncio
async def test_dropping_requires_a_note(staff: AsyncClient, seeded) -> None:
    # The note is the whole point of the endpoint — the stage move alone is
    # reachable through /move.
    res = await staff.put(
        f"/api/v1/pipeline/mappings/{seeded['mine'].id}/dropped",
        json={},
    )
    assert res.status_code == 422, res.text
    assert (await Mapping.get(seeded["mine"].id)).stage == PipelineStage.sent_to_client


@pytest.mark.asyncio
async def test_dropping_twice_does_not_stack_history(staff: AsyncClient, seeded) -> None:
    url = f"/api/v1/pipeline/mappings/{seeded['mine'].id}/dropped"
    assert (await staff.put(url, json={"dropped_notes": "first"})).status_code == 200
    assert (await staff.put(url, json={"dropped_notes": "second"})).status_code == 200

    refreshed = await Mapping.get(seeded["mine"].id)
    assert refreshed.dropped_notes == "second"
    drops = [e for e in refreshed.history if e.stage == PipelineStage.candidate_dropped]
    assert len(drops) == 1, "already-dropped mapping should not re-enter the stage"


@pytest.mark.asyncio
async def test_dropping_refused_on_another_brands_mapping(staff: AsyncClient, seeded) -> None:
    res = await staff.put(
        f"/api/v1/pipeline/mappings/{seeded['foreign'].id}/dropped",
        json={"dropped_notes": "not mine to drop"},
    )
    assert res.status_code == 404, res.text
    assert (await Mapping.get(seeded["foreign"].id)).stage == PipelineStage.sent_to_client


# ── PATCH /pipeline/match ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_match_assigns_a_candidate_to_a_position(staff: AsyncClient, seeded) -> None:
    mapping = seeded["mine"]
    cand = await Candidate(
        brand_id=_BRAND, email="fresh@test.com", full_name="Fresh", source="internal"
    ).insert()

    res = await staff.patch(
        "/api/v1/pipeline/match",
        json={
            "position_id": str(mapping.position_id),
            "candidate_id": str(cand.id),
            "target_status": "pending",
        },
    )
    assert res.status_code == 200, res.text
    assert await Mapping.find_one({"candidate_id": cand.id, "position_id": mapping.position_id})


@pytest.mark.asyncio
async def test_match_rejects_a_status_outside_the_contract(staff: AsyncClient, seeded) -> None:
    # The board sends COLUMNS ids; anything else must not be silently accepted.
    res = await staff.patch(
        "/api/v1/pipeline/match",
        json={
            "position_id": str(seeded["mine"].position_id),
            "candidate_id": str(seeded["mine"].candidate_id),
            "target_status": "interview",
        },
    )
    assert res.status_code == 422, res.text


# ── GET /pipeline/board and /pipeline/filtered ─────────────────────────────────


@pytest.mark.asyncio
async def test_board_returns_stage_columns_for_staff(staff: AsyncClient, seeded) -> None:
    res = await staff.get("/api/v1/pipeline/board")
    assert res.status_code == 200, res.text

    stages = res.json()["stages"]
    ids = {m["mapping_id"] for col in stages for m in col["mappings"]}
    assert str(seeded["mine"].id) in ids
    assert str(seeded["theirs"].id) in ids
    # Another brand's mapping must never appear.
    assert str(seeded["foreign"].id) not in ids


@pytest.mark.asyncio
async def test_board_shows_a_client_only_their_own_pipeline(client_1: AsyncClient, seeded) -> None:
    res = await client_1.get("/api/v1/pipeline/board")
    assert res.status_code == 200, res.text

    ids = {m["mapping_id"] for col in res.json()["stages"] for m in col["mappings"]}
    assert str(seeded["mine"].id) in ids
    assert str(seeded["theirs"].id) not in ids


@pytest.mark.asyncio
async def test_filtered_requires_a_position_and_scopes_to_it(staff: AsyncClient, seeded) -> None:
    # position_id is a required query param; omitting it is a 422, not an
    # unfiltered dump of the brand's pipeline.
    assert (await staff.get("/api/v1/pipeline/filtered")).status_code == 422

    res = await staff.get(f"/api/v1/pipeline/filtered?position_id={seeded['mine'].position_id}")
    assert res.status_code == 200, res.text
