"""CV ownership: who is handed resume_url / cv_link, and who is not.

The rule lives in recruitment/utils/cv_access.py — a recruiter sees the CV of a
candidate they added, and of anyone unowned; maintainers and admins see all of
them. Enforced server-side because the URLs are public once known, so hiding
them in the UI would not be a restriction at all.

Two recruiters share one brand here, which is the case the rule exists for.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_tenant
from app.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_PRIYA = PydanticObjectId()
_KARAN = PydanticObjectId()

AS_PRIYA = TenantScope(brand_id=_BRAND, employee_id=_PRIYA)
AS_KARAN = TenantScope(brand_id=_BRAND, employee_id=_KARAN)
AS_MANAGER = TenantScope(brand_id=_BRAND, employee_id=PydanticObjectId(), role=UserRole.maintainer)

CV_LINK = "https://drive.example.com/cv/anita.pdf"
PAYLOAD = {
    "full_name": "Anita Rao",
    "email": "anita@test.com",
    "phone": "+91 98765 00002",
    "experience_years": 4,
    "skills": ["Mixology"],
    "cv_link": CV_LINK,
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


@pytest_asyncio.fixture
async def api():
    """A client whose acting recruiter can be switched mid-test."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:

        def act_as(scope: TenantScope) -> AsyncClient:
            app.dependency_overrides[get_tenant] = lambda: scope
            return c

        yield act_as
    app.dependency_overrides.pop(get_tenant, None)


async def _priya_adds_a_candidate(api) -> str:
    res = await api(AS_PRIYA).post("/api/v1/candidates", json=PAYLOAD)
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.mark.asyncio
async def test_owner_sees_their_own_cv(api) -> None:
    cid = await _priya_adds_a_candidate(api)

    body = (await api(AS_PRIYA).get(f"/api/v1/candidates/{cid}")).json()
    assert body["cv_link"] == CV_LINK
    assert body["cv_locked"] is False
    assert body["created_by_id"] == str(_PRIYA)


@pytest.mark.asyncio
async def test_another_recruiter_gets_the_profile_without_the_cv(api) -> None:
    cid = await _priya_adds_a_candidate(api)

    body = (await api(AS_KARAN).get(f"/api/v1/candidates/{cid}")).json()
    assert body["full_name"] == "Anita Rao"  # the profile is still shared
    assert body["cv_link"] is None
    assert body["resume_url"] is None
    assert body["cv_locked"] is True


@pytest.mark.asyncio
async def test_the_list_masks_per_viewer_too(api) -> None:
    await _priya_adds_a_candidate(api)

    mine = (await api(AS_PRIYA).get("/api/v1/candidates")).json()["items"][0]
    theirs = (await api(AS_KARAN).get("/api/v1/candidates")).json()["items"][0]

    assert mine["cv_link"] == CV_LINK
    assert theirs["cv_link"] is None
    assert theirs["cv_locked"] is True


@pytest.mark.asyncio
async def test_maintainer_sees_every_cv(api) -> None:
    cid = await _priya_adds_a_candidate(api)

    body = (await api(AS_MANAGER).get(f"/api/v1/candidates/{cid}")).json()
    assert body["cv_link"] == CV_LINK
    assert body["cv_locked"] is False


@pytest.mark.asyncio
async def test_unowned_candidates_stay_shared(api) -> None:
    """Public applications and pre-ownership records belong to nobody."""
    doc = Candidate(
        brand_id=_BRAND,
        full_name="Walk In",
        email="walkin@test.com",
        cv_link=CV_LINK,
    )
    await doc.insert()

    body = (await api(AS_KARAN).get(f"/api/v1/candidates/{doc.id}")).json()
    assert body["cv_link"] == CV_LINK
    assert body["cv_locked"] is False
    assert body["created_by_id"] is None


@pytest.mark.asyncio
async def test_a_masked_edit_cannot_wipe_the_cv(api) -> None:
    """Karan was served cv_link: null, so saving must not write that back."""
    cid = await _priya_adds_a_candidate(api)

    res = await api(AS_KARAN).patch(
        f"/api/v1/candidates/{cid}", json={"phone": "+91 90000 11111", "cv_link": ""}
    )
    assert res.status_code == 200

    still_there = (await api(AS_PRIYA).get(f"/api/v1/candidates/{cid}")).json()
    assert still_there["cv_link"] == CV_LINK
    assert still_there["phone"] == "+91 90000 11111"  # the rest of the edit landed


@pytest.mark.asyncio
async def test_filter_by_the_recruiter_who_added_them(api) -> None:
    await _priya_adds_a_candidate(api)
    await api(AS_KARAN).post(
        "/api/v1/candidates",
        json={**PAYLOAD, "email": "vikram@test.com", "full_name": "Vikram S"},
    )
    unowned = Candidate(brand_id=_BRAND, full_name="Walk In", email="walkin@test.com")
    await unowned.insert()

    mine = (await api(AS_PRIYA).get(f"/api/v1/candidates?created_by={_PRIYA}")).json()
    assert [c["full_name"] for c in mine["items"]] == ["Anita Rao"]

    theirs = (await api(AS_PRIYA).get(f"/api/v1/candidates?created_by={_KARAN}")).json()
    assert [c["full_name"] for c in theirs["items"]] == ["Vikram S"]

    nobody = (await api(AS_PRIYA).get("/api/v1/candidates?created_by=unassigned")).json()
    assert [c["full_name"] for c in nobody["items"]] == ["Walk In"]
