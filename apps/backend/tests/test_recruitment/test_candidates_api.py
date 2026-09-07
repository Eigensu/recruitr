"""HTTP-level tests for the /api/v1/candidates endpoints.

The auth chain is bypassed by overriding get_tenant with a fixed TenantScope.
Each test runs in a fresh MongoDB database (see conftest.py autouse fixture).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_tenant, get_viewer
from app.core.main import app
from app.modules.recruitment.models import Candidate, Mapping, Position, RefereeUser
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
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


@pytest_asyncio.fixture
async def client_b():
    """FastAPI test client authenticated as brand B (for isolation tests)."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    app.dependency_overrides[get_viewer] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


# ── Helpers ────────────────────────────────────────────────────────────────────

BASE_PAYLOAD = {
    "full_name": "Priya Nair",
    "email": "priya@test.com",
    "phone": "+91 98765 00000",
    "previous_company": "Taj Hotels",
    "experience_years": 3,
    "skills": ["Guest Relations", "POS", "Billing"],
    "communication": "Excellent",
    "education": "Bachelor's",
    "brand_experience": "Taj",
    "department": "Service",
    "specialization": "F&B",
    "city": "Mumbai",
    "gender": "female",
    "current_role": "Manager",
    "expected_salary": 1500000,
    "notice_period": "30 Days",
    "source": "internal",
    "salary": 1200000,
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
        client_a,
        {
            "email": "chef@test.com",
            "full_name": "Chef X",
            "skills": ["Cooking"],
            "communication": "Excellent",
            "education": "Bachelor's",
            "brand_experience": "Taj",
            "department": "Service",
            "specialization": "F&B",
            "city": "Mumbai",
            "gender": "female",
            "current_role": "Manager",
            "expected_salary": 1500000,
            "notice_period": "30 Days",
            "source": "internal",
            "salary": 1200000,
        },
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


# ── Referee attribution (External Candidates tab) ──────────────────────────────
# CandidateCreateStrict/the manual-add endpoint never resolves connect_code to
# referee_id — only the public application form does that (public_controller.py)
# — so these tests set referee_id directly on the document, the way that flow
# would have left it.


async def _create_referee(brand_id: PydanticObjectId, **overrides) -> RefereeUser:
    referee = RefereeUser(
        brand_id=brand_id,
        email=overrides.pop("email", "priya.referee@example.com"),
        name=overrides.pop("name", "Priya Referee"),
        **overrides,
    )
    await referee.insert()
    return referee


@pytest.mark.asyncio
async def test_list_includes_referee_name_when_referred(client_a: AsyncClient) -> None:
    referee = await _create_referee(_BRAND_A)
    created = await _create_via_api(client_a)
    await Candidate.find_one(Candidate.id == PydanticObjectId(created["id"])).set(
        {Candidate.referee_id: referee.id}
    )

    res = await client_a.get("/api/v1/candidates")
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["referee_id"] == str(referee.id)
    assert item["referee_name"] == "Priya Referee"


@pytest.mark.asyncio
async def test_list_referee_name_falls_back_to_email_when_name_missing(
    client_a: AsyncClient,
) -> None:
    referee = await _create_referee(_BRAND_A, name=None, email="dormant.referee@example.com")
    created = await _create_via_api(client_a)
    await Candidate.find_one(Candidate.id == PydanticObjectId(created["id"])).set(
        {Candidate.referee_id: referee.id}
    )

    res = await client_a.get("/api/v1/candidates")
    assert res.json()["items"][0]["referee_name"] == "dormant.referee@example.com"


@pytest.mark.asyncio
async def test_list_candidates_without_a_referee_have_null_referee_fields(
    client_a: AsyncClient,
) -> None:
    await _create_via_api(client_a)

    res = await client_a.get("/api/v1/candidates")
    item = res.json()["items"][0]
    assert item["referee_id"] is None
    assert item["referee_name"] is None


@pytest.mark.asyncio
async def test_list_filter_by_referee_id(client_a: AsyncClient) -> None:
    referee = await _create_referee(_BRAND_A)
    referred = await _create_via_api(client_a, {"email": "referred@test.com"})
    await _create_via_api(client_a, {"email": "unreferred@test.com"})
    await Candidate.find_one(Candidate.id == PydanticObjectId(referred["id"])).set(
        {Candidate.referee_id: referee.id}
    )

    res = await client_a.get(f"/api/v1/candidates?referee_id={referee.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 1
    assert body["items"][0]["email"] == "referred@test.com"


@pytest.mark.asyncio
async def test_list_filter_referee_id_none_returns_unreferred_only(
    client_a: AsyncClient,
) -> None:
    referee = await _create_referee(_BRAND_A)
    referred = await _create_via_api(client_a, {"email": "referred@test.com"})
    await _create_via_api(client_a, {"email": "unreferred@test.com"})
    await Candidate.find_one(Candidate.id == PydanticObjectId(referred["id"])).set(
        {Candidate.referee_id: referee.id}
    )

    res = await client_a.get("/api/v1/candidates?referee_id=none")
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 1
    assert body["items"][0]["email"] == "unreferred@test.com"


@pytest.mark.asyncio
async def test_get_candidate_detail_includes_referee_name(client_a: AsyncClient) -> None:
    referee = await _create_referee(_BRAND_A)
    created = await _create_via_api(client_a)
    await Candidate.find_one(Candidate.id == PydanticObjectId(created["id"])).set(
        {Candidate.referee_id: referee.id}
    )

    res = await client_a.get(f"/api/v1/candidates/{created['id']}")
    assert res.status_code == 200
    assert res.json()["referee_name"] == "Priya Referee"


@pytest.mark.asyncio
async def test_list_candidate_referees_only_includes_referees_with_candidates(
    client_a: AsyncClient,
) -> None:
    referred_by = await _create_referee(_BRAND_A, email="active@example.com", name="Active Ref")
    await _create_referee(_BRAND_A, email="unused@example.com", name="Unused Ref")
    created = await _create_via_api(client_a)
    await Candidate.find_one(Candidate.id == PydanticObjectId(created["id"])).set(
        {Candidate.referee_id: referred_by.id}
    )

    res = await client_a.get("/api/v1/candidates/referees")
    assert res.status_code == 200
    body = res.json()
    assert body == [{"id": str(referred_by.id), "name": "Active Ref"}]


@pytest.mark.asyncio
async def test_list_candidate_referees_is_brand_scoped() -> None:
    """A referee attributed only in brand B must not surface in brand A's list."""
    referee_b = await _create_referee(_BRAND_B, name="Other Brand Ref")

    # Step 1: create + attribute as brand B
    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    app.dependency_overrides[get_viewer] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        res_b = await cb.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_b.status_code == 201
        await Candidate.find_one(Candidate.id == PydanticObjectId(res_b.json()["id"])).set(
            {Candidate.referee_id: referee_b.id}
        )

    # Step 2: query as brand A
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        res = await ca.get("/api/v1/candidates/referees")
        assert res.status_code == 200
        assert res.json() == []

    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


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


@pytest.mark.asyncio
async def test_create_without_phone_returns_422(client_a: AsyncClient) -> None:
    payload = {k: v for k, v in BASE_PAYLOAD.items() if k != "phone"}
    res = await client_a.post("/api/v1/candidates", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_without_email_succeeds(client_a: AsyncClient) -> None:
    payload = {k: v for k, v in BASE_PAYLOAD.items() if k != "email"}
    res = await client_a.post("/api/v1/candidates", json=payload)
    assert res.status_code == 201, res.text
    assert res.json()["email"] is None


@pytest.mark.asyncio
async def test_two_emailless_candidates_in_one_brand_do_not_collide(
    client_a: AsyncClient,
) -> None:
    """The unique email index is partial for exactly this reason.

    A plain unique index treats every missing/null email as the same indexed
    value, so the second candidate without an email would 409 as a
    "duplicate" of the first. It isn't one — neither has an email at all.
    """
    payload = {k: v for k, v in BASE_PAYLOAD.items() if k != "email"}
    first = await client_a.post("/api/v1/candidates", json={**payload, "full_name": "No Email One"})
    second = await client_a.post(
        "/api/v1/candidates", json={**payload, "full_name": "No Email Two"}
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


# Every CandidateCreate field must survive the trip to Mongo and back. The
# handler used to name each field by hand and had quietly stopped copying
# expected_salary, notice_period, source and source_channel —
# the Add Candidate form sent them and they vanished.
@pytest.mark.asyncio
async def test_create_persists_every_submitted_field(client_a: AsyncClient) -> None:
    extras = {
        "expected_salary": 85000,
        "notice_period": "30 days",
        "salary": 60000,
        "source": "internal",
        "source_channel": "LinkedIn",
        "current_role": "Guest Relations Manager",
        "city": "Mumbai",
        "area": "Andheri",
        "gender": "female",
        "age": 29,
        "education_level": "Bachelors",
        "preferred_train_line": "Western",
        "cv_link": "https://cv.test/priya",
        "tags": ["senior"],
        "notes": "Strong on escalations.",
    }
    body = await _create_via_api(client_a, extras)

    for field, expected in extras.items():
        assert body[field] == expected, f"{field} missing from the create response"

    doc = await Candidate.get(PydanticObjectId(body["id"]))
    assert doc is not None
    assert doc.expected_salary == 85000
    assert doc.notice_period == "30 days"
    assert doc.source == "internal"
    assert doc.source_channel == "LinkedIn"


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
        json={
            "full_name": "Priya Pillai",
            "experience_years": 4,
            "skills": ["Mixology"],
            "communication": "Excellent",
            "education": "Bachelor's",
            "brand_experience": "Taj",
            "department": "Service",
            "specialization": "F&B",
            "city": "Mumbai",
            "gender": "female",
            "current_role": "Manager",
            "expected_salary": 1500000,
            "notice_period": "30 Days",
            "source": "internal",
            "salary": 1200000,
        },
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


# Same drift as create: the PATCH handler's if-chain ignored these fields, so
# filling them in from the candidate drawer looked saved but never was.
@pytest.mark.asyncio
async def test_update_persists_role_and_compensation_fields(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    cid = created["id"]

    patch = {
        "salary": 60000,
        "expected_salary": 92000,
        "notice_period": "60 days",
        "source": "internal",
    }
    res = await client_a.patch(f"/api/v1/candidates/{cid}", json=patch)
    assert res.status_code == 200
    body = res.json()
    for field, expected in patch.items():
        assert body[field] == expected, f"{field} missing from the update response"

    doc = await Candidate.get(PydanticObjectId(cid))
    assert doc is not None
    assert doc.salary == 60000
    assert doc.expected_salary == 92000
    assert doc.notice_period == "60 days"


@pytest.mark.asyncio
async def test_update_leaves_omitted_fields_untouched(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a, {"notice_period": "30 days", "notes": "keep me"})

    res = await client_a.patch(
        f"/api/v1/candidates/{created['id']}", json={"full_name": "Priya Pillai"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "Priya Pillai"
    assert body["notice_period"] == "30 days"
    assert body["notes"] == "keep me"


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
    app.dependency_overrides[get_viewer] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        res_b = await cb.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_b.status_code == 201
        cand_b_id = res_b.json()["id"]

    # Step 2: query as brand A
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        list_res = await ca.get("/api/v1/candidates")
        assert list_res.status_code == 200
        assert list_res.json()["meta"]["total"] == 0

        detail_res = await ca.get(f"/api/v1/candidates/{cand_b_id}")
        assert detail_res.status_code == 404

    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


@pytest.mark.asyncio
async def test_same_email_allowed_in_different_brands() -> None:
    """Email uniqueness is per-brand; the same email is valid in brand A and B."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        res_a = await ca.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_a.status_code == 201

    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    app.dependency_overrides[get_viewer] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        res_b = await cb.post("/api/v1/candidates", json=BASE_PAYLOAD)
        assert res_b.status_code == 201

    assert res_a.json()["id"] != res_b.json()["id"]
    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


@pytest.mark.asyncio
async def test_candidate_mappings_not_accessible_cross_brand() -> None:
    """Brand A cannot read the mappings of brand B's candidate."""
    app.dependency_overrides[get_tenant] = lambda: TENANT_B
    app.dependency_overrides[get_viewer] = lambda: TENANT_B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cb:
        created_b = await _create_via_api(cb)

    app.dependency_overrides[get_tenant] = lambda: TENANT_A
    app.dependency_overrides[get_viewer] = lambda: TENANT_A
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ca:
        res = await ca.get(f"/api/v1/candidates/{created_b['id']}/mappings")
        assert res.status_code == 404

    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


# ── Resume confirm ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_resume(client_a: AsyncClient) -> None:
    created = await _create_via_api(client_a)
    cid = created["id"]
    assert created["resume_url"] is None

    from app.core.config import settings

    cloud_name = settings.CLOUDINARY_CLOUD_NAME or "test"
    valid_url = f"https://res.cloudinary.com/{cloud_name}/abc123.pdf"

    res = await client_a.post(
        f"/api/v1/candidates/{cid}/resume",
        json={"resume_public_id": "resumes/abc123", "resume_url": valid_url},
    )
    assert res.status_code == 200
    assert res.json()["resume_url"] == valid_url
