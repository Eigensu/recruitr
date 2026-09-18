"""DTOs for the inbound lead queue."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.common.dtos.pagination import PaginationMeta
from app.modules.recruitment.enums import (
    IntakeDecision,
    IntakeLeadStatus,
    IntakeRejectReason,
)


class IntakeLeadResponse(BaseModel):
    """One lead as the queue shows it.

    Carries the candidate's contact details inline rather than making the client
    fetch the candidate separately: a telecaller works a list of people to ring,
    and the phone number is the whole point of the screen.
    """

    id: str
    status: IntakeLeadStatus
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
    recruiter_id: str | None = None
    recruiter_assigned_at: datetime | None = None
    recruiter_actioned_at: datetime | None = None
    recruiter_response_seconds: int | None = None
    reassignment_count: int = 0
    # Filled on the admin list, where the table is read by someone who does not
    # know the ids; left None on the telecaller's own queue, which is all theirs.
    telecaller_name: str | None = None
    recruiter_name: str | None = None
    # Whether the leg this lead is waiting on is past its SLA. Computed here
    # rather than by the client, which would have to know both limits and be
    # trusted to apply the right one to each status.
    overdue: bool = False


class IntakeAcceptRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class IntakeRejectRequest(BaseModel):
    reason: IntakeRejectReason | None = None
    notes: str | None = Field(default=None, max_length=2000)


class IntakeReassignRequest(BaseModel):
    employee_id: str


class IntakeSyncResponse(BaseModel):
    """What a manual sync did, or why it did nothing."""

    ran: bool
    detail: str
    created: int = 0
    matched_existing: int = 0
    already_ingested: int = 0
    unusable: int = 0


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
    pending_recruiter: int = 0
    actioned: int = 0
    duplicate: int = 0


class IntakeRejectReasonCount(BaseModel):
    reason: str
    count: int


class IntakeSourceStatus(BaseModel):
    """How the sheet connection itself is doing, so a silent failure is visible."""

    configured: bool = False
    enabled: bool = False
    last_synced_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class IntakeOverviewResponse(BaseModel):
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
    rejected: int = 0
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


class IntakeConfigResponse(BaseModel):
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
