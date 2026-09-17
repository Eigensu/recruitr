"""Global FastAPI dependencies for authentication, employee resolution, and tenant scoping."""

from __future__ import annotations

from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings
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


def deny_outsiders(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Raise 403 for client, referee and telecaller; allow recruiters and management.

    For routes that authenticate with get_current_user alone and never resolve
    a tenant, so get_tenant's refusal never runs for them: the leaderboard, which
    would otherwise show an employer, a referee or a telecaller our recruiters'
    names and scores; the Cloudinary upload signature, a credential to write
    into the agency's storage account that none of them has reason to hold; and
    brand creation, which runs at onboarding before any tenant exists and which
    a telecaller, being on the agency domain, would otherwise pass.

    Was deny_clients, which let referees through; nothing in the referee portal
    calls any of these, so refusing them closes a gap rather than breaking a page.
    """
    from app.modules.auth.models import UserRole

    if user.role in (UserRole.client, UserRole.referee, UserRole.telecaller):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This area is not available to {user.role.value} accounts.",
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


def _staff_scope(employee, user):
    """TenantScope for a user who holds an Employee record, once their role is cleared.

    Callers decide which roles may reach this; it only enforces that onboarding
    finished, so every path that admits a staff-shaped user applies the same
    brand check rather than re-deriving it.
    """
    from app.modules.recruitment.schemas import TenantScope

    if employee.brand_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a brand. Please complete onboarding.",
        )
    return TenantScope(brand_id=employee.brand_id, employee_id=employee.id, role=user.role)


def get_tenant(
    employee=Depends(get_current_employee),  # noqa: B008
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """Return a staff TenantScope for the current request.

    Raises 403 if the employee has not yet been assigned to a brand
    (i.e. onboarding is incomplete), and for the client and telecaller roles
    outright.

    Refusing them here is the whole containment strategy: nearly every endpoint
    depends on this, so they are denied everywhere by default and access has to
    be granted deliberately, one endpoint at a time. Forgetting an endpoint locks
    them out; it cannot leak.

    A telecaller is staff in the data model (an Employee, a brand) but not a
    recruiter, and these endpoints were written when every caller that got this
    far was one. Admitting the role here would hand it the candidate directory,
    positions, clients and the pipeline board on the day it was created.
    """
    from app.modules.auth.models import UserRole

    if user.role in (UserRole.client, UserRole.telecaller):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This area is not available to {user.role.value} accounts.",
        )
    return _staff_scope(employee, user)


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

    A telecaller is refused, because this defers to get_tenant — which is what
    keeps them off the pipeline, positions and dashboard endpoints built on it.
    """
    from app.modules.auth.models import UserRole

    if user.role == UserRole.client:
        return await get_client_scope(user)

    employee = await get_current_employee(user)
    return get_tenant(employee, user)


def get_telecaller_tenant(
    employee=Depends(get_current_employee),  # noqa: B008
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """TenantScope for the lead queue: telecallers, plus the people who run it.

    The narrow counterpart to get_tenant's refusal. Recruiters are excluded on
    purpose — the queue is screening work, not recruiting, and a recruiter with
    no lead assigned to them has nothing to do here.
    """
    from app.modules.auth.models import UserRole

    if user.role not in (UserRole.telecaller, UserRole.maintainer, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is not available to this account.",
        )
    return _staff_scope(employee, user)


async def get_inbox_viewer(
    user=Depends(get_current_user_doc),  # noqa: B008
):
    """TenantScope for the notification inbox, the one get_viewer surface a telecaller needs.

    Not a widening of get_viewer: that would open every endpoint built on it.
    The inbox handler narrows telecallers to rows addressed to them by
    employee_id, so a telecaller never sees the brand-wide staff reminders.
    """
    from app.modules.auth.models import UserRole

    if user.role == UserRole.telecaller:
        return _staff_scope(await get_current_employee(user), user)
    return await get_viewer(user)
