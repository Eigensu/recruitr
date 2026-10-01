"""Turning a Naukri candidate export (.xlsx) into leads.

Pure functions over the workbook's bytes — no database — like lead_sheet.py,
whose ParsedLead and SkippedRow this produces so the rows go through exactly
the same ingest as the Meta sheet: same duplicate checks, same telecaller
round-robin, same review.

The export this was written against (one sheet, one header row):

    # · Candidate Name · Resume Title · Contact No. · Email · Work Exp
    Annual Salary · Current Location · Preferred Location · Current Employer
    Designation · U.G. Course · P. G. Course · Post P. G. Course
    Age/Date of Birth · Postal Address · Last Active · Comment 1–5

Headers are matched by name after normalisation, never by position, so a
re-ordered or trimmed export still reads; the header row is searched for in
the first few rows, since exports sometimes carry a title above it. Every row
is kept verbatim in `raw`.

Naukri reports salary per year ("INR 3.8 L"). Candidate salaries are per month,
so this is the one place a yearly figure is converted: ₹3.8 L → ₹31,667.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from openpyxl import load_workbook

from app.modules.recruitment.enums import EducationLevel
from app.modules.recruitment.utils.lead_sheet import (
    ParsedLead,
    SkippedRow,
    infer_department,
    normalize_header,
    parse_education_level,
    parse_email,
)
from app.modules.recruitment.utils.phone import normalize_phone

SOURCE_CHANNEL = "Naukri"
# Below this a monthly salary is almost certainly a mis-keyed export value
# ("INR 0.2 L" is ₹1,667 a month); flagged in the preview, never blocked.
LOW_SALARY_WARNING = 5000

_HEADER_SEARCH_ROWS = 10
_LAKH = 100_000
_CRORE = 10_000_000

# Normalised header → field. normalize_header lowercases and collapses
# punctuation to underscores ("Contact No." → "contact_no").
_COLUMNS = {
    "candidate_name": "full_name",
    "name": "full_name",
    "contact_no": "phone",
    "contact_number": "phone",
    "mobile": "phone",
    "mobile_no": "phone",
    "phone": "phone",
    "email": "email",
    "email_id": "email",
    "resume_title": "resume_title",
    "work_exp": "work_exp",
    "work_experience": "work_exp",
    "total_experience": "work_exp",
    "annual_salary": "annual_salary",
    "current_salary": "annual_salary",
    "current_location": "city",
    "preferred_location": "preferred_location",
    "preferred_locations": "preferred_location",
    "current_employer": "current_company",
    "current_company": "current_company",
    "designation": "designation",
    "current_designation": "designation",
    "u_g_course": "ug_course",
    "ug_course": "ug_course",
    "p_g_course": "pg_course",
    "pg_course": "pg_course",
    "post_p_g_course": "post_pg_course",
    "age_date_of_birth": "age",
    "age": "age",
}
_REQUIRED = {"full_name": "Candidate Name", "phone": "Contact No."}

_EXP = re.compile(r"(?:(\d+)\s*y)?\s*(?:(\d+)\s*m)?", re.I)
_SALARY = re.compile(r"([\d,]+(?:\.\d+)?)\s*(lakhs?|lacs?|l|crores?|cr|k)?\b", re.I)
_LEADING_INT = re.compile(r"^\s*(\d{1,3})\b")


class NaukriFileError(ValueError):
    """The file as a whole can't be read as a Naukri export. The message is for the user."""


@dataclass(frozen=True)
class NaukriRows:
    leads: list[ParsedLead]
    skipped: list[SkippedRow]
    # The spreadsheet row each lead came from, aligned with `leads`.
    lead_rows: list[int]


def parse_work_exp(raw: str | None) -> float:
    """Years from "3Y 5 M", "3 Years 5 Months", "11 M", "Fresher" or blank."""
    if not raw:
        return 0.0
    match = _EXP.search(raw.strip())
    if not match or not any(match.groups()):
        return 0.0
    years = int(match.group(1) or 0)
    months = int(match.group(2) or 0)
    return round(years + months / 12, 2)


def parse_monthly_salary(raw: str | None) -> float | None:
    """₹ per month from a yearly figure: "INR 3.8 L" → 31667.

    Lakh, crore and thousand suffixes are honoured; a bare number is read as
    yearly rupees ("INR 3,80,000"). Blank, "Not disclosed" and anything without
    a number give None — no salary is better than an invented one.
    """
    if not raw:
        return None
    match = _SALARY.search(raw)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "").lower()
    if unit.startswith("cr"):
        amount *= _CRORE
    elif unit.startswith("l"):
        amount *= _LAKH
    elif unit == "k":
        amount *= 1000
    return float(round(amount / 12))


