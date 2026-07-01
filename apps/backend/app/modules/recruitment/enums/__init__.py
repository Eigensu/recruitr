"""Recruitment domain enums."""

from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.enums.decision import Decision
from app.modules.recruitment.enums.education_level import EducationLevel
from app.modules.recruitment.enums.gender import Gender
from app.modules.recruitment.enums.pipeline_stage import (
    INACTIVE_STAGES,
    KANBAN_STAGES,
    PIPELINE_ORDER,
    TERMINAL_STAGES,
    PipelineStage,
)
from app.modules.recruitment.enums.position_status import PositionStatus
from app.modules.recruitment.enums.seniority import Seniority

__all__ = [
    "PipelineStage",
    "KANBAN_STAGES",
    "TERMINAL_STAGES",
    "INACTIVE_STAGES",
    "PIPELINE_ORDER",
    "PositionStatus",
    "Seniority",
    "Decision",
    "ActivityType",
    "EducationLevel",
    "Gender",
]
