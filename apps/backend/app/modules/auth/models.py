"""Beanie Document model for the User."""

from datetime import UTC, datetime
from enum import Enum

from beanie import Document, Replace, Update, before_event
from pydantic import Field
from pymongo import IndexModel


class UserRole(str, Enum):
    """Access tier for a login user. Hierarchy: admin ⊇ maintainer ⊇ employee.

    - employee: regular recruiter; appears in the leaderboard and earns points.
    - maintainer: company manager (CEO); manages teams but is not a recruiter.
    - admin: full system access (single owner). Not a recruiter.
    """

    employee = "employee"
    maintainer = "maintainer"
    admin = "admin"


class User(Document):
    email: str
    hashed_password: str | None = None  # None for Google-only accounts
    full_name: str | None = None
    google_id: str | None = None  # Google sub (unique user ID)
    is_active: bool = True
    role: UserRole = UserRole.employee
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event(Update, Replace)
    def update_timestamp(self):
        self.updated_at = datetime.now(UTC)

    class Settings:
        name = "users"
        indexes = [
            IndexModel("email", unique=True),
            # Partial, not sparse. A sparse index skips documents where the
            # field is *absent*, but Beanie always serialises google_id — so
            # every password-only account stored an explicit null, the first
            # one claimed it, and the next signup died on a duplicate key.
            # Matching on $type string indexes real Google IDs and nothing else.
            IndexModel(
                "google_id",
                unique=True,
                partialFilterExpression={"google_id": {"$type": "string"}},
            ),
        ]
