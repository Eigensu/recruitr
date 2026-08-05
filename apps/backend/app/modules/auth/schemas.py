"""Pydantic schemas for authentication payloads and endpoints."""

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.models import UserRole


class UserCreate(BaseModel):
    """Schema for creating a new user (signup)."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class TokenPayload(BaseModel):
    """Decoded custom JWT payload."""

    sub: str  # User._id as string
    exp: int | None = None
    iat: int | None = None


class UserInfoResponse(BaseModel):
    """Response model for /auth/me."""

    user_id: str
    email: str
    full_name: str | None = None
    role: UserRole
    # Employee / tenant context — null until ensure_employee_for_user runs
    employee_id: str | None = None
    brand_id: str | None = None
    brand_name: str | None = None
    brand_domain: str | None = None
    # Client context — set only for the client role, which has no Employee row.
    # The frontend needs brand_id populated for both roles, or it treats a
    # signed-in client as someone who never finished onboarding.
    client_id: str | None = None
    client_name: str | None = None


class UserUpdate(BaseModel):
    """Payload for PATCH /auth/me."""

    full_name: str | None = Field(None, max_length=120)
