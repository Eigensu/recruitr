"""Beanie Document model for the User."""

from datetime import datetime

from beanie import Document, before_event, Update, Replace
from pydantic import Field
from pymongo import IndexModel


class User(Document):
    email: str
    hashed_password: str
    full_name: str | None = None
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
        ]
