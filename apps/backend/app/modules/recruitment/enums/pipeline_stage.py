"""Pipeline stage enum and stage constants."""

from enum import StrEnum


class PipelineStage(StrEnum):
    sourced = "sourced"
    sent_to_client = "sent_to_client"
    interview = "interview"
    decision_pending = "decision_pending"
    offer = "offer"
    offer_accepted = "offer_accepted"
    position_close = "position_close"
    rejected = "rejected"
    on_hold = "on_hold"


# Ordered columns on the Kanban board (Sourced renders as a tray, not a column)
KANBAN_STAGES: list[PipelineStage] = [
    PipelineStage.sent_to_client,
    PipelineStage.interview,
    PipelineStage.decision_pending,
    PipelineStage.offer,
    PipelineStage.offer_accepted,
    PipelineStage.position_close,
]

# Stages that close a mapping's active lifecycle
TERMINAL_STAGES: frozenset[PipelineStage] = frozenset(
    {PipelineStage.position_close, PipelineStage.rejected}
)

# Stages that should not appear in active-pipeline counts
INACTIVE_STAGES: frozenset[PipelineStage] = frozenset(
    {PipelineStage.position_close, PipelineStage.rejected, PipelineStage.on_hold}
)

# For dashboard pipeline funnel — full ordered list
PIPELINE_ORDER: list[PipelineStage] = [
    PipelineStage.sourced,
    PipelineStage.sent_to_client,
    PipelineStage.interview,
    PipelineStage.decision_pending,
    PipelineStage.offer,
    PipelineStage.offer_accepted,
    PipelineStage.position_close,
    PipelineStage.rejected,
    PipelineStage.on_hold,
]
