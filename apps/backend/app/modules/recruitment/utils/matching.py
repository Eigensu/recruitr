"""Keyword match scoring engine.

Score formula (per spec §5):
    score = |skills_normalized(candidate) ∩ requirements(position)| / |requirements(position)|

Returns 0..1.  A null score means the position has no requirements — the
frontend must hide the score ring entirely, never render 0%.
"""

from __future__ import annotations

from app.modules.recruitment.models import Candidate, Position
from app.modules.recruitment.schemas import TenantScope

# Aggregation operator constants
_MATCH = "$match"
_SORT = "$sort"
_LIMIT = "$limit"
_ADD_FIELDS = "$addFields"
_PROJECT = "$project"
_TO_STR = "$toString"


def compute_single_score(skills_normalized: list[str], requirements: list[str]) -> float | None:
    """Pure-Python intersection score for a single candidate.

    Used at map-time to snapshot the score without an extra DB round-trip.
    Returns None (not 0) when the position has no requirements.
    """
    if not requirements:
        return None
    reqs = {r.lower() for r in requirements}
    matched = len(reqs & set(skills_normalized))
    return matched / len(reqs)


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
    reqs = [r.lower() for r in (position.requirements or [])]

    match_stage: dict = {"brand_id": scope.brand_id, "is_active": True}
    if exclude_candidate_ids:
        match_stage["_id"] = {"$nin": exclude_candidate_ids}

    if reqs:
        score_field: dict = {
            "$divide": [
                {"$size": {"$setIntersection": ["$skills_normalized", reqs]}},
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

    return await (await Candidate.get_motor_collection().aggregate(pipeline)).to_list(None)
