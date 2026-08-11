"""Recruitment domain enums."""

from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.enums.candidate_event_type import CandidateEventType
from app.modules.recruitment.enums.candidate_status import CandidateStatus
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
    "CandidateStatus",
    "CandidateEventType",
    "ActivityType",
    "EducationLevel",
    "Gender",
    "ClientMessageTarget",
    "ClientMessageType",
]
from .client_message import ClientMessageTarget, ClientMessageType
