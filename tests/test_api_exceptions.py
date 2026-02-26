"""Tests for API exceptions"""

import pytest
from velvetecho.api.exceptions import (
    VelvetEchoException,
    ValidationException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ConflictException,
    RateLimitException,
)


def test_velvetecho_exception():
    """Test base exception"""
    exc = VelvetEchoException("Something went wrong", error_code="CUSTOM_ERROR", status_code=500)

    assert str(exc) == "Something went wrong"
    assert exc.error_code == "CUSTOM_ERROR"
    assert exc.status_code == 500

    error_dict = exc.to_dict()
    assert error_dict["success"] is False
    assert error_dict["error"] == "CUSTOM_ERROR"
    assert error_dict["message"] == "Something went wrong"


def test_validation_exception():
    """Test validation exception"""
    exc = ValidationException("Invalid email", details={"field": "email"})

    assert exc.error_code == "VALIDATION_ERROR"
    assert exc.status_code == 400
    assert exc.details == {"field": "email"}


def test_not_found_exception():
    """Test not found exception"""
    exc = NotFoundException("User", "123")

    assert exc.error_code == "NOT_FOUND"
    assert exc.status_code == 404
    assert "User not found: 123" in str(exc)


def test_unauthorized_exception():
    """Test unauthorized exception"""
    exc = UnauthorizedException()

    assert exc.error_code == "UNAUTHORIZED"
    assert exc.status_code == 401


def test_forbidden_exception():
    """Test forbidden exception"""
    exc = ForbiddenException("Access denied")

    assert exc.error_code == "FORBIDDEN"
    assert exc.status_code == 403


def test_conflict_exception():
    """Test conflict exception"""
    exc = ConflictException("Resource already exists", details={"id": "123"})

    assert exc.error_code == "CONFLICT"
    assert exc.status_code == 409


def test_rate_limit_exception():
    """Test rate limit exception"""
    exc = RateLimitException(retry_after=60)

    assert exc.error_code == "RATE_LIMIT_EXCEEDED"
    assert exc.status_code == 429
    assert exc.details["retry_after"] == 60
