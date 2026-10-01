"""End-to-end cover for the public application form and the review that follows.

An applicant lands as PENDING; a maintainer then opens the record, fills in what
the public form never asked for, and approves. Every step has to preserve the
fields added along the way.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_tenant, require_maintainer
from app.core.main import app
from app.modules.brands.models import Brand
from app.modules.recruitment.models import Candidate, RefereeUser
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()

TENANT = TenantScope(brand_id=_BRAND, employee_id=_EMP)


@pytest_asyncio.fixture
async def brand() -> Brand:
    """The agency the public form targets."""
    doc = Brand(id=_BRAND, owner_id=str(_EMP), name="Binge Talent", domain="binge.test")
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def client():
    """Client authenticated as a maintainer of the seeded brand."""
    app.dependency_overrides[get_tenant] = lambda: TENANT
    app.dependency_overrides[require_maintainer] = lambda: object()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(require_maintainer, None)


APPLICATION = {
    "brand_id": str(_BRAND),
    "full_name": "Rhea Kapoor",
    "email": "Rhea@Applicant.test",
    "phone": "+91 90000 11111",
    "current_role": "Front Office Associate",
    "city": "Mumbai",
    "education_level": "Bachelors",
    "source_channel": "LinkedIn",
    "current_salary": "28000",  # ₹ per month; required on every external form
}


@pytest.mark.asyncio
async def test_apply_lands_as_pending_external(brand: Brand, client: AsyncClient) -> None:
    res = await client.post("/api/v1/public/apply", data=APPLICATION)
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["status"] == "PENDING"
    assert body["email"] == "rhea@applicant.test"
    assert body["current_role"] == "Front Office Associate"
    assert body["education_level"] == "Bachelors"
    assert body["source_channel"] == "LinkedIn"
    # Lowercase so the directory's source filter (internal | external) matches it.
    assert body["source"] == "external"


@pytest.mark.asyncio
async def test_pending_application_can_be_filled_in_then_approved(
    brand: Brand, client: AsyncClient
) -> None:
    created = await client.post("/api/v1/public/apply", data=APPLICATION)
    cid = created.json()["id"]

    # The recruiter adds what the public form never asked for.
    res = await client.patch(
        f"/api/v1/candidates/{cid}",
        json={
            "salary": 60000,
            "previous_company": "Taj Hotels",
            "expected_salary": 75000,
            "notice_period": "45 days",
            "experience_years": 4,
            "notes": "Called — available immediately after notice.",
        },
    )
    assert res.status_code == 200, res.text
    patched = res.json()
    assert patched["expected_salary"] == 75000
    assert patched["notice_period"] == "45 days"
    assert patched["salary"] == 60000
    # Reviewing must not approve by itself.
    assert patched["status"] == "PENDING"

    res = await client.post(f"/api/v1/candidates/{cid}/approve")
    assert res.status_code == 200, res.text
    approved = res.json()
    assert approved["status"] == "APPROVED"
    # The details added during review survive the approval.
    assert approved["expected_salary"] == 75000
    assert approved["notice_period"] == "45 days"
    assert approved["salary"] == 60000
    assert approved["notes"] == "Called — available immediately after notice."

    doc = await Candidate.get(PydanticObjectId(cid))
    assert doc is not None
    assert doc.expected_salary == 75000
    assert doc.notice_period == "45 days"


@pytest.mark.asyncio
async def test_pending_application_is_hidden_from_the_default_directory(
    brand: Brand, client: AsyncClient
) -> None:
    await client.post("/api/v1/public/apply", data=APPLICATION)

    res = await client.get("/api/v1/candidates")
    assert res.status_code == 200
    assert res.json()["items"] == []

    res = await client.get("/api/v1/candidates", params={"status": "PENDING"})
    assert [c["full_name"] for c in res.json()["items"]] == ["Rhea Kapoor"]


# ── Salary: current required, expected optional, both ₹ per month ────────────


async def _stored(email: str = "rhea@applicant.test") -> dict:
    return await Candidate.get_motor_collection().find_one({"email": email})


@pytest.mark.asyncio
async def test_current_salary_is_stored_as_monthly(brand: Brand, client: AsyncClient) -> None:
    res = await client.post("/api/v1/public/apply", data=APPLICATION)

    assert res.status_code == 201, res.text
    assert (res.json()["salary"], res.json()["expected_salary"]) == (28000, None)
    stored = await _stored()
    assert stored["salary"] == 28000
    assert stored["salary_period"] == "monthly"


@pytest.mark.asyncio
async def test_expected_salary_is_stored_when_given(brand: Brand, client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/public/apply", data={**APPLICATION, "expected_salary": "35000"}
    )

    assert res.status_code == 201, res.text
    stored = await _stored()
    assert (stored["salary"], stored["expected_salary"]) == (28000, 35000)


@pytest.mark.asyncio
async def test_current_salary_is_required(brand: Brand, client: AsyncClient) -> None:
    form = {k: v for k, v in APPLICATION.items() if k != "current_salary"}

    res = await client.post("/api/v1/public/apply", data=form)

    assert res.status_code == 422
    assert await Candidate.find_all().count() == 0


@pytest.mark.asyncio
async def test_a_bad_salary_is_refused(brand: Brand, client: AsyncClient) -> None:
    for bad in (
        {"current_salary": "-1"},
        {"current_salary": "about 30k"},
        {"expected_salary": "-5"},
    ):
        res = await client.post("/api/v1/public/apply", data={**APPLICATION, **bad})
        assert res.status_code == 422, (bad, res.text)

    assert await Candidate.find_all().count() == 0


@pytest.mark.asyncio
async def test_a_referral_stores_the_salary_too(brand: Brand, client: AsyncClient) -> None:
    """The referee refer page submits the same form, carrying a connect code."""
    referee = RefereeUser(brand_id=_BRAND, email="ref@x.test", connect_code="BINGE7")
    await referee.insert()

    res = await client.post(
        "/api/v1/public/apply",
        data={**APPLICATION, "connect_code": "binge7", "expected_salary": "33000"},
    )

    assert res.status_code == 201, res.text
    stored = await _stored()
    assert stored["referee_id"] == referee.id
    assert (stored["salary"], stored["expected_salary"]) == (28000, 33000)
