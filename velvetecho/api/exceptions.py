"""Custom exceptions for API layer"""

from typing import Optional, Any


class VelvetEchoException(Exception):
    """Base exception for all VelvetEcho errors"""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert to error response dict"""
        return {
            "success": False,
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationException(VelvetEchoException):
    """Raised when input validation fails"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class NotFoundException(VelvetEchoException):
    """Raised when a resource is not found"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": str(identifier)},
        )


class UnauthorizedException(VelvetEchoException):
    """Raised when authentication is required but missing/invalid"""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=401,
        )


class ForbiddenException(VelvetEchoException):
    """Raised when user lacks permission for operation"""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            status_code=403,
        )


class ConflictException(VelvetEchoException):
    """Raised when operation conflicts with current state"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details,
        )


class RateLimitException(VelvetEchoException):
    """Raised when rate limit is exceeded"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )
