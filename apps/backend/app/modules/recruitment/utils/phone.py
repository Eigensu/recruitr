"""Reducing a typed phone number to something two records can be compared on."""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"\D")

# Indian mobile numbers are 10 digits. Anything longer is a country code, a
# trunk prefix, or both, and anything shorter is not a number we can match on.
_LOCAL_LENGTH = 10


def normalize_phone(raw: str | None) -> str | None:
    """The last 10 digits of a phone number, or None if there are fewer.

    The same person reaches us as "+919876543210", "919876543210",
    "09876543210" and "98765 43210", and a lead has to be recognised as someone
    already in the pool however they typed it. Taking the last 10 digits
    collapses every one of those to "9876543210" without a phone-number library
    or a guess about which country code was omitted.

    Returning None rather than a short string matters: a blank cell, "n/a" and
    "12345" must never compare equal to each other, which is exactly what a
    "whatever digits are here" fallback would do.
    """
    if not raw:
        return None
    digits = _NON_DIGITS.sub("", raw)
    if len(digits) < _LOCAL_LENGTH:
        return None
    return digits[-_LOCAL_LENGTH:]
