"""Removing a referee from the settings screen.

The endpoint called to_object_id without its field name, so every removal
500'd and the referee kept their access.
"""

import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.models import RefereeUser
from tests.staff import auth_headers, make_staff

_BRAND = PydanticObjectId()
_URL = "/api/v1/referees"


@pytest_asyncio.fixture(autouse=True)
async def staff(init_test_db):
    await make_staff(_BRAND, "chief", UserRole.admin)


async def test_removing_a_referee_revokes_their_access(http):
    referee = RefereeUser(brand_id=_BRAND, email="ref@gmail.com")
    await referee.insert()

    res = await http.delete(f"{_URL}/{referee.id}", headers=await auth_headers("chief"))

    assert res.status_code == 204, res.text
    assert (await RefereeUser.get(referee.id)).is_active is False


async def test_another_workspace_s_referee_is_not_found(http):
    theirs = RefereeUser(brand_id=PydanticObjectId(), email="ref@gmail.com")
    await theirs.insert()

    res = await http.delete(f"{_URL}/{theirs.id}", headers=await auth_headers("chief"))

    assert res.status_code == 404
    assert (await RefereeUser.get(theirs.id)).is_active is True
