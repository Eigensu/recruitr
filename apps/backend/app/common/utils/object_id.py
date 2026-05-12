"""Helpers for validating and converting MongoDB ObjectIds."""

from beanie import PydanticObjectId
from fastapi import HTTPException, status


def to_object_id(value: str | None, field_name: str) -> PydanticObjectId | None:
    """Convert a string to PydanticObjectId or raise a 400 error."""
    if value is None:
        return None

    try:
        return PydanticObjectId(value)
    except Exception as exc:  # pragma: no cover - defensive validation guard
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}",
        ) from exc
