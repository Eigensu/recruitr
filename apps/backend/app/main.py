"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.auth.router import router as auth_router
from app.modules.brands.router import router as brands_router
from app.modules.candidates.router import router as candidates_router
from app.config import settings
from app.database import init_db
from app.modules.gamification.router import router as gamification_router
from app.modules.pipeline.router import router as pipeline_router
from app.modules.positions.router import router as positions_router
from app.modules.storage.router import router as storage_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database connection on startup, clean up on shutdown."""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router,         prefix="/api/v1/auth",         tags=["Auth"])
app.include_router(brands_router,       prefix="/api/v1/brands",       tags=["Brands"])
app.include_router(positions_router,    prefix="/api/v1/positions",    tags=["Positions"])
app.include_router(candidates_router,   prefix="/api/v1/candidates",   tags=["Candidates"])
app.include_router(pipeline_router,     prefix="/api/v1/pipeline",     tags=["Pipeline"])
app.include_router(gamification_router, prefix="/api/v1/gamify",       tags=["Gamification"])
app.include_router(storage_router,      prefix="/api/v1/storage",      tags=["Storage"])


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}
