from enum import StrEnum


class CandidateStatus(StrEnum):
    pending = "PENDING"
    approved = "APPROVED"
    rejected = "REJECTED"
