"""FastAPI dependency injection utilities"""

from typing import Annotated
from fastapi import Depends

from velvetecho.config import get_config, VelvetEchoConfig
from velvetecho.tasks.client import get_client, TemporalClient


def get_config_dep() -> VelvetEchoConfig:
    """FastAPI dependency: Get VelvetEcho configuration"""
    return get_config()


def get_client_dep() -> TemporalClient:
    """FastAPI dependency: Get Temporal client"""
    return get_client()


# Type aliases for cleaner route signatures
ConfigDep = Annotated[VelvetEchoConfig, Depends(get_config_dep)]
ClientDep = Annotated[TemporalClient, Depends(get_client_dep)]
