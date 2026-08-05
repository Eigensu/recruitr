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


def deny_clients(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Raise 403 for the client role; allow any staff member.

    For routers that authenticate with get_current_user alone and never resolve
    a tenant — the leaderboard and gamification, which are agency-internal and
    would otherwise show an employer our recruiters' names and scores.
    """
    from app.modules.auth.models import UserRole

    if user.role == UserRole.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is not available to client accounts.",
        )
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
    """Return a staff TenantScope for the current request.

    Raises 403 if the employee has not yet been assigned to a brand
    (i.e. onboarding is incomplete), and for the client role outright.

    Refusing clients here is the whole containment strategy: nearly every
    endpoint depends on this, so a client is denied everywhere by default and
    access has to be granted deliberately, one endpoint at a time, by switching
    it to get_viewer. Forgetting an endpoint locks a client out; it cannot leak.
    """
    from app.modules.auth.models import UserRole
    from app.modules.recruitment.schemas import TenantScope

    if user.role == UserRole.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is not available to client accounts.",
        )
    if employee.brand_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a brand. Please complete onboarding.",
        )
    return TenantScope(brand_id=employee.brand_id, employee_id=employee.id, role=user.role)


async def get_client_scope(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Resolve a client-role user to the single employer they may see.

    The ClientUser row is the source of truth rather than a client_id copied
    onto User: revoking access there takes effect on the next request instead of
    leaving a stale grant behind on the login record.
    """
    from app.modules.recruitment.models import ClientUser
    from app.modules.recruitment.schemas import TenantScope

    grant = await ClientUser.find_one(
        {"email": user.email.lower(), "is_active": True},
    )
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is no longer authorized for any company.",
        )
    return TenantScope(
        brand_id=grant.brand_id,
        employee_id=None,
        role=user.role,
        client_id=grant.client_id,
    )


async def get_viewer(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """TenantScope for an endpoint that both staff and clients may read.

    Staff resolve exactly as get_tenant does; a client gets a scope carrying
    client_id, and the handler must narrow its query with `scope.scoped(...)`.
    Only use this on read endpoints that have been checked for that.
    """
    from app.modules.auth.models import UserRole

    if user.role == UserRole.client:
        return await get_client_scope(user)

    employee = await get_current_employee(user)
    return get_tenant(employee, user)
