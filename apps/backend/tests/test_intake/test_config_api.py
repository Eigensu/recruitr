"""Connecting the sheet from the settings screen, without a deploy.

The one thing this must never do is hand back the service-account key, which is
why it lives in the environment and not in the row these endpoints edit.
"""

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.recruitment.models import Employee, IntakeSourceConfig

_BRAND = PydanticObjectId()
_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1JMg0WtubG9lWeKSoWHsF7M2zOJfsgIWdBQYvOb0X0yM/edit?gid=0"
)
_SHEET_ID = "1JMg0WtubG9lWeKSoWHsF7M2zOJfsgIWdBQYvOb0X0yM"


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def staff(monkeypatch):
    """An admin and a maintainer, and an environment that configures nothing.

    The repo-root .env is real, so the env-derived defaults are pinned here
    rather than left to whatever the developer running this has set.
    """
    monkeypatch.setattr(settings, "INTAKE_SPREADSHEET_ID", "")
    monkeypatch.setattr(settings, "INTAKE_SHEET_RANGE", "Sheet1!A:U")
    monkeypatch.setattr(settings, "GOOGLE_SHEETS_ENABLED", False)
    monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    for name, role in (("chief", UserRole.admin), ("boss", UserRole.maintainer)):
        email = f"{name}@binge.consulting"
        await User(email=email, role=role).insert()
        await Employee(brand_id=_BRAND, name=name, email=email, role=role.value).insert()


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


# ── Reading ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unconfigured_brand_gets_a_form_not_a_404(http):
    res = await http.get("/api/v1/intake/config", headers=await _headers("boss"))

    assert res.status_code == 200
    body = res.json()
    # The screen shows what switching it on would use, rather than an error.
    assert body["configured"] is False
    assert body["enabled"] is False
    assert body["sheet_range"] == "Sheet1!A:U"
    assert body["telecaller_sla_hours"] == settings.TELECALLER_SLA_HOURS


@pytest.mark.asyncio
async def test_the_service_account_key_is_never_returned(http, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", '{"private_key":"SUPER-SECRET"}')

    res = await http.get("/api/v1/intake/config", headers=await _headers("boss"))

    assert "SUPER-SECRET" not in res.text
    # Only whether one exists, which is what the screen needs to say.
    assert res.json()["credentials_configured"] is True


@pytest.mark.asyncio
async def test_the_last_read_is_reported_so_a_silent_failure_is_visible(http):
    await IntakeSourceConfig(
        brand_id=_BRAND,
        spreadsheet_id=_SHEET_ID,
        enabled=True,
        last_error="403: caller does not have permission",
        consecutive_failures=7,
    ).insert()

    body = (await http.get("/api/v1/intake/config", headers=await _headers("boss"))).json()

    assert body["configured"] is True
    assert body["consecutive_failures"] == 7
    assert "permission" in body["last_error"]


# ── Writing ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_pasted_sheet_url_is_accepted_as_the_id(http):
    res = await http.put(
        "/api/v1/intake/config",
        json={"spreadsheet_id": _SHEET_URL},
        headers=await _headers("chief"),
    )

    # Everyone copies the address bar; storing that verbatim produces a 404 from
    # Google that reads like a permissions problem.
    assert res.json()["spreadsheet_id"] == _SHEET_ID
    assert (await IntakeSourceConfig.find_one({})).spreadsheet_id == _SHEET_ID


@pytest.mark.asyncio
async def test_a_bare_id_is_left_alone(http):
    res = await http.put(
        "/api/v1/intake/config", json={"spreadsheet_id": _SHEET_ID}, headers=await _headers("chief")
    )

    assert res.json()["spreadsheet_id"] == _SHEET_ID


@pytest.mark.asyncio
async def test_connecting_a_sheet_needs_an_id(http):
    res = await http.put(
        "/api/v1/intake/config", json={"enabled": True}, headers=await _headers("chief")
    )

    assert res.status_code == 400
    assert await IntakeSourceConfig.find_one({}) is None


@pytest.mark.asyncio
async def test_switching_it_on_stamps_the_line_between_history_and_live(http):
    headers = await _headers("chief")
    await http.put("/api/v1/intake/config", json={"spreadsheet_id": _SHEET_ID}, headers=headers)
    assert (await IntakeSourceConfig.find_one({})).activated_at is None

    res = await http.put("/api/v1/intake/config", json={"enabled": True}, headers=headers)

    # Everything in the sheet older than this is history, and history is
    # imported on purpose by the backfill script rather than assigned to
    # telecallers with an SLA clock already running.
    assert res.json()["activated_at"] is not None


@pytest.mark.asyncio
async def test_switching_it_off_and_on_again_does_not_move_the_line(http):
    headers = await _headers("chief")
    await http.put(
        "/api/v1/intake/config",
        json={"spreadsheet_id": _SHEET_ID, "enabled": True},
        headers=headers,
    )
    first = (await IntakeSourceConfig.find_one({})).activated_at

    await http.put("/api/v1/intake/config", json={"enabled": False}, headers=headers)
    await http.put("/api/v1/intake/config", json={"enabled": True}, headers=headers)

    # Re-stamping would skip every lead that arrived during the outage —
    # exactly the ones somebody still has to ring.
    assert (await IntakeSourceConfig.find_one({})).activated_at == first


@pytest.mark.asyncio
async def test_an_update_changes_only_what_it_sends(http):
    headers = await _headers("chief")
    await http.put(
        "/api/v1/intake/config",
        json={"spreadsheet_id": _SHEET_ID, "sheet_range": "Leads!A:U", "enabled": True},
        headers=headers,
    )

    res = await http.put(
        "/api/v1/intake/config", json={"sheet_range": "Form Responses 1!A:U"}, headers=headers
    )

    body = res.json()
    assert body["sheet_range"] == "Form Responses 1!A:U"
    assert body["spreadsheet_id"] == _SHEET_ID
    assert body["enabled"] is True


# ── Who may change it ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_maintainer_may_look_but_not_rewire(http):
    headers = await _headers("boss")

    assert (await http.get("/api/v1/intake/config", headers=headers)).status_code == 200
    changed = await http.put(
        "/api/v1/intake/config", json={"spreadsheet_id": _SHEET_ID}, headers=headers
    )

    assert changed.status_code == 403
    assert await IntakeSourceConfig.find_one({}) is None


@pytest.mark.asyncio
async def test_a_telecaller_cannot_reach_the_configuration(http):
    await User(email="caller@binge.consulting", role=UserRole.telecaller).insert()
    await Employee(
        brand_id=_BRAND, name="caller", email="caller@binge.consulting", role="telecaller"
    ).insert()
    headers = await _headers("caller")

    assert (await http.get("/api/v1/intake/config", headers=headers)).status_code == 403
    assert (
        await http.put("/api/v1/intake/config", json={"enabled": True}, headers=headers)
    ).status_code == 403
