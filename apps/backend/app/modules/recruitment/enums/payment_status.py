"""Payment status enum for referrals."""

from enum import StrEnum


class PaymentStatus(StrEnum):
    pending = "Pending"
    owed = "Owed"
    paid = "Paid"
