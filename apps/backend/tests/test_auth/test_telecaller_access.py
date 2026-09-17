"""A telecaller reaches their own account and inbox, and no staff endpoint.

The role holds an Employee record and a brand like a recruiter, which is what
makes it dangerous: every staff endpoint was written when anything that got past
get_tenant was a recruiter. Nothing here overrides a dependency — each request
carries a real signed token, so the whole chain runs (JWT decode, User lookup,
Employee lookup, get_tenant / get_viewer / deny_outsiders). The sweep enumerates
routes from the OpenAPI schema rather than a hand-kept list, so an endpoint added
later that forgets its guard fails here instead of shipping.
"""

import re

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import NON_RECRUITER_ROLES, User, UserRole
from app.modules.auth.router import _post_login_path
from app.modules.auth.security import create_access_token
from app.modules.recruitment.enums import NotificationKind
from app.modules.recruitment.models import Employee, Notification

# Reachable by a telecaller on purpose: signing in and managing their own
# account, the public application form, the Cloudinary webhook (authenticated by
# its own signature, not by a login), and the notification inbox.
_ALLOWED_PREFIXES = ("/api/v1/auth/", "/api/v1/public/")
_ALLOWED_PATHS = {
    "/health",
    "/api/v1/storage/webhook/cloudinary",
    "/api/v1/notifications",
    "/api/v1/notifications/{notification_id}/read",
}

_PATH_PARAM = re.compile(r"\{[^}]+\}")
_BRAND = PydanticObjectId()


async def _sign_up(role: UserRole, email: str, *, with_employee: bool = True) -> Employee | None:
    """Insert the User (and, for staff-shaped roles, the Employee) a real login would have."""
    await User(email=email, role=role).insert()
    if not with_employee:
        return None
    employee = Employee(brand_id=_BRAND, name=email, email=email, role=role.value)
    await employee.insert()
    return employee


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _headers(email: str) -> dict[str, str]:
    user = await User.find_one({"email": email})
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# ── Containment ────────────────────────────────────────────────────────────────


def _guarded_operations() -> list[tuple[str, str]]:
    operations = []
    for path, methods in app.openapi()["paths"].items():
        if path.startswith(_ALLOWED_PREFIXES) or path in _ALLOWED_PATHS:
            continue
        operations.extend((method.upper(), path) for method in methods)
    return operations


def test_the_sweep_is_not_vacuous():
    # A route-discovery change (FastAPI 0.141 already moved included routers out
    # of app.routes) would otherwise make the sweep below pass by checking nothing.
    assert len(_guarded_operations()) > 80


@pytest.mark.asyncio
async def test_no_staff_endpoint_answers_a_telecaller(http: AsyncClient):
    await _sign_up(UserRole.telecaller, "caller@binge.consulting")
    headers = await _headers("caller@binge.consulting")

    reachable = []
    for method, path in _guarded_operations():
        url = _PATH_PARAM.sub(str(PydanticObjectId()), path)
        res = await http.request(method, url, headers=headers)
        if res.status_code != 403:
            reachable.append(f"{method} {path} -> {res.status_code}")

    assert not reachable, "Telecaller reached staff endpoints:\n" + "\n".join(reachable)


@pytest.mark.asyncio
async def test_a_recruiter_still_gets_past_the_same_guards(http: AsyncClient):
    # Without this, a get_tenant that refused everyone would pass the sweep.
    await _sign_up(UserRole.employee, "recruiter@binge.consulting")
    headers = await _headers("recruiter@binge.consulting")

    res = await http.get("/api/v1/candidates", headers=headers)

    assert res.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.client, UserRole.referee, UserRole.telecaller])
async def test_outsiders_cannot_fetch_an_upload_credential(http: AsyncClient, role: UserRole):
    email = f"{role.value}@example.com"
    await _sign_up(role, email, with_employee=role == UserRole.telecaller)

    res = await http.get("/api/v1/storage/sign", headers=await _headers(email))

    assert res.status_code == 403


# ── Inbox ──────────────────────────────────────────────────────────────────────


async def _notify(message: str, **fields) -> None:
    await Notification(
        brand_id=_BRAND, kind=NotificationKind.awaiting_decision, message=message, **fields
    ).insert()


@pytest_asyncio.fixture
async def inbox():
    caller = await _sign_up(UserRole.telecaller, "caller@binge.consulting")
    recruiter = await _sign_up(UserRole.employee, "recruiter@binge.consulting")

    await _notify("brand-wide")
    await _notify("to caller", employee_id=caller.id)
    await _notify("to recruiter", employee_id=recruiter.id)
    await _notify("to someone else", employee_id=PydanticObjectId())
    await _notify("to a client", client_id=PydanticObjectId())
    # Written before Notification.employee_id existed: the field is absent, not null.
    await Notification.get_motor_collection().insert_one(
        {
            "brand_id": _BRAND,
            "client_id": None,
            "kind": NotificationKind.awaiting_decision.value,
            "message": "legacy brand-wide",
        }
    )
    return {"caller": caller, "recruiter": recruiter}


async def _messages(http: AsyncClient, email: str) -> set[str]:
    res = await http.get("/api/v1/notifications", headers=await _headers(email))
    assert res.status_code == 200
    return {row["message"] for row in res.json()}


@pytest.mark.asyncio
async def test_a_telecaller_sees_only_rows_addressed_to_them(http: AsyncClient, inbox):
    assert await _messages(http, "caller@binge.consulting") == {"to caller"}


@pytest.mark.asyncio
async def test_a_recruiter_sees_brand_wide_and_their_own_rows(http: AsyncClient, inbox):
    assert await _messages(http, "recruiter@binge.consulting") == {
        "brand-wide",
        "legacy brand-wide",
        "to recruiter",
    }


@pytest.mark.asyncio
async def test_a_telecaller_cannot_mark_a_brand_wide_row_read(http: AsyncClient, inbox):
    headers = await _headers("caller@binge.consulting")
    brand_wide = await Notification.find_one({"message": "brand-wide"})
    own = await Notification.find_one({"message": "to caller"})

    refused = await http.post(f"/api/v1/notifications/{brand_wide.id}/read", headers=headers)
    allowed = await http.post(f"/api/v1/notifications/{own.id}/read", headers=headers)

    assert refused.status_code == 404
    assert allowed.status_code == 200


# ── Not a recruiter ────────────────────────────────────────────────────────────


def test_telecallers_are_excluded_from_recruiter_rosters():
    assert UserRole.telecaller.value in NON_RECRUITER_ROLES
    assert UserRole.employee.value not in NON_RECRUITER_ROLES


@pytest.mark.asyncio
async def test_employee_listing_hides_telecallers(http: AsyncClient):
    await _sign_up(UserRole.maintainer, "boss@binge.consulting")
    await _sign_up(UserRole.employee, "recruiter@binge.consulting")
    await _sign_up(UserRole.telecaller, "caller@binge.consulting")

    res = await http.get("/api/v1/teams/employees", headers=await _headers("boss@binge.consulting"))

    assert res.status_code == 200
    assert {row["email"] for row in res.json()} == {"recruiter@binge.consulting"}


# ── Login redirect ─────────────────────────────────────────────────────────────


def test_a_telecaller_lands_on_the_lead_queue():
    caller = User(email="caller@binge.consulting", role=UserRole.telecaller)

    assert _post_login_path(caller, has_brand=True, is_referee=False) == "/leads"
    # No brand yet: onboarding, the same as any other staff member.
    assert _post_login_path(caller, has_brand=False, is_referee=False) == "/onboarding"
