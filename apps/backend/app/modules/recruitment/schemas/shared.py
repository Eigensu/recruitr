"""Shared DTOs and value objects for the recruitment domain."""

from dataclasses import dataclass

from beanie import PydanticObjectId
from pydantic import BaseModel

from app.modules.auth.models import UserRole


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Resolved per-request tenant context produced by get_tenant()."""

    brand_id: PydanticObjectId
    employee_id: PydanticObjectId
    role: UserRole = UserRole.employee

    @property
    def is_recruiter(self) -> bool:
        """Only employee-role users count toward the leaderboard and activity feeds."""
        return self.role == UserRole.employee


class ResumeConfirm(BaseModel):
    """Sent after a successful Cloudinary direct-upload to attach the asset."""

    resume_public_id: str
    resume_url: str
