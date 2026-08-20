"""In-app pipeline-action reminders — see dashboard/tasks.py for how these get created.

Endpoints:
  GET  /api/v1/notifications            list this viewer's notifications (newest first)
  POST /api/v1/notifications/{id}/read  mark one read
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.common.utils.object_id import to_object_id
from app.dependencies import get_viewer
from app.modules.recruitment.enums import NotificationKind
from app.modules.recruitment.models import Notification
from app.modules.recruitment.schemas import TenantScope

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

_Viewer = Annotated[TenantScope, Depends(get_viewer)]
_ERR_NOT_FOUND = "Notification not found"


class NotificationResponse(BaseModel):
    id: str
    mapping_id: str
    kind: NotificationKind
    message: str
    created_at: datetime
    read_at: datetime | None = None


def _to_response(doc: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=str(doc.id),
        mapping_id=str(doc.mapping_id),
        kind=doc.kind,
        message=doc.message,
        created_at=doc.created_at,
        read_at=doc.read_at,
    )


def _scope_match(scope: TenantScope) -> dict:
    """Client sees only their own notifications; staff see the brand-wide ones
    raised for them (client_id=None) — see Notification's own docstring for why
    the reminder job writes one row of each per stuck mapping."""
    return {"brand_id": scope.brand_id, "client_id": scope.client_id}


@router.get("")
async def list_notifications(
    viewer: _Viewer, unread_only: bool = False
) -> list[NotificationResponse]:
    match = _scope_match(viewer)
    if unread_only:
        match["read_at"] = None
    docs = await Notification.find(match).sort("-created_at").limit(50).to_list()
    return [_to_response(d) for d in docs]


@router.post("/{notification_id}/read")
async def mark_notification_read(viewer: _Viewer, notification_id: str) -> NotificationResponse:
    oid = to_object_id(notification_id, "notification_id")
    match = _scope_match(viewer)
    match["_id"] = oid
    doc = await Notification.find_one(match)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _ERR_NOT_FOUND)
    if doc.read_at is None:
        doc.read_at = datetime.now(UTC)
        await doc.save()
    return _to_response(doc)
