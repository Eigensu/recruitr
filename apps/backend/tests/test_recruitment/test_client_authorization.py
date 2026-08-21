"""Tests for client authorization on positions and pipeline."""

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
_EMP = PydanticObjectId()
_CLIENT_ID_1 = PydanticObjectId()
_CLIENT_ID_2 = PydanticObjectId()

# Staff scope
_TENANT = TenantScope(brand_id=_BRAND, employee_id=_EMP, role=UserRole.employee)

# Client 1 scope
_CLIENT_SCOPE_1 = TenantScope(
    brand_id=_BRAND, employee_id=None, role=UserRole.client, client_id=_CLIENT_ID_1
)

# Client 2 scope
_CLIENT_SCOPE_2 = TenantScope(
    brand_id=_BRAND, employee_id=None, role=UserRole.client, client_id=_CLIENT_ID_2
)


_EMP_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.employee, email="emp@test.com")
_CLIENT_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.client, email="cli@test.com")


@pytest_asyncio.fixture
async def staff_client():
    app.dependency_overrides[get_tenant] = lambda: _TENANT
    app.dependency_overrides[get_viewer] = lambda: _TENANT
    app.dependency_overrides[get_current_user_doc] = lambda: _EMP_USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_1():
    # Client is blocked by get_tenant, so any endpoint using get_tenant should return 403.
    # To simulate the actual dependency returning 403, we can just let get_tenant throw 403.
    from fastapi import HTTPException

    def mock_get_tenant():
        raise HTTPException(403, "This area is not available to client accounts.")

    app.dependency_overrides[get_tenant] = mock_get_tenant
    app.dependency_overrides[get_viewer] = lambda: _CLIENT_SCOPE_1
    app.dependency_overrides[get_current_user_doc] = lambda: _CLIENT_USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_2():
    from fastapi import HTTPException

    def mock_get_tenant():
        raise HTTPException(403, "This area is not available to client accounts.")

    app.dependency_overrides[get_tenant] = mock_get_tenant
    app.dependency_overrides[get_viewer] = lambda: _CLIENT_SCOPE_2
    app.dependency_overrides[get_current_user_doc] = lambda: _CLIENT_USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def seed_data(init_test_db):
    c1 = Client(id=_CLIENT_ID_1, brand_id=_BRAND, code="C1", name="Client 1")
    c2 = Client(id=_CLIENT_ID_2, brand_id=_BRAND, code="C2", name="Client 2")
    await c1.insert()
    await c2.insert()

    cand1 = Candidate(
        brand_id=_BRAND, email="cand1@test.com", full_name="Cand 1", source="internal"
    )
    cand2 = Candidate(
        brand_id=_BRAND, email="cand2@test.com", full_name="Cand 2", source="internal"
    )
    await cand1.insert()
    await cand2.insert()

    pos1 = Position(
        brand_id=_BRAND,
        code="P1",
        client_id=_CLIENT_ID_1,
        client_name="Client 1",
        role="Role",
        total_seats=1,
        remaining_seats=1,
    )
    pos2 = Position(
        brand_id=_BRAND,
        code="P2",
        client_id=_CLIENT_ID_2,
        client_name="Client 2",
        role="Role",
        total_seats=1,
        remaining_seats=1,
    )
    await pos1.insert()
    await pos2.insert()

    m1 = Mapping(
        brand_id=_BRAND,
        candidate_id=cand1.id,
        position_id=pos1.id,
        employee_id=_EMP,
        stage=PipelineStage.sent_to_client,
    )
    m2 = Mapping(
        brand_id=_BRAND,
        candidate_id=cand2.id,
        position_id=pos2.id,
        employee_id=_EMP,
        stage=PipelineStage.sent_to_client,
    )
    await m1.insert()
    await m2.insert()

    return {"m1": str(m1.id), "m2": str(m2.id)}


