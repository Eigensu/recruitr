"""Decision outcome enum."""

from enum import StrEnum


class Decision(StrEnum):
    pending = "pending"
    selected = "selected"
    rejected = "rejected"
