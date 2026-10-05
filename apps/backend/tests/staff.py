"""Staff who sign in with real tokens.

Tests that use these go through the role guards as production runs them,
instead of overriding get_tenant or get_viewer, so a wrong guard fails the
test rather than being assumed.
"""

from typing import Any

from beanie import PydanticObjectId

from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.recruitment.models import Employee

_DOMAIN = "binge.consulting"


async def make_staff(
    brand_id: PydanticObjectId,
    name: str,
    role: UserRole,
    *,
    display_name: str | None = None,
    **employee: Any,
) -> Employee:
    """A User and Employee in `role`, signing in as `name`@binge.consulting.

    The Employee is called `display_name`, or `name` when that's not given;
    extra fields go on the Employee.
    """
    email = f"{name}@{_DOMAIN}"
    await User(email=email, role=role).insert()
    doc = Employee(
        brand_id=brand_id, name=display_name or name, email=email, role=role.value, **employee
    )
    await doc.insert()
    return doc


async def auth_headers(name: str) -> dict[str, str]:
    """Bearer headers for the staff member make_staff created as `name`."""
    user = await User.find_one({"email": f"{name}@{_DOMAIN}"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}
