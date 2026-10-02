"""Enums for the inbound lead intake pipeline (Meta lead ads → telecaller → recruiter)."""

from enum import StrEnum


class IntakeSource(StrEnum):
    """Where a lead was read from. One member today; the field exists so a
    second intake channel does not require a migration to tell them apart."""

    google_sheet = "google_sheet"


class IntakeLeadStatus(StrEnum):
    """Where a lead sits in the two-leg review journey.

    unassigned is not a failure state to be ignored: leads that arrive when no
    telecaller is active must still be ingested and must still be visible to an
    admin, rather than being dropped because there was nobody to hand them to.
    """

    pending_telecaller = "pending_telecaller"  # assigned, awaiting their decision
    unassigned = "unassigned"  # ingested, nobody to assign it to
    rejected = "rejected"  # telecaller rejected — terminal
    pending_recruiter = "pending_recruiter"  # accepted, awaiting the first mapping
    actioned = "actioned"  # recruiter mapped them — terminal
    duplicate = "duplicate"  # matched a candidate already in the pool — terminal


# Statuses where an SLA clock is running, i.e. someone owes an action.
OPEN_INTAKE_STATUSES: frozenset[IntakeLeadStatus] = frozenset(
    {
        IntakeLeadStatus.pending_telecaller,
        IntakeLeadStatus.pending_recruiter,
    }
)


class IntakeDecision(StrEnum):
    """A telecaller's verdict on a lead."""

    accept = "accept"
    reject = "reject"


class IntakeRejectReason(StrEnum):
    """Why a telecaller turned a lead away.

    Optional on the reject endpoint, because forcing a reason on a caller
    working through a queue produces whichever value is first in the list
    rather than the true one. It drives the admin reject-reason breakdown.
    """

    wrong_number = "wrong_number"
    not_reachable = "not_reachable"
    not_interested = "not_interested"
    not_eligible = "not_eligible"
    duplicate = "duplicate"
    other = "other"
