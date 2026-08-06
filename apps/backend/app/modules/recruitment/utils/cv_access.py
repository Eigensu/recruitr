"""Who may open a candidate's CV.

A recruiter's own sourcing is their work product: the directory is shared, but
the resume file and the external CV link behind it are not. A recruiter sees the
CV of a candidate they added; anyone else sees the profile with the CV withheld.

The rule is enforced server-side, on every response that carries `resume_url` or
`cv_link` — the candidate directory, the position pipeline, and the suggestion
panels. Withholding it in the UI alone would be no restriction at all: the URLs
are unguessable but public once known, so a masked field has to never leave the
API in the first place.

Three exemptions, in order:

  - Client-role viewers. An employer looking at their own pipeline is not a
    recruiter competing for credit; they are the person the CV was sent to.
  - Maintainers and admins. They manage the desk and need to see all of it.
  - Unowned candidates. Public-form applications have no recruiter behind them,
    and records predating `created_by_id` cannot be attributed. Those stay
    shared rather than becoming invisible to everyone.
"""

from __future__ import annotations

from typing import Any

from beanie import PydanticObjectId

from app.modules.auth.models import UserRole
from app.modules.recruitment.schemas import TenantScope

# Fields blanked out on a candidate the viewer does not own.
_CV_FIELDS = ("resume_url", "cv_link")


def can_view_cv(scope: TenantScope, owner_id: PydanticObjectId | str | None) -> bool:
    """Whether this viewer may be handed the CV of a candidate owned by owner_id."""
    if scope.is_client:
        return True
    if scope.role in (UserRole.maintainer, UserRole.admin):
        return True
    if owner_id in (None, ""):
        return True
    return str(owner_id) == str(scope.employee_id)


def mask_cv_fields(
    row: dict[str, Any], scope: TenantScope, owner_key: str = "created_by_id"
) -> dict[str, Any]:
    """Blank the CV fields on one raw aggregation row unless the viewer owns it.

    Mutates and returns the row. Sets `cv_locked` either way so the UI can say
    "held by another recruiter" instead of silently showing nothing.
    """
    if can_view_cv(scope, row.get(owner_key)):
        row["cv_locked"] = False
        return row
    for field in _CV_FIELDS:
        if field in row:
            row[field] = None
    row["cv_locked"] = True
    return row


def mask_cv_rows(
    rows: list[dict[str, Any]], scope: TenantScope, owner_key: str = "created_by_id"
) -> list[dict[str, Any]]:
    """mask_cv_fields over a list of aggregation rows."""
    return [mask_cv_fields(row, scope, owner_key) for row in rows]
