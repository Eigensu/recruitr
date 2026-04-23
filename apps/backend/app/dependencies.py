"""Global FastAPI dependencies for authentication and common services."""

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from app.config import settings
from app.modules.auth.schemas import TokenPayload


async def get_current_user(request: Request) -> TokenPayload:
    """Decode and validate the local JWT from the access_token HttpOnly cookie.

    Returns a TokenPayload with the user's sub.
    Raises 401 if the token is invalid or expired.
    """
    token = request.cookies.get("access_token")
    if not token:
        # Fallback to Authorization Header (Bearer) just in case NextJS Server Action calls it
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
        )
