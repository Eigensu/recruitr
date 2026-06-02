"""Tests for leaderboard query functions."""

import pytest
from beanie import PydanticObjectId

from app.modules.dashboard.models import JobOpening
from app.modules.leaderboard.models import EmployeeStat
from app.modules.leaderboard.repository import queries


@pytest.mark.asyncio
async def test_fetch_company_progress_success() -> None:
    # Set up some test JobOpenings (one active, one inactive)
    active_job = JobOpening(
        client_name="Eigensu Corp",
        role="Software Engineer",
        total_seats=5,
        filled_seats=2,
        is_active=True,
    )
    inactive_job = JobOpening(
        client_name="Old Corp",
        role="Product Manager",
        total_seats=3,
        filled_seats=1,
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
    # Set up some EmployeeStats
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
    # It queries EmployeeStat.find(EmployeeStat.is_active == True)
    # The active stat has id1. The inactive one has id2.
    # Growth series should only contain employee_id1 if that employee profile exists,
    # or series could be empty if they don't have dashboard employee profiles,
    # but the query should execute successfully without TypeError.
    assert isinstance(growth, dict)
    assert "labels" in growth
    assert "series" in growth
