"""Adding telecallers from the settings screen.

The bug this exists for: a telecaller promoted on their User alone stayed out of
the roster until they next signed in, because the roster reads Employee.role and
only login copies the role across. The endpoint writes both halves, and a person
provisioned before they have an account keeps the role through their sign-up.
"""

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.recruitment.models import Employee

_BRAND = PydanticObjectId()
_URL = "/api/v1/intake/telecallers"


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def staff(monkeypatch):
    # Pinned: the repo-root .env is real, and an agency domain set there would
    # let the sign-up test pass without the provisioned row doing any work.
    monkeypatch.setattr(settings, "AGENCY_EMAIL_DOMAINS", "")
    for name, role in (("chief", UserRole.admin), ("boss", UserRole.maintainer)):
        email = f"{name}@binge.consulting"
        await User(email=email, role=role).insert()
        await Employee(brand_id=_BRAND, name=name, email=email, role=role.value).insert()


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _roster(http) -> list[str]:
    res = await http.get("/api/v1/intake/assignees", headers=await _headers("boss"))
    return [person["email"] for person in res.json()["telecallers"]]


@pytest.mark.asyncio
async def test_a_user_promoted_only_on_their_account_joins_the_roster(http):
    # The state `migrate_user_roles promote` leaves behind before they sign in.
    await User(email="caller@gmail.com", role=UserRole.telecaller).insert()
    await Employee(brand_id=_BRAND, name="Caller", email="caller@gmail.com").insert()
    assert "caller@gmail.com" not in await _roster(http)

    res = await http.post(_URL, json={"email": "Caller@Gmail.com"}, headers=await _headers("chief"))

    assert res.status_code == 201
    assert res.json()["has_account"] is True
    assert "caller@gmail.com" in await _roster(http)


@pytest.mark.asyncio
async def test_a_recruiter_is_converted_on_both_records(http):
    await User(email="rec@binge.consulting", role=UserRole.employee).insert()
    await Employee(brand_id=_BRAND, name="Rec", email="rec@binge.consulting").insert()

    await http.post(_URL, json={"email": "rec@binge.consulting"}, headers=await _headers("chief"))

    user = await User.find_one({"email": "rec@binge.consulting"})
    employee = await Employee.find_one({"email": "rec@binge.consulting"})
    assert user.role == UserRole.telecaller
    assert employee.role == UserRole.telecaller.value


@pytest.mark.asyncio
async def test_someone_without_an_account_keeps_the_role_through_sign_up(http):
    res = await http.post(
        _URL, json={"email": "new@gmail.com", "name": "New Caller"}, headers=await _headers("chief")
    )
    assert res.status_code == 201
    assert res.json()["has_account"] is False
    assert res.json()["name"] == "New Caller"

    # Not on an agency domain: the provisioned row is what lets them in.
    signup = await http.post(
        "/api/v1/auth/signup", json={"email": "new@gmail.com", "password": "correct-horse"}
    )
    assert signup.status_code == 201

    user = await User.find_one({"email": "new@gmail.com"})
    employee = await Employee.find_one({"email": "new@gmail.com"})
    assert user.role == UserRole.telecaller
    # Sign-up syncs User.role onto the Employee; with the default role it
    # would have overwritten the telecaller just provisioned.
    assert employee.role == UserRole.telecaller.value
    assert employee.user_id == user.id
    assert "new@gmail.com" in await _roster(http)


@pytest.mark.asyncio
async def test_an_unprovisioned_sign_up_is_still_a_recruiter(http, monkeypatch):
    monkeypatch.setattr(settings, "AGENCY_EMAIL_DOMAINS", "binge.consulting")

    await http.post(
        "/api/v1/auth/signup", json={"email": "hire@binge.consulting", "password": "correct-horse"}
    )

    assert (await User.find_one({"email": "hire@binge.consulting"})).role == UserRole.employee


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["chief", "boss"])
async def test_management_cannot_be_demoted_by_mistake(http, name):
    res = await http.post(
        _URL, json={"email": f"{name}@binge.consulting"}, headers=await _headers("chief")
    )

    assert res.status_code == 409
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    assert user.role in (UserRole.admin, UserRole.maintainer)


@pytest.mark.asyncio
async def test_a_client_account_cannot_be_made_staff(http):
    await User(email="hr@employer.com", role=UserRole.client).insert()

    res = await http.post(_URL, json={"email": "hr@employer.com"}, headers=await _headers("chief"))

    assert res.status_code == 409
    assert await Employee.find_one({"email": "hr@employer.com"}) is None


@pytest.mark.asyncio
async def test_another_workspace_s_employee_is_left_alone(http):
    await Employee(brand_id=PydanticObjectId(), name="Theirs", email="theirs@x.com").insert()

    res = await http.post(_URL, json={"email": "theirs@x.com"}, headers=await _headers("chief"))

    assert res.status_code == 409
    assert (await Employee.find_one({"email": "theirs@x.com"})).role == "employee"


@pytest.mark.asyncio
async def test_only_an_admin_can_add_one(http):
    res = await http.post(_URL, json={"email": "x@gmail.com"}, headers=await _headers("boss"))

    assert res.status_code == 403
    assert await Employee.find_one({"email": "x@gmail.com"}) is None


@pytest.mark.asyncio
async def test_pausing_takes_them_out_of_the_rotation_but_not_the_list(http):
    added = (
        await http.post(_URL, json={"email": "p@gmail.com"}, headers=await _headers("chief"))
    ).json()

    res = await http.patch(
        f"{_URL}/{added['id']}", json={"is_active": False}, headers=await _headers("chief")
    )

    assert res.status_code == 200
    assert res.json()["is_active"] is False
    assert "p@gmail.com" not in await _roster(http)
    listed = (await http.get(_URL, headers=await _headers("boss"))).json()
    assert [(row["email"], row["is_active"]) for row in listed] == [("p@gmail.com", False)]

    # Adding them again is how you would expect to undo it, so it resumes too.
    await http.post(_URL, json={"email": "p@gmail.com"}, headers=await _headers("chief"))
    assert "p@gmail.com" in await _roster(http)


@pytest.mark.asyncio
async def test_pause_only_reaches_telecallers_in_this_brand(http):
    recruiter = Employee(brand_id=_BRAND, name="Rec", email="rec@binge.consulting")
    await recruiter.insert()

    res = await http.patch(
        f"{_URL}/{recruiter.id}", json={"is_active": False}, headers=await _headers("chief")
    )

    assert res.status_code == 404
    assert (await Employee.get(recruiter.id)).is_active is True
