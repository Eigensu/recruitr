"""Pydantic schemas for authentication payloads and endpoints."""

from pydantic import BaseModel, EmailStr, Field


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

    sub: str  # User structure ID
    exp: int | None = None
    iat: int | None = None


class UserInfoResponse(BaseModel):
    """Response model for /auth/verify or /auth/me."""

    user_id: str
    email: str
    full_name: str | None = None
