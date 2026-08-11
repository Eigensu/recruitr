from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field, model_validator

from app.modules.recruitment.enums.client_message import ClientMessageTarget, ClientMessageType


class ClientMessageBase(BaseModel):
    message_text: str = Field(..., min_length=1)
    target_type: ClientMessageTarget
    target_client_ids: list[PydanticObjectId] = Field(default_factory=list)
    start_at: datetime
    end_at: datetime
    type: ClientMessageType
    cta_url: str | None = None

    @model_validator(mode="after")
    def validate_logic(self) -> "ClientMessageBase":
        # Validate dates
        if self.start_at >= self.end_at:
            raise ValueError("end_at must be strictly after start_at")

        # Validate target_type and target_client_ids
        if self.target_type == ClientMessageTarget.specific and not self.target_client_ids:
            raise ValueError("target_client_ids must not be empty when target_type is specific")
        if self.target_type == ClientMessageTarget.all:
            self.target_client_ids = []

        return self


class ClientMessageCreate(ClientMessageBase):
    pass


class ClientMessageUpdate(BaseModel):
    message_text: str | None = Field(None, min_length=1)
    target_type: ClientMessageTarget | None = None
    target_client_ids: list[PydanticObjectId] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    type: ClientMessageType | None = None
    cta_url: str | None = None

    # We omit a complex model_validator for Update to keep it simple,
    # and we validate at the controller level instead if needed.


class ClientMessageOut(ClientMessageBase):
    id: PydanticObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    created_by_id: PydanticObjectId | None = None

    class Config:
        populate_by_name = True


class ClientMessagePublicOut(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    message_text: str
    type: ClientMessageType
    cta_url: str | None = None

    class Config:
        populate_by_name = True
