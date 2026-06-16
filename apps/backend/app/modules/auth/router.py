"""Auth API endpoints."""

import secrets
import urllib.parse
from datetime import timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    TokenPayload,
    UserCreate,
    UserInfoResponse,
    UserLogin,
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
    """Ensure an Employee record exists for the user. Returns True if brand is assigned."""
    try:
        from app.modules.recruitment.service import ensure_employee_for_user

        employee = await ensure_employee_for_user(user)
        return employee.brand_id is not None
    except Exception:  # noqa: BLE001
        return False


# ── Standard email/password endpoints ────────────────────────────────────────


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate) -> dict:
    email = user_in.email.lower()
    if await User.find_one(User.email == email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")
    user = User(
        email=email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
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
    return {"status": "ok", "message": "Logged in successfully"}


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

    employee = await Employee.find_one({"email": user.email.lower()})

    return UserInfoResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
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


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    frontend = settings.FRONTEND_URL

    if error:
        return RedirectResponse(f"{frontend}/sign-in?error=google_denied")

    stored_state = request.session.pop("oauth_state", None)
    if not state or state != stored_state:
        return RedirectResponse(f"{frontend}/sign-in?error=invalid_state")

    if not code:
        return RedirectResponse(f"{frontend}/sign-in?error=missing_code")

    profile = await _fetch_google_profile(code)
    if profile is None:
        return RedirectResponse(f"{frontend}/sign-in?error=token_exchange_failed")

    if profile.get("email_verified") is not True:
        return RedirectResponse(f"{frontend}/sign-in?error=email_unverified")

    google_id = profile.get("sub")
    email = (profile.get("email") or "").lower()
    if not google_id or not email:
        return RedirectResponse(f"{frontend}/sign-in?error=userinfo_missing")

    user, _ = await _find_or_create_google_user(google_id, email, profile.get("name"))
    has_brand = await _ensure_employee(user)

    redirect_path = "/" if has_brand else "/onboarding"
    redirect = RedirectResponse(f"{frontend}{redirect_path}")
    _set_auth_cookie(redirect, str(user.id))
    return redirect
