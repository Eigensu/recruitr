"""Importing a Naukri candidate export as leads.

The parser is pure and tested on workbooks built here; the API is exercised
with real tokens and no dependency overrides, like test_review.py, so the role
guards are tested rather than assumed. Imported people go through the same
ingest as the Meta sheet: telecaller round-robin, duplicate detection, review.
"""

import io

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.recruitment.enums import (
    CandidateStatus,
    EducationLevel,
    IntakeLeadStatus,
    IntakeSource,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeLead
from app.modules.recruitment.utils.naukri_sheet import (
    NaukriFileError,
    parse_age,
    parse_monthly_salary,
    parse_naukri_xlsx,
    parse_work_exp,
)

_BRAND = PydanticObjectId()
_URL = "/api/v1/intake"

HEADER = [
    "#",
    "Candidate Name",
    "Resume Title",
    "Contact No.",
    "Email",
    "Work Exp",
    "Annual Salary",
    "Current Location",
    "Preferred Location",
    "Current Employer",
    "Designation",
    "U.G. Course",
    "Age/Date of Birth",
]


def _row(n: int, name: str, phone: str, *, salary="INR 3.8 L", email=None, **kw) -> list:
    return [
        n,
        name,
        kw.get("title", "Hospitality professional"),
        phone,
        email or f"{(name.split() or [f'row{n}'])[0].lower()}@example.com",
        kw.get("exp", "3Y 2 M"),
        salary,
        kw.get("city", "Mumbai"),
        kw.get("preferred", "Mumbai"),
        kw.get("company", "Paul Cafe"),
        kw.get("designation", "Floor Supervisor"),
        kw.get("ug", "B.sc"),
        kw.get("age", "27 y\n(24 May 1999)"),
    ]


def _xlsx(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _file(data: bytes, name: str = "naukri.xlsx") -> dict:
    return {
        "file": (name, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }


# ── Field parsers ──────────────────────────────────────────────────────────────


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("raw", "years"),
    [("3Y 5 M", 3.42), ("2Y 11 M", 2.92), ("11 M", 0.92), ("4Y", 4.0), ("Fresher", 0.0), ("", 0.0)],
)
def test_work_exp(raw, years):
    assert parse_work_exp(raw) == years


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("raw", "monthly"),
    [
        ("INR 3.8 L", 31667),  # the meeting's own example: ₹3.8 L a year
        ("INR 0.2 L", 1667),
        ("INR 12.5 L", 104167),
        ("INR 3,80,000", 31667),  # a bare figure is yearly rupees
        ("INR 1.2 Cr", 1_000_000),
        ("INR 360 K", 30000),
        ("Not Disclosed", None),
        ("", None),
    ],
)
def test_salary_is_converted_to_monthly(raw, monthly):
    assert parse_monthly_salary(raw) == monthly


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("raw", "age"), [("29 y\n(06 May 1997)", 29), ("31", 31), ("", None), ("n/a", None)]
)
def test_age(raw, age):
    assert parse_age(raw) == age


# ── Workbook parsing ───────────────────────────────────────────────────────────


@pytest.mark.no_db
def test_a_real_shaped_row_becomes_a_lead():
    data = _xlsx([HEADER, _row(1, "Shawn Dsouza", "9819844180", city="Mumbai, Maharashtra")])

    [lead] = parse_naukri_xlsx(data).leads

    assert lead.external_id == "naukri:9819844180"
    assert (lead.full_name, lead.phone_normalized) == ("Shawn Dsouza", "9819844180")
    assert (lead.current_role, lead.previous_company) == ("Floor Supervisor", "Paul Cafe")
    assert (lead.salary, lead.experience_years, lead.age) == (31667, 3.17, 27)
    assert lead.city == "Mumbai"
    assert lead.education_level == EducationLevel.bachelors  # "B.sc"
    assert lead.source_channel == "Naukri"
    assert "Hospitality professional" in lead.notes
    assert "Preferred location: Mumbai" in lead.notes
    assert lead.raw["Annual Salary"] == "INR 3.8 L"


@pytest.mark.no_db
def test_headers_are_found_by_name_below_a_title_and_in_any_order():
    header = list(reversed(HEADER))
    row = list(reversed(_row(1, "Shawn Dsouza", "9819844180")))
    data = _xlsx([["Naukri Resdex export — 30 Sep 2026"], [], header, row])

    parsed = parse_naukri_xlsx(data)

    assert [lead.full_name for lead in parsed.leads] == ["Shawn Dsouza"]
    assert parsed.lead_rows == [4]


