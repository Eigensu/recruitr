"""In-app pipeline-action reminders — see dashboard/tasks.py for how these get created.

Endpoints:
  GET  /api/v1/notifications            list this viewer's notifications (newest first)
  POST /api/v1/notifications/{id}/read  mark one read
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.common.utils.object_id import to_object_id
from app.core.dependencies import get_viewer
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums import NotificationKind
from app.modules.recruitment.models import Notification
from app.modules.recruitment.schemas import TenantScope

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

_Viewer = Annotated[TenantScope, Depends(get_viewer)]
_ERR_NOT_FOUND = "Notification not found"


class NotificationResponse(BaseModel):
    id: str
    mapping_id: str | None = None
    kind: NotificationKind
    message: str
    created_at: datetime
    read_at: datetime | None = None


def _to_response(doc: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=str(doc.id),
        mapping_id=str(doc.mapping_id) if doc.mapping_id else None,
        kind=doc.kind,
        message=doc.message,
        created_at=doc.created_at,
        read_at=doc.read_at,
    )


# No notification carries this as its client_id (the field holds an ObjectId or
# None), so it matches nothing — a deliberate empty result for referees. Kept
# beside the only function that reads it: it is not a shared value, it is how
# this one predicate says "no rows".
_REFEREE_NO_NOTIFICATIONS = "__referee_has_no_notifications__"


def _scope_match(scope: TenantScope) -> dict[str, Any]:
    """Client sees only their own notifications; staff see the brand-wide ones
    raised for them (client_id=None) — see Notification's own docstring for why
    the reminder job writes one row of each per stuck mapping.

    Never returns an _id key: mark_notification_read adds its own, and a
    restriction expressed on _id would be silently replaced by it.
    """
    match: dict[str, Any] = {"brand_id": scope.brand_id}
    if scope.role == UserRole.client:
        match["client_id"] = scope.client_id
    elif scope.role == UserRole.referee:
        # Referees have no notifications currently.
        match["client_id"] = _REFEREE_NO_NOTIFICATIONS
    else:
        match["client_id"] = None
    return match


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
        # set(), not save(): save() rewrites every field from this in-memory
        # copy, so a concurrent write to the same row would be undone by a
        # request that only meant to stamp read_at.
        await doc.set({"read_at": doc.read_at})
    return _to_response(doc)
