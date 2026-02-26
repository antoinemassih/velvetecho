"""FastAPI integration and patterns"""

from velvetecho.api.responses import StandardResponse, ErrorResponse, PaginatedResponse
from velvetecho.api.exceptions import VelvetEchoException, ValidationException, NotFoundException
from velvetecho.api.middleware import setup_middleware
from velvetecho.api.dependencies import get_config_dep, get_client_dep

__all__ = [
    "StandardResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "VelvetEchoException",
    "ValidationException",
    "NotFoundException",
    "setup_middleware",
    "get_config_dep",
    "get_client_dep",
]
