"""Who is allowed to hold a staff account in the agency workspace.

Access used to be a side effect: `ensure_employee_for_user` assigned the sole
existing brand to any user who had none, and sign-up was open to the world. Any
address that reached the sign-up page therefore ended up with full recruiter
access to every candidate, position and client.

Two ways in now, and nothing else:

  - the address is on a domain in AGENCY_EMAIL_DOMAINS, or
  - an Employee row for the address already carries a brand_id, i.e. somebody
    provisioned it deliberately.

The second is what keeps existing staff working after this gate turned on, and
is the manual escape hatch while there is no invite endpoint.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Message shown to a refused address. Deliberately says nothing about which
# domains are allowed — that is a hint to anyone probing the sign-up form.
NOT_AUTHORIZED = (
    "This email is not authorized for this workspace. Ask an administrator to invite you."
)


def email_domain(email: str) -> str:
    """The bare domain of an address, lowercased. Empty when there is no '@'."""
    _, _, domain = email.strip().lower().rpartition("@")
    return domain


def is_agency_email(email: str) -> bool:
    """True if the address belongs to a configured staff domain."""
    domains = settings.staff_domains
    if not domains:
        return False
    return email_domain(email) in domains


async def has_provisioned_employee(email: str) -> bool:
    """True if somebody already gave this address a workspace.

    Imported lazily: this module is pulled in by the auth router, and the
    recruitment models import back through the dependency chain.
    """
    from app.modules.recruitment.models import Employee

    employee = await Employee.find_one({"email": email.strip().lower()})
    return employee is not None and employee.brand_id is not None


async def may_hold_staff_account(email: str) -> bool:
    """Whether this address may be given, or keep, agency access."""
    return is_agency_email(email) or await has_provisioned_employee(email)


async def find_client_authorization(email: str):
    """The active ClientUser grant for this address, if an admin created one.

    Returns the row rather than a bool: callers need its client_id to record the
    link at login. Revoked grants (is_active False) do not match, so revoking
    one shuts the account out on its next sign-in.
    """
    from app.modules.recruitment.models import ClientUser

    return await ClientUser.find_one({"email": email.strip().lower(), "is_active": True})


async def find_referee_authorization(email: str):
    """The active RefereeUser grant for this address, if an admin created one."""
    from app.modules.recruitment.models import RefereeUser

    return await RefereeUser.find_one({"email": email.strip().lower(), "is_active": True})


async def may_sign_in(email: str) -> tuple[bool, bool, bool]:
    """(allowed, is_client, is_referee) for an address arriving at sign-up or OAuth.

    Staff is checked first: an agency address that also appears on a client's
    contact list stays staff rather than being demoted to a client account.
    """
    if await may_hold_staff_account(email):
        return True, False, False
    if await find_client_authorization(email) is not None:
        return True, True, False
    if await find_referee_authorization(email) is not None:
        return True, False, True
    return False, False, False


def warn_if_unconfigured() -> None:
    """Log once at startup if no staff domain is set.

    Worth shouting about: the deployment is secure but cannot onboard anyone,
    and the failure otherwise shows up as a confusing refusal at sign-up.
    """
    if not settings.staff_domains:
        logger.warning(
            "AGENCY_EMAIL_DOMAINS is not set. No new staff account can be "
            "created — sign-up and Google OAuth will refuse every address that "
            "does not already have an Employee record with a brand. Set it to "
            "your agency's email domain(s), comma-separated, to allow sign-ups."
        )
