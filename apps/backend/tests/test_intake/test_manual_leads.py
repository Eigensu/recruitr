"""Leads added from the Leads page — typed in, or read from uploaded resumes.

Real PDFs are built here with pymupdf (the library the app reads them with) and
Cloudinary is stubbed, so nothing leaves the process. The API runs with real
tokens and no dependency overrides, like test_review.py.
"""

import json

import pymupdf
import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.main import app
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import create_access_token
from app.modules.brands.models import Brand
from app.modules.recruitment.enums import (
    CandidateStatus,
    Department,
    IntakeLeadStatus,
    IntakeSource,
)
from app.modules.recruitment.models import Candidate, Employee, IntakeLead
from app.modules.recruitment.service import resume_service
from app.modules.recruitment.service.lead_entry import check_resume
from app.modules.recruitment.utils.constants import RESUME_BATCH_MAX_FILES, RESUME_MAX_BYTES
from app.modules.recruitment.utils.phone import normalize_phone
from app.modules.recruitment.utils.resume_parser import parse_resume

_BRAND = PydanticObjectId()
_URL = "/api/v1/intake/leads"

RESUME_TEXT = """SHAWN DSOUZA
shawn.dsouza@example.com | +91 98198 44180
Andheri, Mumbai

Floor Supervisor at Paul Cafe (2022 - Present)
Captain at The Nutcracker (2019 - 2022)

Skills: guest relations, POS, team handling
"""


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


# ── Parser: name, city, role ──────────────────────────────────────────────────


@pytest.mark.no_db
def test_the_parser_reads_name_city_and_role():
    parsed = parse_resume(RESUME_TEXT)

    assert parsed.full_name == "Shawn Dsouza"
    assert parsed.city == "Mumbai"
    # The earliest catalogue role — the current job leads the resume.
    assert (parsed.current_role, parsed.department) == ("Floor Supervisor", Department.service)
    assert parsed.email == "shawn.dsouza@example.com"


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("RESUME\nPriya Nair\npriya@example.com", "Priya Nair"),
        ("Curriculum Vitae\n\nRavi Kumar Singh\nPune", "Ravi Kumar Singh"),
        ("Name: Asha Rao\n9819844180", None),  # labelled lines are skipped, not guessed
        ("Objective\nTo work in a reputed hotel and grow my career there", None),
        ("", None),
    ],
)
def test_name_is_taken_only_when_it_looks_like_one(text, name):
    assert parse_resume(text).full_name == name


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("text", "city"),
    [
        ("Lives in Navi Mumbai", "Mumbai"),
        ("Based out of Bengaluru", "Bangalore"),
        ("New Delhi 110001", "Delhi"),
        ("Hometown: Nashik", None),
    ],
)
def test_city_is_matched_to_the_form_list(text, city):
    assert parse_resume(text).city == city


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("text", "number"),
    [
        # The 5+5 split is how most Indian resumes write a mobile. The old
        # pattern cut the last digit off every one of these, leaving a
        # different number for a telecaller to dial.
        ("+91 99887 76655", "9988776655"),
        ("+91 98198 44180", "9819844180"),
        ("098198-44180", "9819844180"),
        ("91 98198 44180", "9819844180"),
        ("+919819844180", "9819844180"),
        ("9819844180", "9819844180"),
        ("Worked 2019 - 2022, mobile 98198 44180", "9819844180"),
        ("Tel: 022 2345 6789", "2223456789"),  # not a mobile: the general pattern still reads it
    ],
)
def test_phone_numbers_are_read_whole(text, number):
    assert normalize_phone(parse_resume(text).phone) == number


# ── File checks ────────────────────────────────────────────────────────────────


@pytest.mark.no_db
def test_resume_files_are_checked_by_content_and_size():
    assert check_resume("cv.pdf", _pdf("Asha Rao")).error is None
    assert check_resume("cv.docx", b"PK\x03\x04rest").error is None
    assert "PDF and Word" in check_resume("cv.pdf", b"just text").error  # renamed text file
    assert "5 MB" in check_resume("big.pdf", b"%PDF-" + b"x" * RESUME_MAX_BYTES).error


