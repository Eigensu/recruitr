"""Seat accounting on a position as candidates come and go.

filled_seats/remaining_seats are derived state — recomputed by counting the
mappings currently sitting in a terminal-positive stage, never incremented by
hand. Every path that can move a candidate into or out of one of those stages
therefore has to trigger the recount, or the position quietly diverges from
reality and stays that way.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_tenant, require_maintainer
from app.main import app
from app.modules.recruitment.models import Client, Position
from app.modules.recruitment.schemas import TenantScope
from tests.test_recruitment.payloads import candidate_payload

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
TENANT = TenantScope(brand_id=_BRAND, employee_id=_EMP)


@pytest_asyncio.fixture
async def client_a():
    """Authenticated as a maintainer — reopening a position is gated on it."""
    app.dependency_overrides[get_tenant] = lambda: TENANT
    app.dependency_overrides[require_maintainer] = lambda: object()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(require_maintainer, None)


@pytest_asyncio.fixture
async def position() -> Position:
    client = Client(brand_id=_BRAND, code="CLI-001", name="Hunger Inc")
    await client.insert()
    pos = Position(
        brand_id=_BRAND,
        code="CLI-001-POS-001",
        client_id=client.id,
        client_name="Hunger Inc",
        role="Sous Chef",
        total_seats=1,
        remaining_seats=1,
    )
    await pos.insert()
    return pos


async def _candidate(client: AsyncClient, email: str) -> str:
    res = await client.post(
        "/api/v1/candidates",
        json=candidate_payload(
            full_name="Anita Rao",
            email=email,
            phone="+91 98765 00003",
            experience_years=4,
            skills=[],
        ),
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _map_and_join(client: AsyncClient, position: Position, candidate_id: str) -> str:
    mapped = await client.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": candidate_id}
    )
    assert mapped.status_code in (200, 201), mapped.text
    mapping_id = mapped.json()["mapping_id"]
    moved = await client.post(
        f"/api/v1/pipeline/mappings/{mapping_id}/move", json={"new_stage": "position_close"}
    )
    assert moved.status_code == 200, moved.text
    return mapping_id


@pytest.mark.asyncio
async def test_joining_fills_the_seat_and_closes_the_position(
    client_a: AsyncClient, position: Position
) -> None:
    await _map_and_join(client_a, position, await _candidate(client_a, "anita@test.com"))

    after = await Position.get(position.id)
    assert after.filled_seats == 1
    assert after.remaining_seats == 0
    assert after.status == "closed"


@pytest.mark.asyncio
async def test_unmapping_a_hire_gives_the_seat_back(
    client_a: AsyncClient, position: Position
) -> None:
    cid = await _candidate(client_a, "anita@test.com")
    await _map_and_join(client_a, position, cid)

    unmapped = await client_a.post(
        f"/api/v1/positions/{position.id}/unmap-candidate?candidate_id={cid}"
    )
    assert unmapped.status_code == 200, unmapped.text

    after = await Position.get(position.id)
    assert after.filled_seats == 0
    assert after.remaining_seats == 1


@pytest.mark.asyncio
async def test_a_reopened_position_does_not_slam_shut_again(
    client_a: AsyncClient, position: Position
) -> None:
    """The stuck state this guards: reopen used to be undone by the next recount.

    Status is left alone by the recount on purpose — a maintainer may have
    closed a position deliberately (the client cancelled the requirement), and
    freeing a seat must not silently reopen it. What must hold is that once
    they *do* reopen it, the stale seat count cannot immediately re-close it.
    """
    cid = await _candidate(client_a, "anita@test.com")
    await _map_and_join(client_a, position, cid)
    await client_a.post(f"/api/v1/positions/{position.id}/unmap-candidate?candidate_id={cid}")

    reopened = await client_a.post(f"/api/v1/positions/{position.id}/reopen")
    assert reopened.status_code == 200, reopened.text

    # Any later recount — here, mapping somebody new — must leave it open.
    other = await _candidate(client_a, "vikram@test.com")
    await client_a.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": other}
    )

    after = await Position.get(position.id)
    assert after.status == "open"
    assert after.remaining_seats == 1


@pytest.mark.asyncio
async def test_unmapping_a_candidate_who_never_landed_leaves_seats_alone(
    client_a: AsyncClient, position: Position
) -> None:
    cid = await _candidate(client_a, "anita@test.com")
    await client_a.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": cid}
    )

    await client_a.post(f"/api/v1/positions/{position.id}/unmap-candidate?candidate_id={cid}")

    after = await Position.get(position.id)
    assert after.filled_seats == 0
    assert after.remaining_seats == 1
    assert after.status == "open"
