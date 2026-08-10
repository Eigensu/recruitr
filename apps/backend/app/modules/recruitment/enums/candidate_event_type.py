"""Event kinds recorded on a candidate's permanent history."""

from enum import StrEnum


class CandidateEventType(StrEnum):
    """What happened to a candidate, in ATS terms.

    Distinct from ActivityType, which drives the (90-day TTL) activity feed and
    the leaderboard. These are the events that must outlive the Kanban board:
    they are never expired and never deleted, so a candidate profile can always
    answer "where has this person been put forward, and what came of it".
    """

    created = "created"  # added to the talent pool by a recruiter
    applied = "applied"  # arrived through the public application form
    approved = "approved"  # application accepted into the directory
    declined = "declined"  # application turned away at review
    mapped = "mapped"  # put forward for a position
    stage_moved = "stage_moved"  # advanced/returned within a position's pipeline
    unmapped = "unmapped"  # withdrawn from a position
