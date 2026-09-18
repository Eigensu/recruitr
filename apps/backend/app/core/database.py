"""MongoDB connection and Beanie ODM initialization."""

import asyncio
import logging
import os
from typing import NoReturn

import pymongo.errors
from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.core.config import settings
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
    ClientMessage,
    ClientUser,
    Counter,
    Employee,
    Mapping,
    Notification,
    PaymentBatch,
    Position,
    RecruiterTag,
    RecruitmentTask,
    RefereeUser,
    ReferralRecord,
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
# The collections that could not sync, so /health can name them rather than
# implying the whole database is unconstrained.
index_sync_degraded_collections: list[str] = []

# Matches the exit code uvicorn uses when application startup fails, so the
# gunicorn master reports the same "Worker failed to boot" as before.
_BOOT_FAILURE_EXIT_CODE = 3

# pymongo appends a full TopologyDescription to ServerSelectionTimeoutError —
# one ServerDescription per replica-set member, each repeating the same
# underlying error verbatim. It is the bulk of a ~2000-character message that
# carries one useful sentence.
_TOPOLOGY_MARKER = ", Topology Description:"
_MAX_ERROR_CHARS = 500

# 13 Unauthorized, 18 AuthenticationFailed. Not retried: the cluster answered,
# so it is reachable, and it said no. Almost always a rotated password or a
# dropped database user, neither of which fixes itself in the seconds a retry
# would buy.
_AUTH_REJECTED_CODES = frozenset({13, 18})


def _brief(exc: BaseException) -> str:
    """Trim a pymongo error down to the part that identifies the failure."""
    text = str(exc)
    head, marker, _ = text.partition(_TOPOLOGY_MARKER)
    if marker:
        text = head
    if len(text) > _MAX_ERROR_CHARS:
        text = f"{text[:_MAX_ERROR_CHARS]}…"
    return text


def _abort_boot(message: str, *args: object, exc_info: bool = False) -> NoReturn:
    """Log one compact fatal line and kill the worker without a traceback.

    Letting a startup exception propagate out of the lifespan looks tidier but
    is what made this failure so expensive to diagnose: uvicorn catches it and
    prints the whole stack, and because FastAPI nests one `merged_lifespan`
    frame per included router, that stack is ~100 lines. Multiplied by every
    worker, a single unreachable database emitted enough output in one second
    to hit the log platform's rate limit and drop the lines that explained why.

    os._exit skips the interpreter's own teardown, so nothing re-raises and
    nothing re-prints. Handlers are flushed first — the whole point is that this
    one line survives.
    """
    logging.critical(message, *args, exc_info=exc_info)
    logging.shutdown()  # flush handlers; os._exit does not
    os._exit(_BOOT_FAILURE_EXIT_CODE)


# 85: IndexOptionsConflict, 86: IndexKeySpecsConflict, 8000: QuotaExceeded.
_INDEX_CONFLICT_CODES = frozenset({85, 86, 8000})


def _is_index_conflict(e: pymongo.errors.OperationFailure) -> bool:
    return e.code in _INDEX_CONFLICT_CODES or "quota" in str(e).lower()


async def _init_beanie(database, document_models: list) -> None:
    """Register document models, isolating any that cannot sync their indexes.

    init_beanie creates every model's indexes in one pass, so a single
    conflicting index used to take the whole pass down and the only recovery
    was skip_indexes=True for ALL of them. One stale index on one collection
    therefore silently switched off every unique constraint in the system —
    a far worse outcome than the drift that caused it, and invisible unless
    someone read the startup logs.

    On conflict each model is now registered on its own, so only the models
    that genuinely conflict lose their indexes and every other collection keeps
    its constraints enforced.
    """
    global index_sync_degraded, index_sync_error

    try:
        await init_beanie(
            database=database,
            document_models=document_models,
            allow_index_dropping=settings.ALLOW_INDEX_DROPPING,
        )
        return
    except pymongo.errors.OperationFailure as e:
        if not _is_index_conflict(e):
            raise
        first_error = e

    degraded: list[str] = []
    for model in document_models:
        try:
            await init_beanie(
                database=database,
                document_models=[model],
                allow_index_dropping=settings.ALLOW_INDEX_DROPPING,
            )
        except pymongo.errors.OperationFailure as e:
            if not _is_index_conflict(e):
                raise
            collection = getattr(getattr(model, "Settings", None), "name", model.__name__)
            degraded.append(collection)
            logging.critical(
                "MongoDB index sync FAILED for %s (%s): %s. This collection's declared "
                "indexes, including any unique constraint, are NOT enforced. Run "
                "scripts/inspect_indexes.py to see the drift and "
                "scripts/fix_index_conflicts.py --confirm to repair it.",
                collection,
                e.code,
                _brief(e),
            )
            await init_beanie(
                database=database,
                document_models=[model],
                allow_index_dropping=False,
                skip_indexes=True,
            )

    if degraded:
        index_sync_degraded = True
        index_sync_error = f"({first_error.code}) {_brief(first_error)}"
        index_sync_degraded_collections.extend(degraded)
        logging.critical(
            "MongoDB index sync degraded for %d of %d models: %s. Every other model "
            "synced normally and keeps its constraints.",
            len(degraded),
            len(document_models),
            ", ".join(degraded),
        )


