"""Client resource DTOs."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

# Names arrive from free-text inputs — trim and bound them at the edge so the
# stored value is exactly what the dropdown will render.
ClientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ClientCity = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]


class ClientResponse(BaseModel):
    id: str
    code: str
    name: str
    city: str | None = None
    is_active: bool = True
    # Active positions currently pointing at this client — surfaced so admins can
    # see the impact of archiving before they try it.
    position_count: int = 0

    model_config = {"from_attributes": True}


class ClientCreate(BaseModel):
    name: ClientName
    city: ClientCity | None = None


class ClientUpdate(BaseModel):
    name: ClientName | None = None
    city: ClientCity | None = None
    is_active: bool | None = None
