"""The historical backfill script: what it prints, and what it writes.

Worth testing at this level rather than only through the service, because this
is the piece an operator points at production. The sheet read and the database
bootstrap are stubbed; everything else runs as it would for real.
"""

from argparse import Namespace

import pytest
import pytest_asyncio
from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import IntakeLeadStatus
from app.modules.recruitment.models import Candidate, Employee, IntakeLead, IntakeSourceConfig
from scripts import backfill_intake_leads as backfill

from .test_sheet_mapping import HEADERS, _row

_BRAND = PydanticObjectId()


def _args(**overrides) -> Namespace:
    defaults = {"confirm": False, "since": None, "assign": False, "limit": None}
    return Namespace(**{**defaults, **overrides})


@pytest_asyncio.fixture(autouse=True)
async def configured(monkeypatch):
    """A configured source, a telecaller, and a sheet of two rows."""
    await IntakeSourceConfig(
        brand_id=_BRAND, spreadsheet_id="sheet-1", sheet_range="Sheet1!A:U", enabled=True
    ).insert()
    await Employee(
        brand_id=_BRAND, name="Caller", email="caller@binge.consulting", role=UserRole.telecaller
    ).insert()

    async def _values(spreadsheet_id: str, sheet_range: str):
        return [
            HEADERS,
            _row(id="l_1", phone_number="9000000001", email="one@example.com"),
            _row(id="l_2", phone_number="9000000002", email="two@example.com"),
        ]

    monkeypatch.setattr(backfill, "fetch_values", _values)
    # Beanie is already initialised against the test database by conftest;
    # letting the script re-initialise would point it at the real one.
    monkeypatch.setattr(backfill, "init_db", _noop)


async def _noop() -> None:
    return None


@pytest.mark.asyncio
async def test_report_mode_writes_nothing(capsys):
    await backfill._run(_args())

    assert await Candidate.find({"brand_id": _BRAND}).count() == 0
    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 0
    output = capsys.readouterr().out
    assert "genuinely new" in output
    assert "Nothing written" in output


@pytest.mark.asyncio
async def test_confirm_imports_the_rows(capsys):
    await backfill._run(_args(confirm=True))

    assert await Candidate.find({"brand_id": _BRAND}).count() == 2
    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 2


@pytest.mark.asyncio
async def test_imported_history_lands_in_nobody_queue(capsys):
    await backfill._run(_args(confirm=True))

    leads = await IntakeLead.find({"brand_id": _BRAND}).to_list()
    assert {lead.status for lead in leads} == {IntakeLeadStatus.unassigned}
    assert all(lead.telecaller_id is None for lead in leads)
    # No SLA clock is running, so tomorrow's sweep reports nothing overdue.
    assert all(lead.telecaller_assigned_at is None for lead in leads)
    assert "nobody's queue" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_assign_hands_them_out_and_starts_the_clock():
    await backfill._run(_args(confirm=True, assign=True))

    leads = await IntakeLead.find({"brand_id": _BRAND}).to_list()
    assert {lead.status for lead in leads} == {IntakeLeadStatus.pending_telecaller}
    assert all(lead.telecaller_assigned_at is not None for lead in leads)


@pytest.mark.asyncio
async def test_re_running_imports_nothing_twice(capsys):
    await backfill._run(_args(confirm=True))
    await backfill._run(_args(confirm=True))

    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 2
    assert await Candidate.find({"brand_id": _BRAND}).count() == 2
    # Whitespace-insensitive: the report is column-aligned, not a fixed string.
    report = " ".join(capsys.readouterr().out.split())
    assert "already ingested 2" in report


@pytest.mark.asyncio
async def test_limit_takes_a_slice():
    await backfill._run(_args(confirm=True, limit=1))

    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 1


@pytest.mark.asyncio
async def test_since_excludes_older_rows(capsys):
    # The stub rows are dated 2026-09-15.
    await backfill._run(_args(confirm=True, since="2026-09-16"))

    assert await IntakeLead.find({"brand_id": _BRAND}).count() == 0
    assert "before --since" in capsys.readouterr().out


def test_a_malformed_since_is_refused_before_anything_runs():
    with pytest.raises(SystemExit):
        backfill._since("last tuesday")
