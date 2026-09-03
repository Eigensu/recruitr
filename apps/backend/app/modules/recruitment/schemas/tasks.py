from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.models import TaskAssignmentType


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    tracked_activity_type: ActivityType
    target_count: int = Field(gt=0)
    assignee_type: TaskAssignmentType
    assignee_id: str | None = None
    start_date: datetime
    due_date: datetime


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
    is_active: bool
    created_at: datetime

    # Progress for the viewing user (if single) or overall summary
    completed_count: int = 0
    progress_percentage: int = 0

    # Detailed progress if queried by Admin for a Team/All task
    detailed_progress: list[RecruiterProgress] | None = None
