"""DTOs for the inbound lead queue."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.common.dtos.pagination import PaginationMeta
from app.modules.recruitment.enums import (
    MAX_CALL_ATTEMPTS,
    Department,
    EstablishmentTag,
    Gender,
    IntakeCallOutcome,
    IntakeDecision,
    IntakeLeadStatus,
    IntakeNoteStage,
    IntakeRejectReason,
    IntakeSource,
)


class _UtcTimestamps(BaseModel):
    """Serialise every datetime with its timezone, because Mongo drops it.

    The driver stores UTC and hands it back **naive**, and Pydantic then writes
    it out as `2026-09-24T02:50:12` with no offset. JavaScript parses a
    date-time in that form as *local* time, so every elapsed time on the screen
    came out wrong by the viewer's UTC offset — five and a half hours in IST.
    That produced a queue reading "waiting 1d 3h" on a lead the server, quite
    correctly, did not consider overdue against a 24-hour limit.

    The same naive-datetime trap as `intake_service.as_utc`, one layer out: this
    is the wire, that one is the comparison. Stamping it here rather than at
    each call site means a field added later cannot quietly reintroduce it.
    """

    @field_validator("*", mode="before")
    @classmethod
    def _stamp_utc(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class CvUploadLinkInfo(_UtcTimestamps):
    """What the public CV upload page shows: enough to greet the person, no more.

    Unauthenticated, and the link may be forwarded, so a first name only: the
    page must not tell whoever holds it the candidate's phone or email.
    """

    first_name: str
    brand_name: str
    brand_logo_url: str | None = None
    expires_at: datetime
    uploaded: bool


class IntakeCvLinkResponse(_UtcTimestamps):
    """A CV upload link: the page is /cv/{token} on the app's own domain."""

    token: str
    expires_at: datetime


class IntakeLeadResponse(_UtcTimestamps):
    """One lead as the queue shows it.

    Carries the candidate's contact details inline rather than making the client
    fetch the candidate separately: a telecaller works a list of people to ring,
    and the phone number is the whole point of the screen.
    """

    id: str
    status: IntakeLeadStatus
    source: IntakeSource = IntakeSource.google_sheet
    candidate_id: str
    full_name: str
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    current_role: str | None = None
    experience_years: float = 0
    role_interest: str | None = None
    education: str | None = None
    source_channel: str | None = None
    campaign_name: str | None = None
    external_created_at: datetime | None = None
    ingested_at: datetime
    telecaller_id: str | None = None
    telecaller_assigned_at: datetime | None = None
    telecaller_actioned_at: datetime | None = None
    telecaller_decision: IntakeDecision | None = None
    telecaller_reject_reason: IntakeRejectReason | None = None
    telecaller_notes: str | None = None
    telecaller_response_seconds: int | None = None
    team_id: str | None = None
    team_name: str | None = None
    reviewed_at: datetime | None = None
    recruiter_id: str | None = None
    recruiter_assigned_at: datetime | None = None
    recruiter_actioned_at: datetime | None = None
    recruiter_response_seconds: int | None = None
    recruiter_decision: IntakeDecision | None = None
    recruiter_accepted_at: datetime | None = None
    recruiter_reject_reason: IntakeRejectReason | None = None
    recruiter_notes: str | None = None
    reassignment_count: int = 0
    # Calls made so far and when the last one was, from the telecaller's log. The
    # fifth unanswered call closes the lead, so `max_call_attempts` lets the card
    # say "call 3 of 5" without the client hard-coding the limit.
    call_attempts: int = 0
    last_call_at: datetime | None = None
    max_call_attempts: int = MAX_CALL_ATTEMPTS
    # When the latest CV upload link stops working, and when the candidate last
    # used one (service/cv_requests.py).
    cv_link_expires_at: datetime | None = None
    cv_uploaded_at: datetime | None = None
    # The candidate's CV, under the directory's rule (utils/cv_access): None when
    # there is none or the viewer may not open it, and cv_locked says which.
    cv_link: str | None = None
    resume_url: str | None = None
    cv_locked: bool = False
    # Filled on the admin list, where the table is read by someone who does not
    # know the ids; left None on the telecaller's own queue, which is all theirs.
    telecaller_name: str | None = None
    recruiter_name: str | None = None
    # Whether the leg this lead is waiting on is past its SLA. Computed here
    # rather than by the client, which would have to know both limits and be
    # trusted to apply the right one to each status.
    overdue: bool = False