# ── API ────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def cloudinary(monkeypatch):
    """Record uploads instead of sending them."""
    calls: list[str] = []

    def fake_upload(data: bytes, filename: str) -> dict:
        calls.append(filename)
        return {"secure_url": f"https://cdn.test/{filename}", "public_id": f"res/{filename}"}

    monkeypatch.setattr(resume_service, "upload_bytes_to_cloudinary", fake_upload)
    return calls


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
    await Brand(id=_BRAND, owner_id="x", name="Binge", domain="binge.test").insert()
    return {
        "recruiter": await _staff("rae", UserRole.employee),
        "telecaller": await _staff("tara", UserRole.telecaller),
    }


def _files(*items: tuple[str, bytes]) -> list:
    return [("files", (name, data, "application/pdf")) for name, data in items]


def _draft(**overrides) -> dict:
    return {
        "full_name": "Shawn Dsouza",
        "phone": "+91 98198 44180",
        "email": "shawn.dsouza@example.com",
        "city": "Mumbai",
        "current_role": "Floor Supervisor",
        "department": "Service",
        "current_company": "Paul Cafe",
        "experience_years": 3,
        "salary": 32000,
        "expected_salary": 38000,
        **overrides,
    }


async def _submit(http, drafts: list[dict], files: list | None = None, who: str = "rae"):
    return await http.post(
        f"{_URL}/manual",
        data={"drafts": json.dumps(drafts)},
        files=files or None,
        headers=await _headers(who),
    )


async def test_parsing_returns_one_draft_per_file_and_stores_nothing(http, people, cloudinary):
    res = await http.post(
        f"{_URL}/parse-resumes",
        files=_files(
            ("shawn.pdf", _pdf(RESUME_TEXT)),
            ("notes.pdf", b"not really a pdf"),
            ("big.pdf", b"%PDF-" + b"x" * RESUME_MAX_BYTES),
        ),
        headers=await _headers("rae"),
    )

    assert res.status_code == 200, res.text
    shawn, notes, big = res.json()
    assert shawn["filename"] == "shawn.pdf" and shawn["error"] is None
    assert (shawn["full_name"], shawn["city"], shawn["current_role"]) == (
        "Shawn Dsouza",
        "Mumbai",
        "Floor Supervisor",
    )
    assert shawn["email"] == "shawn.dsouza@example.com"
    assert normalize_phone(shawn["phone"]) == "9819844180"  # the whole number, not 9 digits of it
    assert "PDF and Word" in notes["error"]  # a bad file fails on its own…
    assert "5 MB" in big["error"]  # …and so does an oversize one
    assert cloudinary == []  # nothing uploaded
    assert await Candidate.find_all().count() == 0
    assert await IntakeLead.find_all().count() == 0


async def test_too_many_resumes_are_refused(http, people):
    files = _files(*[(f"cv{i}.pdf", _pdf("A B")) for i in range(RESUME_BATCH_MAX_FILES + 1)])
    res = await http.post(f"{_URL}/parse-resumes", files=files, headers=await _headers("rae"))
    assert res.status_code == 400
    assert str(RESUME_BATCH_MAX_FILES) in res.text


async def test_a_submitted_draft_becomes_a_lead_with_its_resume(http, people, cloudinary):
    res = await _submit(
        http, [_draft(resume_index=0)], files=_files(("shawn.pdf", _pdf(RESUME_TEXT)))
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["queued"], body["error"]) == (1, 0)
    assert body["results"][0]["status"] == "queued"

    lead = await IntakeLead.find_one({"brand_id": _BRAND})
    assert lead.source == IntakeSource.recruiter_manual
    assert lead.submitted_by_id == people["recruiter"].id
    assert lead.status == IntakeLeadStatus.pending_telecaller
    assert lead.telecaller_id == people["telecaller"].id

    candidate = await Candidate.get(lead.candidate_id)
    assert candidate.status == CandidateStatus.pending
    assert (candidate.salary, candidate.expected_salary, candidate.salary_period) == (
        32000,
        38000,
        "monthly",
    )
    assert candidate.previous_company == "Paul Cafe"
    # The role given is the specialization that goes with the department.
    assert (candidate.department, candidate.specialization) == ("Service", "Floor Supervisor")
    assert candidate.resume_url == "https://cdn.test/shawn.pdf"
    assert cloudinary == ["shawn.pdf"]


