"""A referee acting on their own referral — and only ever on their own.

The referee portal used to be read-only. These endpoints let a referee move a
candidate they sourced, which makes ownership the whole ballgame: a referee has
no Employee record and no client_id, so TenantScope.scoped() and
scope_mapping_match() are both no-ops for them and neither would stop one
referee reaching another's pipeline.
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.models import UserRole
from app.modules.dashboard.referee_router import get_current_referee
from app.modules.recruitment.enums import Decision, PipelineStage, RefereeKanbanStage
from app.modules.recruitment.models import (
    Candidate,
    Mapping,
    Position,
    RefereeUser,
    ReferralRecord,
)

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()

_MINE = "referee-a@test.com"
_THEIRS = "referee-b@test.com"


def _as(email: str):
    return SimpleNamespace(id=PydanticObjectId(), role=UserRole.referee, email=email)


@pytest_asyncio.fixture
async def seeded(init_test_db):
    """Two referees in one brand, each with a referral at sent_to_client."""
    out = {}
    for key, email in (("mine", _MINE), ("theirs", _THEIRS)):
        grant = RefereeUser(brand_id=_BRAND, email=email, name=key)
        await grant.insert()

        candidate = Candidate(
            brand_id=_BRAND,
            email=f"cand-{key}@test.com",
            full_name=f"Cand {key}",
            source="referral",
            referee_id=grant.id,
        )
        await candidate.insert()

        position = Position(
            brand_id=_BRAND,
            code=f"P-{key}",
            client_id=PydanticObjectId(),
            client_name="Client",
            role="Role",
            total_seats=1,
            remaining_seats=1,
        )
        await position.insert()

        mapping = Mapping(
            brand_id=_BRAND,
            candidate_id=candidate.id,
            position_id=position.id,
            employee_id=_EMP,
            stage=PipelineStage.sent_to_client,
        )
        await mapping.insert()

        referral = ReferralRecord(
            brand_id=_BRAND,
            referee_id=grant.id,
            mapping_id=mapping.id,
            candidate_id=candidate.id,
            position_id=position.id,
            kanban_stage=RefereeKanbanStage.cv_reviewed.value,
        )
        await referral.insert()

        out[key] = {"grant": grant, "mapping": mapping, "referral": referral}
    return out


@pytest_asyncio.fixture
async def portal(seeded):
    """An HTTP client signed in as referee A."""
    app.dependency_overrides[get_current_referee] = lambda: _as(_MINE)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _move_url(mapping_id) -> str:
    return f"/api/v1/referee-dashboard/referrals/{mapping_id}/move"


async def test_referee_advances_their_own_referral(portal, seeded):
    mapping = seeded["mine"]["mapping"]

    res = await portal.post(_move_url(mapping.id), json={"new_stage": "interview"})

    assert res.status_code == 200, res.text
    assert (await Mapping.get(mapping.id)).stage == PipelineStage.interview


async def test_referee_cannot_touch_another_referees_referral(portal, seeded):
    """The whole point: B's mapping is a real id, and A must still be refused.

    404 rather than 403 — whether that mapping exists is not A's to learn.
    """
    theirs = seeded["theirs"]["mapping"]

    res = await portal.post(_move_url(theirs.id), json={"new_stage": "interview"})

    assert res.status_code == 404
    assert (await Mapping.get(theirs.id)).stage == PipelineStage.sent_to_client


@pytest.mark.parametrize("target", ["joined", "selected", "sourced"])
async def test_referee_cannot_skip_ahead(portal, seeded, target):
    """Only the two moves the client gets are legal from sent_to_client."""
    mapping = seeded["mine"]["mapping"]

    res = await portal.post(_move_url(mapping.id), json={"new_stage": target})

    assert res.status_code == 403
    assert (await Mapping.get(mapping.id)).stage == PipelineStage.sent_to_client


async def test_rejecting_does_not_regress_the_tracker(portal, seeded):
    """A rejected referral holds its last real step instead of resetting.

    sync_referral_with_mapping skips closed stages precisely so the referee's
    journey view does not snap back to "CV Received" the moment someone says no.
    """
    mapping = seeded["mine"]["mapping"]
    referral = seeded["mine"]["referral"]

    res = await portal.post(_move_url(mapping.id), json={"new_stage": "rejected"})

    assert res.status_code == 200, res.text
    moved = await Mapping.get(mapping.id)
    assert moved.stage == PipelineStage.rejected
    assert moved.decision == Decision.rejected

    after = await ReferralRecord.get(referral.id)
    assert after.kanban_stage == RefereeKanbanStage.cv_reviewed.value


async def test_the_move_is_attributed_to_the_referee(portal, seeded):
    """History says "referee", and the recruiter on the mapping is left alone.

    Mapping.employee_id is required, and a referee has none — blanking it would
    erase the recruiter who actually worked the candidate.
    """
    mapping = seeded["mine"]["mapping"]

    await portal.post(_move_url(mapping.id), json={"new_stage": "interview"})

    after = await Mapping.get(mapping.id)
    assert after.employee_id == _EMP
    assert after.history[-1].actor == "referee"
    assert after.history[-1].by_employee_id is None


async def test_offer_letter_refused_before_selected(portal, seeded):
    mapping = seeded["mine"]["mapping"]

    res = await portal.put(
        f"/api/v1/referee-dashboard/referrals/{mapping.id}/offer-letter",
        files={"file": ("offer.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert res.status_code == 403
    assert (await Mapping.get(mapping.id)).offer_letter_url is None


async def test_offer_letter_attaches_once_selected(portal, seeded, monkeypatch):
    from app.modules.storage import service as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_offer_letter",
        lambda *_args, **_kw: {"secure_url": "https://cdn.test/offer.pdf"},
    )

    mapping = seeded["mine"]["mapping"]
    mapping.stage = PipelineStage.selected
    await mapping.save()

    res = await portal.put(
        f"/api/v1/referee-dashboard/referrals/{mapping.id}/offer-letter",
        files={"file": ("offer.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert res.status_code == 200, res.text
    assert (await Mapping.get(mapping.id)).offer_letter_url == "https://cdn.test/offer.pdf"


async def test_offer_letter_rejects_a_non_pdf(portal, seeded):
    mapping = seeded["mine"]["mapping"]
    mapping.stage = PipelineStage.selected
    await mapping.save()

    res = await portal.put(
        f"/api/v1/referee-dashboard/referrals/{mapping.id}/offer-letter",
        files={"file": ("offer.exe", b"MZ", "application/octet-stream")},
    )

    assert res.status_code == 400
