"""Activity type enum for the activity feed and gamification."""

from enum import StrEnum


class ActivityType(StrEnum):
    """Activity types recorded in the activity feed (analytics + leaderboard)."""

    mapped = "mapped"
    stage_moved = "stage_moved"
    offer_sent = "offer_sent"
    offer_accepted = "offer_accepted"
    joined = "joined"
    rejected = "rejected"
    unmapped = "unmapped"
    position_created = "position_created"
