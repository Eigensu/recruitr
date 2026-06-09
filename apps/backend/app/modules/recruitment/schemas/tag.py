from bson import ObjectId
from pydantic import BaseModel, field_validator


class RecruiterTagResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        try:
            return str(ObjectId(v))
        except Exception as e:
            raise ValueError(f"Invalid ObjectId: {v!r}") from e


class RecruiterTagCreate(BaseModel):
    name: str
