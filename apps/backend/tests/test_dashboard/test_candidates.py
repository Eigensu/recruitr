"""The admin dashboard's candidate list must tolerate a candidate with no email.

Candidate.email is optional (phone is the mandatory contact channel for a
manually-added candidate, and imported leads often have no email at all), but
CandidateAnalyticsItem kept a required `str`. One emailless candidate in the
brand then failed validation and 500'd GET /api/v1/dashboard/candidates for
every page that included it.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_tenant
from app.core.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
# A maintainer: the brand-wide candidate list is closed to recruiters, which
# is what TenantScope's default employee role with an employee_id means.
TENANT = TenantScope(brand_id=_BRAND, employee_id=PydanticObjectId(), role=UserRole.maintainer)


@pytest_asyncio.fixture
async def api():
    app.dependency_overrides[get_tenant] = lambda: TENANT
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)


@pytest.mark.asyncio
async def test_candidates_without_an_email_are_listed(api: AsyncClient) -> None:
    await Candidate(brand_id=_BRAND, full_name="Has Email", email="has@test.com").insert()
    await Candidate(brand_id=_BRAND, full_name="Phone Only", phone="+91 90000 22222").insert()

    res = await api.get("/api/v1/dashboard/candidates")

    assert res.status_code == 200, res.text
    emails = {item["full_name"]: item["email"] for item in res.json()["items"]}
    assert emails == {"Has Email": "has@test.com", "Phone Only": None}
