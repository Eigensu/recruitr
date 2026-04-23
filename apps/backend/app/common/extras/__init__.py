"""Extra utilities that don't fit neatly into other common categories."""

from beanie import PydanticObjectId
from fastapi import HTTPException, status


def parse_object_id(value: str) -> PydanticObjectId:
    """Parse a string to PydanticObjectId, raising 422 on invalid format."""
    try:
        return PydanticObjectId(value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{value}' is not a valid ObjectId.",
        )


def serialize_doc(doc) -> dict:
    """Convert a Beanie document to a JSON-serialisable dict with string id."""
    data = doc.model_dump(mode="json")
    data["id"] = str(doc.id)
    return data
