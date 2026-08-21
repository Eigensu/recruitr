"""Referee-facing kanban stage enum."""

from enum import StrEnum


class RefereeKanbanStage(StrEnum):
    cv_received = "CV Received"
    cv_reviewed = "CV Reviewed"
    interview = "Interview Round(s)"
    selected = "Selected"
    joined = "Joined"


# Left-to-right order of the referee portal's timeline. Also the ranking used to
# pick which of a candidate's mappings drives that timeline when they are in play
# with more than one client — the furthest along one wins.
REFEREE_STAGE_ORDER: list[RefereeKanbanStage] = [
    RefereeKanbanStage.cv_received,
    RefereeKanbanStage.cv_reviewed,
    RefereeKanbanStage.interview,
    RefereeKanbanStage.selected,
    RefereeKanbanStage.joined,
]
