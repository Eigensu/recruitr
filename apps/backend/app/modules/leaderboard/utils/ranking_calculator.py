from app.modules.leaderboard.enums import ActivityTypeEnum

JOINED_POINTS = 15
OFFER_POINTS = 8
MAPPING_POINTS = 4
REJECTION_PENALTY = 2


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