_REQUIRED_TEXT = (
    "full_name",
    "phone",
    "communication",
    "education",
    "specialization",
    "current_role",
    "city",
    "notice_period",
)


class IntakeCandidateDetails(BaseModel):
    """What a telecaller fills in on the call before accepting a lead.

    The same required fields as adding a candidate by hand
    (`CandidateCreateStrict`) except three. Brand experience is left to the
    recruiter, who is the one placing the person with a brand. The CV link is
    optional: a telecaller is on the phone, and a lead from an Instagram ad
    usually has no CV to link to — requiring one would make accept impossible.
    Both salaries are optional too: plenty of leads won't say, or have none.
    Omitting one keeps the figure on file; sending null clears it.
    Source is not asked for at all: every lead here is external by definition.
    """

    full_name: str = Field(..., min_length=1, max_length=200)
    # Not EmailStr: that rejects addresses the public form and the sheet ingest
    # already stored (reserved domains, for one), and a telecaller cannot
    # accept a lead over an email they never typed. Same shape check as ingest.
    email: str | None = Field(default=None, max_length=254)
    phone: str = Field(..., min_length=1, max_length=30)
    communication: str = Field(..., min_length=1, max_length=100)
    education: str = Field(..., min_length=1, max_length=200)
    department: Department
    specialization: str = Field(..., min_length=1, max_length=200)
    establishment_tag: EstablishmentTag | None = None
    current_role: str = Field(..., min_length=1, max_length=200)
    experience_years: float = Field(..., ge=0)
    city: str = Field(..., min_length=1, max_length=100)
    area: str | None = Field(default=None, max_length=100)
    gender: Gender
    age: int | None = Field(default=None, gt=0)
    # Optional, and null is not the same as omitted: see the docstring.
    expected_salary: float | None = Field(default=None, ge=0)
    salary: float | None = Field(default=None, ge=0)
    notice_period: str = Field(..., min_length=1, max_length=100)
    cv_link: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _clean(self) -> IntakeCandidateDetails:
        # Whitespace-only passes min_length, so trim before checking it is there.
        for name in _REQUIRED_TEXT:
            value = getattr(self, name).strip()
            if not value:
                raise ValueError(f"{name} is required")
            setattr(self, name, value)
        if self.cv_link is not None:
            self.cv_link = self.cv_link.strip() or None
        if self.cv_link and not re.match(r"^https?://", self.cv_link, re.IGNORECASE):
            raise ValueError("CV Link must be a valid HTTP(S) URL")
        if self.email is not None and self.email.strip():
            # Imported here: the utils package imports schemas at load time.
            from app.modules.recruitment.utils.lead_sheet import parse_email

            email = parse_email(self.email)
            if email is None:
                raise ValueError("Email doesn't look like an email address")
            self.email = email
        else:
            self.email = None
        return self


class IntakeCandidateDraft(BaseModel):
    """The candidate as the system holds them now, to prefill the accept form.

    Every field optional and loosely typed: this is whatever the ad form or the
    public application captured, and a value that does not fit a dropdown is
    still worth showing the telecaller rather than dropping.
    """

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    communication: str | None = None
    education: str | None = None
    department: str | None = None
    specialization: str | None = None
    establishment_tag: str | None = None
    current_role: str | None = None
    experience_years: float | None = None
    city: str | None = None
    area: str | None = None
    gender: str | None = None
    age: int | None = None
    expected_salary: float | None = None
    salary: float | None = None
    notice_period: str | None = None
    cv_link: str | None = None
    # Not editable here, but the telecaller should know it is on file.
    has_resume: bool = False


