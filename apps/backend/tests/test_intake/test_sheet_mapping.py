"""Reading the Meta lead-ads sheet: headers, values, and which rows are unusable.

No database and no network — this is all pure parsing, and it is the layer that
breaks when someone edits the wording of a form question.

HEADERS below is the real header row of the connected sheet, copied verbatim
(including the "?" and the parenthesised aside in the experience question), so
these tests fail if the mapping stops fitting the sheet we actually read.
"""

import pytest

from app.modules.recruitment.enums import Department, EducationLevel
from app.modules.recruitment.utils.lead_sheet import (
    infer_department,
    normalize_header,
    parse_education_level,
    parse_email,
    parse_experience_years,
    parse_rows,
    parse_source_channel,
    parse_timestamp,
    resolve_columns,
)
from app.modules.recruitment.utils.phone import normalize_phone


@pytest.fixture(autouse=True)
def init_test_db():
    """Shadow conftest's autouse fixture — nothing here touches Mongo.

    That fixture creates and drops a database per test, which costs about two
    seconds each. These are pure functions, so the module pays ~100s for a
    connection it never uses.
    """
    yield


HEADERS = [
    "id",
    "created_time",
    "ad_id",
    "ad_name",
    "adset_id",
    "adset_name",
    "campaign_id",
    "campaign_name",
    "form_id",
    "form_name",
    "is_organic",
    "platform",
    "highest_educational_qualification",
    "what_role_are_you_interested_in?",
    "experience_working_in_the_f&b_industry_(in_years)?_(restaurants,_cafe,_hotels,_bars,_pubs_etc)",
    "your_current_role?",
    "your_current_location?",
    "full_name",
    "email",
    "phone_number",
    "lead_status",
]


def _row(**overrides: str) -> list[str]:
    """A complete, valid sheet row, with named columns replaced."""
    values = {
        "id": "l_1001",
        "created_time": "2026-09-15T10:23:45+05:30",
        "ad_id": "ad_1",
        "ad_name": "Bartender Sept",
        "adset_id": "as_1",
        "adset_name": "Mumbai 21-35",
        "campaign_id": "c_1",
        "campaign_name": "F&B Hiring Sept",
        "form_id": "f_1",
        "form_name": "Apply now",
        "is_organic": "false",
        "platform": "ig",
        "highest_educational_qualification": "Graduate",
        "what_role_are_you_interested_in?": "Bartender",
        "experience_working_in_the_f&b_industry_(in_years)?_(restaurants,_cafe,_hotels,_bars,_pubs_etc)": "2-3 years",
        "your_current_role?": "Barback",
        "your_current_location?": "Andheri",
        "full_name": "Asha Rao",
        "email": "asha@example.com",
        "phone_number": "+91 98765 43210",
        "lead_status": "new",
    }
    values.update(overrides)
    return [values[header] for header in HEADERS]


# ── Headers ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "header",
    ["Your current role?", "your_current_role?", "YOUR CURRENT ROLE", "  your current role  "],
)
def test_headers_fold_to_the_same_key_however_they_are_written(header: str):
    assert normalize_header(header) == "your_current_role"


def test_the_real_header_row_maps_every_field_we_need():
    columns = resolve_columns(HEADERS)

    assert {HEADERS[index]: name for index, name in columns.items()} == {
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
        "highest_educational_qualification": "education",
        "what_role_are_you_interested_in?": "role_interest",
        HEADERS[14]: "experience_years",
        "your_current_role?": "current_role",
        "your_current_location?": "city",
        "full_name": "full_name",
        "email": "email",
        "phone_number": "phone",
        "lead_status": "lead_status",
    }


def test_the_two_role_questions_are_not_confused():
    # Both contain "role". Reading the wrong one records the job someone wants
    # as the job they already have.
    columns = resolve_columns(["your_current_role?", "what_role_are_you_interested_in?"])

    assert columns == {0: "current_role", 1: "role_interest"}


def test_an_override_retargets_a_renamed_column():
    columns = resolve_columns(
        ["Which area do you live in?"], overrides={"Which area do you live in?": "city"}
    )

    assert columns == {0: "city"}


def test_an_unknown_column_is_left_unmapped_rather_than_guessed():
    assert resolve_columns(["favourite_colour"]) == {}


