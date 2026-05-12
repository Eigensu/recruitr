"""Beanie models for the dashboard module collections."""

from datetime import datetime

from beanie import Document, PydanticObjectId, Replace, Update, before_event
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.modules.dashboard.enums import ActivityType, JobStatus, PipelineStage, TargetEntityType


def _touch_updated_at(document: Document) -> None:
    document.updated_at = datetime.utcnow()  # type: ignore[attr-defined]


class EmployeeMappings(BaseModel):
    offers_received: int = 0
    joined_candidates: int = 0
    rejected_candidates: int = 0


class DashboardEmployee(Document):
    name: str
    email: str
    mappings: EmployeeMappings = Field(default_factory=EmployeeMappings)
    total_mappings: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch_updated_at(self)

    class Settings:
        name = "employees"
        indexes = [
            IndexModel("email", unique=True),
            IndexModel("is_active"),
            IndexModel("created_at"),
            IndexModel("updated_at"),
        ]


class DashboardCandidate(Document):
    full_name: str
    email: str
    phone: str | None = None
    previous_company: str | None = None
    experience: float = 0
    skills: list[str] = Field(default_factory=list)
    resume_link: str | None = None
    current_stage: PipelineStage = PipelineStage.added
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch_updated_at(self)

    class Settings:
        name = "candidates"
        indexes = [
            IndexModel("email", unique=True),
            IndexModel("current_stage"),
            IndexModel("skills"),
            IndexModel("is_active"),
            IndexModel("created_at"),
            IndexModel("updated_at"),
        ]


class JobOpening(Document):
    client_name: str
    role: str
    total_seats: int = 0
    filled_seats: int = 0
    remaining_seats: int = 0
    status: JobStatus = JobStatus.open
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch_updated_at(self)

    class Settings:
        name = "job_openings"
        indexes = [
            IndexModel("client_name"),
            IndexModel("status"),
            IndexModel("is_active"),
            IndexModel("created_at"),
            IndexModel("updated_at"),
        ]


class CandidateMapping(Document):
    employee_id: PydanticObjectId
    candidate_id: PydanticObjectId
    job_opening_id: PydanticObjectId
    pipeline_stage: PipelineStage = PipelineStage.added
    mapped_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch_updated_at(self)

    class Settings:
        name = "candidate_mappings"
        indexes = [
            IndexModel([("candidate_id", 1), ("job_opening_id", 1)], unique=True),
            IndexModel("employee_id"),
            IndexModel("candidate_id"),
            IndexModel("job_opening_id"),
            IndexModel("pipeline_stage"),
            IndexModel("mapped_at"),
            IndexModel("updated_at"),
        ]


class ActivityLog(Document):
    employee_id: PydanticObjectId | None = None
    activity_type: ActivityType
    target_entity_type: TargetEntityType
    target_entity_id: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "activities"
        indexes = [
            IndexModel("employee_id"),
            IndexModel("activity_type"),
            IndexModel("target_entity_type"),
            IndexModel("target_entity_id"),
            IndexModel("created_at"),
        ]


class CandidateDocument(Document):
    candidate_id: PydanticObjectId
    file_name: str
    file_type: str
    file_url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "documents"
        indexes = [
            IndexModel("candidate_id"),
            IndexModel("file_type"),
            IndexModel("uploaded_at"),
        ]
