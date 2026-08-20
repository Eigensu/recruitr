"""Pipeline stage enum and stage constants."""

from enum import StrEnum


class PipelineStage(StrEnum):
    sourced = "sourced"
    sent_to_client = "sent_to_client"
    interview = "interview"
    selected = "selected"
    joined = "joined"
    rejected = "rejected"
    candidate_dropped = "candidate_dropped"
    on_hold = "on_hold"


# Ordered columns on the Kanban board
KANBAN_STAGES: list[PipelineStage] = [
    PipelineStage.sourced,
    PipelineStage.sent_to_client,
    PipelineStage.interview,
    PipelineStage.selected,
    PipelineStage.joined,
    PipelineStage.rejected,
    PipelineStage.candidate_dropped,
]

# Stages that close a mapping's active lifecycle
TERMINAL_STAGES: frozenset[PipelineStage] = frozenset(
    {
        PipelineStage.rejected,
        PipelineStage.joined,
        PipelineStage.candidate_dropped,
    }
)

# Stages that should not appear in active-pipeline counts
INACTIVE_STAGES: frozenset[PipelineStage] = frozenset(
    {
        PipelineStage.rejected,
        PipelineStage.on_hold,
        PipelineStage.joined,
        PipelineStage.candidate_dropped,
    }
)

# For dashboard pipeline funnel — full ordered list
PIPELINE_ORDER: list[PipelineStage] = [
    PipelineStage.sourced,
    PipelineStage.sent_to_client,
    PipelineStage.interview,
    PipelineStage.selected,
    PipelineStage.joined,
    PipelineStage.rejected,
    PipelineStage.on_hold,
    PipelineStage.candidate_dropped,
]
