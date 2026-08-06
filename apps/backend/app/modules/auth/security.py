"""Password hashing and JWT generation helpers."""

from datetime import datetime, timedelta

import bcrypt
from jose import jwt

from app.config import settings

# bcrypt only ever reads the first 72 bytes of a password. Up to bcrypt 4.x it
# truncated silently; 5.0 raises ValueError instead. We truncate ourselves so
# that behaviour stays identical either way — anyone who signed up with a
# longer password was already stored as its 72-byte prefix, and rejecting it
# now would lock them out of an account they can still log into.
_MAX_BCRYPT_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed/unknown hash in the database — treat as a failed login
        # rather than a 500, but never as a success.
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt
