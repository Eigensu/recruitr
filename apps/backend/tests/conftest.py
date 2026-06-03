"""Pytest configuration and global fixtures."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.config import settings
from app.modules.auth.models import User
from app.modules.brands.models import Brand
from app.modules.candidates.models import Candidate
from app.modules.dashboard.models import (
    ActivityLog,
    CandidateDocument,
    CandidateMapping,
    DashboardCandidate,
    DashboardEmployee,
    JobOpening,
)
from app.modules.gamification.models import RecruiterProfile
from app.modules.leaderboard.models import (
    Badge,
    EmployeeStat,
    LeaderboardHistory,
    RecruiterActivity,
)
from app.modules.positions.models import Position


@pytest_asyncio.fixture(autouse=True)
async def init_test_db() -> AsyncGenerator[None, None]:
    """Initialize database connection for each test using a separate test database."""
    test_db_name = f"{settings.MONGODB_DB_NAME}_test"
    client = AsyncMongoClient(settings.MONGODB_URI)
    await init_beanie(
        database=client[test_db_name],
        document_models=[
            User,
            Brand,
            Position,
            Candidate,
            RecruiterProfile,
            ActivityLog,
            CandidateDocument,
            CandidateMapping,
            DashboardCandidate,
            DashboardEmployee,
            JobOpening,
            EmployeeStat,
            LeaderboardHistory,
            Badge,
            RecruiterActivity,
        ],
        allow_index_dropping=True,
    )
    yield
    # Clean up test database after the test
    await client.drop_database(test_db_name)
    await client.close()
