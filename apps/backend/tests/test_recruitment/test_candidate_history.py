"""The candidate profile's permanent history.

What this is guarding: the Kanban board is working state, and the activity feed
expires after 90 days. Neither can answer "which companies has this person been
put in front of, and what came of it" a year later. candidate_events can, and
has to keep doing so after the mapping behind an event is gone.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_tenant
from app.main import app
from app.modules.recruitment.models import Client, Employee, Mapping, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
TENANT = TenantScope(brand_id=_BRAND, employee_id=_EMP)

PAYLOAD = {
    "full_name": "Anita Rao",
    "email": "anita@test.com",
    "experience_years": 4,
    "skills": ["Mixology"],
}


@pytest_asyncio.fixture
async def client_a():
    app.dependency_overrides[get_tenant] = lambda: TENANT
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)


@pytest_asyncio.fixture
async def position() -> Position:
    await Employee(id=_EMP, brand_id=_BRAND, name="Priya Nair", email="priya@agency.test").insert()
    client = Client(brand_id=_BRAND, code="CLI-001", name="Hunger Inc")
    await client.insert()
    pos = Position(
        brand_id=_BRAND,
        code="CLI-001-POS-001",
        client_id=client.id,
        client_name="Hunger Inc",
        role="Sous Chef",
        total_seats=1,
    )
    await pos.insert()
    return pos


async def _add_candidate(client: AsyncClient) -> str:
    res = await client.post("/api/v1/candidates", json=PAYLOAD)
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.mark.asyncio
async def test_history_opens_with_the_candidate_being_added(client_a: AsyncClient) -> None:
    cid = await _add_candidate(client_a)

    body = (await client_a.get(f"/api/v1/candidates/{cid}/history")).json()
    assert [e["event_type"] for e in body["events"]] == ["created"]
    assert body["events"][0]["employee_id"] == str(_EMP)
    assert body["placements"] == []


@pytest.mark.asyncio
async def test_mapping_and_stage_moves_are_recorded(
    client_a: AsyncClient, position: Position
) -> None:
    cid = await _add_candidate(client_a)

    mapped = await client_a.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": cid}
    )
    assert mapped.status_code in (200, 201), mapped.text
    mapping_id = mapped.json()["mapping_id"]

    for stage in ("interview", "offer", "position_close"):
        moved = await client_a.post(
            f"/api/v1/pipeline/mappings/{mapping_id}/move", json={"new_stage": stage}
        )
        assert moved.status_code == 200, moved.text

    body = (await client_a.get(f"/api/v1/candidates/{cid}/history")).json()
    kinds = [e["event_type"] for e in body["events"]]
    assert kinds == ["created", "mapped", "stage_moved", "stage_moved", "stage_moved"]

    # Oldest first, and each move says where it came from.
    moves = [e for e in body["events"] if e["event_type"] == "stage_moved"]
    assert [(m["from_stage"], m["to_stage"]) for m in moves] == [
        ("sourced", "interview"),
        ("interview", "offer"),
        ("offer", "position_close"),
    ]
    # The company is on the entry itself, not looked up at read time.
    assert all(m["client_name"] == "Hunger Inc" for m in moves)


@pytest.mark.asyncio
async def test_joining_a_company_becomes_a_placement(
    client_a: AsyncClient, position: Position
) -> None:
    cid = await _add_candidate(client_a)
    mapped = await client_a.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": cid}
    )
    await client_a.post(
        f"/api/v1/pipeline/mappings/{mapped.json()['mapping_id']}/move",
        json={"new_stage": "position_close"},
    )

    body = (await client_a.get(f"/api/v1/candidates/{cid}/history")).json()
    assert len(body["placements"]) == 1
    placement = body["placements"][0]
    assert placement["client_name"] == "Hunger Inc"
    assert placement["role"] == "Sous Chef"
    assert placement["stage"] == "position_close"
    assert placement["is_current"] is True


@pytest.mark.asyncio
async def test_a_placement_survives_being_unmapped(
    client_a: AsyncClient, position: Position
) -> None:
    """The whole point: the mapping row is deleted, the history is not."""
    cid = await _add_candidate(client_a)
    mapped = await client_a.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": cid}
    )
    await client_a.post(
        f"/api/v1/pipeline/mappings/{mapped.json()['mapping_id']}/move",
        json={"new_stage": "position_close"},
    )

    unmapped = await client_a.post(
        f"/api/v1/positions/{position.id}/unmap-candidate?candidate_id={cid}"
    )
    assert unmapped.status_code == 200, unmapped.text
    assert await Mapping.find({"candidate_id": PydanticObjectId(cid)}).count() == 0

    body = (await client_a.get(f"/api/v1/candidates/{cid}/history")).json()
    assert [p["client_name"] for p in body["placements"]] == ["Hunger Inc"]
    assert body["placements"][0]["is_current"] is False
    assert body["events"][-1]["event_type"] == "unmapped"


@pytest.mark.asyncio
async def test_a_placement_missing_both_timestamps_falls_back_to_created_at(
    client_a: AsyncClient, position: Position
) -> None:
    """A raw legacy document with neither mapped_at nor updated_at set.

    Beanie's default_factory means no mapping written through the app can be
    missing both, but _live_placements reads the motor collection directly —
    it does not get that guarantee for free. Before the fallback, `at` came
    back None and CandidatePlacement(at=None) failed validation, 500ing the
    whole history endpoint for this candidate.
    """
    cid = await _add_candidate(client_a)
    await Mapping.get_motor_collection().insert_one(
        {
            "brand_id": _BRAND,
            "candidate_id": PydanticObjectId(cid),
            "position_id": position.id,
            "client_id": position.client_id,
            "employee_id": _EMP,
            "stage": "position_close",
            "decision": "pending",
            "history": [],
            # mapped_at and updated_at deliberately omitted.
        }
    )

    res = await client_a.get(f"/api/v1/candidates/{cid}/history")
    assert res.status_code == 200, res.text
    placements = res.json()["placements"]
    assert len(placements) == 1
    assert placements[0]["at"] is not None


@pytest.mark.asyncio
async def test_a_rejection_is_history_but_not_a_placement(
    client_a: AsyncClient, position: Position
) -> None:
    cid = await _add_candidate(client_a)
    mapped = await client_a.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": cid}
    )
    await client_a.post(
        f"/api/v1/pipeline/mappings/{mapped.json()['mapping_id']}/move",
        json={"new_stage": "rejected"},
    )

    body = (await client_a.get(f"/api/v1/candidates/{cid}/history")).json()
    assert body["placements"] == []
    assert body["events"][-1]["to_stage"] == "rejected"
