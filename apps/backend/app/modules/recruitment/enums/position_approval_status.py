"""Position approval status enum."""

from enum import StrEnum


class PositionApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
