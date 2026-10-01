"""Centralized error types used across all API routes."""
from fastapi import HTTPException
from typing import Optional


class AppError(HTTPException):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail={"code": code, "message": detail})


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            code="NOT_FOUND",
            detail=f"{resource} '{resource_id}' not found",
            status_code=404,
        )


class ForbiddenError(AppError):
    def __init__(self, action: str = "perform this action"):
        super().__init__(
            code="FORBIDDEN",
            detail=f"You are not authorized to {action}",
            status_code=403,
        )


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(code="UNAUTHORIZED", detail=detail, status_code=401)


class ConflictError(AppError):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(code="CONFLICT", detail=detail, status_code=409)

