"""Configuration management for VelvetEcho"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class VelvetEchoConfig(BaseSettings):
    """
    Core configuration for VelvetEcho infrastructure.

    Can be configured via:
    - Environment variables (prefixed with VELVETECHO_)
    - .env file
    - Direct instantiation
    """

    model_config = SettingsConfigDict(
        env_prefix="VELVETECHO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Service identity
    service_name: str
    service_version: str = "0.1.0"
    environment: str = "development"  # development, staging, production

    # Temporal configuration
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: Optional[str] = None  # Defaults to service_name
    temporal_worker_count: int = 4
    temporal_max_concurrent_activities: int = 100

    # Redis configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 5

    # Cache configuration
    cache_ttl_default: int = 3600  # 1 hour
    cache_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60

    # API configuration (optional, for services using API module)
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    api_workers: int = 1

    # Database configuration (optional)
    database_url: Optional[str] = None
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Monitoring
    metrics_enabled: bool = True
    tracing_enabled: bool = False
    log_level: str = "INFO"

    @property
    def task_queue(self) -> str:
        """Get task queue name (defaults to service_name)"""
        return self.temporal_task_queue or f"{self.service_name}-tasks"

    def model_post_init(self, __context) -> None:
        """Validate configuration after initialization"""
        if not self.service_name:
            raise ValueError("service_name is required")


# Global config instance (can be overridden)
_config: Optional[VelvetEchoConfig] = None


def init_config(config: VelvetEchoConfig) -> None:
    """Initialize global config instance"""
    global _config
    _config = config


def get_config() -> VelvetEchoConfig:
    """Get global config instance"""
    if _config is None:
        raise RuntimeError(
            "VelvetEcho not initialized. Call init_config() first or use explicit config."
        )
    return _config