class IntakeAcceptRequest(BaseModel):
    details: IntakeCandidateDetails
    notes: str | None = Field(default=None, max_length=2000)


class IntakeNoteCreate(BaseModel):
    """A screening note. Whitespace around it is trimmed, and blank is refused."""

    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body", mode="before")
    @classmethod
    def _trimmed(cls, v: object) -> object:
        # Before the length checks, so padding can't push a fitting note over the
        # limit and a blank one fails min_length like an empty one.
        return v.strip() if isinstance(v, str) else v


class IntakeNoteResponse(BaseModel):
    id: str
    lead_id: str
    candidate_id: str
    stage: IntakeNoteStage
    body: str
    author_id: str
    author_name: str | None = None
    author_role: str | None = None
    created_at: datetime
    # Filled on the management log, where notes from many leads are read together.
    candidate_name: str | None = None


class IntakeCallRequest(BaseModel):
    """An unanswered call, with an optional note on how it went."""

    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def _blank_is_none(cls, v: object) -> object:
        # A note box left empty (or spaces) is no note, so the log never holds one.
        if isinstance(v, str):
            return v.strip() or None
        return v


class IntakeCallResponse(BaseModel):
    id: str
    lead_id: str
    attempt: int
    outcome: IntakeCallOutcome
    note: str | None = None
    at: datetime
    telecaller_id: str
    telecaller_name: str | None = None
    # Filled on the management log, where rows from many leads are read together.
    lead_name: str | None = None


class IntakeLogCallResponse(BaseModel):
    """The lead after the call, the call itself, and whether it closed the lead."""

    lead: IntakeLeadResponse
    call: IntakeCallResponse
    dead: bool = False


class IntakeRejectRequest(BaseModel):
    reason: IntakeRejectReason | None = None
    notes: str | None = Field(default=None, max_length=2000)


class IntakeReassignRequest(BaseModel):
    employee_id: str


class IntakeAssignTeamRequest(BaseModel):
    """Hand one or more reviewed leads to a team."""

    lead_ids: list[str] = Field(..., min_length=1, max_length=100)
    team_id: str


class IntakeAssignTeamResponse(BaseModel):
    """What happened to each lead. Partial success is normal: another reviewer
    may have assigned some of the selection a moment earlier."""

    assigned: list[IntakeLeadResponse] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)  # lead ids no longer awaiting review


class IntakeTeamOption(BaseModel):
    """A team a reviewer can assign to, and how loaded it already is."""

    id: str
    name: str
    recruiters: int  # active recruiters the round-robin can pick from
    open_leads: int  # leads its recruiters have not yet mapped


class IntakeSyncResponse(BaseModel):
    """What a manual sync did, or why it did nothing."""

    ran: bool
    detail: str
    created: int = 0
    matched_existing: int = 0
    already_ingested: int = 0
    unusable: int = 0


# ── Naukri import ──────────────────────────────────────────────────────────────


class NaukriPreviewRow(BaseModel):
    """One spreadsheet row as it would be imported."""

    row_number: int
    full_name: str
    phone: str
    email: str | None = None
    city: str | None = None
    designation: str | None = None
    current_company: str | None = None
    experience_years: float = 0
    salary: float | None = None  # ₹ per month, converted from Naukri's yearly figure
    # new: becomes a lead for the telecallers (a new candidate, or one in the
    # pool nobody is screening) · matched_existing: already in the pool and
    # being screened, filed as a duplicate · already_ingested: imported before ·
    # duplicate_in_sheet: this person is on an earlier row of the same file.
    outcome: str
    warnings: list[str] = Field(default_factory=list)


class NaukriSkippedRow(BaseModel):
    row_number: int
    reason: str


class NaukriPreviewResponse(BaseModel):
    """What importing this file would do. Nothing has been written."""

    rows: list[NaukriPreviewRow]
    skipped: list[NaukriSkippedRow]
    new: int
    matched_existing: int
    already_ingested: int
    duplicate_in_sheet: int


