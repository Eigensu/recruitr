"""Referee-facing kanban stage enum."""

from enum import StrEnum


class RefereeKanbanStage(StrEnum):
    cv_received = "CV Received"
    cv_reviewed = "CV Reviewed"
    interview = "Interview Round(s)"
    selected = "Selected"
    joined = "Joined"
