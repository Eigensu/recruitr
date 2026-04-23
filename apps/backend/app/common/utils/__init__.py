"""Shared utility functions used across modules."""

import re
from datetime import date, datetime


def normalize_skill(skill: str) -> str:
    """Lowercase, strip, and collapse whitespace for consistent skill matching."""
    return re.sub(r"\s+", " ", skill.strip().lower())


def normalize_skills(skills: list[str]) -> list[str]:
    """Normalize a list of skills, deduplicating in order."""
    seen: set[str] = set()
    result = []
    for skill in skills:
        normalized = normalize_skill(skill)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def is_same_day(dt: datetime) -> bool:
    """Return True if the given datetime is on today's calendar date."""
    return dt.date() == date.today()


def utcnow() -> datetime:
    """Return the current UTC time (single source of truth to avoid tz bugs)."""
    return datetime.utcnow()


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text)
