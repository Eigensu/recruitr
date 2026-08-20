"""Client resource DTOs."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints

# Names arrive from free-text inputs — trim and bound them at the edge so the
# stored value is exactly what the dropdown will render.
ClientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ClientCity = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
ClientText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class ClientResponse(BaseModel):
    id: str
    code: str
    name: str
    city: str | None = None
    industry: str | None = None
    logo_url: str | None = None
    brand_description: str | None = None
    website: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    allowed_domains: list[str] = []
    allowed_emails: list[str] = []
    is_active: bool = True
    # Active positions currently pointing at this client — surfaced so admins can
    # see the impact of archiving before they try it.
    position_count: int = 0
    # Distinct candidates mapped to any of this client's positions.
    candidate_count: int = 0
    user_count: int = 0
    created_by_id: str | None = None
    updated_by_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ClientCreate(BaseModel):
    name: ClientName
    city: ClientCity | None = None
    industry: ClientText | None = None
    website: ClientText | None = None
    contact_person: ClientText | None = None
    contact_email: ClientText | None = None
    contact_phone: ClientText | None = None
    allowed_domains: list[ClientText] | None = None
    allowed_emails: list[ClientText] | None = None


class ClientUpdate(BaseModel):
    name: ClientName | None = None
    city: ClientCity | None = None
    industry: ClientText | None = None
    website: ClientText | None = None
    contact_person: ClientText | None = None
    contact_email: ClientText | None = None
    contact_phone: ClientText | None = None
    allowed_domains: list[ClientText] | None = None
    allowed_emails: list[ClientText] | None = None
    is_active: bool | None = None


class ClientSelfUpdate(BaseModel):
    logo_url: str | None = None
    brand_description: str | None = None


class ClientUserResponse(BaseModel):
    id: str
    name: str | None = None
    email: str
    role: str
    # "Active" once they have signed in, "Inactive" once access is revoked,
    # "Pending" while the invitation has not been taken up.
    status: str
    last_login: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientUserInvite(BaseModel):
    email: EmailStr
    role: ClientText = "client"
