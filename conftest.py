"""Pytest configuration for VelvetEcho tests"""

import pytest
from velvetecho.config import VelvetEchoConfig, init_config


@pytest.fixture(scope="session", autouse=True)
def initialize_velvetecho():
    """Initialize VelvetEcho configuration for all tests"""
    config = VelvetEchoConfig(
        service_name="velvetecho-test",
        service_version="1.0.0",
        environment="test",
        redis_url="redis://localhost:6379/15",  # Use test DB 15
        cache_enabled=True,
        metrics_enabled=False,
        tracing_enabled=False,
        log_level="ERROR",  # Reduce noise in tests
    )
    init_config(config)
    yield
    # Cleanup after all tests
