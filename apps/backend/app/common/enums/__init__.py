"""Application-wide enums."""

from enum import StrEnum


class CandidateStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PositionStatus(StrEnum):
    OPEN = "open"
    FILLED = "filled"
    ARCHIVED = "archived"


class GamificationPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ResourceType(StrEnum):
    """Cloudinary resource types."""

    RAW = "raw"  # PDFs / documents
    IMAGE = "image"
    VIDEO = "video"
