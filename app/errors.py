"""Domain errors mapped to HTTP status codes by the app error handlers.

Keeping these distinct from ``abort`` lets services be unit-tested directly
while the web layer still returns the contract required by FP-AUTH-3.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-visible application errors."""

    status = 400
    default_message = "The request could not be processed."

    def __init__(self, message: str | None = None, status: int | None = None):
        self.message = message or self.default_message
        if status is not None:
            self.status = status
        super().__init__(self.message)


class ValidationError(AppError):
    status = 400
    default_message = "Invalid input."


class UnauthorizedError(AppError):
    status = 401
    default_message = "Authentication required."


class ForbiddenError(AppError):
    status = 403
    default_message = "You are not allowed to perform this action."


class NotFoundError(AppError):
    status = 404
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    status = 409
    default_message = "The request conflicts with the current state."
