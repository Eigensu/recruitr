"""Canonical Beanie document models for the recruitment domain.

All domain documents carry brand_id for strict per-brand tenant isolation.
The dashboard and leaderboard modules read from these same collections.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from beanie import Document, PydanticObjectId, Replace, Update, before_event
from pydantic import BaseModel, Field
from pymongo import IndexModel

from app.modules.recruitment.enums import (
    ActivityType,
    CandidateEventType,
    CandidateStatus,
    ClientMessageTarget,
    ClientMessageType,
    Decision,
    Department,
    EducationLevel,
    EstablishmentTag,
    Gender,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeRejectReason,
    IntakeSource,
    NotificationKind,
    PaymentStatus,
    PipelineStage,
    PositionApprovalStatus,
    PositionStatus,
    RefereeKanbanStage,
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
    brand_description: str | None = None
    # Contact/CRM detail — all optional, all shown on the client detail page.
    industry: str | None = None
    establishment_tag: EstablishmentTag | None = None
    website: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    # Who may be authorized against this client. A domain entry ("@acme.com")
    # admits any address under it; an email entry admits exactly one address.
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_emails: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_by_id: PydanticObjectId | None = None  # FK → employees._id
    updated_by_id: PydanticObjectId | None = None
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
        ]


class ClientUser(Document):
    """An email authorized to see one client's pipeline, once a client portal exists.

    Deliberately NOT a login account. Creating a `User` here would be unsafe:
    `ensure_employee_for_user` assigns the sole existing brand to any user who
    has none, so a client contact would sign in with full agency access to every
    candidate and position. This row records the authorization only — a future
    portal login checks it before granting scoped access.

    `user_id` and `last_login` stay null until that portal exists; a row with no
    `user_id` is reported as "Pending".
    """

    brand_id: PydanticObjectId
    client_id: PydanticObjectId  # FK → clients._id
    email: str  # lowercased; unique per client
    name: str | None = None  # filled in when the person actually signs up
    role: str = "client"
    user_id: PydanticObjectId | None = None  # FK → users._id, once they sign up
    last_login: datetime | None = None
    is_active: bool = True
    invited_by_id: PydanticObjectId | None = None  # FK → employees._id
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "client_users"
        indexes = [
            IndexModel([("client_id", 1), ("email", 1)], unique=True),
            IndexModel([("brand_id", 1), ("client_id", 1)]),
        ]


class RefereeUser(Document):
    """An email authorized to use the referee portal.

    Similar to ClientUser, this is an authorization grant. When the referee signs up
    or logs in, their User account will be associated with this grant.
    """

    brand_id: PydanticObjectId
    email: str  # lowercased; unique within brand
    # Optional on read, always set on write: rows created before this field
    # existed have no code, and a required field would fail to parse them —
    # breaking the referee's login, since every sign-in loads this grant.
    # utils/connect_code.py mints one lazily for those rows.
    connect_code: str | None = None
    name: str | None = None
    role: str = "referee"
    user_id: PydanticObjectId | None = None  # FK → users._id, once they sign up
    last_login: datetime | None = None
    is_active: bool = True
    invited_by_id: PydanticObjectId | None = None  # FK → employees._id
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "referee_users"
        indexes = [
            IndexModel([("brand_id", 1), ("email", 1)], unique=True),
            # Partial for the same reason as Candidate.email: a missing
            # connect_code indexes as null for every legacy row, so a plain
            # unique index would reject all but the first of them. The code is
            # global, not per-brand — a public applicant types it with no brand
            # in hand (see public_controller.public_apply).
            IndexModel(
                [("connect_code", 1)],
                unique=True,
                partialFilterExpression={"connect_code": {"$type": "string"}},
            ),
        ]


# ── Position ───────────────────────────────────────────────────────────────────


class Position(Document):
    brand_id: PydanticObjectId
    code: str  # "CLI-031-POS-001" — unique within brand
    client_id: PydanticObjectId
    client_name: str  # denormalized for list rendering
    role: str
    department: Department | None = None
    salary: str | None = None
    mumbai_area: str | None = None
    city: str | None = None
    train_line: str | None = None
    seniority: Seniority = Seniority.mid
    requirements: list[str] = Field(default_factory=list)  # lowercased keywords
    total_seats: int = 0
    filled_seats: int = 0
    remaining_seats: int = 0
    status: PositionStatus = PositionStatus.open
    approval_status: PositionApprovalStatus | None = None  # e.g. "pending", "approved", "rejected"
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
            IndexModel([("brand_id", 1), ("client_id", 1)]),
            IndexModel([("brand_id", 1), ("status", 1)]),
            IndexModel("assigned_employee_id"),
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
    # Optional: phone is the mandatory contact channel for a manually-added
    # candidate now (see CandidateCreate), email is not. The unique index
    # below is partial for exactly this reason — see its comment.
    email: str | None = None
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
    communication: str | None = None
    education: str | None = None
    brand_experience: str | None = None
    department: Department | None = None
    specialization: str | None = None
    establishment_tag: EstablishmentTag | None = None
    preferred_train_line: str | None = None
    cv_link: str | None = None
    resume_url: str | None = None
    resume_public_id: str | None = None  # Cloudinary public_id
    resume_raw_text: str | None = None
    current_role: str | None = None
    expected_salary: float | None = None
    notice_period: str | None = None
    source: str | None = None  # internal | external — how the candidate entered the system
    source_channel: str | None = None  # where they came from: LinkedIn, Naukri, referral, …
    connect_code: str | None = None
    salary: float | None = None
    notes: str | None = None
    current_stage: PipelineStage = PipelineStage.sourced  # denormalized latest stage
    status: CandidateStatus = CandidateStatus.approved
    # The referee who referred this candidate (if any) — FK → referee_users._id
    referee_id: PydanticObjectId | None = None
    # The recruiter who put this person in the pool — FK → employees._id. Null
    # for public-form applications (nobody sourced them) and for records that
    # predate the field. Ownership gates who may open the CV: see
    # utils/cv_access.py, where a null owner means "shared, anyone may view".
    created_by_id: PydanticObjectId | None = None
    # The recruiter an accepted inbound lead was assigned to — FK → employees._id.
    # Deliberately not created_by_id: that field means "who sourced this person"
    # and gates CV visibility, and a lead was sourced by an ad, not a recruiter.
    # Reusing it would silently lock the lead's CV to whoever got the handoff.
    assigned_recruiter_id: PydanticObjectId | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "candidates"
        indexes = [
            # Partial, not a plain unique index: email is now optional (phone is
            # the mandatory contact field), and Mongo indexes a missing/null
            # email as the same value for every such document — a second
            # emailless candidate in the same brand would 409 as a "duplicate"
            # of the first without this filter excluding them from the index.
            IndexModel(
                [("brand_id", 1), ("email", 1)],
                unique=True,
                partialFilterExpression={"email": {"$type": "string"}},
                name="candidate_brand_email_partial",
            ),
            IndexModel("tags"),
            IndexModel([("brand_id", 1), ("current_stage", 1)]),
            IndexModel([("brand_id", 1), ("created_by_id", 1)]),
            IndexModel([("brand_id", 1), ("assigned_recruiter_id", 1)]),
            IndexModel("created_at"),
        ]


# ── Mapping ────────────────────────────────────────────────────────────────────


class StageEvent(BaseModel):
    """Immutable history entry appended on every stage transition.

    The trail for one mapping, and it dies with that mapping — unmapping a
    candidate deletes the row. CandidateEvent below is the permanent record.
    """

    stage: PipelineStage
    # Absent on entries written before this field existed, and on the opening
    # event of a mapping (there is no stage to have come from).
    from_stage: PipelineStage | None = None
    decision: Decision = Decision.pending
    by_employee_id: PydanticObjectId | None = None
    # Who actually triggered the move: a recruiter, the client themselves
    # (via the dashboard tick/cross), the referee who sourced the candidate
    # (via the Binge Connect portal), or the daily auto-join job. Defaults to
    # "employee" so history entries written before this field existed keep
    # reading as staff-authored, which is what they were.
    actor: Literal["employee", "client", "referee", "system"] = "employee"
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
    interview_date: datetime | None = None
    joining_date: datetime | None = None
    offer_letter_url: str | None = None
    salary_offered: float | None = None
    dropped_notes: str | None = None
    reminders_sent: list[str] = Field(default_factory=list)
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
    role: str = "employee"  # mirrors User.role; synced on every login
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
            IndexModel([("brand_id", 1), ("is_active", 1), ("role", 1)]),
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
            IndexModel([("brand_id", 1), ("created_at", -1)]),
            IndexModel("employee_id"),
            IndexModel("target_entity_id"),
            IndexModel("created_at", expireAfterSeconds=7776000),  # 90-day TTL
        ]


# ── CandidateEvent ─────────────────────────────────────────────────────────────


class CandidateEvent(Document):
    """One permanent entry in a candidate's employment history.

    Append-only, and deliberately not the activity feed: ActivityLog above
    carries a 90-day TTL and is keyed to the recruiter for the leaderboard, so
    a placement made last year has already vanished from it. This collection
    never expires and is never deleted — it is what the candidate profile reads
    to answer "which companies has this person been put in front of, and what
    came of it".

    Client, position and role are snapshotted rather than joined at read time.
    A mapping is deleted outright when a candidate is unmapped, and a position
    can be closed or renamed; the history has to survive both, so it stores
    what was true when the event happened.
    """

    brand_id: PydanticObjectId
    candidate_id: PydanticObjectId
    event_type: CandidateEventType
    at: datetime = Field(default_factory=_utcnow)
    # Who acted. Null for public-form applications and backfilled rows whose
    # actor could not be recovered.
    employee_id: PydanticObjectId | None = None
    employee_name: str | None = None
    # Position context — null on events that are not about a position
    # (created/applied/approved/declined).
    position_id: PydanticObjectId | None = None
    position_code: str | None = None
    position_role: str | None = None
    client_id: PydanticObjectId | None = None
    client_name: str | None = None
    # Stage transition — set on mapped/stage_moved.
    from_stage: PipelineStage | None = None
    to_stage: PipelineStage | None = None
    note: str | None = None

    class Settings:
        name = "candidate_events"
        indexes = [
            IndexModel([("brand_id", 1), ("candidate_id", 1), ("at", -1)]),
            IndexModel([("brand_id", 1), ("event_type", 1)]),
            IndexModel("position_id"),
            IndexModel("employee_id"),
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


# ── ClientMessage ──────────────────────────────────────────────────────────────


class ClientMessage(Document):
    """A targeted message shown to clients on their dashboard."""

    brand_id: PydanticObjectId
    message_text: str
    target_type: ClientMessageTarget
    target_client_ids: list[PydanticObjectId] = Field(default_factory=list)
    start_at: datetime
    end_at: datetime
    type: ClientMessageType
    cta_url: str | None = None
    created_by_id: PydanticObjectId | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "client_messages"
        indexes = [
            IndexModel([("brand_id", 1), ("start_at", 1), ("end_at", 1)]),
            IndexModel("target_client_ids"),
        ]


# ── Binge Connect ──────────────────────────────────────────────────────────────


class ReferralRecord(Document):
    """Tracks a candidate referred by a Referee User."""

    brand_id: PydanticObjectId
    referee_id: PydanticObjectId
    mapping_id: PydanticObjectId | None = None
    candidate_id: PydanticObjectId
    position_id: PydanticObjectId
    role_level: str | None = None
    submission_date: datetime = Field(default_factory=_utcnow)
    kanban_stage: str = RefereeKanbanStage.cv_received.value
    joining_date: datetime | None = None
    joining_plus7_eligible: bool = False
    incentive_amount: float | None = None
    # The enum's value, not a hand-written "PENDING": the eligibility and
    # payment jobs select on {"$in": [PaymentStatus.pending.value, ...]}, so a
    # record defaulted to a different spelling is silently never processed and
    # the referee never accrues anything.
    payment_status: str = PaymentStatus.pending.value
    payment_date: datetime | None = None
    cycle_month: str | None = None
    notified_actioned: bool = False
    notified_joined: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "referral_records"
        indexes = [
            # One ledger entry per referred candidate, not per mapping: a
            # candidate put forward to a second client must not accrue twice.
            IndexModel([("brand_id", 1), ("candidate_id", 1)], unique=True),
            IndexModel("brand_id"),
            IndexModel("referee_id"),
            IndexModel("mapping_id"),
            IndexModel("candidate_id"),
            IndexModel("position_id"),
            IndexModel([("brand_id", 1), ("referee_id", 1)]),
            IndexModel([("referee_id", 1), ("cycle_month", 1)]),
            IndexModel("payment_status"),
        ]


class PaymentBatch(Document):
    """Tracks a monthly payment run for a referee."""

    batch_id: str
    brand_id: PydanticObjectId
    cycle_month: str
    referee_id: PydanticObjectId
    total_amount: float
    paid_on: datetime
    payment_reference: str
    notified_paid: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "payment_batches"
        indexes = [
            IndexModel([("brand_id", 1), ("referee_id", 1), ("cycle_month", 1)], unique=True),
        ]


# ── Notification ─────────────────────────────────────────────────────────────


class Notification(Document):
    """An in-app reminder for a pipeline action sitting unactioned too long.

    client_id is None for a staff-wide notification (every employee in the
    brand sees it) and set for a single client's notification — mirroring how
    the PDF spec wants every action to have a client-side and a staff-side
    fallback. One row per (mapping_id, kind, client_id): the reminder job
    checks for an existing unread row before creating another, so a mapping
    stuck for a week doesn't spam a new notification every run.
    """

    brand_id: PydanticObjectId
    client_id: PydanticObjectId | None = None
    # Set to address one staff member — the only staff rows a telecaller sees.
    # None (and absent, on rows predating the field) is a brand-wide staff row.
    employee_id: PydanticObjectId | None = None
    mapping_id: PydanticObjectId | None = None
    intake_lead_id: PydanticObjectId | None = None
    kind: NotificationKind
    message: str
    created_at: datetime = Field(default_factory=_utcnow)
    read_at: datetime | None = None

    class Settings:
        name = "notifications"
        indexes = [
            IndexModel([("brand_id", 1), ("client_id", 1), ("read_at", 1)]),
            IndexModel([("mapping_id", 1), ("kind", 1), ("client_id", 1)]),
            IndexModel("created_at"),
        ]


# ── Recruitment Tasks ────────────────────────────────────────────────────────


class TaskAssignmentType(StrEnum):
    single = "single"
    team = "team"
    all = "all"


class RecruitmentTask(Document):
    brand_id: PydanticObjectId
    title: str
    description: str | None = None
    tracked_activity_type: ActivityType
    target_count: int
    assignee_type: TaskAssignmentType
    assignee_id: PydanticObjectId | None = None
    start_date: datetime
    due_date: datetime
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "recruitment_tasks"
        indexes = [
            IndexModel([("brand_id", 1)]),
            IndexModel([("brand_id", 1), ("is_active", 1)]),
        ]


# ── Lead intake ──────────────────────────────────────────────────────────────


class IntakeAttribution(BaseModel):
    """Which ad, campaign and form a lead came from.

    Snapshotted onto the lead rather than looked up later: these are Meta's ids
    and names, we have no copy of that catalogue, and an ad that is renamed or
    deleted must not change what an already-ingested lead says it came from.
    """

    ad_id: str | None = None
    ad_name: str | None = None
    adset_id: str | None = None
    adset_name: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None
    form_id: str | None = None
    form_name: str | None = None


class IntakeLead(Document):
    """One inbound lead, its review journey, and the timings behind both.

    A separate document rather than fields on Candidate. Candidate already
    carries ~45 fields and this workflow applies to a subset of its rows, so
    this follows Mapping and ReferralRecord: a record *about* a candidate,
    keyed to it, with its own lifecycle.

    The two `*_response_seconds` fields are denormalised at action time so the
    analytics aggregations can average and sort a plain number instead of
    recomputing a date difference over nullable fields on every read.
    """

    brand_id: PydanticObjectId
    candidate_id: PydanticObjectId  # FK → candidates._id; set even when duplicate

    # ── Provenance ──
    source: IntakeSource = IntakeSource.google_sheet
    source_channel: str | None = None  # "Instagram" | "Facebook"
    # Meta's own lead id. The idempotency key: re-reading the same sheet row
    # must never create a second lead, which is what lets the poll read the
    # whole range every run instead of tracking a cursor.
    external_id: str
    external_created_at: datetime | None = None  # the sheet's created_time
    external_status: str | None = None  # the sheet's lead_status column, read-only
    is_organic: bool | None = None
    attribution: IntakeAttribution = Field(default_factory=IntakeAttribution)
    # The row exactly as read, including columns this model does not map. A
    # column added to the form is then never lost, and a mapping bug stays
    # diagnosable after the fact.
    raw: dict[str, str] = Field(default_factory=dict)

    status: IntakeLeadStatus = IntakeLeadStatus.pending_telecaller
    ingested_at: datetime = Field(default_factory=_utcnow)

    # ── Telecaller leg ──
    telecaller_id: PydanticObjectId | None = None  # FK → employees._id
    telecaller_assigned_at: datetime | None = None
    telecaller_actioned_at: datetime | None = None
    telecaller_decision: IntakeDecision | None = None
    telecaller_reject_reason: IntakeRejectReason | None = None
    telecaller_notes: str | None = None
    telecaller_response_seconds: int | None = None
    # Stamped when the breach notification fires, and the reason it fires once:
    # a lead stuck for a week raises one notification, not one per sweep.
    telecaller_sla_breached_at: datetime | None = None

    # ── Recruiter leg ──
    recruiter_id: PydanticObjectId | None = None  # FK → employees._id
    recruiter_assigned_at: datetime | None = None
    recruiter_actioned_at: datetime | None = None
    recruiter_action_mapping_id: PydanticObjectId | None = None
    recruiter_response_seconds: int | None = None
    recruiter_sla_breached_at: datetime | None = None

    # Reassignment restarts the SLA clock for the new owner, so this counts how
    # often that happened — otherwise a lead could be passed around indefinitely
    # and never appear overdue.
    reassignment_count: int = 0

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "intake_leads"
        # No TTL: this is the permanent audit record of where every lead went,
        # like CandidateEvent and unlike the 90-day ActivityLog.
        indexes = [
            IndexModel([("brand_id", 1), ("external_id", 1)], unique=True),
            # The SLA sweep: open leads whose assignment is older than the cutoff.
            IndexModel([("brand_id", 1), ("status", 1), ("telecaller_assigned_at", 1)]),
            IndexModel([("brand_id", 1), ("status", 1), ("recruiter_assigned_at", 1)]),
            IndexModel([("brand_id", 1), ("telecaller_id", 1), ("status", 1)]),
            IndexModel([("brand_id", 1), ("recruiter_id", 1), ("status", 1)]),
            IndexModel([("brand_id", 1), ("candidate_id", 1)]),
            IndexModel([("brand_id", 1), ("ingested_at", -1)]),
        ]


class IntakeSourceConfig(Document):
    """Which sheet to read, per brand, and how the last read went.

    Editable by an admin so changing a tab name or range is not a deploy. The
    service-account credentials deliberately stay in the environment: this row
    is readable by anyone who can read the database, and a Google key is not.

    One row today, for the single brand. It is keyed by brand_id under a unique
    index anyway, so a second brand is another row rather than a migration.
    """

    brand_id: PydanticObjectId
    spreadsheet_id: str
    sheet_range: str = "Sheet1!A:U"
    enabled: bool = False
    default_source_channel: str = "Instagram"
    # Stamped when enabled first turns true. The poll ignores leads older than
    # this, so switching the integration on does not round-robin the sheet's
    # entire history into telecaller queues in one tick and start an SLA clock
    # on every one of them. History goes through scripts/backfill_intake_leads.py.
    activated_at: datetime | None = None

    last_synced_at: datetime | None = None  # last attempt, successful or not
    last_success_at: datetime | None = None
    last_row_count: int = 0
    last_ingested_count: int = 0
    last_skipped_count: int = 0
    last_error: str | None = None  # surfaced in the admin UI
    consecutive_failures: int = 0

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self) -> None:
        _touch(self)

    class Settings:
        name = "intake_source_configs"
        indexes = [
            IndexModel([("brand_id", 1)], unique=True),
        ]
