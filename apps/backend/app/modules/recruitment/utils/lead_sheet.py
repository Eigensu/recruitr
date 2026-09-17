"""Turning rows of a Meta lead-ads sheet into candidate-shaped data.

Pure functions, no database and no network, because this is the part most
exposed to change: the columns are Meta form questions, and the wording of a
question is the advertiser's to edit at any time. Everything here is therefore
tolerant — headers are matched after normalisation, then by keyword — and every
row is kept verbatim in `raw` so a mapping that guesses wrong stays diagnosable
and a column added to the form is never silently dropped.

The sheet this was written against:

    id · created_time · ad_id · ad_name · adset_id · adset_name · campaign_id
    campaign_name · form_id · form_name · is_organic · platform
    highest_educational_qualification · what_role_are_you_interested_in?
    experience_working_in_the_f&b_industry_(in_years)?_(restaurants,_cafe,...)
    your_current_role? · your_current_location? · full_name · email
    phone_number · lead_status
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache

from app.modules.recruitment.enums import Department, EducationLevel
from app.modules.recruitment.utils.constants import ROLES_BY_CATEGORY
from app.modules.recruitment.utils.phone import normalize_phone

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_FIRST_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def normalize_header(header: str) -> str:
    """Fold a column heading to a comparable key.

    "Your current role?", "your_current_role?" and "YOUR CURRENT ROLE" are the
    same question; Meta's export and a human editing the sheet disagree about
    case, spaces and punctuation, and none of that should break ingest.
    """
    return _NON_ALNUM.sub("_", header.strip().lower()).strip("_")


# Stable machine-generated columns: matched exactly, after normalisation.
_EXACT_COLUMNS: dict[str, str] = {
    "id": "external_id",
    "created_time": "created_time",
    "ad_id": "ad_id",
    "ad_name": "ad_name",
    "adset_id": "adset_id",
    "adset_name": "adset_name",
    "campaign_id": "campaign_id",
    "campaign_name": "campaign_name",
    "form_id": "form_id",
    "form_name": "form_name",
    "is_organic": "is_organic",
    "platform": "platform",
    "full_name": "full_name",
    "email": "email",
    "phone_number": "phone",
    "phone": "phone",
    "lead_status": "lead_status",
}

# Form questions, matched by keyword because the wording is editable. Ordered:
# the first match wins, so the more specific phrase has to come first —
# "your_current_role?" and "what_role_are_you_interested_in?" both contain
# "role", and reading the second as the first would record the job someone wants
# as the job they already have.
_KEYWORD_COLUMNS: list[tuple[str, str]] = [
    ("current_role", "current_role"),
    ("current_location", "city"),
    ("interested", "role_interest"),
    ("experience", "experience_years"),
    ("qualification", "education"),
    ("education", "education"),
    ("location", "city"),
    ("city", "city"),
]


def resolve_columns(headers: list[str], overrides: dict[str, str] | None = None) -> dict[int, str]:
    """Map column index -> field name for the headers we recognise.

    `overrides` is keyed by raw or normalised header and wins over both tables,
    so a column can be retargeted from configuration without a deploy.
    """
    normalized_overrides = {
        normalize_header(key): value for key, value in (overrides or {}).items()
    }
    resolved: dict[int, str] = {}

    for index, header in enumerate(headers):
        key = normalize_header(header)
        if key in normalized_overrides:
            resolved[index] = normalized_overrides[key]
            continue
        if key in _EXACT_COLUMNS:
            resolved[index] = _EXACT_COLUMNS[key]
            continue
        for needle, field_name in _KEYWORD_COLUMNS:
            if needle in key:
                resolved[index] = field_name
                break

    return resolved


# ── Value parsing ──────────────────────────────────────────────────────────────


def parse_experience_years(raw: str | None) -> float:
    """Years of experience from free text, defaulting to 0.

    Answers arrive as "2", "2.5", "2-3 years", "more than 5", "fresher" and
    blanks. The first number in the string is the honest reading of all of them:
    for a range it is the low end, which under-promises rather than over.
    """
    if not raw:
        return 0.0
    match = _FIRST_NUMBER.search(raw)
    if not match:
        return 0.0
    try:
        return max(0.0, float(match.group()))
    except ValueError:  # pragma: no cover - the regex only matches numbers
        return 0.0


# Substrings that identify a qualification, most specific first: "post graduate"
# contains "graduate", so bachelors must not be tested first.
#
# Every needle here is long enough to be unambiguous. Short ones like "ba" and
# "pg" were removed: they match inside unrelated words, and a wrong rung is
# worse than none, because the raw answer is stored either way and only the
# derived field would be lying.
_EDUCATION_RULES: list[tuple[tuple[str, ...], EducationLevel]] = [
    (("phd", "doctorate"), EducationLevel.phd),
    (
        ("post grad", "postgrad", "post_grad", "master", "mba", "m.tech", "mtech"),
        EducationLevel.masters,
    ),
    (
        ("graduate", "bachelor", "degree", "b.tech", "btech", "bsc", "bcom"),
        EducationLevel.bachelors,
    ),
    (("10th", "12th", "ssc", "hsc", "high school", "highschool"), EducationLevel.high_school),
]


def parse_education_level(raw: str | None) -> EducationLevel | None:
    """Best-effort EducationLevel. The raw answer is stored regardless.

    None is a normal outcome, not a failure: "Diploma" and "ITI" are common
    answers here and belong to no rung of this four-value enum. Forcing them
    into the nearest one would put a claim in the record that the candidate
    never made.
    """
    if not raw:
        return None
    text = raw.strip().lower()
    for needles, level in _EDUCATION_RULES:
        if any(needle in text for needle in needles):
            return level
    return None


@lru_cache(maxsize=1)
def _role_index() -> dict[str, Department]:
    """Role name -> department, built once. Rebuilding it per row would walk the
    whole catalogue for every lead in the sheet."""
    return {
        role.lower(): department
        for department, roles in ROLES_BY_CATEGORY.items()
        for role in roles
    }


def infer_department(role_text: str | None) -> Department | None:
    """Which department a stated role interest belongs to, if it is one we know.

    Matched against the same role catalogue the rest of the app uses, so an
    ingested lead lands in the same department a recruiter would have picked.
    """
    if not role_text:
        return None
    text = role_text.strip().lower()
    index = _role_index()
    if text in index:
        return index[text]
    # "Bartender / Mixologist", "chef (commi 1)" — the answer is free text and
    # often carries the role inside it.
    for role, department in index.items():
        if role in text:
            return department
    return None


_PLATFORMS = {"ig": "Instagram", "instagram": "Instagram", "fb": "Facebook", "facebook": "Facebook"}


def parse_source_channel(raw: str | None, default: str) -> str:
    """Meta's platform code as the channel name the rest of the app uses.

    dashboard/repository.py already sorts "instagram" and "facebook" into
    Social Media for the sourcing analytics, so these names slot straight in.
    """
    if not raw or not raw.strip():
        return default
    return _PLATFORMS.get(raw.strip().lower(), raw.strip().title())


_TRUTHY = {"true", "yes", "1", "y"}


def parse_bool(raw: str | None) -> bool | None:
    if raw is None or not raw.strip():
        return None
    return raw.strip().lower() in _TRUTHY


def parse_timestamp(raw: str | None) -> datetime | None:
    """Meta's created_time as a timezone-aware datetime, or None.

    Naive values are read as UTC. They are compared against the ingest cutoff
    and stored beside timezone-aware fields, and in Python a naive datetime
    raises on comparison with an aware one rather than sorting oddly — so an
    unparsed offset would take down the poll, not just skew a timestamp.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_email(raw: str | None) -> str | None:
    """A usable address, lowercased, or None.

    Anything that is not one is dropped rather than stored: Candidate.email
    carries a unique index, and a sheet full of "-" or "n/a" would collide on
    the second row.
    """
    if not raw:
        return None
    text = raw.strip().lower()
    return text if _EMAIL.match(text) else None


