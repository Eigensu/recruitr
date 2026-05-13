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
from app.modules.auth.schemas import TokenPayload, UserCreate, UserInfoResponse, UserLogin
from app.modules.auth.security import create_access_token, get_password_hash, verify_password

# Cookie should only be Secure in production (HTTPS).
# On local HTTP dev, secure=True causes the browser to silently drop the cookie.
_COOKIE_SECURE = not settings.DEBUG

# ── Google OAuth2 constants ───────────────────────────────────────────────────
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _set_auth_cookie(response: Response, user_id: str) -> None:
    """Issue a JWT and stamp it as an HttpOnly cookie on the response."""
    token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Standard email/password endpoints ────────────────────────────────────────


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate) -> dict:
    """Register a new user."""
    email = user_in.email.lower()
    user = await User.find_one(User.email == email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )

    user = User(
        email=email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
    )
    await user.insert()
    return {"status": "ok", "message": "User created successfully"}


@router.post("/login")
async def login(user_in: UserLogin, response: Response) -> dict:
    """Authenticate a user and set an HttpOnly access token cookie."""
    email = user_in.email.lower()
    user = await User.find_one(User.email == email)

    # Guard: Google-only users have no password — tell them to use Google sign-in.
    if user and user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account was created with Google. Please sign in with Google.",
        )

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    _set_auth_cookie(response, str(user.id))
    return {"status": "ok", "message": "Logged in successfully"}


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Clear the access token cookie."""
    response.delete_cookie(key="access_token", httponly=True, secure=_COOKIE_SECURE, samesite="lax")
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me", response_model=UserInfoResponse)
async def read_user_me(current_user: TokenPayload = Depends(get_current_user)) -> UserInfoResponse:  # noqa: B008
    """Get current user details."""
    user = await User.get(current_user.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserInfoResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
    )


# ── Google OAuth2 endpoints ───────────────────────────────────────────────────


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    """
    Step 1: Redirect the browser to Google's consent screen.
    A random `state` token is stored in the session to prevent CSRF.
    """
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
    url = f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """
    Step 2: Google redirects here after the user grants consent.
    Exchange the authorization code for user info, then set our JWT cookie.
    """
    frontend = settings.FRONTEND_URL

    # User denied consent on Google's screen
    if error:
        return RedirectResponse(f"{frontend}/sign-in?error=google_denied")

    # CSRF check: state must match what we stored in the session
    stored_state = request.session.pop("oauth_state", None)
    if not state or state != stored_state:
        return RedirectResponse(f"{frontend}/sign-in?error=invalid_state")

    if not code:
        return RedirectResponse(f"{frontend}/sign-in?error=missing_code")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            # Exchange authorization code → access token
            token_resp = await client.post(
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
                return RedirectResponse(f"{frontend}/sign-in?error=token_exchange_failed")

            google_access_token = token_resp.json().get("access_token")

            # Fetch user profile from Google
            userinfo_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {google_access_token}"},
            )
            if userinfo_resp.status_code != 200:
                return RedirectResponse(f"{frontend}/sign-in?error=userinfo_failed")
    except (httpx.RequestError, httpx.TimeoutException):
        return RedirectResponse(f"{frontend}/sign-in?error=network_error")

    profile = userinfo_resp.json()
    if profile.get("email_verified") is not True:
        return RedirectResponse(f"{frontend}/sign-in?error=email_unverified")
        
    google_id = profile.get("sub")
    email = profile.get("email")
    if not google_id or not email:
        return RedirectResponse(f"{frontend}/sign-in?error=userinfo_missing")

    email = email.lower()
    full_name: str | None = profile.get("name")

    # ── Find or create user ───────────────────────────────────────────────────
    user = await User.find_one(User.google_id == google_id)

    if user is None:
        # Check if an existing email/password account uses this email — link them.
        user = await User.find_one(User.email == email)
        if user is not None:
            user.google_id = google_id
            await user.save()
        else:
            # Brand-new Google user — create account and send to onboarding.
            user = User(email=email, full_name=full_name, google_id=google_id)
            await user.insert()

            # Set cookie on the onboarding redirect so the session is active.
            redirect = RedirectResponse(f"{frontend}/onboarding")
            _set_auth_cookie(redirect, str(user.id))
            return redirect

    # Existing user — go straight to dashboard.
    redirect = RedirectResponse(f"{frontend}/")
    _set_auth_cookie(redirect, str(user.id))
    return redirect
