from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str


class EmployeeTeamResponse(BaseModel):
    id: str
    name: str
    email: str
    team_id: str | None = None

    model_config = {"from_attributes": True}


class BulkAssignEmployees(BaseModel):
    employee_ids: list[str]
    team_id: str | None = None