# ── Rows ───────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedLead:
    """One sheet row, parsed. Candidate-shaped fields plus lead provenance."""

    external_id: str
    full_name: str
    phone: str
    phone_normalized: str
    email: str | None = None
    city: str | None = None
    current_role: str | None = None
    experience_years: float = 0.0
    education: str | None = None
    education_level: EducationLevel | None = None
    role_interest: str | None = None
    department: Department | None = None
    source_channel: str = "Instagram"
    external_created_at: datetime | None = None
    external_status: str | None = None
    is_organic: bool | None = None
    attribution: dict[str, str | None] = field(default_factory=dict)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkippedRow:
    """A row that could not become a candidate, and why. Reported, never dropped silently."""

    row_number: int  # 1-based, matching the spreadsheet's own row numbering
    reason: str
    raw: dict[str, str]


_ATTRIBUTION_FIELDS = (
    "ad_id",
    "ad_name",
    "adset_id",
    "adset_name",
    "campaign_id",
    "campaign_name",
    "form_id",
    "form_name",
)


def parse_rows(
    values: list[list[str]],
    *,
    default_source_channel: str = "Instagram",
    overrides: dict[str, str] | None = None,
) -> tuple[list[ParsedLead], list[SkippedRow]]:
    """Parse a sheet range (first row = headers) into leads and skipped rows.

    Google omits trailing empty cells, so a row is frequently shorter than the
    header list; cells are read by index with a blank default rather than
    zipped, which would drop real values whenever a row happened to be short.
    """
    if not values:
        return [], []

    headers = [str(cell) for cell in values[0]]
    columns = resolve_columns(headers, overrides)
    leads: list[ParsedLead] = []
    skipped: list[SkippedRow] = []

    for offset, row in enumerate(values[1:]):
        row_number = offset + 2  # +1 for the header, +1 for 1-based numbering
        raw = {
            headers[index]: str(row[index]).strip() if index < len(row) else ""
            for index in range(len(headers))
        }
        fields = {
            name: (str(row[index]).strip() if index < len(row) else "")
            for index, name in columns.items()
        }

        external_id = fields.get("external_id", "")
        full_name = fields.get("full_name", "")
        phone = fields.get("phone", "")
        phone_normalized = normalize_phone(phone)

        if not external_id:
            skipped.append(SkippedRow(row_number, "no lead id", raw))
            continue
        if not full_name:
            skipped.append(SkippedRow(row_number, "no name", raw))
            continue
        if not phone_normalized:
            # Without a phone there is nothing for a telecaller to call, and
            # nothing to deduplicate on.
            skipped.append(SkippedRow(row_number, "no usable phone number", raw))
            continue

        role_interest = fields.get("role_interest") or None
        education = fields.get("education") or None
        leads.append(
            ParsedLead(
                external_id=external_id,
                full_name=full_name,
                phone=phone,
                phone_normalized=phone_normalized,
                email=parse_email(fields.get("email")),
                city=fields.get("city") or None,
                current_role=fields.get("current_role") or None,
                experience_years=parse_experience_years(fields.get("experience_years")),
                education=education,
                education_level=parse_education_level(education),
                role_interest=role_interest,
                department=infer_department(role_interest),
                source_channel=parse_source_channel(fields.get("platform"), default_source_channel),
                external_created_at=parse_timestamp(fields.get("created_time")),
                external_status=fields.get("lead_status") or None,
                is_organic=parse_bool(fields.get("is_organic")),
                attribution={name: fields.get(name) or None for name in _ATTRIBUTION_FIELDS},
                raw=raw,
            )
        )

    return leads, skipped
