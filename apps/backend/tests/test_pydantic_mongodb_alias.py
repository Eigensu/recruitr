"""Pydantic populate-by-name / alias behaviour with BSON ObjectIds."""

from typing import Annotated

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _objectid_to_str(value: object) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str):
        return value
    msg = f"Expected ObjectId or str, got {type(value).__name__}"
    raise TypeError(msg)


ObjectIdStr = Annotated[str, BeforeValidator(_objectid_to_str)]


class BaseAnalyticsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: ObjectIdStr = Field(alias="_id")


def test_objectid_populates_id_and_alias_round_trip() -> None:
    test_id = ObjectId()
    item = BaseAnalyticsItem.model_validate({"_id": test_id})
    assert item.id == str(test_id)
    dumped = item.model_dump(by_alias=True)
    assert "_id" in dumped
