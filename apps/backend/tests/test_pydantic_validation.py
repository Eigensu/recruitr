"""Pydantic validation expectations for analytics-style id fields."""

import pytest
from pydantic import BaseModel, ValidationError


class StrictIdModel(BaseModel):
    id: str


def test_model_validate_rejects_mongo_style_id_key() -> None:
    with pytest.raises(ValidationError):
        StrictIdModel.model_validate({"_id": "123"})
