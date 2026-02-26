"""Standard API response models"""

from typing import Any, Optional, Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard API response format.

    Provides consistent structure across all endpoints:
    - success: True/False
    - data: Response payload
    - message: Optional message
    - metadata: Optional metadata (request_id, timestamp, etc.)

    Example:
        @router.get("/users/{id}")
        async def get_user(id: str):
            user = await get_user_by_id(id)
            return StandardResponse(
                data=user,
                message="User retrieved successfully"
            )
    """

    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    metadata: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "message": "Operation successful",
                "metadata": {"request_id": "req-123", "timestamp": "2024-01-01T00:00:00Z"},
            }
        }


class ErrorResponse(BaseModel):
    """
    Standard error response format.

    Example:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="VALIDATION_ERROR",
                message="Invalid input",
                details={"field": "email", "issue": "Invalid format"}
            ).model_dump()
        )
    """

    success: bool = False
    error: str = Field(..., description="Error code (e.g., VALIDATION_ERROR, NOT_FOUND)")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error context")
    metadata: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "NOT_FOUND",
                "message": "Resource not found",
                "details": {"resource": "User", "id": "123"},
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response format.

    Example:
        @router.get("/users")
        async def list_users(page: int = 1, limit: int = 10):
            users, total = await get_users_paginated(page, limit)
            return PaginatedResponse(
                items=users,
                total=total,
                page=page,
                limit=limit
            )
    """

    items: List[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    limit: int = Field(..., description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        limit: int,
    ) -> "PaginatedResponse[T]":
        """Convenience method to create paginated response"""
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=(page * limit) < total,
            has_prev=page > 1,
        )

    class Config:
        json_schema_extra = {
            "example": {
                "items": [{"id": "1"}, {"id": "2"}],
                "total": 100,
                "page": 1,
                "limit": 10,
                "has_next": True,
                "has_prev": False,
            }
        }
