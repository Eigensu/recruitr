"""Reusable Python decorators for FastAPI route handlers."""

import functools
import time
from collections.abc import Callable

from fastapi import HTTPException, status


def require_org(func: Callable) -> Callable:
    """Decorator that raises 403 if the current user has no org_id.

    Usage:
        @router.get("/brands")
        @require_org
        async def list_brands(current_user: TokenPayload = Depends(get_current_user)):
            ...
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get("current_user")
        if not current_user or not current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires an organisation (brand) account.",
            )
        return await func(*args, **kwargs)

    return wrapper


def timed(func: Callable) -> Callable:
    """Log execution time of an async handler (dev/debug use)."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"[timed] {func.__name__} took {elapsed:.1f}ms")
        return result

    return wrapper
