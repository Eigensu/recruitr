"""Activity-feed lines must say who was actioned, not just what happened.

The dashboard renders ActivityLog.description as the headline of each feed
item, so "Moved to Selected" on its own leaves the reader with no idea which
candidate moved.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_tenant, get_viewer
from app.main import app
from app.modules.recruitment.models import ActivityLog, Client, Employee, Position
from app.modules.recruitment.repository_impl import candidate_display_name
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
TENANT = TenantScope(brand_id=_BRAND, employee_id=_EMP)

CANDIDATE = {
    "full_name": "Anita Rao",
    "email": "anita@test.com",
    "phone": "+91 98765 00001",
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
}


@pytest_asyncio.fixture
async def api():
    app.dependency_overrides[get_tenant] = lambda: TENANT
    app.dependency_overrides[get_viewer] = lambda: TENANT
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_tenant, None)
    app.dependency_overrides.pop(get_viewer, None)


@pytest_asyncio.fixture
async def position() -> Position:
    await Employee(id=_EMP, brand_id=_BRAND, name="Priya Nair", email="priya@agency.test").insert()
    client = Client(brand_id=_BRAND, code="CLI-001", name="Hunger Inc")
    await client.insert()
    pos = Position(
        brand_id=_BRAND,
        code="CLI-001-POS-001",
        client_id=client.id,
        client_name="Hunger Inc",
        role="Sous Chef",
        total_seats=1,
    )
    await pos.insert()
    return pos


async def _descriptions() -> list[str]:
    return [a.description for a in await ActivityLog.find({"brand_id": _BRAND}).to_list()]


@pytest.mark.asyncio
async def test_mapping_and_stage_moves_name_the_candidate(
    api: AsyncClient, position: Position
) -> None:
    cid = (await api.post("/api/v1/candidates", json=CANDIDATE)).json()["id"]

    mapped = await api.post(
        f"/api/v1/positions/{position.id}/map-candidate", json={"candidate_id": cid}
    )
    mapping_id = mapped.json()["mapping_id"]

    moved = await api.post(
        f"/api/v1/pipeline/mappings/{mapping_id}/move", json={"new_stage": "interview"}
    )
    assert moved.status_code == 200, moved.text

    descriptions = await _descriptions()
    assert descriptions, "no activity was logged at all"
    # Every line about this candidate names them.
    assert any("Anita Rao" in d and "Interview" in d for d in descriptions), descriptions
    assert any("Anita Rao" in d and "Sous Chef" in d for d in descriptions), descriptions
    # The bare form that prompted this is gone.
    assert "Moved to Interview" not in descriptions


@pytest.mark.asyncio
async def test_display_name_falls_back_for_a_deleted_candidate() -> None:
    # Read long after the fact, the candidate row may be gone; the line must
    # still say something rather than render blank.
    assert await candidate_display_name(PydanticObjectId()) == "Unknown candidate"
