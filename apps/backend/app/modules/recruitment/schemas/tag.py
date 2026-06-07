from pydantic import BaseModel


class RecruiterTagResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class RecruiterTagCreate(BaseModel):
    name: str
