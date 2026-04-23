"""Centralized error handling — custom exceptions and FastAPI exception handlers."""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse


class EigensuError(Exception):
    """Base application error."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundError(EigensuError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found."


class ConflictError(EigensuError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists."


class ForbiddenError(EigensuError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have permission to perform this action."


class UnauthorizedError(EigensuError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication required."


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app instance."""

    @app.exception_handler(EigensuError)
    async def eigensu_error_handler(request: Request, exc: EigensuError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
