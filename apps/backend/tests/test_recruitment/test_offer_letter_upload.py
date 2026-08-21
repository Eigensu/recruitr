"""The client portal's offer-letter upload, which used to 422 on every call.

PUT /pipeline/mappings/{id}/offer-letter took {offer_letter_url, salary_offered}
as JSON while its only caller posted multipart. That single mismatch killed the
whole selected -> joined flow, because the portal's "Set Joining Details" block
only renders once offer_letter_url is set and set_joining_date refuses a client
who has none. The old test posted JSON, so it passed against a contract nothing
used — these go through the shape the portal actually sends.
"""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_doc, get_tenant, get_viewer
from app.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import PipelineStage
from app.modules.recruitment.models import Candidate, Client, Mapping, Position
from app.modules.recruitment.schemas import TenantScope

_BRAND = PydanticObjectId()
_EMP = PydanticObjectId()
_CLIENT_ID = PydanticObjectId()

_CLIENT_SCOPE = TenantScope(
    brand_id=_BRAND, employee_id=None, role=UserRole.client, client_id=_CLIENT_ID
)
_CLIENT_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.client, email="c@test.com")

_PDF = {"file": ("offer.pdf", b"%PDF-1.4 fake", "application/pdf")}


@pytest.fixture(autouse=True)
def stub_cloudinary(monkeypatch):
    """Keep every upload in this module off the network."""
    from app.modules.storage import service as storage_service

    monkeypatch.setattr(
        storage_service,
        "upload_offer_letter",
        lambda *_a, **_kw: {"secure_url": "https://cdn.test/offer.pdf"},
    )


@pytest_asyncio.fixture
async def mapping(init_test_db) -> Mapping:
    await Client(id=_CLIENT_ID, brand_id=_BRAND, code="C1", name="Client 1").insert()
    candidate = Candidate(
        brand_id=_BRAND, email="c1@test.com", full_name="Cand One", source="internal"
    )
    await candidate.insert()
    position = Position(
        brand_id=_BRAND,
        code="P1",
        client_id=_CLIENT_ID,
        client_name="Client 1",
        role="Role",
        total_seats=1,
        remaining_seats=1,
    )
    await position.insert()
    doc = Mapping(
        brand_id=_BRAND,
        candidate_id=candidate.id,
        position_id=position.id,
        employee_id=_EMP,
        stage=PipelineStage.selected,
    )
    await doc.insert()
    return doc


@pytest_asyncio.fixture
async def portal(mapping):
    app.dependency_overrides[get_viewer] = lambda: _CLIENT_SCOPE
    app.dependency_overrides[get_tenant] = lambda: _CLIENT_SCOPE
    app.dependency_overrides[get_current_user_doc] = lambda: _CLIENT_USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _url(mapping_id) -> str:
    return f"/api/v1/pipeline/mappings/{mapping_id}/offer-letter"


async def test_multipart_upload_attaches_the_offer_letter(portal, mapping):
    """The exact shape uploadMappingOffer() sends. This was a 422."""
    res = await portal.put(_url(mapping.id), files=_PDF)

    assert res.status_code == 200, res.text
    assert res.json()["offer_letter_url"] == "https://cdn.test/offer.pdf"
    assert (await Mapping.get(mapping.id)).offer_letter_url == "https://cdn.test/offer.pdf"


async def test_a_non_pdf_is_refused(portal, mapping):
    res = await portal.put(
        _url(mapping.id), files={"file": ("offer.exe", b"MZ", "application/octet-stream")}
    )

    assert res.status_code == 400
    assert (await Mapping.get(mapping.id)).offer_letter_url is None


async def test_an_oversize_file_is_refused(portal, mapping):
    from app.modules.storage.uploads import MAX_OFFER_LETTER_BYTES

    too_big = b"%PDF-1.4 " + b"x" * MAX_OFFER_LETTER_BYTES
    res = await portal.put(
        _url(mapping.id), files={"file": ("offer.pdf", too_big, "application/pdf")}
    )

    assert res.status_code == 413
    assert (await Mapping.get(mapping.id)).offer_letter_url is None


async def test_a_client_cannot_upload_before_the_candidate_is_selected(portal, mapping):
    mapping.stage = PipelineStage.interview
    await mapping.save()

    res = await portal.put(_url(mapping.id), files=_PDF)

    assert res.status_code == 403
    assert (await Mapping.get(mapping.id)).offer_letter_url is None


async def test_the_joining_step_persists_the_salary(portal, mapping):
    """The portal has always sent salary_offered here; it was silently dropped.

    PipelineSetJoiningRequest did not declare the field, so pydantic discarded
    it and Mapping.salary_offered stayed null — leaving the salary the kanban
    card renders for a joined candidate permanently blank.
    """
    await portal.put(_url(mapping.id), files=_PDF)

    res = await portal.put(
        f"/api/v1/pipeline/mappings/{mapping.id}/joining-date",
        json={"joining_date": "2026-09-01T00:00:00Z", "salary_offered": 50000},
    )

    assert res.status_code == 200, res.text
    assert (await Mapping.get(mapping.id)).salary_offered == 50000


async def test_the_joining_step_still_works_without_a_salary(portal, mapping):
    """salary_offered is optional — staff callers omit it entirely."""
    await portal.put(_url(mapping.id), files=_PDF)

    res = await portal.put(
        f"/api/v1/pipeline/mappings/{mapping.id}/joining-date",
        json={"joining_date": "2026-09-01T00:00:00Z"},
    )

    assert res.status_code == 200, res.text
    assert (await Mapping.get(mapping.id)).salary_offered is None