class NaukriImportResponse(BaseModel):
    """What importing the file did. Every row lands in exactly one count."""

    rows_read: int
    created: int
    assigned: int  # of those created, handed to a telecaller
    unassigned: int  # created, but no telecaller was active
    matched_existing: int
    already_ingested: int
    repeated_in_file: int
    unusable: int
    errors: list[str] = Field(default_factory=list)


# ── Leads added by hand or from resumes ───────────────────────────────────────


class ResumeLeadDraft(BaseModel):
    """One uploaded resume, read into the lead form's fields. Nothing is saved.

    Every field is a best guess for a person to check; `error` means the file
    couldn't be used at all, `notice` that it was taken but not read.
    """

    filename: str
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    current_role: str | None = None
    department: Department | None = None
    current_company: str | None = None
    experience_years: float | None = None
    error: str | None = None
    notice: str | None = None


class ManualLeadDraft(BaseModel):
    """One lead as a staff member submits it, after checking any resume prefill."""

    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    email: str | None = None
    city: str | None = None
    current_role: str | None = None
    department: Department | None = None
    current_company: str | None = None
    experience_years: float = Field(default=0, ge=0)
    salary: float | None = Field(default=None, ge=0)  # current, ₹ per month
    expected_salary: float | None = Field(default=None, ge=0)  # ₹ per month
    # Which of the uploaded files is this lead's resume, if any.
    resume_index: int | None = Field(default=None, ge=0)

    @field_validator(
        "full_name", "phone", "email", "city", "current_role", "current_company", mode="before"
    )
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ManualLeadResult(BaseModel):
    """What happened to one submitted draft, in submission order."""

    index: int
    full_name: str | None = None
    # queued: with a telecaller · waiting: created, no telecaller active ·
    # duplicate: already in the pool, filed as a duplicate · error: not added.
    status: str
    detail: str


class ManualLeadsResponse(BaseModel):
    results: list[ManualLeadResult]
    queued: int
    waiting: int
    duplicate: int
    error: int


# ── Admin observability ────────────────────────────────────────────────────────


class IntakeLegStats(BaseModel):
    """Time-to-action for one leg of the journey: telecaller, or recruiter.

    Median and p90 sit beside the mean because they answer a different question.
    One lead left over a long weekend drags an average past the SLA on its own,
    which reads as a team problem; the median says whether the team is actually
    slow, and p90 says how bad the tail is.
    """

    assigned: int = 0
    actioned: int = 0
    pending: int = 0
    overdue: int = 0  # still pending, and past the SLA
    avg_hours: float | None = None
    median_hours: float | None = None
    p90_hours: float | None = None
    within_sla: int = 0
    sla_hours: int
    sla_compliance: float | None = None  # within_sla ÷ actioned, 0–1
    oldest_pending_hours: float | None = None
    # Telecaller leg only — the recruiter leg has no accept/reject decision, so
    # these stay None there rather than reporting a rate that does not exist.
    accepted: int | None = None
    rejected: int | None = None
    accept_rate: float | None = None


class IntakePersonStats(IntakeLegStats):
    """One row of the per-telecaller or per-recruiter table."""

    employee_id: str | None = None
    name: str
    email: str | None = None


class IntakeFunnel(BaseModel):
    """Where every lead in the window ended up. The parts sum to `ingested`."""

    ingested: int = 0
    pending_telecaller: int = 0
    unassigned: int = 0
    rejected: int = 0
    pending_review: int = 0
    pending_recruiter: int = 0
    actioned: int = 0
    archived: int = 0
    duplicate: int = 0


class IntakeRejectReasonCount(BaseModel):
    reason: str
    count: int


