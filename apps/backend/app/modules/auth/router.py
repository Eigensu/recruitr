"""Auth API endpoints."""

import secrets
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_current_user
from app.modules.auth.access import (
    NOT_AUTHORIZED,
    find_client_authorization,
    may_sign_in,
)
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import (
    TokenPayload,
    UserCreate,
    UserInfoResponse,
    UserLogin,
    UserUpdate,
)
from app.modules.auth.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)

_COOKIE_SECURE = not settings.DEBUG

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 — public OAuth endpoint, not a secret
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _set_auth_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key="access_token",
        value=token,
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def _ensure_employee(user: User) -> bool:
    """Ensure an Employee record exists for the user. Returns True if brand is assigned.

    Skipped for client accounts: they are not recruiters, and an Employee row
    would put an outsider in the team roster, the leaderboard and every
    employee picker.
    """
    if user.role == UserRole.client:
        return await _link_client_login(user)
    if user.role == UserRole.referee:
        return await _link_referee_login(user)

    try:
        from app.modules.recruitment.service import ensure_employee_for_user

        employee = await ensure_employee_for_user(user)
        return employee.brand_id is not None
    except Exception:  # noqa: BLE001
        return False


async def _link_client_login(user: User) -> bool:
    """Attach the login to its ClientUser grant and stamp the sign-in.

    Returns whether a live grant exists — a revoked one leaves the account able
    to authenticate but scoped to nothing, which get_client_scope then refuses.
    """
    grant = await find_client_authorization(user.email)
    if grant is None:
        return False
    await grant.set(
        {
            "user_id": user.id,
            "name": grant.name or user.full_name,
            "last_login": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )
    return True


async def _link_referee_login(user: User) -> bool:
    """Attach the login to its RefereeUser grant and stamp the sign-in."""
    from app.modules.auth.access import find_referee_authorization
    from app.modules.recruitment.utils.connect_code import ensure_connect_code

    grant = await find_referee_authorization(user.email)
    if grant is None:
        return False
    await grant.set(
        {
            "user_id": user.id,
            "name": grant.name or user.full_name,
            "last_login": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )
    await ensure_connect_code(grant)
    return True


# ── Standard email/password endpoints ────────────────────────────────────────


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate) -> dict:
    email = user_in.email.lower()
    # Checked before the existence probe so an outsider cannot use the differing
    # replies to work out which addresses are registered.
    allowed, is_client, is_referee = await may_sign_in(email)
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_AUTHORIZED)
    if await User.find_one(User.email == email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")

    role = UserRole.employee
    if is_client:
        role = UserRole.client
    elif is_referee:
        role = UserRole.referee

    user = User(
        email=email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=role,
    )
    await user.insert()
    await _ensure_employee(user)
    return {"status": "ok", "message": "User created successfully"}


@router.post("/login")
async def login(user_in: UserLogin, response: Response) -> dict:
    email = user_in.email.lower()
    user = await User.find_one(User.email == email)

    if user and user.hashed_password is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This account was created with Google. Please sign in with Google.",
        )

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    await _ensure_employee(user)
    _set_auth_cookie(response, str(user.id))
    return {"status": "ok", "message": "Logged in successfully", "role": user.role.value}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(
        key="access_token",
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
    )
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me")
async def read_user_me(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> UserInfoResponse:
    from beanie import PydanticObjectId

    from app.modules.recruitment.models import Employee

    user = await User.get(PydanticObjectId(current_user.sub))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    from app.modules.brands.models import Brand

    # A client has no Employee row — their tenant comes from the grant instead.
    if user.role == UserRole.client:
        from app.modules.recruitment.models import Client

        grant = await find_client_authorization(user.email)
        if grant is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "This account is no longer authorized for any company.",
            )
        brand = await Brand.get(grant.brand_id)
        employer = await Client.get(grant.client_id)
        return UserInfoResponse(
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            brand_id=str(grant.brand_id),
            brand_name=brand.name if brand else None,
            brand_domain=brand.domain if brand else None,
            client_id=str(grant.client_id),
            client_name=employer.name if employer else None,
        )

    if user.role == UserRole.referee:
        from app.modules.auth.access import find_referee_authorization
        from app.modules.recruitment.utils.connect_code import ensure_connect_code

        grant = await find_referee_authorization(user.email)
        if grant is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "This account is no longer authorized as a referee.",
            )
        brand = await Brand.get(grant.brand_id)
        return UserInfoResponse(
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            brand_id=str(grant.brand_id),
            brand_name=brand.name if brand else None,
            brand_domain=brand.domain if brand else None,
            # Minted here rather than left null: this is the response the portal
            # reads the code from, and a referee predating the field would
            # otherwise see an empty code on every page that offers to share it.
            connect_code=await ensure_connect_code(grant),
        )

    employee = await Employee.find_one({"email": user.email.lower()})

    # Brand identity ships with the user so callers don't need a second request
    # (the public application link is built from brand_domain).
    brand = None
    if employee and employee.brand_id:
        brand = await Brand.get(employee.brand_id)

    return UserInfoResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        employee_id=str(employee.id) if employee else None,
        brand_id=str(employee.brand_id) if employee and employee.brand_id else None,
        brand_name=brand.name if brand else None,
        brand_domain=brand.domain if brand else None,
    )


