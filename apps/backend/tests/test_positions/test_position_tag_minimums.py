"""A position's minimum communication and brand experience.

Both are optional, on the candidate scales (Basic/Good/Excellent and
Low/Mid/Premium), and absent means "no minimum". Unlike the other editable
fields on PATCH, an explicit null has to clear them — "no minimum" is a real
choice, not a missing value.
"""

import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_tenant, get_viewer
from app.core.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.models import Client, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_SCOPE = TenantScope(brand_id=_BRAND, employee_id=PydanticObjectId(), role=UserRole.maintainer)
_URL = "/api/v1/positions"


@pytest_asyncio.fixture
async def client_doc(init_test_db) -> Client:
    doc = Client(brand_id=_BRAND, code="CLI-001", name="Hunger Inc")
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def api(client_doc):
    app.dependency_overrides[get_viewer] = lambda: _SCOPE
    app.dependency_overrides[get_tenant] = lambda: _SCOPE
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _new(client_id, **extra) -> dict:
    return {
        "client_id": str(client_id),
        "role": "Bartender",
        "department": "Service",
        "total_seats": 1,
        **extra,
    }


async def test_create_stores_and_returns_both_minimums(api, client_doc):
    res = await api.post(
        _URL, json=_new(client_doc.id, communication="Good", brand_experience="Premium")
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["communication"], body["brand_experience"]) == ("Good", "Premium")
    stored = await Position.get(body["id"])
    assert (stored.communication, stored.brand_experience) == ("Good", "Premium")


async def test_both_are_optional(api, client_doc):
    res = await api.post(_URL, json=_new(client_doc.id))

    assert res.status_code == 201, res.text
    assert res.json()["communication"] is None
    assert res.json()["brand_experience"] is None


async def test_a_value_off_the_candidate_scale_is_refused(api, client_doc):
    for bad in ({"communication": "Fluent"}, {"brand_experience": "Luxury"}):
        res = await api.post(_URL, json=_new(client_doc.id, **bad))
        assert res.status_code == 422, (bad, res.text)

    assert await Position.find_all().count() == 0


async def test_list_and_detail_return_them(api, client_doc):
    created = (
        await api.post(
            _URL, json=_new(client_doc.id, communication="Basic", brand_experience="Mid")
        )
    ).json()

    [row] = (await api.get(_URL)).json()["items"]
    detail = (await api.get(f"{_URL}/{created['id']}")).json()

    for item in (row, detail):
        assert (item["communication"], item["brand_experience"]) == ("Basic", "Mid")


async def test_update_sets_changes_and_clears(api, client_doc):
    pid = (await api.post(_URL, json=_new(client_doc.id))).json()["id"]

    res = await api.patch(f"{_URL}/{pid}", json={"communication": "Excellent"})
    assert res.status_code == 200, res.text
    assert res.json()["communication"] == "Excellent"

    res = await api.patch(f"{_URL}/{pid}", json={"brand_experience": "Low"})
    assert res.json()["brand_experience"] == "Low"
    # Omitted on that call, so left alone.
    assert res.json()["communication"] == "Excellent"

    res = await api.patch(f"{_URL}/{pid}", json={"communication": None})
    assert res.status_code == 200, res.text
    stored = await Position.get(pid)
    assert stored.communication is None
    assert stored.brand_experience == "Low"


async def test_an_unrelated_update_leaves_them_alone(api, client_doc):
    pid = (
        await api.post(_URL, json=_new(client_doc.id, communication="Good", brand_experience="Mid"))
    ).json()["id"]

    res = await api.patch(f"{_URL}/{pid}", json={"notes": "Weekend shifts"})

    assert res.status_code == 200, res.text
    stored = await Position.get(pid)
    assert (stored.communication, stored.brand_experience) == ("Good", "Mid")


async def test_update_refuses_a_value_off_the_scale(api, client_doc):
    pid = (await api.post(_URL, json=_new(client_doc.id, communication="Good"))).json()["id"]

    res = await api.patch(f"{_URL}/{pid}", json={"communication": "Fluent"})

    assert res.status_code == 422
    assert (await Position.get(pid)).communication == "Good"
