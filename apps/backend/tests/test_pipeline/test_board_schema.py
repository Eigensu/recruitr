"""Board DTOs must tolerate a candidate with no email.

Candidate.email went optional when phone became the mandatory contact channel
for manually-added candidates, but the board/list DTOs kept a required `str`.
A single emailless candidate mapped into any Kanban stage then took down the
whole of GET /api/v1/pipeline/board with a 500 — not just its own card — so the
pipeline page rendered no columns at all.
"""

from datetime import UTC, datetime

import pytest

from app.modules.recruitment.schemas.pipeline import StageMappingItem
from app.modules.recruitment.schemas.position import PositionMappedCandidate, TopCandidateItem


@pytest.fixture(autouse=True)
def init_test_db() -> None:
    """Override the global fixture: these are pure schema checks, no Mongo needed."""
    return None


_ROW = {
    "mapping_id": "65f0000000000000000000a1",
    "candidate_id": "65f0000000000000000000b2",
    "candidate_name": "Candidate With No Email",
    "position_id": "65f0000000000000000000c3",
    "position_code": "EIG-001",
    "position_role": "Backend Engineer",
    "position_client": "Acme",
    "stage": "sourced",
    "mapped_at": datetime.now(UTC),
}


def test_board_item_accepts_null_email() -> None:
    """An explicit null — what Mongo stores for an emailless candidate."""
    item = StageMappingItem(**_ROW, candidate_email=None)
    assert item.candidate_email is None


def test_board_item_accepts_absent_email() -> None:
    """$project drops the key entirely when the field is missing on the doc."""
    assert StageMappingItem(**_ROW).candidate_email is None


def test_position_mapped_candidate_accepts_null_email() -> None:
    """Same fix for GET /positions/{id}/candidates."""
    cand = PositionMappedCandidate(
        mapping_id=_ROW["mapping_id"],
        candidate_id=_ROW["candidate_id"],
        full_name="Candidate With No Email",
        email=None,
        experience_years=3.0,
        skills=["python"],
        stage="sourced",
    )
    assert cand.email is None


def test_top_candidate_item_accepts_null_email() -> None:
    """Same fix for GET /positions/{id}/top-candidates, which validates rows
    straight off the candidates collection."""
    top = TopCandidateItem(
        id=_ROW["candidate_id"],
        full_name="Candidate With No Email",
        email=None,
        experience_years=3.0,
        skills=["python"],
    )
    assert top.email is None
