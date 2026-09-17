"""DTOs for the inbound lead queue."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

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
