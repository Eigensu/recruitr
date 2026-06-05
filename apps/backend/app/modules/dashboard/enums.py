"""Dashboard module enums — re-exported from the canonical recruitment enums."""

# Import from the unified recruitment module so the entire codebase uses
# one enum definition.  Code that still imports from here continues to work.
from app.modules.recruitment.enums import (  # noqa: F401
    INACTIVE_STAGES,
    KANBAN_STAGES,
    PIPELINE_ORDER,
    TERMINAL_STAGES,
    ActivityType,
    PipelineStage,
)
from app.modules.recruitment.enums import (
    PositionStatus as JobStatus,
)

__all__ = [
    "ActivityType",
    "INACTIVE_STAGES",
    "JobStatus",
    "KANBAN_STAGES",
    "PIPELINE_ORDER",
    "PipelineStage",
    "TERMINAL_STAGES",
]
