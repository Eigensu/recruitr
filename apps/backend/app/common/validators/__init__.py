"""Reusable validators for request data."""

import re


def validate_domain(domain: str) -> str:
    """Validate and normalise a brand domain (e.g. 'acme.com')."""
    domain = domain.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
    pattern = r"^([a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
    if not re.match(pattern, domain):
        raise ValueError(f"'{domain}' is not a valid domain name.")
    return domain


def validate_skill_list(skills: list[str]) -> list[str]:
    """Reject empty strings and cap list at 50 skills."""
    cleaned = [s.strip() for s in skills if s.strip()]
    if len(cleaned) > 50:
        raise ValueError("A maximum of 50 skills is allowed per record.")
    return cleaned


def validate_phone(phone: str | None) -> str | None:
    """Basic E.164-ish phone validation (optional field)."""
    if phone is None:
        return None
    digits = re.sub(r"\D", "", phone)
    if not (7 <= len(digits) <= 15):
        raise ValueError("Phone number must be between 7 and 15 digits.")
    return phone.strip()
