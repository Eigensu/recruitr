"""Recruitment domain enums."""

from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.enums.candidate_event_type import CandidateEventType
from app.modules.recruitment.enums.candidate_status import CandidateStatus
from app.modules.recruitment.enums.decision import Decision
from app.modules.recruitment.enums.department import Department
from app.modules.recruitment.enums.education_level import EducationLevel
from app.modules.recruitment.enums.gender import Gender
from app.modules.recruitment.enums.pipeline_stage import (
    INACTIVE_STAGES,
    KANBAN_STAGES,
    PIPELINE_ORDER,
    TERMINAL_STAGES,
    PipelineStage,
)
from app.modules.recruitment.enums.position_approval_status import PositionApprovalStatus
from app.modules.recruitment.enums.position_status import PositionStatus
from app.modules.recruitment.enums.seniority import Seniority

from .client_message import ClientMessageTarget, ClientMessageType
from .notification_kind import NotificationKind
from .payment_status import PaymentStatus
from .referee_stage import REFEREE_STAGE_ORDER, RefereeKanbanStage

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
    "RefereeKanbanStage",
    "REFEREE_STAGE_ORDER",
    "PaymentStatus",
    "NotificationKind",
    "Department",
    "PositionApprovalStatus",
]