# ── Values ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2", 2.0),
        ("2.5", 2.5),
        ("2-3 years", 2.0),  # the low end of a range under-promises
        ("more than 5", 5.0),
        ("fresher", 0.0),
        ("", 0.0),
        (None, 0.0),
    ],
)
def test_experience_is_read_from_free_text(raw: str | None, expected: float):
    assert parse_experience_years(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Post Graduate", EducationLevel.masters),
        ("Graduate", EducationLevel.bachelors),
        ("12th", EducationLevel.high_school),
        ("PhD", EducationLevel.phd),
        # Real answers that belong to no rung of the enum. None is correct; the
        # raw text is kept on the candidate either way.
        ("Diploma", None),
        ("ITI", None),
        ("", None),
    ],
)
def test_qualifications_map_only_when_unambiguous(raw: str, expected: EducationLevel | None):
    assert parse_education_level(raw) == expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("Bartender", Department.service),
        ("Commi 1", Department.boh),
        ("Bartender / Mixologist", Department.service),  # free text around a known role
        ("Astronaut", None),
    ],
)
def test_department_is_inferred_from_the_role_catalogue(role: str, expected: Department | None):
    assert infer_department(role) == expected


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("ig", "Instagram"), ("fb", "Facebook"), ("instagram", "Instagram"), ("", "Instagram")],
)
def test_platform_becomes_a_channel_name(platform: str, expected: str):
    assert parse_source_channel(platform, "Instagram") == expected


@pytest.mark.parametrize("raw", ["", "n/a", "-", "not-an-email", None])
def test_junk_emails_are_dropped(raw: str | None):
    # Candidate.email is uniquely indexed; storing "n/a" would make the second
    # such row a duplicate-key error.
    assert parse_email(raw) is None


def test_timestamps_always_come_back_timezone_aware():
    assert parse_timestamp("2026-09-15T10:23:45+05:30").utcoffset().total_seconds() == 19800
    # Naive input is read as UTC. A naive datetime would raise on comparison
    # with the aware ingest cutoff, taking down the poll rather than skewing.
    assert parse_timestamp("2026-09-15 10:23:45").tzinfo is not None
    assert parse_timestamp("") is None
    assert parse_timestamp("not a date") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+919876543210", "9876543210"),
        ("919876543210", "9876543210"),
        ("09876543210", "9876543210"),
        ("98765 43210", "9876543210"),
        ("+91-98765-43210", "9876543210"),
        ("12345", None),
        ("n/a", None),
        ("", None),
        (None, None),
    ],
)
def test_phone_numbers_reduce_to_ten_digits(raw: str | None, expected: str | None):
    assert normalize_phone(raw) == expected


# ── Rows ───────────────────────────────────────────────────────────────────────


def test_a_full_row_becomes_a_lead():
    leads, skipped = parse_rows([HEADERS, _row()])

    assert not skipped
    (lead,) = leads
    assert lead.external_id == "l_1001"
    assert lead.full_name == "Asha Rao"
    assert lead.phone == "+91 98765 43210"
    assert lead.phone_normalized == "9876543210"
    assert lead.email == "asha@example.com"
    assert lead.city == "Andheri"
    assert lead.current_role == "Barback"
    assert lead.experience_years == 2.0
    assert lead.education == "Graduate"
    assert lead.education_level == EducationLevel.bachelors
    assert lead.role_interest == "Bartender"
    assert lead.department == Department.service
    assert lead.source_channel == "Instagram"
    assert lead.external_status == "new"
    assert lead.is_organic is False
    assert lead.attribution["campaign_name"] == "F&B Hiring Sept"
    assert lead.external_created_at is not None


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("full_name", "", "no name"),
        ("phone_number", "", "no usable phone number"),
        ("phone_number", "n/a", "no usable phone number"),
        ("id", "", "no lead id"),
    ],
)
def test_unusable_rows_are_reported_not_dropped(column: str, value: str, reason: str):
    leads, skipped = parse_rows([HEADERS, _row(**{column: value})])

    assert not leads
    assert [(row.row_number, row.reason) for row in skipped] == [(2, reason)]
    # The row survives on the report so somebody can see what was rejected.
    assert skipped[0].raw["full_name"] or column == "full_name"


def test_a_short_row_does_not_break_or_shift_columns():
    # Google omits trailing empty cells, so rows arrive shorter than the header
    # row. Zipping headers against cells would silently misalign every field.
    short = _row()[:18]  # cut email, phone_number, lead_status

    leads, skipped = parse_rows([HEADERS, short])

    assert not leads
    assert skipped[0].reason == "no usable phone number"


def test_every_column_is_kept_verbatim_including_unmapped_ones():
    headers = [*HEADERS, "favourite_colour"]
    row = [*_row(), "blue"]

    leads, _ = parse_rows([headers, row])

    assert leads[0].raw["favourite_colour"] == "blue"
    assert leads[0].raw["what_role_are_you_interested_in?"] == "Bartender"


def test_an_empty_sheet_is_not_an_error():
    assert parse_rows([]) == ([], [])
    assert parse_rows([HEADERS]) == ([], [])
