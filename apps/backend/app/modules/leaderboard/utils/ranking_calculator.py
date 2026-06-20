import math

from app.modules.leaderboard.enums import ActivityTypeEnum

JOINED_POINTS = 15
OFFER_POINTS = 8
MAPPING_POINTS = 4
REJECTION_PENALTY = 2

# Progressive level curve: cumulative XP to reach level L is XP_PER_LEVEL*(L-1)**2,
# i.e. level = floor(sqrt(xp / XP_PER_LEVEL)) + 1. Lower XP_PER_LEVEL = faster levels.
XP_PER_LEVEL = 20


def level_for_xp(xp: int) -> int:
    """Return the level for a given total XP using a gentle progressive curve.

    L2=20xp, L3=80, L4=180, L5=320, L6=500, L7=720 ... each level costs more
    than the last. Tune the pace with XP_PER_LEVEL alone.
    """
    return 1 + math.isqrt(max(int(xp), 0) // XP_PER_LEVEL)


def calculate_score(
    *,
    joined_candidates: int,
    offers_received: int,
    total_mappings: int,
    rejected_candidates: int,
) -> int:
    score = (
        joined_candidates * JOINED_POINTS
        + offers_received * OFFER_POINTS
        + total_mappings * MAPPING_POINTS
        - rejected_candidates * REJECTION_PENALTY
    )
    return max(score, 0)


def activity_points(activity_type: ActivityTypeEnum) -> int:
    return {
        ActivityTypeEnum.MAPPING_COMPLETED: MAPPING_POINTS,
        ActivityTypeEnum.OFFER_RECEIVED: OFFER_POINTS,
        ActivityTypeEnum.CANDIDATE_JOINED: JOINED_POINTS,
        ActivityTypeEnum.CANDIDATE_REJECTED: -REJECTION_PENALTY,
    }.get(activity_type, 0)
