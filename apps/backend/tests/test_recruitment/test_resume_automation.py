"""The brand's resume automation switches, enforced in resume_service.

The switches live on Brand.automation and are read at three call sites (resume
confirm, bulk upload, public apply), but all three funnel through the helpers
tested here — so this is where "off actually means off" is pinned down.
"""

from __future__ import annotations

import pytest

from app.modules.brands.models import AutomationSettings
from app.modules.recruitment.services import resume_service
from app.modules.recruitment.services.resume_service import (
    build_candidate_resume_update,
    parse_resume_with,
    process_resume_bytes,
)

RESUME_TEXT = """
Anita Rao
anita@test.com
+91 98765 00002

Skills: barista, latte art, customer service, inventory management, upselling

Work Experience:
Blue Tokai Coffee
Jan 2019 - Present
Bachelor of Science
"""

ALL_ON = AutomationSettings()
TAGS_OFF = AutomationSettings(resume_parsing_enabled=True, auto_tagging_enabled=False)
PARSING_OFF = AutomationSettings(resume_parsing_enabled=False, auto_tagging_enabled=False)


class _StubCandidate:
    """Stands in for a Candidate doc — build_candidate_resume_update only reads."""

    phone = None
    experience_years = 0
    education_level = None
    previous_company = None


# ── parse_resume_with ──────────────────────────────────────────────────────────


def test_everything_on_parses_and_tags():
    parsed = parse_resume_with(RESUME_TEXT, ALL_ON)
    assert parsed.email == "anita@test.com"
    assert parsed.skills
    assert parsed.tags


def test_auto_tagging_off_keeps_skills_but_drops_tags():
    parsed = parse_resume_with(RESUME_TEXT, TAGS_OFF)
    assert parsed.skills, "turning tags off must not stop skill extraction"
    assert parsed.tags == []


def test_parsing_off_infers_nothing():
    parsed = parse_resume_with(RESUME_TEXT, PARSING_OFF)
    assert parsed.tags == []
    assert parsed.skills == []
    assert parsed.email is None
    assert parsed.phone is None
    assert parsed.experience_years is None
    assert parsed.education_level is None
    assert parsed.previous_company is None


def test_parsing_off_still_recovers_the_email_for_bulk_upload():
    """Bulk upload identifies candidates by email, so that one field survives."""
    parsed = parse_resume_with(RESUME_TEXT, PARSING_OFF, email_only=True)
    assert parsed.email == "anita@test.com"
    assert parsed.skills == []
    assert parsed.tags == []


# ── build_candidate_resume_update ──────────────────────────────────────────────


def test_update_with_parsing_off_only_attaches_the_file():
    parsed = parse_resume_with(RESUME_TEXT, PARSING_OFF, email_only=True)
    update = build_candidate_resume_update(
        _StubCandidate(),
        parsed,
        raw_text=None,
        resume_url="https://cdn.example.com/anita.pdf",
        resume_public_id="anita",
    )
    assert update == {
        "resume_url": "https://cdn.example.com/anita.pdf",
        "resume_public_id": "anita",
    }
    assert "resume_raw_text" not in update, "raw text is a parsing artifact"


def test_update_with_tags_off_still_syncs_skills():
    parsed = parse_resume_with(RESUME_TEXT, TAGS_OFF)
    update = build_candidate_resume_update(_StubCandidate(), parsed, raw_text=RESUME_TEXT)
    assert update["skills"]
    assert "tags" not in update


# ── process_resume_bytes ───────────────────────────────────────────────────────


@pytest.fixture
def stub_storage(monkeypatch):
    """Replace text extraction and the Cloudinary upload; record extraction calls."""
    calls: list[bytes] = []

    def fake_extract(file_bytes: bytes) -> str:
        calls.append(file_bytes)
        return RESUME_TEXT

    monkeypatch.setattr(resume_service, "extract_text_from_file", fake_extract)
    monkeypatch.setattr(
        resume_service,
        "upload_bytes_to_cloudinary",
        lambda _b, _f: {"secure_url": "https://cdn.example.com/a.pdf", "public_id": "a"},
    )
    return calls


async def test_parsing_off_never_reads_the_file(stub_storage):
    raw_text, parsed, url, public_id = await process_resume_bytes(b"pdf", "a.pdf", PARSING_OFF)

    assert stub_storage == [], "the file must not be read at all when parsing is off"
    assert raw_text is None
    assert parsed.tags == [] and parsed.skills == []
    # The resume is still stored and linked — disabled parsing, not disabled upload.
    assert url == "https://cdn.example.com/a.pdf"
    assert public_id == "a"


async def test_parsing_off_with_email_only_reads_but_keeps_nothing(stub_storage):
    raw_text, parsed, url, _ = await process_resume_bytes(
        b"pdf", "a.pdf", PARSING_OFF, email_only=True
    )

    assert stub_storage, "bulk upload still needs the email out of the file"
    assert parsed.email == "anita@test.com"
    assert raw_text is None, "the text was read for the email only, never retained"
    assert url == "https://cdn.example.com/a.pdf"


async def test_parsing_on_returns_the_raw_text(stub_storage):
    raw_text, parsed, _, _ = await process_resume_bytes(b"pdf", "a.pdf", ALL_ON)

    assert raw_text == RESUME_TEXT
    assert parsed.skills and parsed.tags
