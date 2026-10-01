"""A recruiter's dashboard shows what they are part of, and nothing about anyone else.

Part of = a mapping on a position assigned to them, a mapping they last acted
on, or one they moved at any point (stage history); positions = assigned to
them or holding such a mapping; activity = their own. Signed in with real
tokens, like the intake tests, so the role checks run as they do in the app.
"""

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.dashboard.schemas import DashboardFilters
from app.modules.dashboard.services.service import _cache_key
from app.modules.recruitment.enums import ActivityType, PipelineStage
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    Client,
    Employee,
    Mapping,
    Position,
    StageEvent,
)

_BRAND = PydanticObjectId()
_URL = "/api/v1/dashboard"


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _staff(name: str, role: UserRole) -> Employee:
    email = f"{name}@binge.consulting"
    await User(email=email, role=role).insert()
    employee = Employee(brand_id=_BRAND, name=name, email=email, role=role.value)
    await employee.insert()
    return employee


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _position(code: str, assigned: Employee | None, client: Client) -> Position:
    doc = Position(
        brand_id=_BRAND,
        code=code,
        client_id=client.id,
        client_name=client.name,
        role="Bartender",
        total_seats=2,
        remaining_seats=2,
        assigned_employee_id=assigned.id if assigned else None,
    )
    await doc.insert()
    return doc


async def _mapping(
    name: str, position: Position, last: Employee, *, moved_by: list[Employee] = ()
) -> Mapping:
    candidate = Candidate(brand_id=_BRAND, full_name=name, email=f"{name}@x.com".lower())
    await candidate.insert()
    doc = Mapping(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        position_id=position.id,
        client_id=position.client_id,
        employee_id=last.id,
        stage=PipelineStage.sent_to_client,
        history=[
            StageEvent(stage=PipelineStage.sent_to_client, by_employee_id=e.id) for e in moved_by
        ],
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def world(init_test_db):
    rae = await _staff("rae", UserRole.employee)  # the recruiter under test
    sam = await _staff("sam", UserRole.employee)
    await _staff("mona", UserRole.maintainer)
    client = Client(brand_id=_BRAND, code="C1", name="Hunger Inc")
    await client.insert()

    p1 = await _position("P1", rae, client)  # Rae's
    p2 = await _position("P2", sam, client)  # Sam's — Rae worked one candidate on it
    p3 = await _position("P3", sam, client)  # nothing to do with Rae

    await _mapping("OnRaesPosition", p1, last=sam, moved_by=[sam])  # counts: assigned
    await _mapping("RaeLastMoved", p2, last=rae, moved_by=[rae])  # counts: last actor
    await _mapping("RaeMovedEarlier", p2, last=sam, moved_by=[rae, sam])  # counts: history
    await _mapping("NeverTouched", p2, last=sam, moved_by=[sam])  # doesn't
    await _mapping("OtherPosition", p3, last=sam, moved_by=[sam])  # doesn't

    for who, n in ((rae, 2), (sam, 3)):
        for i in range(n):
            await ActivityLog(
                brand_id=_BRAND,
                employee_id=who.id,
                activity_type=ActivityType.mapped,
                target_entity_type="candidate",
                target_entity_id=f"{who.name}-{i}",
                description=f"{who.name} mapped someone",
            ).insert()
    return {"rae": rae, "sam": sam, "p1": p1, "p2": p2, "p3": p3}


async def _get(http, path: str, who: str, **params):
    res = await http.get(f"{_URL}{path}", params=params, headers=await _headers(who))
    assert res.status_code == 200, (path, res.text)
    return res.json()


async def test_the_pipeline_counts_only_what_the_recruiter_is_part_of(http, world):
    body = await _get(http, "/pipeline", "rae")
    assert body["total_candidates"] == 3


async def test_the_overview_scopes_positions_and_candidates(http, world):
    summary = (await _get(http, "/overview", "rae"))["summary"]
    assert summary["open_positions"] == 2  # P1 (assigned) and P2 (worked a candidate)
    assert summary["candidates_in_pipeline"] == 3


async def test_asking_for_a_colleague_returns_your_own_numbers(http, world):
    sam = str(world["sam"].id)
    assert (await _get(http, "/pipeline", "rae", employee_id=sam))["total_candidates"] == 3
    mine = await _get(http, "/activity", "rae", employee_id=sam)
    assert {row["employee_id"] for row in mine["items"]} == {str(world["rae"].id)}
    assert len(mine["items"]) == 2


async def test_mappings_and_clients_are_scoped_too(http, world):
    mappings = await _get(http, "/mappings", "rae")
    assert mappings["meta"]["total"] == 3
    clients = await _get(http, "/clients", "rae")
    assert {row["id"] for row in clients["items"]} == {str(world["p1"].id), str(world["p2"].id)}


async def test_a_recruiter_with_nothing_sees_zeros_not_everything(http, world):
    await _staff("newbie", UserRole.employee)
    assert (await _get(http, "/pipeline", "newbie"))["total_candidates"] == 0
    assert (await _get(http, "/overview", "newbie"))["summary"]["open_positions"] == 0
    assert (await _get(http, "/clients", "newbie"))["items"] == []


@pytest.mark.parametrize("path", ["/employees", "/client-profiles", "/sourcing", "/candidates"])
async def test_brand_wide_reports_are_closed_to_recruiters(http, world, path):
    res = await http.get(f"{_URL}{path}", headers=await _headers("rae"))
    assert res.status_code == 403, res.text
    res = await http.get(f"{_URL}{path}", headers=await _headers("mona"))
    assert res.status_code == 200, res.text


async def test_a_maintainer_still_sees_the_whole_brand_and_can_filter(http, world):
    assert (await _get(http, "/pipeline", "mona"))["total_candidates"] == 5
    assert (await _get(http, "/overview", "mona"))["summary"]["open_positions"] == 3
    sam = str(world["sam"].id)
    # The filter is still "who last acted", as before — it isn't the scope.
    assert (await _get(http, "/pipeline", "mona", employee_id=sam))["total_candidates"] == 4


@pytest.mark.no_db
def test_two_recruiters_never_share_a_cache_entry():
    common = {"brand_id": str(_BRAND)}
    a = DashboardFilters(**common, scope_employee_id="a", scope_position_ids=["p1"])
    b = DashboardFilters(**common, scope_employee_id="b", scope_position_ids=["p1"])
    whole_brand = DashboardFilters(**common)
    keys = {_cache_key("overview", f) for f in (a, b, whole_brand)}
    assert len(keys) == 3
