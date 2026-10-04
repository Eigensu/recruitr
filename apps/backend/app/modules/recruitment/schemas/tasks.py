from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field, model_validator

from app.common.utils.datetime_utils import normalize_datetime
from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.models import TaskAssignmentType

DATE_ERROR_MSG = "due_date must be greater than or equal to start_date"
START_IN_PAST_MSG = "start_date can't be earlier than today"


def starts_in_the_past(start_date: datetime) -> bool:
    """True if a checklist would start before the creator's today.

    The browser sends the start as local midnight, and nothing here knows the
    creator's timezone — so "before today" can't be a calendar comparison: IST
    midnight is 18:30Z the *previous* UTC day, and comparing against UTC
    midnight would refuse every task created in India for its own today. The
    creator's today began less than 24 hours ago in any zone, and yesterday
    began at least 24 hours ago, which is the whole test.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    return normalize_datetime(start_date) <= now - timedelta(hours=24)


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
        if starts_in_the_past(self.start_date):
            raise ValueError(START_IN_PAST_MSG)
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
