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

# Module-level client reference for transaction access
_client: AsyncMongoClient | None = None

# Set when init_beanie had to fall back to skip_indexes=True. While true, NO
# index is synced for ANY model — including new unique constraints, which then
# silently do not exist. Surfaced on /health so the degraded state is visible
# rather than buried in startup logs.
index_sync_degraded: bool = False
index_sync_error: str | None = None


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
            global index_sync_degraded, index_sync_error
            index_sync_degraded = True
            index_sync_error = f"({e.code}) {e}"
            logging.critical(
                "MongoDB index sync FAILED (%s). Starting with skip_indexes=True, which "
                "disables index synchronisation for ALL %d models — not just the one that "
                "conflicted. Declared indexes, including unique constraints, will NOT be "
                "created while this persists. Run scripts/inspect_indexes.py to see the "
                "drift and scripts/fix_ttl_indexes.py to repair it. Error: %s",
                e.code,
                len(document_models),
                e,
            )
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
