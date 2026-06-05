"""Tests for leaderboard query functions."""

import pytest
from beanie import PydanticObjectId

from app.modules.leaderboard.models import EmployeeStat
from app.modules.leaderboard.repository import queries
from app.modules.recruitment.models import Position


@pytest.mark.asyncio
async def test_fetch_company_progress_success() -> None:
    brand_id = PydanticObjectId()
    client_id = PydanticObjectId()

    active_job = Position(
        brand_id=brand_id,
        code="CLI-001-POS-001",
        client_id=client_id,
        client_name="Eigensu Corp",
        role="Software Engineer",
        total_seats=5,
        filled_seats=2,
        remaining_seats=3,
        is_active=True,
    )
    inactive_job = Position(
        brand_id=brand_id,
        code="CLI-001-POS-002",
        client_id=client_id,
        client_name="Old Corp",
        role="Product Manager",
        total_seats=3,
        filled_seats=1,
        remaining_seats=2,
        is_active=False,
    )
    await active_job.insert()
    await inactive_job.insert()

    progress = await queries.fetch_company_progress(limit=5)
    assert len(progress) == 1
    assert progress[0]["company"] == "Eigensu Corp"
    assert progress[0]["role"] == "Software Engineer"
    assert progress[0]["totalSeats"] == 5
    assert progress[0]["filled"] == 2


@pytest.mark.asyncio
async def test_fetch_monthly_growth_success() -> None:
    employee_id1 = PydanticObjectId()
    stat1 = EmployeeStat(
        employee_id=employee_id1,
        total_score=100,
        is_active=True,
    )
    employee_id2 = PydanticObjectId()
    stat2 = EmployeeStat(
        employee_id=employee_id2,
        total_score=50,
        is_active=False,
    )
    await stat1.insert()
    await stat2.insert()

    growth = await queries.fetch_monthly_growth()
    assert isinstance(growth, dict)
    assert "labels" in growth
    assert "series" in growth
