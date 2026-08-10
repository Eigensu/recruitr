"""Pytest configuration and global fixtures."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.config import settings
from app.modules.auth.models import User
from app.modules.brands.models import Brand
from app.modules.gamification.models import RecruiterProfile
from app.modules.leaderboard.models import (
    Badge,
    EmployeeStat,
    LeaderboardHistory,
    RecruiterActivity,
)

# Unified recruitment domain models (replaces old positions/candidates/pipeline/dashboard models)
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    CandidateDocument,
    CandidateEvent,
    Client,
    ClientUser,
    Counter,
    Employee,
    Mapping,
    Position,
    RecruiterTag,
    Team,
)


@pytest_asyncio.fixture(autouse=True)
async def init_test_db() -> AsyncGenerator[None, None]:
    """Initialize an isolated test database for each test, then drop it."""
    test_db_name = f"{settings.MONGODB_DB_NAME}_test"
    client = AsyncMongoClient(settings.MONGODB_URI)
    await init_beanie(
        database=client[test_db_name],
        document_models=[
            # Auth
            User,
            Brand,
            # Recruitment domain. Keep in step with app/database.py — a model
            # missing here is not caught until some endpoint happens to query
            # it, and then fails as CollectionWasNotInitialized rather than as
            # anything that points at this list.
            Counter,
            Client,
            ClientUser,
            Position,
            Candidate,
            Mapping,
            Employee,
            Team,
            RecruiterTag,
            ActivityLog,
            CandidateEvent,
            CandidateDocument,
            # Gamification
            RecruiterProfile,
            # Leaderboard
            EmployeeStat,
            LeaderboardHistory,
            Badge,
            RecruiterActivity,
        ],
        allow_index_dropping=True,
    )
    yield
    await client.drop_database(test_db_name)
    await client.close()
