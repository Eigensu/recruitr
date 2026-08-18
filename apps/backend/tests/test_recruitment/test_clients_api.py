"""HTTP-level tests for the /api/v1/clients endpoints.

The auth chain is bypassed by overriding get_tenant with a fixed TenantScope.
Admin-gated writes go through the real require_admin guard, with only the user
lookup it depends on stubbed — so the role check itself is under test.
Each test runs in a fresh MongoDB database (see conftest.py autouse fixture).
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
from app.modules.recruitment.models import Client, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND_A = PydanticObjectId()
_BRAND_B = PydanticObjectId()
_EMP_A = PydanticObjectId()

TENANT_A = TenantScope(brand_id=_BRAND_A, employee_id=_EMP_A)


_ADMIN = SimpleNamespace(id=PydanticObjectId(), role=UserRole.admin, email="admin@test.com")
_MAINTAINER = SimpleNamespace(
    id=PydanticObjectId(), role=UserRole.maintainer, email="boss@test.com"
)


@pytest_asyncio.fixture
async def admin_a():
    """Brand A client whose user is an admin — passes require_admin."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    app.dependency_overrides[get_current_user_doc] = lambda: _ADMIN
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def maintainer_a():
    """Brand A client whose user is only a maintainer — require_admin must reject."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    app.dependency_overrides[get_current_user_doc] = lambda: _MAINTAINER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────
#
# Brand B never gets its own HTTP client: dependency_overrides is global, so two
# tenant-scoped clients in one test would collide. Cross-brand rows are seeded
# straight through the models instead.


async def _create(client: AsyncClient, name: str, city: str | None = None) -> dict:
    payload: dict = {"name": name}
    if city is not None:
        payload["city"] = city
    res = await client.post("/api/v1/clients", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


async def _seed_client(brand_id: PydanticObjectId, name: str) -> Client:
    doc = Client(brand_id=brand_id, code=f"CLI-{name[:3].upper()}", name=name)
    await doc.insert()
    return doc


async def _seed_position(brand_id: PydanticObjectId, client_id: str, client_name: str) -> Position:
    pos = Position(
        brand_id=brand_id,
        code=f"POS-{client_name}",
        client_id=PydanticObjectId(client_id),
        client_name=client_name,
        role="Sous Chef",
        total_seats=1,
        remaining_seats=1,
    )
    await pos.insert()
    return pos


# ── List / create ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_empty(admin_a: AsyncClient) -> None:
    res = await admin_a.get("/api/v1/clients")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_create_then_appears_in_list(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc", "Mumbai")
    assert created["name"] == "Hunger Inc"
    assert created["city"] == "Mumbai"
    assert created["code"].startswith("CLI-")
    assert created["is_active"] is True
    assert created["position_count"] == 0

    res = await admin_a.get("/api/v1/clients")
    assert [c["id"] for c in res.json()] == [created["id"]]


@pytest.mark.asyncio
async def test_create_trims_name_and_blank_city(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "  Bombay Canteen  ", "   ")
    assert created["name"] == "Bombay Canteen"
    assert created["city"] is None


@pytest.mark.asyncio
async def test_create_rejects_blank_name(admin_a: AsyncClient) -> None:
    res = await admin_a.post("/api/v1/clients", json={"name": "   "})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_name_is_conflict_case_insensitive(admin_a: AsyncClient) -> None:
    await _create(admin_a, "Hunger Inc")
    res = await admin_a.post("/api/v1/clients", json={"name": "hunger inc"})
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_revives_archived_client(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc")
    assert (await admin_a.delete(f"/api/v1/clients/{created['id']}")).status_code == 204

    res = await admin_a.post("/api/v1/clients", json={"name": "Hunger Inc", "city": "Pune"})
    assert res.status_code == 201, res.text
    revived = res.json()
    # Same row, same code — not a second client for the same name.
    assert revived["id"] == created["id"]
    assert revived["code"] == created["code"]
    assert revived["is_active"] is True
    assert revived["city"] == "Pune"


@pytest.mark.asyncio
async def test_list_hides_archived_unless_requested(admin_a: AsyncClient) -> None:
    keep = await _create(admin_a, "Keep Co")
    drop = await _create(admin_a, "Drop Co")
    assert (await admin_a.delete(f"/api/v1/clients/{drop['id']}")).status_code == 204

    active = await admin_a.get("/api/v1/clients")
    assert [c["id"] for c in active.json()] == [keep["id"]]

    everything = await admin_a.get("/api/v1/clients?include_archived=true")
    assert {c["id"] for c in everything.json()} == {keep["id"], drop["id"]}


@pytest.mark.asyncio
async def test_list_is_alphabetical_with_position_counts(admin_a: AsyncClient) -> None:
    zeta = await _create(admin_a, "Zeta Foods")
    alpha = await _create(admin_a, "Alpha Foods")
    await _seed_position(_BRAND_A, alpha["id"], "Alpha Foods")
    await _seed_position(_BRAND_A, alpha["id"], "Alpha Foods 2")

    rows = (await admin_a.get("/api/v1/clients")).json()
    assert [c["id"] for c in rows] == [alpha["id"], zeta["id"]]
    assert rows[0]["position_count"] == 2
    assert rows[1]["position_count"] == 0


@pytest.mark.asyncio
async def test_brands_are_isolated(admin_a: AsyncClient) -> None:
    await _seed_client(_BRAND_B, "Brand B Client")
    mine = await _create(admin_a, "Brand A Client")
    assert [c["id"] for c in (await admin_a.get("/api/v1/clients")).json()] == [mine["id"]]


# ── Position dropdown integration ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_new_client_is_offered_by_position_filters(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc")
    filters = (await admin_a.get("/api/v1/positions/filters")).json()
    assert [c["id"] for c in filters["clients"]] == [created["id"]]


@pytest.mark.asyncio
async def test_archived_client_cannot_receive_new_positions(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc")
    assert (await admin_a.delete(f"/api/v1/clients/{created['id']}")).status_code == 204

    res = await admin_a.post(
        "/api/v1/positions", json={"client_id": created["id"], "role": "Sous Chef"}
    )
    assert res.status_code == 400


# ── Update ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_fans_out_to_position_client_name(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc")
    pos = await _seed_position(_BRAND_A, created["id"], "Hunger Inc")

    res = await admin_a.patch(f"/api/v1/clients/{created['id']}", json={"name": "Hunger Group"})
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Hunger Group"

    refreshed = await Position.get(pos.id)
    assert refreshed is not None
    # client_name is denormalized onto the position — it has to follow the rename.
    assert refreshed.client_name == "Hunger Group"


@pytest.mark.asyncio
async def test_rename_onto_existing_name_is_conflict(admin_a: AsyncClient) -> None:
    first = await _create(admin_a, "Hunger Inc")
    await _create(admin_a, "Bombay Canteen")

    res = await admin_a.patch(f"/api/v1/clients/{first['id']}", json={"name": "bombay canteen"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_city_only_keeps_name(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc", "Mumbai")
    res = await admin_a.patch(f"/api/v1/clients/{created['id']}", json={"city": "Pune"})
    assert res.status_code == 200
    res_json = res.json()
    res_json.pop("updated_at", None)
    res_json.pop("created_at", None)
    expected = {**created, "city": "Pune"}
    expected.pop("updated_at", None)
    expected.pop("created_at", None)
    assert res_json == expected


@pytest.mark.asyncio
async def test_restore_via_patch(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc")
    await admin_a.delete(f"/api/v1/clients/{created['id']}")

    res = await admin_a.patch(f"/api/v1/clients/{created['id']}", json={"is_active": True})
    assert res.status_code == 200
    assert res.json()["is_active"] is True
    assert [c["id"] for c in (await admin_a.get("/api/v1/clients")).json()] == [created["id"]]


@pytest.mark.asyncio
async def test_update_unknown_client_is_404(admin_a: AsyncClient) -> None:
    res = await admin_a.patch(f"/api/v1/clients/{PydanticObjectId()}", json={"name": "Nope"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_another_brands_client(admin_a: AsyncClient) -> None:
    foreign = await _seed_client(_BRAND_B, "Brand B Client")
    res = await admin_a.patch(f"/api/v1/clients/{foreign.id}", json={"name": "Hijacked"})
    assert res.status_code == 404


# ── Archive ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_archive_blocked_while_positions_are_active(admin_a: AsyncClient) -> None:
    created = await _create(admin_a, "Hunger Inc")
    pos = await _seed_position(_BRAND_A, created["id"], "Hunger Inc")

    res = await admin_a.delete(f"/api/v1/clients/{created['id']}")
    assert res.status_code == 409
    assert "1 active position" in res.json()["detail"]

    # Soft-deleting the position clears the way.
    await pos.set({"is_active": False})
    assert (await admin_a.delete(f"/api/v1/clients/{created['id']}")).status_code == 204

    doc = await Client.get(PydanticObjectId(created["id"]))
    assert doc is not None
    assert doc.is_active is False


# ── Role gate ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_admin_can_create_but_not_edit(maintainer_a: AsyncClient) -> None:
    # Creating is deliberately open: picking a client is part of creating a position.
    created = await _create(maintainer_a, "Hunger Inc")

    assert (
        await maintainer_a.patch(f"/api/v1/clients/{created['id']}", json={"name": "Nope"})
    ).status_code == 403
    assert (await maintainer_a.delete(f"/api/v1/clients/{created['id']}")).status_code == 403
