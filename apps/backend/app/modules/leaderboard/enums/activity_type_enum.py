from enum import StrEnum


class ActivityTypeEnum(StrEnum):
    MAPPING_COMPLETED = "mapping_completed"
    OFFER_RECEIVED = "offer_received"
    CANDIDATE_JOINED = "candidate_joined"
    CANDIDATE_REJECTED = "candidate_rejected"
    BADGE_UNLOCKED = "badge_unlocked"
    RANK_INCREASED = "rank_increased"
