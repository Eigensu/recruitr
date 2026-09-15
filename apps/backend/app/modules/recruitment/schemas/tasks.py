from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.common.utils.datetime_utils import normalize_datetime
from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.models import TaskAssignmentType

DATE_ERROR_MSG = "due_date must be greater than or equal to start_date"


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    tracked_activity_type: ActivityType
    target_count: int = Field(gt=0)
    assignee_type: TaskAssignmentType
    assignee_id: str | None = None
    start_date: datetime
    due_date: datetime

    @model_validator(mode="after")
    def check_dates(self) -> "TaskCreate":
        if self.start_date and self.due_date:
            s_dt = normalize_datetime(self.start_date)
            d_dt = normalize_datetime(self.due_date)
            if d_dt < s_dt:
                raise ValueError(DATE_ERROR_MSG)
        return self


class TaskUpdate(BaseModel):
    is_active: bool


class RecruiterProgress(BaseModel):
    employee_id: str
    name: str
    completed_count: int
    progress_percentage: int


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str | None
    tracked_activity_type: ActivityType
    target_count: int
    assignee_type: TaskAssignmentType
    assignee_id: str | None
    start_date: datetime
    due_date: datetime

    @model_validator(mode="after")
    def check_dates(self) -> "TaskResponse":
        if self.start_date and self.due_date:
            s_dt = normalize_datetime(self.start_date)
            d_dt = normalize_datetime(self.due_date)
            if d_dt < s_dt:
                raise ValueError(DATE_ERROR_MSG)
        return self

    is_active: bool
    created_at: datetime

    # Progress for the viewing user (if single) or overall summary
    completed_count: int = 0
    progress_percentage: int = 0

    # Detailed progress if queried by Admin for a Team/All task
    detailed_progress: list[RecruiterProgress] | None = None


class TaskUpdatePayload(BaseModel):
    title: str | None = None
    description: str | None = None
    tracked_activity_type: ActivityType | None = None
    target_count: int | None = Field(None, gt=0)
    assignee_type: TaskAssignmentType | None = None
    assignee_id: str | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "TaskUpdatePayload":
        if self.start_date and self.due_date:
            s_dt = normalize_datetime(self.start_date)
            d_dt = normalize_datetime(self.due_date)
            if d_dt < s_dt:
                raise ValueError(DATE_ERROR_MSG)
        return self
