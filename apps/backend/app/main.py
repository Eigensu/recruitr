"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app import database
from app.common.extras.redis_cache import dashboard_cache, leaderboard_cache
from app.config import settings
from app.database import init_db
from app.dependencies import deny_clients
from app.modules.auth.access import warn_if_unconfigured
from app.modules.auth.router import router as auth_router
from app.modules.brands.router import router as brands_router
from app.modules.dashboard.notifications_router import router as notifications_router
from app.modules.dashboard.referee_router import router as referee_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.leaderboard.routes import router as leaderboard_router
from app.modules.recruitment.controller import (
    activity_router,
    candidates_router,
    client_messaging_router,
    clients_router,
    pipeline_router,
    positions_router,
    public_router,
    referees_router,
    tags_router,
    tasks_router,
    teams_router,
)
from app.modules.storage.router import router as storage_router

_COOKIE_SECURE = not settings.DEBUG  # True in prod (HTTPS), False in local dev


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database connection on startup, clean up on shutdown."""
    await init_db()
    warn_if_unconfigured()
    try:
        yield
    finally:
        await dashboard_cache.close()
        await leaderboard_cache.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    https_only=_COOKIE_SECURE,
    same_site="lax",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(public_router, prefix="/api/v1/public", tags=["Public"])
app.include_router(brands_router, prefix="/api/v1/brands", tags=["Brands"])
app.include_router(candidates_router, prefix="/api/v1/candidates", tags=["Candidates"])
app.include_router(clients_router, prefix="/api/v1/clients", tags=["Clients"])
app.include_router(
    client_messaging_router, prefix="/api/v1/client-messaging", tags=["Client Messaging"]
)
app.include_router(positions_router, prefix="/api/v1/positions", tags=["Positions"])
app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["Pipeline"])
app.include_router(tags_router, prefix="/api/v1/tags", tags=["Tags"])
app.include_router(teams_router, prefix="/api/v1/teams", tags=["Teams"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["Tasks"])
app.include_router(referees_router, prefix="/api/v1/referees", tags=["Referees"])
app.include_router(storage_router, prefix="/api/v1/storage", tags=["Storage"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(referee_router)
app.include_router(notifications_router)
# The leaderboard authenticates with get_current_user alone — it never resolves
# a tenant, so nothing else would stop a client account reading our recruiters'
# names and scores. Guarded at the router so endpoints added later inherit it.
app.include_router(
    leaderboard_router,
    prefix="/api/v1/leaderboard",
    tags=["Leaderboard"],
    dependencies=[Depends(deny_clients)],
)
app.include_router(activity_router, prefix="/api/v1/activity", tags=["Activity"])


@app.get("/health", tags=["Health"])
async def health() -> dict:
    # index_sync_degraded means no index — including unique constraints — is
    # being synced. The app serves fine, so this is "degraded", not "down".
    body: dict = {"status": "ok", "version": settings.APP_VERSION}
    if database.index_sync_degraded:
        body["status"] = "degraded"
        body["index_sync"] = {
            "synced": False,
            "detail": "Index sync disabled for all models after a startup failure.",
            "error": database.index_sync_error,
        }
    return body
