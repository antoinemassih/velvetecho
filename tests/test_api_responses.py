"""Tests for API response models"""

import pytest
from velvetecho.api.responses import StandardResponse, ErrorResponse, PaginatedResponse


def test_standard_response_success():
    """Test standard response with data"""
    response = StandardResponse(
        data={"id": "123", "name": "Test"},
        message="Success"
    )

    assert response.success is True
    assert response.data == {"id": "123", "name": "Test"}
    assert response.message == "Success"


def test_standard_response_empty():
    """Test standard response without data"""
    response = StandardResponse()

    assert response.success is True
    assert response.data is None
    assert response.message is None


def test_error_response():
    """Test error response"""
    response = ErrorResponse(
        error="NOT_FOUND",
        message="Resource not found",
        details={"resource": "User", "id": "123"}
    )

    assert response.success is False
    assert response.error == "NOT_FOUND"
    assert response.message == "Resource not found"
    assert response.details == {"resource": "User", "id": "123"}


def test_paginated_response():
    """Test paginated response"""
    items = [{"id": str(i)} for i in range(10)]
    response = PaginatedResponse.create(
        items=items,
        total=100,
        page=1,
        limit=10
    )

    assert len(response.items) == 10
    assert response.total == 100
    assert response.page == 1
    assert response.limit == 10
    assert response.has_next is True
    assert response.has_prev is False


def test_paginated_response_last_page():
    """Test paginated response on last page"""
    items = [{"id": "1"}]
    response = PaginatedResponse.create(
        items=items,
        total=21,
        page=3,
        limit=10
    )

    assert response.has_next is False
    assert response.has_prev is True
