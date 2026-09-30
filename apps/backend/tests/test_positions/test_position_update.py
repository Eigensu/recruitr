"""Editing a position, and what the single-position endpoints send back.

Two bugs with one shape — fields copied across by hand, and the list drifting:
PATCH silently dropped salary and mumbai_area (and could never clear any
optional field), and detail / update / reopen each built their response by
hand with salary, mumbai_area, approval_status, the assignee and the mapped
preview missing. The page merges a response over the row it already holds, so
each missing field blanked on the card after every edit.
"""

from types import SimpleNamespace

import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user_doc, get_tenant, get_viewer
from app.core.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import (
    Department,
    PipelineStage,
    PositionApprovalStatus,
    PositionStatus,
)
from app.modules.recruitment.models import Candidate, Client, Mapping, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_RECRUITER = PydanticObjectId()
_SCOPE = TenantScope(brand_id=_BRAND, employee_id=PydanticObjectId(), role=UserRole.maintainer)
_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.maintainer, email="m@x.com")
_URL = "/api/v1/positions"

# Everything a card renders that the old hand-built responses left out.
_FULL_ROW = {
    "salary": "30k - 40k",
    "mumbai_area": "Andheri",
    "approval_status": "approved",
    "assigned_employee_id": str(_RECRUITER),
}


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
        salary="30k - 40k",
        city="Mumbai",
        mumbai_area="Andheri",
        approval_status=PositionApprovalStatus.approved,
        assigned_employee_id=_RECRUITER,
        total_seats=3,
        filled_seats=1,
        remaining_seats=2,
        notes="Weekend shifts",
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def api(position):
    app.dependency_overrides[get_viewer] = lambda: _SCOPE
    app.dependency_overrides[get_tenant] = lambda: _SCOPE
    app.dependency_overrides[get_current_user_doc] = lambda: _USER  # reopen is maintainer-only
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _map(position: Position, name: str) -> None:
    cand = Candidate(brand_id=_BRAND, full_name=name, email=f"{name}@x.com".lower())
    await cand.insert()
    await Mapping(
        brand_id=_BRAND,
        candidate_id=cand.id,
        position_id=position.id,
        employee_id=_RECRUITER,
        stage=PipelineStage.sourced,
    ).insert()


def _assert_full_row(body: dict) -> None:
    for field, value in _FULL_ROW.items():
        assert body[field] == value, (field, body[field])


# ── The bug: fields accepted, then dropped ─────────────────────────────────────


async def test_editing_salary_and_mumbai_area_is_saved(api, position):
    res = await api.patch(
        f"{_URL}/{position.id}", json={"salary": "45k - 55k", "mumbai_area": "Bandra"}
    )

    assert res.status_code == 200, res.text
    assert (res.json()["salary"], res.json()["mumbai_area"]) == ("45k - 55k", "Bandra")
    stored = await Position.get(position.id)
    assert (stored.salary, stored.mumbai_area) == ("45k - 55k", "Bandra")


async def test_an_optional_field_can_be_cleared_with_null(api, position):
    res = await api.patch(f"{_URL}/{position.id}", json={"salary": None, "notes": None})

    assert res.status_code == 200, res.text
    stored = await Position.get(position.id)
    assert stored.salary is None
    assert stored.notes is None


async def test_omitted_fields_are_left_alone(api, position):
    res = await api.patch(f"{_URL}/{position.id}", json={"role": "Head Bartender"})

    assert res.status_code == 200, res.text
    stored = await Position.get(position.id)
    assert stored.role == "Head Bartender"
    assert (stored.salary, stored.mumbai_area, stored.notes) == (
        "30k - 40k",
        "Andheri",
        "Weekend shifts",
    )


async def test_a_required_field_cannot_be_cleared(api, position):
    for field in ("role", "department", "seniority", "requirements", "total_seats", "status"):
        res = await api.patch(f"{_URL}/{position.id}", json={field: None})
        assert res.status_code == 422, (field, res.text)

    stored = await Position.get(position.id)
    assert stored.role == "Bartender"
    assert stored.total_seats == 3


