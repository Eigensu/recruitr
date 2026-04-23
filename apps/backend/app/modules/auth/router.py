"""Auth API endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import settings
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import TokenPayload, UserCreate, UserInfoResponse, UserLogin
from app.modules.auth.security import create_access_token, get_password_hash, verify_password

router = APIRouter()


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
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,          # ensure it works locally generally depending on test framework, but for dev HTTP might complain. HTTPS required unless localhost
        samesite="lax",       # lax is safer for dev
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {"status": "ok", "message": "Logged in successfully"}


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Clear the access token cookie."""
    response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="lax")
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me", response_model=UserInfoResponse)
async def read_user_me(current_user: TokenPayload = Depends(get_current_user)) -> UserInfoResponse:
    """Get current user details."""
    user = await User.get(current_user.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserInfoResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
    )
