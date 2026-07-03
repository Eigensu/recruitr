"""MongoDB connection and Beanie ODM initialization."""

import logging

import pymongo.errors
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
    RecruiterTag,
    Team,
)

# Module-level client reference for transaction access
_client: AsyncMongoClient | None = None


async def init_db() -> None:
    """Initialize MongoDB connection and register Beanie document models."""
    global _client
    _client = AsyncMongoClient(settings.MONGODB_URI)
    
    document_models = [
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
        Team,
        RecruiterTag,
        ActivityLog,
        CandidateDocument,
        # Gamification
        RecruiterProfile,
        # Leaderboard
        EmployeeStat,
        LeaderboardHistory,
        Badge,
        RecruiterActivity,
    ]
    
    try:
        await init_beanie(
            database=_client[settings.MONGODB_DB_NAME],
            document_models=document_models,
            allow_index_dropping=settings.ALLOW_INDEX_DROPPING,
        )
    except pymongo.errors.OperationFailure as e:
        # Catch known OperationFailure codes during index creation:
        # 85: IndexOptionsConflict, 86: IndexKeySpecsConflict, 8000: QuotaExceeded
        if e.code in (85, 86, 8000) or "quota" in str(e).lower():
            logging.error(f"MongoDB known index-sync failure ({e.code}): {e}")
            logging.warning("Retrying Beanie initialization with skip_indexes=True to bypass the error...")
            await init_beanie(
                database=_client[settings.MONGODB_DB_NAME],
                document_models=document_models,
                allow_index_dropping=False,
                skip_indexes=True,
            )
        else:
            # For unexpected failures, log them (could be metric/alert here) and fail fast
            logging.critical(f"MongoDB unexpected OperationFailure during init_beanie: {e}")
            raise


def get_client() -> AsyncMongoClient:
    """Return the active async Mongo client (for transactions)."""
    if _client is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _client
