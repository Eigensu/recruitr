"""Referee-facing kanban stage enum."""

from enum import StrEnum


class RefereeKanbanStage(StrEnum):
    cv_received = "CV Received"
    cv_reviewed = "CV Reviewed"
    screening_call = "Screening Call"
    interview = "Interview Round(s)"
    offer_extended = "Offer Extended"
    offer_accepted = "Offer Accepted"
    joined = "Joined"
