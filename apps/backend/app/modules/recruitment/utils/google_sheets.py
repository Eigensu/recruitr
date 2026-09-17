"""Reading a range out of a Google Sheet with a service account.

`google-auth` mints and signs the service-account assertion; the Sheets call
itself is one HTTP GET through httpx, which the app already depends on.

`gspread` would have been fewer lines and was rejected: it is synchronous, so
every call would either block the event loop or need wrapping in a thread, and
it pulls a second HTTP stack in for one GET. The token refresh below *is*
blocking — it is `google-auth`'s only interface — so it runs in a worker thread.

Read-only by design. The service account is granted
`spreadsheets.readonly`, so no code path here can modify the advertiser's
sheet, whatever a later caller asks for.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
_VALUES_URL = "https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range}"
_TIMEOUT = httpx.Timeout(30.0)
# Refresh a little before expiry rather than on it, so a token cannot lapse
# between the check and the request going out.
_EXPIRY_MARGIN = timedelta(seconds=60)


class SheetConfigurationError(RuntimeError):
    """The integration is not configured, or is configured with something unusable.

    Distinct from a transport failure: this never succeeds on retry, so the poll
    reports it and stops rather than backing off.
    """


class SheetReadError(RuntimeError):
    """The Sheets API refused or failed the read. Retryable."""


def credentials_info() -> dict[str, Any]:
    """The service-account JSON from settings, accepting raw or base64.

    Public because the admin configuration screen needs to answer "are the
    credentials usable?" without attempting a read of someone's spreadsheet.

    Base64 is supported because the raw key is multi-line JSON containing a PEM
    private key, which several deployment platforms cannot hold in an
    environment variable intact.
    """
    raw = (settings.GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
    if not raw:
        raise SheetConfigurationError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set. Create a service account, enable the "
            "Google Sheets API, and share the spreadsheet with the service account's email."
        )

    if not raw.startswith("{"):
        try:
            raw = base64.b64decode(raw, validate=True).decode()
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise SheetConfigurationError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is neither JSON nor valid base64."
            ) from exc

    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SheetConfigurationError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    missing = {"client_email", "private_key"} - info.keys()
    if missing:
        raise SheetConfigurationError(
            f"Service account JSON is missing {', '.join(sorted(missing))}."
        )
    return info


class _TokenCache:
    """One access token, reused until it is nearly expired.

    The poll runs every few minutes and each run needs one token; minting a
    fresh one per request would add a signed round-trip to Google for nothing.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = asyncio.Lock()

    def _is_valid(self) -> bool:
        return bool(
            self._token
            and self._expires_at
            and datetime.now(UTC) < self._expires_at - _EXPIRY_MARGIN
        )

    async def token(self) -> str:
        async with self._lock:
            if self._is_valid():
                return self._token  # type: ignore[return-value]

            info = credentials_info()
            try:
                # Imported here, not at module import: this module is reachable
                # from the app's import graph, and a deployment that never
                # enables the integration should not need the package present.
                from google.auth.transport.requests import Request
                from google.oauth2 import service_account
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise SheetConfigurationError(
                    "google-auth is not installed; see requirements.txt."
                ) from exc

            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=[SHEETS_SCOPE]
            )
            # Blocking, and the only API google-auth offers.
            await asyncio.to_thread(credentials.refresh, Request())

            self._token = credentials.token
            expiry = credentials.expiry
            # google-auth returns a naive UTC expiry.
            self._expires_at = expiry.replace(tzinfo=UTC) if expiry else None
            if not self._token:
                raise SheetConfigurationError("Google returned no access token.")
            return self._token

    def clear(self) -> None:
        self._token = None
        self._expires_at = None


_tokens = _TokenCache()


async def fetch_values(spreadsheet_id: str, sheet_range: str) -> list[list[str]]:
    """Rows of a sheet range, first row included, as strings.

    Google omits trailing empty cells, so rows come back ragged and shorter
    than the header row; callers must read cells by index rather than zipping
    against the headers. See lead_sheet.parse_rows.
    """
    if not spreadsheet_id:
        raise SheetConfigurationError("No spreadsheet configured.")

    token = await _tokens.token()
    url = _VALUES_URL.format(spreadsheet_id=spreadsheet_id, range=sheet_range)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            # Formatted values, so a number typed into a cell arrives as it is
            # displayed rather than as a float, and dates keep their text form.
            params={"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE"},
        )

    if response.status_code == httpx.codes.UNAUTHORIZED:
        # A revoked or rotated key: drop the cached token so the next attempt
        # mints a new one instead of replaying the dead one until expiry.
        _tokens.clear()
        raise SheetReadError("Google rejected the credentials (401).")
    if response.status_code == httpx.codes.FORBIDDEN:
        raise SheetConfigurationError(
            "Google returned 403. Share the spreadsheet with the service account's "
            "client_email as a Viewer, and check the Sheets API is enabled."
        )
    if response.status_code == httpx.codes.NOT_FOUND:
        raise SheetConfigurationError(
            f"No sheet {spreadsheet_id!r} with range {sheet_range!r}. Check the id and tab name."
        )
    if response.status_code >= httpx.codes.BAD_REQUEST:
        raise SheetReadError(f"Sheets API returned {response.status_code}: {response.text[:200]}")

    values = response.json().get("values", [])
    return [[str(cell) for cell in row] for row in values]
