"""Shared DTOs (Data Transfer Objects) used across multiple modules."""

from pydantic import BaseModel


class PaginationParams(BaseModel):
    """Common query parameters for paginated list endpoints."""
    page: int = 1
    page_size: int = 20

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """Generic paginated response envelope."""
    total: int
    page: int
    page_size: int
    results: list


class MessageResponse(BaseModel):
    """Simple message response for non-data endpoints."""
    message: str
