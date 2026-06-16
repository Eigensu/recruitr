"""Global FastAPI dependencies for authentication, employee resolution, and tenant scoping."""

from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.config import settings
from app.modules.auth.schemas import TokenPayload

# ── Auth ───────────────────────────────────────────────────────────────────────


def get_current_user(request: Request) -> TokenPayload:
    """Decode and validate the local JWT from the access_token HttpOnly cookie."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from None


async def get_current_user_doc(
    token: TokenPayload = Depends(get_current_user),  # noqa: B008
):
    """Load the full User document for the authenticated request.

    A single source of truth for the user's role and identity, resolved once
    per request (FastAPI caches the dependency) and reused by the employee,
    tenant, and role-guard dependencies below.
    """
    from app.modules.auth.models import User

    user = await User.get(PydanticObjectId(token.sub))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User account not found")
    return user


# ── Employee / tenant ──────────────────────────────────────────────────────────


async def get_current_employee(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Resolve the logged-in user to their Employee record.

    Imports are deferred to avoid a circular dependency between this module
    and the recruitment service.
    """
    from app.modules.recruitment.models import Employee
    from app.modules.recruitment.service import ensure_employee_for_user

    employee = await Employee.find_one({"email": user.email.lower()})
    if not employee:
        employee = await ensure_employee_for_user(user)

    return employee


def require_admin(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Raise 403 unless the authenticated user has the admin role."""
    from app.modules.auth.models import UserRole

    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_maintainer(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Raise 403 unless the user is a maintainer or admin (admin ⊇ maintainer)."""
    from app.modules.auth.models import UserRole

    if user.role not in (UserRole.maintainer, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Maintainer access required"
        )
    return user


def get_tenant(
    employee=Depends(get_current_employee),  # noqa: B008
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Return a TenantScope for the current request.

    Raises 403 if the employee has not yet been assigned to a brand
    (i.e. onboarding is incomplete).
    """
    from app.modules.recruitment.schemas import TenantScope

    if employee.brand_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a brand. Please complete onboarding.",
        )
    return TenantScope(brand_id=employee.brand_id, employee_id=employee.id, role=user.role)