class IntakeSourceStatus(_UtcTimestamps):
    """How the sheet connection itself is doing, so a silent failure is visible."""

    configured: bool = False
    enabled: bool = False
    last_synced_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class IntakeOverviewResponse(_UtcTimestamps):
    start_date: datetime | None = None
    end_date: datetime | None = None
    funnel: IntakeFunnel
    telecaller: IntakeLegStats
    recruiter: IntakeLegStats
    reject_reasons: list[IntakeRejectReasonCount] = Field(default_factory=list)
    source: IntakeSourceStatus


class IntakeCampaignRow(BaseModel):
    label: str
    leads: int = 0
    accepted: int = 0
    rejected: int = 0  # by the telecaller, on the call
    recruiter_rejected: int = 0  # passed the call, turned down from Review
    actioned: int = 0
    duplicate: int = 0
    accept_rate: float | None = None
    actioned_rate: float | None = None


class IntakeCampaignResponse(BaseModel):
    group_by: str
    rows: list[IntakeCampaignRow] = Field(default_factory=list)


class IntakeLeadPage(BaseModel):
    items: list[IntakeLeadResponse] = Field(default_factory=list)
    meta: PaginationMeta


# ── Configuration ──────────────────────────────────────────────────────────────

_SPREADSHEET_URL = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _spreadsheet_id(value: str) -> str:
    """Accept either a bare id or a pasted Google Sheets URL.

    Everyone copies the URL out of the address bar. Storing that verbatim makes
    the Sheets API return a 404 that reads as a permissions problem, so the
    address is unpicked here instead of debugged there later.
    """
    value = value.strip()
    found = _SPREADSHEET_URL.search(value)
    return found.group(1) if found else value


class IntakeConfigResponse(_UtcTimestamps):
    """The sheet connection as the settings screen shows it.

    Deliberately never carries the service-account key: it lives in the
    environment precisely so it is not readable by anyone who can read this API.
    `credentials_configured` is the only thing said about it.
    """

    configured: bool
    brand_id: str | None = None
    spreadsheet_id: str = ""
    sheet_range: str = ""
    default_source_channel: str = ""
    enabled: bool = False
    activated_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_success_at: datetime | None = None
    last_row_count: int = 0
    last_ingested_count: int = 0
    last_skipped_count: int = 0
    last_error: str | None = None
    consecutive_failures: int = 0
    credentials_configured: bool = False
    poll_minutes: int = 0
    telecaller_sla_hours: int = 0
    recruiter_sla_hours: int = 0


class IntakeConfigUpdate(BaseModel):
    """A partial update — only the fields sent are changed."""

    spreadsheet_id: str | None = None
    sheet_range: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    default_source_channel: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("spreadsheet_id")
    @classmethod
    def _clean_spreadsheet_id(cls, value: str | None) -> str | None:
        return None if value is None else _spreadsheet_id(value)


class IntakeAssignee(BaseModel):
    """Somebody a lead can be handed to, and how much they are already holding."""

    id: str
    name: str
    email: str | None = None
    open_leads: int = 0


class IntakeTelecallerCreate(BaseModel):
    """Make somebody a telecaller, whether or not they have signed up yet."""

    email: EmailStr
    name: str | None = Field(default=None, max_length=200)


class IntakeTelecallerUpdate(BaseModel):
    """Take a telecaller out of the lead rotation, or put them back in it."""

    is_active: bool


class IntakeTelecaller(BaseModel):
    """One row of the telecaller roster on the settings screen.

    `has_account` separates someone who can already open their queue from
    someone provisioned ahead of their first sign-in — the admin needs to know
    which of the two to chase.
    """

    id: str
    name: str
    email: str
    is_active: bool
    has_account: bool
    open_leads: int = 0


class IntakeAssigneesResponse(BaseModel):
    """The two rosters the round-robin draws from, for the reassign picker.

    Separate lists rather than one flat roster with a role field: a lead waiting
    on a telecaller can only go to a telecaller, and flattening them would put
    the wrong half of the company in the dropdown.
    """

    telecallers: list[IntakeAssignee] = Field(default_factory=list)
    recruiters: list[IntakeAssignee] = Field(default_factory=list)
