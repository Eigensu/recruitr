"""Keyword match scoring engine.

Score formula (per spec §5):
    score = |skills_normalized(candidate) ∩ requirements(position)| / |requirements(position)|

Returns 0..1.  A null score means the position has no requirements — the
frontend must hide the score ring entirely, never render 0%.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.modules.recruitment.models import Candidate, Position
from app.modules.recruitment.schemas import TenantScope

logger = logging.getLogger(__name__)

# Aggregation operator constants
_MATCH = "$match"
_SORT = "$sort"
_LIMIT = "$limit"
_ADD_FIELDS = "$addFields"
_PROJECT = "$project"
_TO_STR = "$toString"

_STOPWORDS = {
    "senior",
    "junior",
    "head",
    "manager",
    "executive",
    "lead",
    "chief",
    "assistant",
    "associate",
    "specialist",
    "coordinator",
    "director",
}

_ROLE_KEYWORDS_FILE = Path(__file__).parent / "role_keywords.json"
_ROLE_KEYWORDS_CACHE: dict[str, list[str]] = {}


def _load_role_keywords() -> dict[str, list[str]]:
    global _ROLE_KEYWORDS_CACHE
    if _ROLE_KEYWORDS_CACHE:
        return _ROLE_KEYWORDS_CACHE
    if not _ROLE_KEYWORDS_FILE.exists():
        logger.warning(
            "role_keywords.json missing at %s — role keyword defaults will be used",
            _ROLE_KEYWORDS_FILE,
        )
        return _ROLE_KEYWORDS_CACHE
    try:
        with open(_ROLE_KEYWORDS_FILE) as f:
            _ROLE_KEYWORDS_CACHE = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.exception("Failed to load %s", _ROLE_KEYWORDS_FILE)
    return _ROLE_KEYWORDS_CACHE


def _get_effective_requirements(position: Position | Any) -> list[str]:
    """Returns explicit reqs, mapped keywords, tokenized role, or empty."""
    if getattr(position, "requirements", None):
        return [r.lower().strip() for r in position.requirements if r.strip()]

    role = getattr(position, "role", "")
    if not role:
        return []

    role_lower = role.lower().strip()

    # Tier 2 fallback: Predefined role keywords from JSON
    role_map = _load_role_keywords()
    if role_lower in role_map:
        return role_map[role_lower]

    # Tier 3 fallback: Tokenized role
    tokens = re.split(r"\W+", role_lower)
    tokens = [t for t in tokens if t and t not in _STOPWORDS]
    if tokens:
        return list(set(tokens))

    return []


def compute_single_score(skills_normalized: list[str], position: Position) -> float | None:
    """Pure-Python intersection score for a single candidate.

    Used at map-time to snapshot the score without an extra DB round-trip.
    Returns None when the position has no explicit requirements and no valid role tokens.
    """
    reqs = _get_effective_requirements(position)
    if not reqs:
        return None

    reqs_set = set(reqs)
    skills_set = set(skills_normalized or [])
    matched = len(reqs_set & skills_set)
    return matched / len(reqs_set)


async def top_candidates(
    *,
    scope: TenantScope,
    position: Position,
    limit: int = 10,
    exclude_candidate_ids: list | None = None,
) -> list[dict]:
    """Return up to `limit` candidates ranked by keyword intersection score.

    The aggregation runs on the `candidates` collection — no Python-side scoring.
    Returns list of dicts with keys: id, full_name, email, phone, previous_company,
    experience_years, skills, resume_url, match_score (float | None).
    """
    reqs = _get_effective_requirements(position)

    match_stage: dict = {"brand_id": scope.brand_id, "is_active": True}
    if exclude_candidate_ids:
        match_stage["_id"] = {"$nin": exclude_candidate_ids}

    if reqs:
        score_field: dict = {
            "$divide": [
                {"$size": {"$setIntersection": [{"$ifNull": ["$skills_normalized", []]}, reqs]}},
                len(reqs),
            ]
        }
        sort_stage = {_SORT: {"match_score": -1, "experience_years": -1}}
        filter_stage = {_MATCH: {"match_score": {"$gt": 0}}}
    else:
        score_field = {"$literal": None}  # type: ignore[assignment]
        sort_stage = {_SORT: {"experience_years": -1, "created_at": -1}}
        filter_stage = {_MATCH: {}}

    pipeline = [
        {_MATCH: match_stage},
        {
            _ADD_FIELDS: {
                "match_score": {
                    "$cond": {
                        "if": {"$gt": [len(reqs), 0]},
                        "then": score_field,
                        "else": None,
                    }
                }
            }
        },
        filter_stage,
        sort_stage,
        {_LIMIT: limit},
        {
            _PROJECT: {
                "id": {_TO_STR: "$_id"},
                "full_name": 1,
                "email": 1,
                "phone": 1,
                "previous_company": 1,
                "experience_years": 1,
                "skills": 1,
                "resume_url": 1,
                "match_score": 1,
            }
        },
    ]

    cursor = Candidate.get_motor_collection().aggregate(pipeline)
    return await cursor.to_list(None)
