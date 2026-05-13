"""Reusable pagination DTOs used by dashboard and other modules."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: PaginationMeta
