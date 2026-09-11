from datetime import datetime

from pydantic import BaseModel


class RefereeUserResponse(BaseModel):
    # Plain, unaliased: an aliased `id` (Field(alias="_id")) serializes as
    # `_id` in the JSON response by default (FastAPI dumps response models
    # with by_alias=True) while every frontend consumer — listReferees(),
    # RefereeSettingsTab's remove/key-by-id, and the External Candidates
    # referee popover — reads `.id`. That mismatch shipped silently: nothing
    # throws on a `key={undefined}` or a DELETE /referees/undefined, they
    # just silently no-op.
    id: str
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


class RefereeUserInvite(BaseModel):
    email: str
    name: str | None = None
    role: str = "referee"
