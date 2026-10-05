"""Enums for the inbound lead intake pipeline (Meta lead ads → telecaller → recruiter)."""

from enum import StrEnum


class IntakeSource(StrEnum):
    """Where a lead came from."""

    google_sheet = "google_sheet"  # Meta lead ads, polled from the sheet
    # The public application form — including referee referrals, which arrive
    # through the same form carrying a connect code.
    public_form = "public_form"
    # A Naukri candidate export (.xlsx) uploaded by a staff member.
    naukri_import = "naukri_import"
    # Added by a staff member from the Leads page, typed in or from a resume.
    recruiter_manual = "recruiter_manual"


class IntakeLeadStatus(StrEnum):
    """Where a lead sits in the review journey: telecaller → reviewer → recruiter.

    unassigned is not a failure state to be ignored: leads that arrive when no
    telecaller is active must still be ingested and must still be visible to an
    admin, rather than being dropped because there was nobody to hand them to.
    """

    pending_telecaller = "pending_telecaller"  # assigned, awaiting their decision
    unassigned = "unassigned"  # ingested, nobody to assign it to
    rejected = "rejected"  # telecaller rejected — terminal
    # Telecaller accepted and filled the details in; waiting for an admin or
    # maintainer to hand it to a team. No SLA clock: nobody specific owes it.
    pending_review = "pending_review"
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
