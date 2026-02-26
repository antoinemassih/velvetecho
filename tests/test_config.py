"""Tests for configuration management"""

import pytest
from velvetecho.config import VelvetEchoConfig, init_config, get_config


def test_config_creation():
    """Test basic config creation"""
    config = VelvetEchoConfig(
        service_name="test-service",
        temporal_host="localhost:7233",
    )

    assert config.service_name == "test-service"
    assert config.temporal_host == "localhost:7233"
    assert config.task_queue == "test-service-tasks"


def test_config_validation():
    """Test config validation fails without service_name"""
    with pytest.raises(ValueError):
        VelvetEchoConfig()


def test_custom_task_queue():
    """Test custom task queue name"""
    config = VelvetEchoConfig(
        service_name="test-service",
        temporal_task_queue="custom-queue",
    )

    assert config.task_queue == "custom-queue"


def test_global_config():
    """Test global config init and retrieval"""
    config = VelvetEchoConfig(service_name="test")
    init_config(config)

    retrieved = get_config()
    assert retrieved.service_name == "test"


def test_config_defaults():
    """Test default configuration values"""
    config = VelvetEchoConfig(service_name="test")

    assert config.environment == "development"
    assert config.temporal_namespace == "default"
    assert config.temporal_worker_count == 4
    assert config.cache_enabled is True
    assert config.metrics_enabled is True