async def test_moving_out_of_mumbai_clears_the_mumbai_area(api, position):
    res = await api.patch(f"{_URL}/{position.id}", json={"city": "Pune"})

    assert res.status_code == 200, res.text
    stored = await Position.get(position.id)
    assert stored.city == "Pune"
    assert stored.mumbai_area is None


async def test_total_seats_still_recomputes_remaining(api, position):
    res = await api.patch(f"{_URL}/{position.id}", json={"total_seats": 5})

    assert res.status_code == 200, res.text
    assert (res.json()["total_seats"], res.json()["remaining_seats"]) == (5, 4)


async def test_assign_and_unassign(api, position):
    other = PydanticObjectId()
    res = await api.patch(f"{_URL}/{position.id}", json={"assigned_employee_id": str(other)})
    assert res.json()["assigned_employee_id"] == str(other)

    res = await api.patch(f"{_URL}/{position.id}", json={"assigned_employee_id": None})
    assert res.status_code == 200, res.text
    assert (await Position.get(position.id)).assigned_employee_id is None


async def test_a_bad_status_or_seniority_is_refused(api, position):
    for body in ({"status": "sort-of-open"}, {"seniority": "Principal"}):
        res = await api.patch(f"{_URL}/{position.id}", json=body)
        assert res.status_code == 422, (body, res.text)


async def test_approval_status_on_patch_is_still_ignored(api, position):
    """Approval has its own endpoint; PATCH never applied it and still doesn't."""
    res = await api.patch(f"{_URL}/{position.id}", json={"approval_status": "rejected"})

    assert res.status_code == 200, res.text
    assert (await Position.get(position.id)).approval_status == PositionApprovalStatus.approved


# ── The other half: responses that blanked the card ───────────────────────────


async def test_detail_update_and_reopen_return_the_whole_row(api, position):
    await _map(position, "Asha")
    await _map(position, "Ravi")

    detail = await api.get(f"{_URL}/{position.id}")
    updated = await api.patch(f"{_URL}/{position.id}", json={"notes": "Nights too"})
    await position.set({"status": PositionStatus.closed})
    reopened = await api.post(f"{_URL}/{position.id}/reopen")

    for res in (detail, updated, reopened):
        assert res.status_code == 200, res.text
        body = res.json()
        _assert_full_row(body)
        assert body["mapped_count"] == 2
        assert sorted(p["full_name"] for p in body["mapped_preview"]) == ["Asha", "Ravi"]


async def test_single_position_responses_match_the_list_row(api, position):
    """The page swaps a response in for its list row; they must agree field for field."""
    await _map(position, "Asha")

    [row] = (await api.get(_URL)).json()["items"]
    detail = (await api.get(f"{_URL}/{position.id}")).json()

    assert detail == row


async def test_a_legacy_candidate_row_does_not_break_the_response(api, position):
    """The preview reads names only, as the list does.

    A candidate written before a model change (here, a lowercase status the
    enum no longer accepts) fails full-document parsing. Loading whole
    Candidates for the preview turned every edit of its position into a 500 —
    after the write had already landed.
    """
    raw = await Candidate.get_motor_collection().insert_one(
        {"brand_id": _BRAND, "full_name": "Old Row", "status": "approved"}
    )
    await Mapping(
        brand_id=_BRAND,
        candidate_id=raw.inserted_id,
        position_id=position.id,
        employee_id=_RECRUITER,
        stage=PipelineStage.sourced,
    ).insert()

    detail = await api.get(f"{_URL}/{position.id}")
    updated = await api.patch(f"{_URL}/{position.id}", json={"salary": "50k"})

    for res in (detail, updated):
        assert res.status_code == 200, res.text
        assert [p["full_name"] for p in res.json()["mapped_preview"]] == ["Old Row"]
