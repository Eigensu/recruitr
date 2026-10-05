"""Candidate salaries are ₹ per month from here on; older rows are left as typed.

Nothing is migrated. `salary_period = "monthly"` marks a row whose salary was
written under the new convention, so the unmarked ones — possibly yearly — can
be found later. The list filter takes real amounts (min / max per month)
instead of the old yearly bands.
"""

import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_tenant, get_viewer
from app.core.main import app
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_SCOPE = TenantScope(brand_id=_BRAND, employee_id=PydanticObjectId())
_URL = "/api/v1/candidates"

_PAYLOAD = {
    "full_name": "Priya Nair",
    "email": "priya@test.com",
    "phone": "+91 98765 00000",
    "previous_company": "Taj Hotels",
    "experience_years": 3,
    "skills": ["Guest Relations"],
    "communication": "Good",
    "education": "Graduate",
    "brand_experience": "Premium",
    "department": "Service",
    "specialization": "F&B",
    "city": "Mumbai",
    "gender": "female",
    "current_role": "Captain",
    "expected_salary": 40000,
    "notice_period": "30 Days",
    "source": "internal",
    "salary": 32000,
}


@pytest_asyncio.fixture
async def api(init_test_db):
    app.dependency_overrides[get_tenant] = lambda: _SCOPE
    app.dependency_overrides[get_viewer] = lambda: _SCOPE
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _legacy(**fields) -> PydanticObjectId:
    """A row as saved before the per-month convention: no salary_period at all."""
    # Everything a row written through the model always carries, minus the marker.
    doc = Candidate(brand_id=_BRAND, full_name="Old Row").model_dump(by_alias=True, exclude={"id"})
    doc.pop("salary_period")
    res = await Candidate.get_motor_collection().insert_one({**doc, **fields})
    return res.inserted_id


async def _raw(cid: PydanticObjectId) -> dict:
    return await Candidate.get_motor_collection().find_one({"_id": cid})


# ── The marker ─────────────────────────────────────────────────────────────────


async def test_a_new_candidate_with_a_salary_is_marked_monthly(api):
    res = await api.post(_URL, json=_PAYLOAD)

    assert res.status_code == 201, res.text
    stored = await _raw(PydanticObjectId(res.json()["id"]))
    assert stored["salary_period"] == "monthly"
    assert (stored["salary"], stored["expected_salary"]) == (32000, 40000)


async def test_any_insert_path_is_marked(init_test_db):
    """The hook is on the model, so paths that build a Candidate directly are covered too."""
    doc = Candidate(brand_id=_BRAND, full_name="Direct", expected_salary=25000)
    await doc.insert()

    assert (await _raw(doc.id))["salary_period"] == "monthly"


async def test_a_new_candidate_without_a_salary_is_not_marked(init_test_db):
    doc = Candidate(brand_id=_BRAND, full_name="No Pay Yet")
    await doc.insert()

    assert (await _raw(doc.id)).get("salary_period") is None


async def test_editing_something_else_leaves_a_legacy_row_unmarked(api):
    cid = await _legacy(salary=380000)

    res = await api.patch(f"{_URL}/{cid}", json={"notes": "Called back"})

    assert res.status_code == 200, res.text
    stored = await _raw(cid)
    assert "salary_period" not in stored
    assert stored["salary"] == 380000


async def test_saving_a_legacy_row_does_not_mark_it(init_test_db):
    """Save and Replace fire for old rows too; only Insert may stamp."""
    cid = await _legacy(salary=380000)
    doc = await Candidate.get(cid)
    doc.notes = "touched"
    await doc.save()

    assert (await _raw(cid)).get("salary_period") is None


async def test_editing_the_salary_marks_the_row(api):
    cid = await _legacy(salary=380000)

    res = await api.patch(f"{_URL}/{cid}", json={"salary": 31667})

    assert res.status_code == 200, res.text
    stored = await _raw(cid)
    assert (stored["salary"], stored["salary_period"]) == (31667, "monthly")


# ── The filter ─────────────────────────────────────────────────────────────────


async def _names(api, **params) -> list[str]:
    res = await api.get(_URL, params={"limit": 50, **params})
    assert res.status_code == 200, res.text
    return sorted(c["full_name"] for c in res.json()["items"])


async def _seed_pool() -> None:
    for name, salary in (("A", 15000), ("B", 25000), ("C", 35000), ("D", 60000)):
        await Candidate(brand_id=_BRAND, full_name=name, salary=salary).insert()
    await Candidate(brand_id=_BRAND, full_name="NoSalary").insert()
    # Stored as a string, as some legacy rows are; the filter converts it.
    await _legacy(full_name="Stringly", salary="20000")


async def test_min_only(api):
    await _seed_pool()
    assert await _names(api, salary_min=25000) == ["B", "C", "D"]


async def test_max_only(api):
    await _seed_pool()
    assert await _names(api, salary_max=25000) == ["A", "B", "Stringly"]


async def test_both_bounds_are_inclusive(api):
    await _seed_pool()
    assert await _names(api, salary_min=25000, salary_max=35000) == ["B", "C"]


async def test_no_bounds_filters_nothing(api):
    await _seed_pool()
    assert await _names(api) == ["A", "B", "C", "D", "NoSalary", "Stringly"]


async def test_rows_without_a_salary_drop_out_once_filtering(api):
    await _seed_pool()
    names = await _names(api, salary_min=0)
    assert "NoSalary" not in names
    assert "Stringly" in names


async def test_min_above_max_is_refused(api):
    res = await api.get(_URL, params={"salary_min": 50000, "salary_max": 20000})
    assert res.status_code == 422


async def test_a_negative_bound_is_refused(api):
    res = await api.get(_URL, params={"salary_min": -1})
    assert res.status_code == 422
