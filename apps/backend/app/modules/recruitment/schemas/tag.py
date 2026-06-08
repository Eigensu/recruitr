from pydantic import BaseModel, field_validator


class RecruiterTagResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


class RecruiterTagCreate(BaseModel):
    name: str