async def test_a_draft_without_a_resume_is_fine(http, people, cloudinary):
    res = await _submit(http, [_draft()])

    assert res.status_code == 200, res.text
    assert res.json()["queued"] == 1
    assert cloudinary == []


async def test_each_draft_succeeds_or_fails_on_its_own(http, people, cloudinary):
    await Candidate(brand_id=_BRAND, full_name="Already Here", phone="9000000001").insert()

    res = await _submit(
        http,
        [
            _draft(),
            _draft(full_name="Already Here", phone="9000000001", email=None),
            _draft(full_name="No Salary", phone="9111111111", email=None, salary=None),
            _draft(full_name="Bad Phone", phone="12345", email=None),
            _draft(full_name="Bad Email", phone="9222222222", email="not-an-email"),
            _draft(full_name="Missing Resume", phone="9333333333", email=None, resume_index=4),
        ],
    )

    assert res.status_code == 200, res.text
    statuses = [(r["full_name"], r["status"]) for r in res.json()["results"]]
    assert statuses == [
        ("Shawn Dsouza", "queued"),
        ("Already Here", "duplicate"),
        ("No Salary", "error"),
        ("Bad Phone", "error"),
        ("Bad Email", "error"),
        ("Missing Resume", "error"),
    ]
    details = {r["full_name"]: r["detail"] for r in res.json()["results"]}
    assert "salary" in details["No Salary"].lower()
    assert "10-digit" in details["Bad Phone"]
    assert "email" in details["Bad Email"].lower()

    leads = await IntakeLead.find({"brand_id": _BRAND}).to_list()
    assert sorted(lead.status for lead in leads) == sorted(
        [IntakeLeadStatus.pending_telecaller, IntakeLeadStatus.duplicate]
    )


async def test_a_failed_resume_upload_keeps_the_lead(http, people, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("cloudinary down")

    monkeypatch.setattr(resume_service, "upload_bytes_to_cloudinary", broken)

    res = await _submit(
        http, [_draft(resume_index=0)], files=_files(("shawn.pdf", _pdf(RESUME_TEXT)))
    )

    assert res.status_code == 200, res.text
    [result] = res.json()["results"]
    assert result["status"] == "queued"
    assert "couldn't be attached" in result["detail"]
    assert await IntakeLead.find_all().count() == 1


async def test_a_telecaller_cannot_add_or_parse(http, people):
    headers = await _headers("tara")
    res = await http.post(
        f"{_URL}/parse-resumes", files=_files(("a.pdf", _pdf("A B"))), headers=headers
    )
    assert res.status_code == 403
    res = await _submit(http, [_draft()], who="tara")
    assert res.status_code == 403
    assert await IntakeLead.find_all().count() == 0


async def test_bad_draft_payloads_are_refused(http, people):
    headers = await _headers("rae")
    for data in ({"drafts": "not json"}, {"drafts": "[]"}, {"drafts": '{"a": 1}'}):
        res = await http.post(f"{_URL}/manual", data=data, headers=headers)
        assert res.status_code == 400, (data, res.text)
    too_many = json.dumps([_draft()] * (RESUME_BATCH_MAX_FILES + 1))
    res = await http.post(f"{_URL}/manual", data={"drafts": too_many}, headers=headers)
    assert res.status_code == 400


async def test_bulk_upload_takes_the_same_limits(http, people):
    files = _files(*[(f"cv{i}.pdf", _pdf("A B")) for i in range(RESUME_BATCH_MAX_FILES + 1)])
    res = await http.post(
        "/api/v1/candidates/bulk-upload", files=files, headers=await _headers("rae")
    )
    assert res.status_code == 400
    assert str(RESUME_BATCH_MAX_FILES) in res.text
