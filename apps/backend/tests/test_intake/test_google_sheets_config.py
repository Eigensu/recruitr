"""Reading the service-account key out of configuration.

No network: this covers the part that fails on a Friday deploy — a key pasted
into an environment variable in the wrong shape — and the error messages that
have to say what to do about it.
"""

import base64
import json

import pytest

from app.core.config import settings
from app.modules.recruitment.utils.google_sheets import (
    SheetConfigurationError,
    credentials_info,
)

_KEY = {
    "type": "service_account",
    "client_email": "intake@example.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
}


@pytest.fixture(autouse=True)
def init_test_db():
    """Shadow conftest's autouse fixture; these tests touch no database."""
    yield


@pytest.fixture
def key(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", value)

    return _set


def test_raw_json_is_accepted(key):
    key(json.dumps(_KEY))

    assert credentials_info()["client_email"] == _KEY["client_email"]


def test_base64_is_accepted(key):
    # The raw key is multi-line JSON wrapping a PEM block, which several
    # platforms will not hold in an environment variable intact.
    key(base64.b64encode(json.dumps(_KEY).encode()).decode())

    assert credentials_info()["client_email"] == _KEY["client_email"]


def test_whitespace_around_the_value_is_tolerated(key):
    key(f"  {json.dumps(_KEY)}\n")

    assert credentials_info()["private_key"] == _KEY["private_key"]


def test_an_unset_key_says_how_to_set_it_up(key):
    key("")

    with pytest.raises(SheetConfigurationError) as error:
        credentials_info()

    # The share step is the one people miss, and it fails as a 403 later.
    assert "share the spreadsheet" in str(error.value).lower()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("{not json at all", "not valid json"),
        ("!!!!not base64!!!!", "neither json nor valid base64"),
    ],
)
def test_an_unusable_key_is_refused_with_a_reason(key, value: str, expected: str):
    key(value)

    with pytest.raises(SheetConfigurationError) as error:
        credentials_info()

    assert expected in str(error.value).lower()


def test_a_key_missing_its_fields_is_refused(key):
    key(json.dumps({"type": "service_account"}))

    with pytest.raises(SheetConfigurationError) as error:
        credentials_info()

    assert "client_email" in str(error.value)
    assert "private_key" in str(error.value)
