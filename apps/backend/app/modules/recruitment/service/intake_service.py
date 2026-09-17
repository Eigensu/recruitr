"""Turning parsed sheet rows into candidates, leads, and telecaller assignments.

The sheet read itself lives in `utils/google_sheets.py` and the parsing in
`utils/lead_sheet.py`; everything here is database work, so it is testable
against a local Mongo with no credentials and no network.

Two rules shape the whole module:

  - **Ingest is idempotent.** `(brand_id, external_id)` is unique on IntakeLead,
    so re-reading a row is a no-op. That is what lets the poll read the entire
    range every few minutes instead of tracking a cursor into someone else's
    spreadsheet.
  - **Nothing is ever dropped silently.** A row that cannot become a candidate
    is counted and reported; a lead that arrives with no telecaller to take it
    is stored `unassigned` and shows up for an admin, rather than vanishing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.modules.auth.models import NON_RECRUITER_ROLES, UserRole
from app.modules.recruitment.enums import (
    CandidateEventType,
    CandidateStatus,
    IntakeLeadStatus,
    IntakeSource,
)
from app.modules.recruitment.models import (
    Candidate,
    Employee,
    IntakeAttribution,
    IntakeLead,
    IntakeSourceConfig,
)
from app.modules.recruitment.repository import next_seq, record_candidate_event
from app.modules.recruitment.schemas import TenantScope
from app.modules.recruitment.utils.lead_sheet import ParsedLead, parse_rows
from app.modules.recruitment.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

# Counter keys for the two round-robin cursors. next_seq() is an atomic $inc,
# so two workers assigning at the same moment get different numbers.
_TELECALLER_CURSOR = "intake_telecaller_rr"
_RECRUITER_CURSOR = "intake_recruiter_rr"


@dataclass
class IngestResult:
    """What one ingest run did. Every input row lands in exactly one count."""

    rows_read: int = 0  # data rows in the sheet, excluding the header
    unusable: int = 0  # no lead id, no name, or no usable phone
    before_cutoff: int = 0  # older than the integration's activation
    already_ingested: int = 0
    matched_existing: int = 0  # the person is already in the candidate pool
    created: int = 0
    assigned: int = 0  # of those created, handed to a telecaller
    unassigned: int = 0  # created, but no telecaller was available
    errors: list[str] = field(default_factory=list)

    @property
    def accounted_for(self) -> int:
        return (
            self.unusable
            + self.before_cutoff
            + self.already_ingested
            + self.matched_existing
            + self.created
        )


class _ContactRow(BaseModel):
    """Projection: the two fields a lead can be matched against.

    Projected rather than loaded whole — Candidate carries `resume_raw_text`,
    and pulling every document in the brand to read two fields would drag the
    full text of every CV through the poll.
    """

    id: PydanticObjectId = Field(alias="_id")
    phone: str | None = None
    email: str | None = None


class _ContactIndex:
    """Phone and email of every live candidate, for matching leads against.

    Built per run and updated as rows are ingested, because the same person can
    appear twice in one sheet: Meta issues a new lead id each time someone
    submits the form again, so both rows are new to the `external_id` check and
    only this stops the second one creating a duplicate candidate.
    """

    def __init__(self) -> None:
        self._by_phone: dict[str, PydanticObjectId] = {}
        self._by_email: dict[str, PydanticObjectId] = {}

    @classmethod
    async def build(cls, brand_id: PydanticObjectId) -> _ContactIndex:
        index = cls()
        rows = (
            await Candidate.find({"brand_id": brand_id, "is_active": True})
            .project(_ContactRow)
            .to_list()
        )
        for row in rows:
            index.add(row.id, row.phone, row.email)
        return index

    def add(self, candidate_id: PydanticObjectId, phone: str | None, email: str | None) -> None:
        normalized = normalize_phone(phone)
        if normalized:
            self._by_phone.setdefault(normalized, candidate_id)
        if email:
            self._by_email.setdefault(email.strip().lower(), candidate_id)

    def match(self, lead: ParsedLead) -> PydanticObjectId | None:
        """The candidate this lead is already in the pool as, if any."""
        found = self._by_phone.get(lead.phone_normalized)
        if found is None and lead.email:
            found = self._by_email.get(lead.email)
        return found


# ── Assignment ─────────────────────────────────────────────────────────────────


async def _roster(brand_id: PydanticObjectId, *, telecallers: bool) -> list[Employee]:
    """Active telecallers, or active recruiters, in a stable order.

    Recruiters are selected by excluding NON_RECRUITER_ROLES rather than by
    matching "employee": Employee rows written before the role field existed
    carry no role at all, and those are recruiters.
    """
    role_filter = (
        {"role": UserRole.telecaller.value}
        if telecallers
        else {"role": {"$nin": list(NON_RECRUITER_ROLES)}}
    )
    return (
        await Employee.find({"brand_id": brand_id, "is_active": True, **role_filter})
        .sort("_id")
        .to_list()
    )


async def next_assignee(brand_id: PydanticObjectId, *, telecallers: bool) -> Employee | None:
    """The next person in the round-robin, or None if nobody is available.

    The cursor is a Counter document incremented with findOneAndUpdate, the same
    primitive behind client and position codes: atomic without a transaction, so
    two concurrent assignments cannot land on the same person. Gaps are harmless
    — the cursor only has to keep moving.
    """
    roster = await _roster(brand_id, telecallers=telecallers)
    if not roster:
        return None
    cursor = _TELECALLER_CURSOR if telecallers else _RECRUITER_CURSOR
    seq = await next_seq(brand_id, cursor)
    return roster[seq % len(roster)]


# ── Ingest ─────────────────────────────────────────────────────────────────────


def _candidate_from(lead: ParsedLead, brand_id: PydanticObjectId) -> Candidate:
    return Candidate(
        brand_id=brand_id,
        full_name=lead.full_name,
        phone=lead.phone,
        email=lead.email,
        city=lead.city,
        current_role=lead.current_role,
        experience_years=lead.experience_years,
        education=lead.education,
        education_level=lead.education_level,
        specialization=lead.role_interest,
        department=lead.department,
        source="external",
        source_channel=lead.source_channel,
        # PENDING keeps them out of the recruiter directory, which filters to
        # APPROVED, until a telecaller has actually spoken to them.
        status=CandidateStatus.pending,
        # Nobody sourced this person; an ad did. Leaving the owner unset keeps
        # the record shared rather than locking its CV to one recruiter.
        created_by_id=None,
    )


def _lead_from(
    lead: ParsedLead,
    *,
    brand_id: PydanticObjectId,
    candidate_id: PydanticObjectId,
    status: IntakeLeadStatus,
    telecaller: Employee | None,
    assigned_at: datetime | None,
) -> IntakeLead:
    return IntakeLead(
        brand_id=brand_id,
        candidate_id=candidate_id,
        source=IntakeSource.google_sheet,
        source_channel=lead.source_channel,
        external_id=lead.external_id,
        external_created_at=lead.external_created_at,
        external_status=lead.external_status,
        is_organic=lead.is_organic,
        attribution=IntakeAttribution(**lead.attribution),
        raw=lead.raw,
        status=status,
        telecaller_id=telecaller.id if telecaller else None,
        telecaller_assigned_at=assigned_at if telecaller else None,
    )


async def _already_ingested_ids(
    brand_id: PydanticObjectId, leads: Sequence[ParsedLead]
) -> set[str]:
    """Which of these external ids this brand already holds — one query, not N."""
    if not leads:
        return set()
    existing = await IntakeLead.find(
        {"brand_id": brand_id, "external_id": {"$in": [lead.external_id for lead in leads]}}
    ).to_list()
    return {row.external_id for row in existing}


async def ingest_leads(
    leads: Sequence[ParsedLead],
    *,
    brand_id: PydanticObjectId,
    assign: bool = True,
    now: datetime | None = None,
) -> IngestResult:
    """Create candidates and leads for rows not already known.

    `assign=False` files everything as `unassigned`, which is what the historical
    backfill uses: assigning leads that are months old would breach their SLA the
    moment the next sweep ran, on every one of them at once.
    """
    result = IngestResult(rows_read=len(leads))
    seen = await _already_ingested_ids(brand_id, leads)
    index = await _ContactIndex.build(brand_id)
    scope = TenantScope(brand_id=brand_id)
    stamp = now or datetime.now(UTC)

    for lead in leads:
        if lead.external_id in seen:
            result.already_ingested += 1
            continue
        seen.add(lead.external_id)

        existing_id = index.match(lead)
        candidate_id = existing_id
        created_candidate: Candidate | None = None

        if existing_id is None:
            created_candidate = _candidate_from(lead, brand_id)
            try:
                await created_candidate.insert()
            except DuplicateKeyError:
                # Candidate.email is uniquely indexed per brand. The contact
                # index is built from live candidates only, so an archived
                # record with the same address still collides here.
                result.errors.append(f"{lead.external_id}: duplicate email {lead.email}")
                continue
            candidate_id = created_candidate.id

        telecaller = None
        if existing_id is not None:
            status = IntakeLeadStatus.duplicate
        elif assign:
            telecaller = await next_assignee(brand_id, telecallers=True)
            status = (
                IntakeLeadStatus.pending_telecaller if telecaller else IntakeLeadStatus.unassigned
            )
        else:
            status = IntakeLeadStatus.unassigned

        try:
            await _lead_from(
                lead,
                brand_id=brand_id,
                candidate_id=candidate_id,  # type: ignore[arg-type]
                status=status,
                telecaller=telecaller,
                assigned_at=stamp,
            ).insert()
        except DuplicateKeyError:
            # Another run ingested this lead between the pre-check and here.
            # The candidate just created belongs to that run's lead, so retire
            # this copy rather than leaving an orphan in the directory.
            if created_candidate is not None:
                await created_candidate.set({"is_active": False})
            result.already_ingested += 1
            continue

        if existing_id is not None:
            result.matched_existing += 1
            continue

        index.add(candidate_id, lead.phone, lead.email)  # type: ignore[arg-type]
        result.created += 1
        if telecaller is not None:
            result.assigned += 1
        else:
            result.unassigned += 1

        await record_candidate_event(
            scope=scope,
            candidate_id=candidate_id,  # type: ignore[arg-type]
            event_type=CandidateEventType.applied,
            note=f"Inbound lead from {lead.source_channel}",
        )

    return result


# ── Configuration ──────────────────────────────────────────────────────────────


async def _sole_brand_id() -> PydanticObjectId | None:
    """The brand, when there is exactly one.

    Fetches two and acts only on one, the same way ensure_employee_for_user
    does: with several brands there is nothing to choose on, and guessing would
    file another tenant's leads into this one. The id is never hardcoded.
    """
    from app.modules.brands.models import Brand

    brands = await Brand.find({}).limit(2).to_list()
    return brands[0].id if len(brands) == 1 else None


async def resolve_source_config() -> IntakeSourceConfig | None:
    """The sheet configuration, seeded from the environment on first use.

    The row is the source of truth once it exists, so an admin editing the tab
    name in the UI is not overwritten by a stale environment variable on the
    next deploy.
    """
    config = await IntakeSourceConfig.find_one({})
    if config is not None:
        return config

    brand_id = await _sole_brand_id()
    if brand_id is None or not settings.INTAKE_SPREADSHEET_ID:
        return None

    config = IntakeSourceConfig(
        brand_id=brand_id,
        spreadsheet_id=settings.INTAKE_SPREADSHEET_ID,
        sheet_range=settings.INTAKE_SHEET_RANGE,
        enabled=settings.GOOGLE_SHEETS_ENABLED,
        # Stamped now, so the first poll ingests what arrives from here on and
        # leaves the sheet's history to scripts/backfill_intake_leads.py.
        activated_at=datetime.now(UTC) if settings.GOOGLE_SHEETS_ENABLED else None,
    )
    await config.insert()
    return config


def before_cutoff(lead: ParsedLead, cutoff: datetime | None) -> bool:
    """Whether this lead predates the integration being switched on.

    A lead with no readable timestamp is treated as current rather than
    historical. Meta always sends `created_time`, so a missing one means the
    column was renamed or the value was unparseable — and dropping live leads
    because of a formatting change is far worse than importing an old one.
    """
    if cutoff is None or lead.external_created_at is None:
        return False
    return lead.external_created_at < cutoff


# ── Poll ───────────────────────────────────────────────────────────────────────


async def poll_google_sheet() -> IngestResult | None:
    """Read the configured sheet and ingest anything new. None if not configured.

    Failures are recorded on the configuration row rather than raised: this runs
    on a schedule with no user attached, and the admin screen needs to be able
    to say why the last read did not work.
    """
    from app.modules.recruitment.utils.google_sheets import (
        SheetConfigurationError,
        SheetReadError,
        fetch_values,
    )

    if not settings.GOOGLE_SHEETS_ENABLED:
        return None

    config = await resolve_source_config()
    if config is None or not config.enabled:
        return None

    now = datetime.now(UTC)
    try:
        values = await fetch_values(config.spreadsheet_id, config.sheet_range)
    except (SheetConfigurationError, SheetReadError) as exc:
        logger.exception("Intake poll failed to read the sheet")
        await config.set(
            {
                "last_synced_at": now,
                "last_error": str(exc),
                "consecutive_failures": config.consecutive_failures + 1,
            }
        )
        return None

    leads, skipped = parse_rows(
        values,
        default_source_channel=config.default_source_channel,
        overrides=settings.intake_column_overrides,
    )
    current = [lead for lead in leads if not before_cutoff(lead, config.activated_at)]

    result = await ingest_leads(current, brand_id=config.brand_id, assign=True, now=now)
    result.rows_read = max(len(values) - 1, 0)
    result.unusable = len(skipped)
    result.before_cutoff = len(leads) - len(current)

    await config.set(
        {
            "last_synced_at": now,
            "last_success_at": now,
            "last_row_count": result.rows_read,
            "last_ingested_count": result.created,
            "last_skipped_count": result.unusable + result.already_ingested,
            "last_error": None,
            "consecutive_failures": 0,
        }
    )
    logger.info(
        "Intake poll: %d rows, %d created, %d matched existing, %d already ingested, %d unusable",
        result.rows_read,
        result.created,
        result.matched_existing,
        result.already_ingested,
        result.unusable,
    )
    return result


# ── Preview (read-only) ────────────────────────────────────────────────────────


@dataclass
class IngestPlan:
    """What an ingest would do, worked out without writing anything.

    The backfill's report mode. It reuses the same _ContactIndex and the same
    order of checks as ingest_leads, so the numbers it prints are the numbers
    you get — a separate reimplementation of "is this a duplicate" would drift
    from the real one exactly when it mattered.
    """

    rows_read: int = 0
    unusable: int = 0
    before_cutoff: int = 0
    already_ingested: int = 0
    matched_existing: int = 0
    duplicate_in_sheet: int = 0
    new: int = 0


async def contact_coverage(brand_id: PydanticObjectId) -> tuple[int, int]:
    """(live candidates, how many of them a lead could actually be matched to).

    The second number is the honest ceiling on deduplication: a candidate with
    no usable phone and no email cannot be recognised however many times the
    same person fills in the form.
    """
    rows = (
        await Candidate.find({"brand_id": brand_id, "is_active": True})
        .project(_ContactRow)
        .to_list()
    )
    reachable = sum(1 for row in rows if normalize_phone(row.phone) or row.email)
    return len(rows), reachable


async def plan_ingest(leads: Sequence[ParsedLead], *, brand_id: PydanticObjectId) -> IngestPlan:
    """Classify rows against the database without touching it."""
    plan = IngestPlan(rows_read=len(leads))
    seen = await _already_ingested_ids(brand_id, leads)
    index = await _ContactIndex.build(brand_id)
    # Candidates this plan would create, so the second row for one person counts
    # as a duplicate within the sheet rather than as another new candidate.
    pending: set[PydanticObjectId] = set()

    for lead in leads:
        if lead.external_id in seen:
            plan.already_ingested += 1
            continue
        seen.add(lead.external_id)

        match = index.match(lead)
        if match is None:
            placeholder = PydanticObjectId()
            pending.add(placeholder)
            index.add(placeholder, lead.phone, lead.email)
            plan.new += 1
        elif match in pending:
            plan.duplicate_in_sheet += 1
        else:
            plan.matched_existing += 1

    return plan
