from pydantic import BaseModel, field_validator


class TeamResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)


class TeamCreate(BaseModel):
    name: str


class EmployeeTeamResponse(BaseModel):
    id: str
    name: str
    email: str
    team_id: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)

    @field_validator("team_id", mode="before")
    @classmethod
    def coerce_team_id(cls, v: object) -> str | None:
        return str(v) if v is not None else None


class BulkAssignEmployees(BaseModel):
    employee_ids: list[str]
    team_id: str | None = None
