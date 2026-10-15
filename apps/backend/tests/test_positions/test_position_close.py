"""Recruiters edit, delete and close positions; closing records why."""

from types import SimpleNamespace

import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user_doc, get_tenant, get_viewer
from app.core.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import Department, PositionStatus
from app.modules.recruitment.models import Client, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_ME = PydanticObjectId()
_SCOPE = TenantScope(brand_id=_BRAND, employee_id=_ME, role=UserRole.employee)
_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.employee, email="r@x.com")
_URL = "/api/v1/positions"


@pytest_asyncio.fixture
async def position(init_test_db) -> Position:
    client = Client(brand_id=_BRAND, code="CLI-001", name="Hunger Inc")
    await client.insert()
    doc = Position(
        brand_id=_BRAND,
        code="CLI-001-POS-001",
        client_id=client.id,
        client_name=client.name,
        role="Bartender",
        department=Department.service,
        total_seats=2,
        remaining_seats=2,
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def api(position):
    """A plain recruiter: the role that used to be refused delete and reopen."""
    app.dependency_overrides[get_viewer] = lambda: _SCOPE
    app.dependency_overrides[get_tenant] = lambda: _SCOPE
    app.dependency_overrides[get_current_user_doc] = lambda: _USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_a_recruiter_can_edit_a_position(api, position):
    res = await api.patch(f"{_URL}/{position.id}", json={"notes": "Nights"})

    assert res.status_code == 200, res.text
    assert (await Position.get(position.id)).notes == "Nights"


async def test_a_recruiter_can_delete_a_position(api, position):
    res = await api.delete(f"{_URL}/{position.id}")

    assert res.status_code == 204, res.text
    assert (await Position.get(position.id)).is_active is False


async def test_closing_records_the_reason_who_and_when(api, position):
    res = await api.post(
        f"{_URL}/{position.id}/close", json={"reason": "  Client hired internally "}
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "closed"
    assert body["close_reason"] == "Client hired internally"
    assert body["closed_at"] is not None
    stored = await Position.get(position.id)
    assert stored.status == PositionStatus.closed
    assert stored.closed_by_id == _ME


async def test_closing_needs_a_reason(api, position):
    for body in ({}, {"reason": ""}, {"reason": "   "}):
        res = await api.post(f"{_URL}/{position.id}/close", json=body)
        assert res.status_code == 422, (body, res.text)

    assert (await Position.get(position.id)).status == PositionStatus.open


async def test_closing_an_already_closed_position_is_refused(api, position):
    await api.post(f"{_URL}/{position.id}/close", json={"reason": "No longer needed"})

    res = await api.post(f"{_URL}/{position.id}/close", json={"reason": "Again"})

    assert res.status_code == 409, res.text
    assert (await Position.get(position.id)).close_reason == "No longer needed"


async def test_patch_cannot_close_without_a_reason(api, position):
    res = await api.patch(f"{_URL}/{position.id}", json={"status": "closed"})

    assert res.status_code == 422, res.text
    assert (await Position.get(position.id)).status == PositionStatus.open


async def test_reopen_stays_maintainer_only(api, position):
    await api.post(f"{_URL}/{position.id}/close", json={"reason": "Paused by client"})

    res = await api.post(f"{_URL}/{position.id}/reopen")

    assert res.status_code == 403, res.text


async def test_reopening_clears_the_closure(api, position):
    await api.post(f"{_URL}/{position.id}/close", json={"reason": "Paused by client"})
    app.dependency_overrides[get_current_user_doc] = lambda: SimpleNamespace(
        id=PydanticObjectId(), role=UserRole.maintainer, email="m@x.com"
    )

    res = await api.post(f"{_URL}/{position.id}/reopen")

    assert res.status_code == 200, res.text
    stored = await Position.get(position.id)
    assert stored.status == PositionStatus.open
    assert (stored.close_reason, stored.closed_at, stored.closed_by_id) == (None, None, None)


async def test_any_patch_status_change_clears_the_closure(api, position):
    await api.post(f"{_URL}/{position.id}/close", json={"reason": "Paused by client"})

    res = await api.patch(f"{_URL}/{position.id}", json={"status": "on_hold"})

    assert res.status_code == 200, res.text
    stored = await Position.get(position.id)
    assert stored.status == PositionStatus.on_hold
    assert (stored.close_reason, stored.closed_at, stored.closed_by_id) == (None, None, None)


async def test_a_padded_reason_that_fits_once_trimmed_is_accepted(api, position):
    res = await api.post(f"{_URL}/{position.id}/close", json={"reason": f"  {'x' * 1000}  "})

    assert res.status_code == 200, res.text