async def init_db() -> None:
    """Initialize MongoDB connection and register Beanie document models.

    A database that is briefly unreachable — an Atlas failover, a paused
    cluster waking, a network blip during a redeploy — should not be fatal on
    the first try, so connection failures are retried with backoff. Once the
    attempts are spent the worker exits: without a database the app can serve
    nothing, and booting "healthy" would only route traffic into errors.
    """
    global _client
    _client = AsyncMongoClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
    )

    document_models = [
        # Auth
        User,
        Brand,
        # Recruitment domain (unified, replaces old positions/candidates/pipeline modules)
        Counter,
        Client,
        ClientUser,
        ClientMessage,
        Position,
        Candidate,
        Mapping,
        Employee,
        Team,
        RecruitmentTask,
        RecruiterTag,
        ActivityLog,
        CandidateEvent,
        CandidateDocument,
        RefereeUser,
        ReferralRecord,
        PaymentBatch,
        Notification,
        # Gamification
        RecruiterProfile,
        # Leaderboard
        EmployeeStat,
        LeaderboardHistory,
        Badge,
        RecruiterActivity,
    ]

    database = _client[settings.MONGODB_DB_NAME]
    attempts = settings.MONGODB_INIT_ATTEMPTS
    for attempt in range(1, attempts + 1):
        try:
            await _init_beanie(database, document_models)
            return
        except pymongo.errors.ConnectionFailure as e:
            # ServerSelectionTimeoutError lands here (via AutoReconnect), which
            # OperationFailure never covered — an unreachable database was an
            # uncaught exception rather than something to wait out.
            if attempt == attempts:
                _abort_boot(
                    "MongoDB unreachable after %d attempt(s) — %s: %s. Worker cannot "
                    "start. Check that the cluster is running and not paused, and that "
                    "this deployment's egress IP is on its network access allow list.",
                    attempts,
                    type(e).__name__,
                    _brief(e),
                )
            delay = settings.MONGODB_INIT_BACKOFF_SECONDS * 2 ** (attempt - 1)
            logging.warning(
                "MongoDB unreachable (attempt %d/%d) — %s: %s. Retrying in %.1fs.",
                attempt,
                attempts,
                type(e).__name__,
                _brief(e),
                delay,
            )
            await asyncio.sleep(delay)
        except pymongo.errors.OperationFailure as e:
            # Sits ahead of the generic handler for the message alone — an auth
            # rejection is exactly as fatal. But "unexpected OperationFailure"
            # reads as a bug in this code, and sends whoever is holding the
            # pager looking for one. Naming the credential is the difference
            # between a two-minute fix and an hour.
            if e.code in _AUTH_REJECTED_CODES:
                _abort_boot(
                    "MongoDB rejected authentication (code %s): %s. Worker cannot start. "
                    "Check the credentials in MONGODB_URI and that the database user still "
                    "exists with access to %s.",
                    e.code,
                    _brief(e),
                    settings.MONGODB_DB_NAME,
                )
            _abort_boot(
                "MongoDB initialisation failed with an unexpected %s (code %s): %s. "
                "Worker cannot start.",
                type(e).__name__,
                e.code,
                _brief(e),
                exc_info=True,
            )
        except Exception as e:
            # Unexpected — keep a traceback, but this one starts here rather than
            # at the top of the lifespan, so it omits the nested router frames.
            _abort_boot(
                "MongoDB initialisation failed with an unexpected %s: %s. Worker cannot start.",
                type(e).__name__,
                _brief(e),
                exc_info=True,
            )


def get_client() -> AsyncMongoClient:
    """Return the active async Mongo client (for transactions)."""
    if _client is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _client