@pytest.mark.asyncio
async def test_client_can_create_position_for_own_org(client_1: AsyncClient):
    res = await client_1.post(
        "/api/v1/positions",
        json={
            "client_id": str(_CLIENT_ID_1),
            "role": "HR",
            "department": "Corporate",
            "city": "Remote",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_client_cannot_create_position_for_other_org(client_1: AsyncClient):
    res = await client_1.post(
        "/api/v1/positions",
        json={
            "client_id": str(_CLIENT_ID_2),
            "role": "HR",
            "department": "Corporate",
            "city": "Remote",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_staff_can_create_position_for_any_org(staff_client: AsyncClient):
    res = await staff_client.post(
        "/api/v1/positions",
        json={
            "client_id": str(_CLIENT_ID_2),
            "role": "HR",
            "department": "Corporate",
            "city": "Remote",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 201


@pytest.mark.asyncio
async def test_client_can_move_own_mapping(client_1: AsyncClient, seed_data):
    res = await client_1.post(
        f"/api/v1/pipeline/mappings/{seed_data['m1']}/move",
        json={"new_stage": "interview"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_client_cannot_move_other_mapping(client_1: AsyncClient, seed_data):
    res = await client_1.post(
        f"/api/v1/pipeline/mappings/{seed_data['m2']}/move",
        json={"new_stage": "interview"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_client_with_empty_client_id_can_create_own_position(client_1: AsyncClient):
    res = await client_1.post(
        "/api/v1/positions",
        json={
            "client_id": "",
            "role": "HR",
            "department": "Corporate",
            "city": "Remote",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 201
    assert res.json()["client_id"] == str(_CLIENT_ID_1)


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_create_position():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            "/api/v1/positions",
            json={
                "client_id": "",
                "role": "HR",
                "department": "Corporate",
                "city": "Remote",
                "seniority": "Mid",
                "total_seats": 2,
            },
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_client_cannot_create_position_without_category(client_1: AsyncClient):
    res = await client_1.post(
        "/api/v1/positions",
        json={
            "client_id": "",
            "role": "Sous Chef",
            "city": "Mumbai",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 422
    assert "Category (department) is required." in res.text


@pytest.mark.asyncio
async def test_client_cannot_create_position_with_invalid_role(client_1: AsyncClient):
    res = await client_1.post(
        "/api/v1/positions",
        json={
            "client_id": "",
            "role": "Not a Real Role",
            "department": "BOH",
            "city": "Mumbai",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 422
    assert "is not valid for category" in res.text


@pytest.mark.asyncio
async def test_client_can_create_position_with_valid_role_and_salary(client_1: AsyncClient):
    res = await client_1.post(
        "/api/v1/positions",
        json={
            "client_id": "",
            "role": "Sous Chef",
            "department": "BOH",
            "salary": "30k - 40k",
            "city": "Mumbai",
            "mumbai_area": "Bandra",
            "seniority": "Mid",
            "total_seats": 2,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["salary"] == "30k - 40k"
    assert data["mumbai_area"] == "Bandra"
    assert data["total_seats"] == 2


@pytest_asyncio.fixture
def stub_cloudinary(monkeypatch):
    """Keep offer-letter uploads off the network."""
    from app.modules.storage import service as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_offer_letter",
        lambda *_a, **_kw: {"secure_url": "https://cdn.test/offer.pdf"},
    )


@pytest.mark.asyncio
async def test_client_pipeline_integration(client_1: AsyncClient, seed_data: dict, stub_cloudinary):
    m1 = seed_data["m1"]

    # 1. Try skipping to joined (should fail)
    res = await client_1.post(f"/api/v1/pipeline/mappings/{m1}/move", json={"new_stage": "joined"})
    assert res.status_code == 403

    # Let's get the mapping to sent_to_client first (as staff or directly in DB)
    from app.modules.recruitment.enums import PipelineStage
    from app.modules.recruitment.models import Mapping

    mapping = await Mapping.get(m1)
    mapping.stage = PipelineStage.sent_to_client.value
    await mapping.save()

    # 2. Move to interview
    res = await client_1.post(
        f"/api/v1/pipeline/mappings/{m1}/move", json={"new_stage": "interview"}
    )
    assert res.status_code == 200

    # 3. Move to selected
    res = await client_1.post(
        f"/api/v1/pipeline/mappings/{m1}/move", json={"new_stage": "selected"}
    )
    assert res.status_code == 200

    # 4. Upload offer letter (allowed because it's selected). Multipart, which
    # is what the portal has always sent — this step used to post JSON and pass
    # against a contract no caller used, which is how the 422 went unnoticed.
    res = await client_1.put(
        f"/api/v1/pipeline/mappings/{m1}/offer-letter",
        files={"file": ("offer.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert res.status_code == 200

    # 5. Set joining date (allowed because offer letter is present)
    res = await client_1.put(
        f"/api/v1/pipeline/mappings/{m1}/joining-date",
        json={"joining_date": "2026-09-01T00:00:00Z", "salary_offered": 50000},
    )
    assert res.status_code == 200
