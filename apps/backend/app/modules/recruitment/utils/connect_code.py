"""The referee's connect code — the string an applicant types to credit a referral.

Generated once per referee at invite time and shown to them in the referee
portal. `public_apply` looks a candidate's submitted code up against every brand,
so codes are unique globally rather than within a brand.

The alphabet drops the characters that get misread when a code is copied off a
screen or read out loud (O/0, I/1/L), which is why it is 31 characters and not
36.
"""

from __future__ import annotations

import secrets

from pymongo.errors import DuplicateKeyError

from app.modules.recruitment.models import RefereeUser

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LENGTH = 8
_MAX_ATTEMPTS = 5


def generate_connect_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


async def ensure_connect_code(referee: RefereeUser) -> str | None:
    """Return the referee's code, minting and persisting one if the row has none.

    Referees provisioned before the field existed have no code, and without one
    the portal has nothing to show and no referral can be attributed to them.
    Rather than making every referee wait on the backfill script, the first
    request that needs the code fills it in. Idempotent, so concurrent logins
    settle on whichever write lands first.

    Returns None if a code could not be assigned. Callers are auth paths: a
    referee with no code yet must still be able to sign in, so a failure here
    degrades the portal rather than locking the account out.
    """
    if referee.connect_code:
        return referee.connect_code

    for _ in range(_MAX_ATTEMPTS):
        code = generate_connect_code()
        try:
            await referee.set({"connect_code": code})
        except DuplicateKeyError:
            continue  # 1-in-8e11 collision with a live code; draw again
        referee.connect_code = code
        return code
    return None
