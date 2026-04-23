"""Common base classes shared across all modules."""

from beanie import Document
from pydantic import BaseModel


class BaseDocument(Document):
    """Base Beanie document with shared helper methods."""

    class Settings:
        use_state_management = True

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class BaseSchema(BaseModel):
    """Base Pydantic schema for all request/response models."""

    model_config = {"from_attributes": True, "populate_by_name": True}
