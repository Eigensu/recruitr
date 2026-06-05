"""MongoDB connection and Beanie ODM initialization."""

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

# Unified recruitment domain models (canonical source of truth)
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    CandidateDocument,
    Client,
    Counter,
    Employee,
    Mapping,
    Position,
)

# Module-level client reference for transaction access
_client: AsyncMongoClient | None = None


async def init_db() -> None:
    """Initialize MongoDB connection and register Beanie document models."""
    global _client
    _client = AsyncMongoClient(settings.MONGODB_URI)
    await init_beanie(
        database=_client[settings.MONGODB_DB_NAME],
        document_models=[
            # Auth
            User,
            Brand,
            # Recruitment domain (unified, replaces old positions/candidates/pipeline modules)
            Counter,
            Client,
            Position,
            Candidate,
            Mapping,
            Employee,
            ActivityLog,
            CandidateDocument,
            # Gamification
            RecruiterProfile,
            # Leaderboard
            EmployeeStat,
            LeaderboardHistory,
            Badge,
            RecruiterActivity,
        ],
        allow_index_dropping=settings.ALLOW_INDEX_DROPPING,
    )


def get_client() -> AsyncMongoClient:
    """Return the active async Mongo client (for transactions)."""
    if _client is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _client