@pytest.mark.no_db
def test_a_phone_stored_as_a_number_still_reads():
    row = _row(1, "Shawn Dsouza", "x")
    row[3] = 9819844180  # Excel cell typed as a number
    [lead] = parse_naukri_xlsx(_xlsx([HEADER, row])).leads
    assert lead.phone_normalized == "9819844180"


@pytest.mark.no_db
def test_unusable_rows_are_reported_and_blank_rows_ignored():
    data = _xlsx(
        [
            HEADER,
            _row(1, "Good Row", "9819844180"),
            _row(2, "", "9819844181"),
            _row(3, "No Phone", "12345"),
            [None] * len(HEADER),
        ]
    )

    parsed = parse_naukri_xlsx(data)

    assert [lead.full_name for lead in parsed.leads] == ["Good Row"]
    assert [(s.row_number, s.reason) for s in parsed.skipped] == [
        (3, "no name"),
        (4, "no usable phone number"),
    ]


@pytest.mark.no_db
def test_a_file_without_the_required_columns_is_refused():
    with pytest.raises(NaukriFileError, match="Contact No."):
        parse_naukri_xlsx(_xlsx([["Candidate Name", "Email"], ["A", "a@x.com"]]))


@pytest.mark.no_db
def test_a_file_that_is_not_a_workbook_is_refused():
    with pytest.raises(NaukriFileError, match="Couldn't read"):
        parse_naukri_xlsx(b"name,phone\nA,9819844180\n")


# ── API ────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def _staff(name: str, role: UserRole) -> Employee:
    email = f"{name}@binge.consulting"
    await User(email=email, role=role).insert()
    employee = Employee(brand_id=_BRAND, name=name, email=email, role=role.value)
    await employee.insert()
    return employee


async def _headers(name: str) -> dict[str, str]:
    user = await User.find_one({"email": f"{name}@binge.consulting"})
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest_asyncio.fixture
async def people(init_test_db):
    return {
        "recruiter": await _staff("rae", UserRole.employee),
        "telecaller": await _staff("tara", UserRole.telecaller),
        "maintainer": await _staff("mona", UserRole.maintainer),
    }


def _export() -> bytes:
    return _xlsx(
        [
            HEADER,
            _row(1, "Shawn Dsouza", "9819844180"),
            _row(2, "Nikhil Unhavane", "9076254618", salary="INR 3.0 L"),
            _row(3, "Umesh Yadav", "9430879672", salary="INR 0.2 L"),
            _row(4, "Shawn Again", "+91 98198 44180", email="shawn2@example.com"),
            _row(5, "Already Here", "9000000001"),
            _row(6, "", "9000000002"),
        ]
    )


async def _existing_candidate() -> Candidate:
    doc = Candidate(brand_id=_BRAND, full_name="Already Here", phone="9000000001")
    await doc.insert()
    return doc


