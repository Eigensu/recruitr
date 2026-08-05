"""Shared DTOs and value objects for the recruitment domain."""

from dataclasses import dataclass

from beanie import PydanticObjectId
from pydantic import BaseModel

from app.modules.auth.models import UserRole


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Resolved per-request tenant context produced by get_tenant() or get_viewer().

    `employee_id` is None and `client_id` is set only for the client role, which
    get_viewer produces. Anything from get_tenant is staff and always has an
    employee_id, so handlers that write are safe to keep assuming it.
    """

    brand_id: PydanticObjectId
    employee_id: PydanticObjectId | None = None
    role: UserRole = UserRole.employee
    # Set only for the client role: restricts every query to one employer.
    client_id: PydanticObjectId | None = None

    @property
    def is_recruiter(self) -> bool:
        """Only employee-role users count toward the leaderboard and activity feeds."""
        return self.role == UserRole.employee

    @property
    def is_client(self) -> bool:
        return self.role == UserRole.client

    def scoped(self, match: dict) -> dict:
        """Add the client restriction to a query that already filters by brand.

        Callers pass a match that is correct for staff; this narrows it for a
        client viewer. Kept as one method so a new client-visible endpoint has a
        single obvious thing to call rather than re-deriving the filter.
        """
        if self.client_id is not None:
            match["client_id"] = self.client_id
        return match


class ResumeConfirm(BaseModel):
    """Sent after a successful Cloudinary direct-upload to attach the asset."""

    resume_public_id: str
    resume_url: str
