"""Dashboard module enums."""

from enum import Enum


class PipelineStage(str, Enum):
    added = "added"
    shortlisted = "shortlisted"
    sent_to_client = "sent_to_client"
    rejected = "rejected"
    hold = "hold"
    offer_sent = "offer_sent"
    offer_accepted = "offer_accepted"
    joined = "joined"
    dropped = "dropped"


class JobStatus(str, Enum):
    open = "open"
    closed = "closed"
    on_hold = "on_hold"


class ActivityType(str, Enum):
    mapped = "mapped"
    offer_sent = "offer_sent"
    offer_accepted = "offer_accepted"
    joined = "joined"
    rejected = "rejected"


class TargetEntityType(str, Enum):
    candidate = "candidate"
    job_opening = "job_opening"
    client = "client"
