"""Application configuration via environment variables with Pydantic validation.

The .env file lives at the monorepo root (two levels up from this file).
Pydantic-settings resolves the path relative to the process working directory,
so we compute the absolute path here to be safe regardless of where the
server is started from.
"""

import secrets
from pathlib import Path

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Monorepo root = two directories above apps/backend/app/config.py
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


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
    MONGODB_URI: str = "mongodb://localhost:27017/eigensu?replicaSet=rs0"
    MONGODB_DB_NAME: str = "eigensu"

    # ── Auth (Custom JWT) ──
    JWT_SECRET: str = "changeme_in_production"
    SESSION_SECRET: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

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

    @field_validator("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
    @classmethod
    def validate_google_credentials(cls, v: str, info: ValidationInfo) -> str:
        if not v and not info.data.get("DEBUG", False):
            raise ValueError(f"{info.field_name} must not be empty.")
        return v

    # ── Frontend ──
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()
