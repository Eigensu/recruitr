"""Application configuration via environment variables with Pydantic validation.

The .env file lives at the monorepo root (three levels up from this file).
Pydantic-settings resolves the path relative to the process working directory,
so we compute the absolute path here to be safe regardless of where the
server is started from.
"""

import secrets
from pathlib import Path

from pydantic import ValidationInfo, field_validator
from pydantic.types import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

# Monorepo root = three directories above apps/backend/app/config.py
try:
    _ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
except IndexError:
    _ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Global application settings loaded from the root .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore NEXT_PUBLIC_* and other frontend-only vars
    )

    # ── App ──
    APP_NAME: str = "Eigensu API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── MongoDB ──
    MONGODB_URI: str = "mongodb://localhost:27017/recruitr"
    MONGODB_DB_NAME: str = "recruitr"
    ALLOW_INDEX_DROPPING: bool = False

    # ── Auth (Custom JWT) ──
    JWT_SECRET: str = "changeme_in_production"
    SESSION_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False
    REDIS_NAMESPACE: str = "dashboard"
    REDIS_CACHE_TTL_SECONDS: PositiveInt = 300
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Cloudinary ──
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_UPLOAD_PRESET: str = "eigensu_resumes"
    CLOUDINARY_WEBHOOK_SECRET: str = ""

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Google OAuth2 ──
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── Frontend ──
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Agency access ──
    # Comma-separated email domains whose addresses may hold a staff account,
    # e.g. "bingeconsulting.in,binge.co". Anyone signing up outside this list is
    # refused rather than being handed the agency workspace.
    #
    # Empty means no NEW account can be provisioned. That is deliberate: an
    # unset value used to mean "admit everyone", which let any address that
    # reached the sign-up page read the whole candidate database. Accounts that
    # already have an Employee row with a brand keep working either way, so an
    # empty value locks nobody out of a workspace they already had.
    AGENCY_EMAIL_DOMAINS: str = ""

    @property
    def agency_email_domains(self) -> frozenset[str]:
        """AGENCY_EMAIL_DOMAINS parsed into bare, lowercased domains."""
        return frozenset(
            part.strip().lower().lstrip("@")
            for part in self.AGENCY_EMAIL_DOMAINS.split(",")
            if part.strip()
        )

    # ── Cookie ──
    # Set to ".eigensu.in" in production so the HttpOnly session cookie is sent
    # to all *.eigensu.in subdomains (frontend + backend share the same parent
    # domain). Without this, a host-only cookie on api.recruitr.eigensu.in is
    # never transmitted to binge.eigensu.in, breaking Next.js middleware auth.
    COOKIE_DOMAIN: str | None = None

    @field_validator("SESSION_SECRET", mode="before")
    @classmethod
    def set_session_secret(cls, v: str | None, info: ValidationInfo) -> str:
        if v:
            return v
        return info.data.get("JWT_SECRET") or secrets.token_hex(32)


settings = Settings()
