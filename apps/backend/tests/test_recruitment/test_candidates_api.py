"""HTTP-level tests for the /api/v1/candidates endpoints.

The auth chain is bypassed by overriding get_tenant with a fixed TenantScope.
Each test runs in a fresh MongoDB database (see conftest.py autouse fixture).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_tenant
from app.main import app
from app.modules.recruitment.models import Candidate, Mapping, Position
from app.modules.recruitment.schemas import TenantScope

# ── Shared test tenant (two different brands for isolation tests) ──────────────

_BRAND_A = PydanticObjectId()
_BRAND_B = PydanticObjectId()
_EMP_A = PydanticObjectId()
_EMP_B = PydanticObjectId()

TENANT_A = TenantScope(brand_id=_BRAND_A, employee_id=_EMP_A)
TENANT_B = TenantScope(brand_id=_BRAND_B, employee_id=_EMP_B)


@pytest_asyncio.fixture
async def client_a():
    """FastAPI test client authenticated as brand A."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)


@pytest_asyncio.fixture
async def client_b():
    """FastAPI test client authenticated as brand B (for isolation tests)."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)


# ── Helpers ────────────────────────────────────────────────────────────────────

BASE_PAYLOAD = {
    "full_name": "Priya Nair",
    "email": "priya@test.com",
    "phone": "+91 98765 00000",
    "previous_company": "Taj Hotels",
    "experience_years": 3,
    "skills": ["Guest Relations", "POS", "Billing"],
}


async def _create_via_api(client: AsyncClient, overrides: dict | None = None) -> dict:
    payload = {**BASE_PAYLOAD, **(overrides or {})}
    res = await client.post("/api/v1/candidates", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


# ── List ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_empty(client_a: AsyncClient) -> None:
    res = await client_a.get("/api/v1/candidates")
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_list_returns_brand_candidates(client_a: AsyncClient) -> None:
    await _create_via_api(client_a)
    await _create_via_api(client_a, {"email": "karan@test.com", "full_name": "Karan M"})

    res = await client_a.get("/api/v1/candidates")
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_list_search_by_name(client_a: AsyncClient) -> None:
    await _create_via_api(client_a)
    await _create_via_api(client_a, {"email": "other@test.com", "full_name": "Rohan Joshi"})

    res = await client_a.get("/api/v1/candidates?search=Priya")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["full_name"] == "Priya Nair"


@pytest.mark.asyncio
async def test_list_search_by_skill(client_a: AsyncClient) -> None:
    await _create_via_api(client_a)  # has "Guest Relations"
    await _create_via_api(
        client_a, {"email": "chef@test.com", "full_name": "Chef X", "skills": ["Cooking"]}
    )

    res = await client_a.get("/api/v1/candidates?search=Guest+Relations")
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_experience_filter_lt2(client_a: AsyncClient) -> None:
    await _create_via_api(client_a, {"email": "a@test.com", "experience_years": 1})
    await _create_via_api(client_a, {"email": "b@test.com", "experience_years": 5})

    res = await client_a.get("/api/v1/candidates?experience=lt2")
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1
    assert res.json()["items"][0]["experience_years"] == 1


@pytest.mark.asyncio
async def test_list_experience_filter_gt5(client_a: AsyncClient) -> None:
    await _create_via_api(client_a, {"email": "a@test.com", "experience_years": 3})
    await _create_via_api(client_a, {"email": "b@test.com", "experience_years": 7})

    res = await client_a.get("/api/v1/candidates?experience=gt5")
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1
    assert res.json()["items"][0]["experience_years"] == 7


# ── Create ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_success(client_a: AsyncClient) -> None:
    res = await client_a.post("/api/v1/candidates", json=BASE_PAYLOAD)
    assert res.status_code == 201
    body = res.json()
    assert body["full_name"] == "Priya Nair"
    assert body["email"] == "priya@test.com"
    assert body["skills"] == ["Guest Relations", "POS", "Billing"]
    assert body["mappings_count"] == 0
    assert "id" in body

    # skills_normalized stored internally — verify via Beanie
    doc = await Candidate.get(PydanticObjectId(body["id"]))
    assert doc is not None
    assert doc.skills_normalized == ["guest relations", "pos", "billing"]
    assert str(doc.brand_id) == str(_BRAND_A)


@pytest.mark.asyncio
async def test_create_duplicate_email_returns_409(client_a: AsyncClient) -> None:
    await _create_via_api(client_a)
    res = await client_a.post("/api/v1/candidates", json=BASE_PAYLOAD)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_create_email_normalised_to_lowercase(client_a: AsyncClient) -> None:
    payload = {**BASE_PAYLOAD, "email": "UPPER@TEST.COM"}
    res = await client_a.post("/api/v1/candidates", json=payload)
    assert res.status_code == 201
    assert res.json()["email"] == "upper@test.com"


# ── Detail ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_candidate_success(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    res = await client_a.get(f"/api/v1/candidates/{created['id']}")
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_candidate_not_found(client_a: AsyncClient) -> None:
    fake_id = str(PydanticObjectId())
    res = await client_a.get(f"/api/v1/candidates/{fake_id}")
    assert res.status_code == 404


# ── Update ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_candidate(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    cid = created["id"]

    res = await client_a.patch(
        f"/api/v1/candidates/{cid}",
        json={"full_name": "Priya Pillai", "experience_years": 4, "skills": ["Mixology"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "Priya Pillai"
    assert body["experience_years"] == 4
    assert body["skills"] == ["Mixology"]

    # skills_normalized updated too
    doc = await Candidate.get(PydanticObjectId(cid))
    assert doc is not None
    assert doc.skills_normalized == ["mixology"]


# ── Mappings (drawer) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_mappings_empty(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    res = await client_a.get(f"/api/v1/candidates/{created['id']}/mappings")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_get_mappings_returns_position_info(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    cand_oid = PydanticObjectId(created["id"])
    client_oid = PydanticObjectId()

    # Insert a position and a mapping directly via Beanie
    pos = Position(
        brand_id=_BRAND_A,
        code="CLI-001-POS-001",
        client_id=client_oid,
        client_name="Test Co",
        role="Steward",
        city="Mumbai",
    )
    await pos.insert()

    mapping = Mapping(
        brand_id=_BRAND_A,
        candidate_id=cand_oid,
        position_id=pos.id,  # type: ignore[arg-type]
        client_id=client_oid,
        employee_id=_EMP_A,
    )
    await mapping.insert()

    res = await client_a.get(f"/api/v1/candidates/{created['id']}/mappings")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["position_code"] == "CLI-001-POS-001"
    assert items[0]["role"] == "Steward"
    assert items[0]["client_name"] == "Test Co"
    assert items[0]["stage"] == "sourced"


# ── Tenant isolation (critical) ────────────────────────────────────────────────
# These tests switch the global override sequentially to avoid the two-fixture
# conflict (both fixtures set the same app.dependency_overrides key).


@pytest.mark.asyncio
async def test_brand_a_cannot_read_brand_b_candidate() -> None:
    """A candidate created in brand B must be invisible to brand A."""
    # Step 1: create as brand B
    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        res_b = await cb.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_b.status_code == 201
        cand_b_id = res_b.json()["id"]

    # Step 2: query as brand A
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        list_res = await ca.get("/api/v1/candidates")
        assert list_res.status_code == 200
        assert list_res.json()["meta"]["total"] == 0

        detail_res = await ca.get(f"/api/v1/candidates/{cand_b_id}")
        assert detail_res.status_code == 404

    app.dependency_overrides.pop(get_tenant, None)


@pytest.mark.asyncio
async def test_same_email_allowed_in_different_brands() -> None:
    """Email uniqueness is per-brand; the same email is valid in brand A and B."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        res_a = await ca.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_a.status_code == 201

    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        res_b = await cb.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_b.status_code == 201

    assert res_a.json()["id"] != res_b.json()["id"]
    app.dependency_overrides.pop(get_tenant, None)


@pytest.mark.asyncio
async def test_candidate_mappings_not_accessible_cross_brand() -> None:
    """Brand A cannot read the mappings of brand B's candidate."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        created_b = await _create_via_api(cb)

    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        res = await ca.get(f"/api/v1/candidates/{created_b['id']}/mappings")
        assert res.status_code == 404

    app.dependency_overrides.pop(get_tenant, None)


# ── Resume confirm ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_resume(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    cid = created["id"]
    assert created["resume_url"] is None

    res = await client_a.post(
        f"/api/v1/candidates/{cid}/resume",
        json={"resume_public_id": "resumes/abc123", "resume_url": "https://cdn.test/abc123.pdf"},
    )
    assert res.status_code == 200
    assert res.json()["resume_url"] == "https://cdn.test/abc123.pdf"
