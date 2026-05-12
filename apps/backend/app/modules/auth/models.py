"""Beanie Document model for the User."""

from datetime import datetime

from beanie import Document, Replace, Update, before_event
from pydantic import Field
from pymongo import IndexModel


class User(Document):
    email: str
    hashed_password: str | None = None  # None for Google-only accounts
    full_name: str | None = None
    google_id: str | None = None  # Google sub (unique user ID)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @before_event(Update, Replace)
    def update_timestamp(self):
        self.updated_at = datetime.utcnow()

    class Settings:
        name = "users"
        indexes = [
            IndexModel("email", unique=True),
            # sparse: allows multiple null values
            IndexModel("google_id", unique=True, sparse=True),
        ]
