"""MongoDB connection and Beanie ODM initialization."""

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
from app.modules.positions.models import Position

# Module-level client reference for transaction access
_client: AsyncMongoClient | None = None


async def init_db() -> None:
    """Initialize MongoDB connection and register Beanie document models."""
    global _client
    _client = AsyncMongoClient(settings.MONGODB_URI)
    await init_beanie(
        database=_client[settings.MONGODB_DB_NAME],
        document_models=[
            User,
            Brand,
            Position,
            Candidate,
            RecruiterProfile,
            DashboardEmployee,
            DashboardCandidate,
            JobOpening,
            CandidateMapping,
            ActivityLog,
            CandidateDocument,
        ],
    )


def get_client() -> AsyncMongoClient:
    """Return the active async Mongo client (for transactions)."""
    if _client is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _client