def parse_age(raw: str | None) -> int | None:
    """Age from "29 y\\n(06 May 1997)" — the leading number of years."""
    if not raw:
        return None
    match = _LEADING_INT.match(raw)
    if not match:
        return None
    age = int(match.group(1))
    return age if 14 <= age <= 90 else None


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        # A phone stored as a number comes back as 9819844180.0.
        return str(int(value))
    return str(value).strip()


def _find_header(rows: list[tuple]) -> tuple[int, dict[int, str]]:
    for index, row in enumerate(rows[:_HEADER_SEARCH_ROWS]):
        columns: dict[int, str] = {}
        for position, cell in enumerate(row):
            name = _COLUMNS.get(normalize_header(_cell(cell)))
            if name and name not in columns.values():
                columns[position] = name
        if all(field in columns.values() for field in _REQUIRED):
            return index, columns
    missing = " and ".join(f'"{label}"' for label in _REQUIRED.values())
    raise NaukriFileError(
        f"This doesn't look like a Naukri export: no row has the {missing} columns."
    )


def _notes(fields: dict[str, str]) -> str | None:
    parts = []
    if fields.get("resume_title"):
        parts.append(fields["resume_title"])
    if fields.get("preferred_location"):
        parts.append(f"Preferred location: {fields['preferred_location']}")
    return "\n".join(parts) or None


def _education(fields: dict[str, str]) -> tuple[str | None, EducationLevel | None]:
    courses = [fields.get(k, "") for k in ("ug_course", "pg_course", "post_pg_course")]
    text = " / ".join(c for c in courses if c) or None
    # The highest course decides the level; the raw text is kept regardless.
    # Naukri writes courses dotted ("B.sc", "B.com"); the shared matcher knows
    # them undotted. Two-letter ones ("B.a" → "ba") still won't match — on
    # purpose, see parse_education_level: no level beats a wrong one.
    for course in reversed(courses):
        if course and (level := parse_education_level(course.replace(".", ""))):
            return text, level
    return text, None


def _lead(fields: dict[str, str], phone_normalized: str, raw: dict[str, str]) -> ParsedLead:
    designation = fields.get("designation") or None
    education, education_level = _education(fields)
    city = (fields.get("city") or "").split(",")[0].strip() or None
    return ParsedLead(
        # The phone is the identity: re-uploading the same export, or a later
        # one that repeats people, never creates a second lead for them.
        external_id=f"naukri:{phone_normalized}",
        full_name=fields["full_name"],
        phone=fields["phone"],
        phone_normalized=phone_normalized,
        email=parse_email(fields.get("email")),
        city=city,
        current_role=designation,
        experience_years=parse_work_exp(fields.get("work_exp")),
        education=education,
        education_level=education_level,
        department=infer_department(designation),
        source_channel=SOURCE_CHANNEL,
        previous_company=fields.get("current_company") or None,
        salary=parse_monthly_salary(fields.get("annual_salary")),
        age=parse_age(fields.get("age")),
        notes=_notes(fields),
        raw=raw,
    )


def parse_naukri_xlsx(data: bytes) -> NaukriRows:
    """Leads and skipped rows from a Naukri export's bytes.

    Raises NaukriFileError when the file isn't a readable workbook or has no
    header row with the required columns — the whole file is refused then,
    rather than silently importing nothing.
    """
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a zoo of types for a bad file
        raise NaukriFileError("Couldn't read this file. Upload the .xlsx Naukri exported.") from exc
    try:
        rows = list(workbook.worksheets[0].iter_rows(values_only=True))
    finally:
        workbook.close()

    header_index, columns = _find_header(rows)
    headers = [_cell(cell) for cell in rows[header_index]]
    leads: list[ParsedLead] = []
    lead_rows: list[int] = []
    skipped: list[SkippedRow] = []

    for offset, row in enumerate(rows[header_index + 1 :]):
        row_number = header_index + offset + 2  # spreadsheet's own 1-based numbering
        cells = [_cell(cell) for cell in row]
        if not any(cells):
            continue  # trailing blank rows are formatting, not data
        raw = {headers[i]: cells[i] if i < len(cells) else "" for i in range(len(headers))}
        fields = {name: cells[i] if i < len(cells) else "" for i, name in columns.items()}

        phone_normalized = normalize_phone(fields.get("phone"))
        if not fields.get("full_name"):
            skipped.append(SkippedRow(row_number, "no name", raw))
        elif not phone_normalized:
            skipped.append(SkippedRow(row_number, "no usable phone number", raw))
        else:
            leads.append(_lead(fields, phone_normalized, raw))
            lead_rows.append(row_number)

    return NaukriRows(leads=leads, skipped=skipped, lead_rows=lead_rows)


def warnings_for(lead: ParsedLead) -> list[str]:
    """What a person should look at in the preview before importing."""
    out = []
    if lead.salary is not None and lead.salary < LOW_SALARY_WARNING:
        out.append(
            f"Monthly salary ₹{lead.salary:,.0f} looks too low — check the export's Annual Salary."
        )
    return out