@router.patch("/me")
async def update_user_me(
    body: UserUpdate,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> UserInfoResponse:
    from beanie import PydanticObjectId

    from app.modules.recruitment.models import Employee

    user = await User.get(PydanticObjectId(current_user.sub))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.full_name is not None:
        user.full_name = body.full_name.strip() or None
    await user.save()

    employee = await Employee.find_one({"email": user.email.lower()})
    return UserInfoResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        employee_id=str(employee.id) if employee else None,
        brand_id=str(employee.brand_id) if employee and employee.brand_id else None,
    )


# ── Google OAuth2 helpers ─────────────────────────────────────────────────────


async def _fetch_google_profile(code: str) -> dict | None:
    """Exchange an auth code for a Google user-info dict, or return None on failure."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
            token_resp = await http.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                return None

            userinfo_resp = await http.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_resp.json().get('access_token')}"},
            )
            if userinfo_resp.status_code != 200:
                return None

            return userinfo_resp.json()
    except (httpx.RequestError, httpx.TimeoutException):
        return None


async def _find_or_create_google_user(
    google_id: str, email: str, full_name: str | None
) -> tuple[User, bool]:
    """Return (user, is_new). Links an existing email account to Google if needed."""
    user = await User.find_one(User.google_id == google_id)
    if user is not None:
        return user, False

    user = await User.find_one(User.email == email)
    if user is not None:
        user.google_id = google_id
        await user.save()
        return user, False

    user = User(email=email, full_name=full_name, google_id=google_id)
    await user.insert()
    return user, True


# ── Google OAuth2 endpoints ───────────────────────────────────────────────────


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}")


class _GoogleCallbackError(Exception):
    """A callback that cannot proceed, carrying the slug the sign-in page renders."""

    def __init__(self, slug: str) -> None:
        super().__init__(slug)
        self.slug = slug


async def _google_identity(
    request: Request,
    code: str | None,
    state: str | None,
    error: str | None,
) -> tuple[str, str, str | None]:
    """(google_id, email, name) for a valid callback, or raise _GoogleCallbackError."""
    if error:
        raise _GoogleCallbackError("google_denied")

    stored_state = request.session.pop("oauth_state", None)
    if not state or state != stored_state:
        raise _GoogleCallbackError("invalid_state")

    if not code:
        raise _GoogleCallbackError("missing_code")

    profile = await _fetch_google_profile(code)
    if profile is None:
        raise _GoogleCallbackError("token_exchange_failed")

    if profile.get("email_verified") is not True:
        raise _GoogleCallbackError("email_unverified")

    google_id = profile.get("sub")
    email = (profile.get("email") or "").lower()
    if not google_id or not email:
        raise _GoogleCallbackError("userinfo_missing")

    return google_id, email, profile.get("name")


def _google_role(current: UserRole, is_client: bool, is_referee: bool) -> UserRole:
    """The role a Google sign-in resolves to, which outranks the stored one."""
    if is_client:
        return UserRole.client
    if is_referee:
        return UserRole.referee
    return current


def _post_login_path(user: User, has_brand: bool, is_referee: bool) -> str:
    if is_referee:
        return "/referee"
    if has_brand or user.role == UserRole.client:
        return "/"
    return "/onboarding"


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    frontend = settings.FRONTEND_URL

    try:
        google_id, email, name = await _google_identity(request, code, state, error)
    except _GoogleCallbackError as exc:
        return RedirectResponse(f"{frontend}/sign-in?error={exc.slug}")

    # Gate before _find_or_create_google_user: a refused address must not leave
    # a User row behind. Anyone already provisioned passes regardless of domain,
    # which is what keeps staff on personal addresses signing in.
    # "not_registered" is the code the sign-in page already renders friendly
    # copy for ("Your organization is not registered with Binge Consulting").
    allowed, is_client, is_referee = await may_sign_in(email)
    if not allowed:
        return RedirectResponse(f"{frontend}/sign-in?error=not_registered")

    user, _ = await _find_or_create_google_user(google_id, email, name)

    role = _google_role(user.role, is_client, is_referee)
    if role != user.role:
        user.role = role
        await user.save()

    has_brand = await _ensure_employee(user)

    redirect = RedirectResponse(f"{frontend}{_post_login_path(user, has_brand, is_referee)}")
    _set_auth_cookie(redirect, str(user.id))
    return redirect
