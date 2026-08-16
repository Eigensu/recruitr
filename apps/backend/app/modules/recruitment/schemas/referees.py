from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RefereeUserResponse(BaseModel):
    id: str = Field(alias="_id")
    brand_id: str
    email: str
    name: str | None = None
    role: str
    # Declared, not incidental: the controller has always passed it, but a field
    # missing from the model is dropped rather than rejected, so the admin list
    # was answering without the code the frontend types as required.
    connect_code: str | None = None
    is_active: bool
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class RefereeUserInvite(BaseModel):
    email: str
    name: str | None = None
    role: str = "referee"
