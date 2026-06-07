from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str
