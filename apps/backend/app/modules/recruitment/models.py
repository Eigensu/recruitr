"""Canonical Beanie document models for the recruitment domain.

All domain documents carry brand_id for strict per-brand tenant isolation.
The dashboard and leaderboard modules read from these same collections.
"""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, PydanticObjectId, Replace, Update, before_event
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.modules.recruitment.enums import (
    ActivityType,
    Decision,
    EducationLevel,
    Gender,
    PipelineStage,
    PositionStatus,
    Seniority,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _touch(doc: Document) -> None:
    doc.updated_at = _utcnow()  # type: ignore[attr-defined]


# ── Counter ────────────────────────────────────────────────────────────────────


class Counter(Document):
    """Atomic sequence generator for human-readable codes (CLI-031, CLI-031-POS-007).

    Use next_seq() in repository.py — never increment seq directly.
    """

    brand_id: PydanticObjectId
    key: str
    seq: int = 0

    class Settings:
        name = "counters"
        indexes = [
            IndexModel([("brand_id", 1), ("key", 1)], unique=True),
        ]


# ── Team & RecruiterTag ─────────────────────────────────────────────────────────


class Team(Document):
    brand_id: PydanticObjectId
    name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "teams"
        indexes = [
            IndexModel([("brand_id", 1), ("name", 1)], unique=True),
        ]


class RecruiterTag(Document):
    brand_id: PydanticObjectId
    name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "recruiter_tags"
        indexes = [
            IndexModel([("brand_id", 1), ("name", 1)], unique=True),
        ]


# ── Client ─────────────────────────────────────────────────────────────────────


class Client(Document):
    brand_id: PydanticObjectId
    code: str  # "CLI-031" — unique within brand
    name: str  # "Hunger Inc"
    city: str | None = None
    logo_url: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "clients"
        indexes = [
            IndexModel([("brand_id", 1), ("code", 1)], unique=True),
            IndexModel([("brand_id", 1), ("name", 1)]),
            IndexModel("brand_id"),
            IndexModel("is_active"),
        ]


# ── Position ───────────────────────────────────────────────────────────────────


class Position(Document):
    brand_id: PydanticObjectId
    code: str  # "CLI-031-POS-001" — unique within brand
    client_id: PydanticObjectId
    client_name: str  # denormalized for list rendering
    role: str
    department: str | None = None
    city: str | None = None
    train_line: str | None = None
    seniority: Seniority = Seniority.mid
    requirements: list[str] = Field(default_factory=list)  # lowercased keywords
    total_seats: int = 0
    filled_seats: int = 0
    remaining_seats: int = 0
    status: PositionStatus = PositionStatus.open
    assigned_employee_id: PydanticObjectId | None = None
    date_opened: datetime = Field(default_factory=_utcnow)
    target_close: datetime | None = None
    notes: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "positions"
        indexes = [
            IndexModel([("brand_id", 1), ("code", 1)], unique=True),
            IndexModel("brand_id"),
            IndexModel([("brand_id", 1), ("client_id", 1)]),
            IndexModel([("brand_id", 1), ("status", 1)]),
            IndexModel("assigned_employee_id"),
            IndexModel("is_active"),
            IndexModel("created_at"),
        ]


# ── Candidate ──────────────────────────────────────────────────────────────────


class Candidate(Document):
    """Unified candidate model — shared talent pool scoped to a brand.

    A single candidate may be mapped to multiple positions across different
    clients without profile duplication.
    """

    brand_id: PydanticObjectId
    full_name: str
    email: str  # unique within brand
    phone: str | None = None
    previous_company: str | None = None
    experience_years: float = 0
    education_level: EducationLevel | None = None
    city: str | None = None
    area: str | None = None
    gender: Gender | None = None
    age: int | None = None
    skills: list[str] = Field(default_factory=list)
    skills_normalized: list[str] = Field(default_factory=list)  # lowercased, for $setIntersection
    tags: list[str] = Field(default_factory=list)
    preferred_train_line: str | None = None
    cv_link: str | None = None
    resume_url: str | None = None
    resume_public_id: str | None = None  # Cloudinary public_id
    resume_raw_text: str | None = None
    current_role: str | None = None
    salary: float | None = None
    notes: str | None = None
    current_stage: PipelineStage = PipelineStage.sourced  # denormalized latest stage
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "candidates"
        indexes = [
            IndexModel([("brand_id", 1), ("email", 1)], unique=True),
            IndexModel("brand_id"),
            IndexModel("skills_normalized"),
            IndexModel("tags"),
            IndexModel([("brand_id", 1), ("current_stage", 1)]),
            IndexModel("is_active"),
            IndexModel("created_at"),
        ]


# ── Mapping ────────────────────────────────────────────────────────────────────


class StageEvent(BaseModel):
    """Immutable history entry appended on every stage transition."""

    stage: PipelineStage
    decision: Decision = Decision.pending
    by_employee_id: PydanticObjectId
    at: datetime = Field(default_factory=_utcnow)


class Mapping(Document):
    """Pipeline entry linking a candidate to a position.

    One per (candidate, position) pair. A candidate may have many mappings
    across different positions (and different clients) within the same brand.
    """

    brand_id: PydanticObjectId
    candidate_id: PydanticObjectId
    position_id: PydanticObjectId
    client_id: PydanticObjectId | None = None  # denormalized for filtering; None for legacy docs
    employee_id: PydanticObjectId  # recruiter who last acted
    stage: PipelineStage = PipelineStage.sourced
    decision: Decision = Decision.pending
    match_score: float | None = None  # snapshotted at map time (0..1)
    feedback: str | None = None
    history: list[StageEvent] = Field(default_factory=list)
    mapped_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "candidate_mappings"
        indexes = [
            IndexModel([("candidate_id", 1), ("position_id", 1)], unique=True),
            IndexModel("brand_id"),
            IndexModel([("brand_id", 1), ("position_id", 1)]),
            IndexModel([("brand_id", 1), ("candidate_id", 1)]),
            IndexModel("client_id"),
            IndexModel("employee_id"),
            IndexModel([("brand_id", 1), ("stage", 1)]),
            IndexModel("mapped_at"),
            IndexModel("updated_at"),
        ]


# ── Employee ───────────────────────────────────────────────────────────────────


class Employee(Document):
    """Recruiter identity record, linked 1-to-1 with a login User.

    brand_id is null until onboarding assigns one; write endpoints 403 until set.
    Score/badge state lives in EmployeeStat (leaderboard module), keyed by this _id.
    """

    brand_id: PydanticObjectId | None = None  # set at onboarding
    user_id: PydanticObjectId | None = None  # FK → users._id
    team_id: PydanticObjectId | None = None  # FK → teams._id
    name: str
    email: str  # globally unique — join key with User
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "employees"
        indexes = [
            IndexModel("email", unique=True),
            IndexModel("user_id", sparse=True),
            IndexModel("brand_id"),
            IndexModel("is_active"),
        ]


# ── ActivityLog ────────────────────────────────────────────────────────────────


class ActivityLog(Document):
    brand_id: PydanticObjectId
    employee_id: PydanticObjectId | None = None
    activity_type: ActivityType
    target_entity_type: str  # "candidate" | "position" | "client"
    target_entity_id: str
    description: str
    created_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "activities"
        indexes = [
            IndexModel("brand_id"),
            IndexModel([("brand_id", 1), ("created_at", -1)]),
            IndexModel("employee_id"),
            IndexModel("activity_type"),
            IndexModel("target_entity_id"),
        ]


# ── CandidateDocument ──────────────────────────────────────────────────────────


class CandidateDocument(Document):
    brand_id: PydanticObjectId
    candidate_id: PydanticObjectId
    file_name: str
    file_type: str
    file_url: str
    uploaded_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "documents"
        indexes = [
            IndexModel("brand_id"),
            IndexModel("candidate_id"),
            IndexModel("file_type"),
            IndexModel("uploaded_at"),
        ]