async def test_preview_classifies_every_row_and_writes_nothing(http, people):
    await _existing_candidate()

    res = await http.post(
        f"{_URL}/imports/naukri/preview", files=_file(_export()), headers=await _headers("rae")
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert [(r["row_number"], r["full_name"], r["outcome"]) for r in body["rows"]] == [
        (2, "Shawn Dsouza", "new"),
        (3, "Nikhil Unhavane", "new"),
        (4, "Umesh Yadav", "new"),
        (5, "Shawn Again", "duplicate_in_sheet"),
        (6, "Already Here", "matched_existing"),
    ]
    assert body["skipped"] == [{"row_number": 7, "reason": "no name"}]
    assert (body["new"], body["duplicate_in_sheet"], body["matched_existing"]) == (3, 1, 1)
    umesh = body["rows"][2]
    assert umesh["salary"] == 1667
    assert umesh["warnings"] and "too low" in umesh["warnings"][0]
    assert await IntakeLead.find_all().count() == 0
    assert await Candidate.find_all().count() == 1  # only the pre-existing one


async def test_import_queues_new_people_for_telecallers(http, people):
    existing = await _existing_candidate()

    res = await http.post(
        f"{_URL}/imports/naukri", files=_file(_export()), headers=await _headers("rae")
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["rows_read"] == 6
    assert (body["created"], body["assigned"], body["unassigned"]) == (3, 3, 0)
    assert (body["matched_existing"], body["repeated_in_file"], body["unusable"]) == (1, 1, 1)

    shawn = await Candidate.find_one({"brand_id": _BRAND, "phone": "9819844180"})
    assert shawn.status == CandidateStatus.pending
    assert (shawn.source, shawn.source_channel) == ("external", "Naukri")
    assert (shawn.salary, shawn.salary_period, shawn.previous_company) == (
        31667,
        "monthly",
        "Paul Cafe",
    )
    assert shawn.created_by_id is None  # sourced by an export, not a recruiter

    leads = await IntakeLead.find({"brand_id": _BRAND}).to_list()
    assert {lead.source for lead in leads} == {IntakeSource.naukri_import}
    assert {lead.submitted_by_id for lead in leads} == {people["recruiter"].id}
    new = [lead for lead in leads if lead.status == IntakeLeadStatus.pending_telecaller]
    assert len(new) == 3
    assert {lead.telecaller_id for lead in new} == {people["telecaller"].id}
    [dupe] = [lead for lead in leads if lead.status == IntakeLeadStatus.duplicate]
    assert dupe.candidate_id == existing.id


async def test_uploading_the_same_export_again_creates_nothing(http, people):
    headers = await _headers("rae")
    await http.post(f"{_URL}/imports/naukri", files=_file(_export()), headers=headers)

    res = await http.post(f"{_URL}/imports/naukri", files=_file(_export()), headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["created"] == 0
    # 4 leads from the first upload, plus "Shawn Again": same phone, so the
    # same lead id as Shawn, which is now stored rather than earlier in the file.
    assert res.json()["already_ingested"] == 5
    assert res.json()["repeated_in_file"] == 0
    assert await IntakeLead.find_all().count() == 4


async def test_a_maintainer_can_import_too(http, people):
    res = await http.post(
        f"{_URL}/imports/naukri", files=_file(_export()), headers=await _headers("mona")
    )
    assert res.status_code == 200, res.text
    lead = await IntakeLead.find_one({"brand_id": _BRAND})
    assert lead.submitted_by_id == people["maintainer"].id


async def test_a_telecaller_cannot_import_preview_or_list(http, people):
    headers = await _headers("tara")
    for method, path in (
        ("post", "/imports/naukri/preview"),
        ("post", "/imports/naukri"),
        ("get", "/leads/submitted"),
    ):
        kwargs = {"files": _file(_export())} if method == "post" else {}
        res = await getattr(http, method)(f"{_URL}{path}", headers=headers, **kwargs)
        assert res.status_code == 403, (path, res.text)
    assert await IntakeLead.find_all().count() == 0


async def test_my_submitted_leads_shows_only_mine(http, people):
    await http.post(f"{_URL}/imports/naukri", files=_file(_export()), headers=await _headers("rae"))
    other = _xlsx([HEADER, _row(1, "Mona Pick", "9111111111")])
    await http.post(f"{_URL}/imports/naukri", files=_file(other), headers=await _headers("mona"))

    res = await http.get(f"{_URL}/leads/submitted", headers=await _headers("rae"))

    assert res.status_code == 200, res.text
    names = sorted(row["full_name"] for row in res.json())
    assert names == ["Already Here", "Nikhil Unhavane", "Shawn Dsouza", "Umesh Yadav"]
    assert {row["source"] for row in res.json()} == {"naukri_import"}


async def test_bad_uploads_are_refused_with_a_reason(http, people):
    headers = await _headers("rae")

    res = await http.post(
        f"{_URL}/imports/naukri", files=_file(_export(), name="naukri.csv"), headers=headers
    )
    assert res.status_code == 400 and ".xlsx" in res.text

    no_columns = _xlsx([["Candidate Name"], ["A"]])
    res = await http.post(f"{_URL}/imports/naukri", files=_file(no_columns), headers=headers)
    assert res.status_code == 400 and "Contact No." in res.text

    res = await http.post(
        f"{_URL}/imports/naukri", files=_file(b"x" * (5 * 1024 * 1024 + 1)), headers=headers
    )
    assert res.status_code == 413

    assert await IntakeLead.find_all().count() == 0
