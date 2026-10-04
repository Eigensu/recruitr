"""The Sheets read: every failure must arrive as one of the two errors the poll records.

The poll writes last_error and consecutive_failures only for SheetReadError and
SheetConfigurationError. Anything else escapes the Celery task and leaves the
admin banner saying "Last synced …" while nothing is being read. No network:
the token and the HTTP transport are both stubbed.
"""

import httpx
import pytest

from app.modules.recruitment.utils import google_sheets
from app.modules.recruitment.utils.google_sheets import SheetReadError, fetch_values


@pytest.fixture(autouse=True)
def init_test_db():
    """Shadow conftest's autouse fixture; these tests touch no database."""
    return None


@pytest.fixture
def token(monkeypatch):
    async def _token() -> str:
        return "t0ken"

    monkeypatch.setattr(google_sheets._tokens, "token", _token)


def _transport(monkeypatch, handler) -> None:
    real = httpx.AsyncClient

    def _client(**kwargs):
        return real(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(google_sheets.httpx, "AsyncClient", _client)


@pytest.mark.asyncio
async def test_a_network_failure_is_a_read_error(token, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    _transport(monkeypatch, handler)

    with pytest.raises(SheetReadError, match="Could not reach"):
        await fetch_values("sheet-id", "Sheet1!A:U")


@pytest.mark.asyncio
async def test_a_token_failure_is_a_read_error(monkeypatch):
    async def _token() -> str:
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(google_sheets._tokens, "token", _token)

    with pytest.raises(SheetReadError, match="access token"):
        await fetch_values("sheet-id", "Sheet1!A:U")


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_read_error(token, monkeypatch):
    _transport(monkeypatch, lambda request: httpx.Response(200, text="<html>"))

    with pytest.raises(SheetReadError, match="not JSON"):
        await fetch_values("sheet-id", "Sheet1!A:U")


@pytest.mark.asyncio
async def test_a_tab_name_with_url_characters_stays_in_the_path(token, monkeypatch):
    seen: list[httpx.URL] = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, json={"values": [["a"]]})

    _transport(monkeypatch, handler)

    assert await fetch_values("sheet-id", "Leads #2 / Q3?!A:U") == [["a"]]
    # Unescaped, the '#' would have cut the path and Google would have 404'd.
    path = seen[0].raw_path.decode()
    assert "/values/Leads%20%232%20%2F%20Q3%3F%21A%3AU?" in path
