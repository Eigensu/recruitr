"""Position status enum."""

from enum import StrEnum


class PositionStatus(StrEnum):
    open = "open"
    on_hold = "on_hold"
    closed = "closed"
