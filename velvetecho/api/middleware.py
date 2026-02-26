"""Middleware for FastAPI applications"""

import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import structlog

from velvetecho.api.exceptions import VelvetEchoException

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds unique request ID to each request.

    Request ID is:
    - Generated for each request
    - Added to response headers (X-Request-ID)
    - Available in logs
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all HTTP requests and responses.

    Logs:
    - Request method, path, headers
    - Response status, duration
    - Errors with stack traces
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Log request
        logger.info(
            "HTTP request started",
            method=request.method,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                "HTTP request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=int(duration * 1000),
                request_id=getattr(request.state, "request_id", None),
            )

            return response
        except Exception as e:
            duration = time.time() - start_time

            # Log error
            logger.error(
                "HTTP request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=int(duration * 1000),
                request_id=getattr(request.state, "request_id", None),
                exc_info=True,
            )

            raise


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Catches and formats exceptions as standard error responses.

    Handles:
    - VelvetEchoException → Formatted error response
    - Other exceptions → Generic 500 error
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except VelvetEchoException as e:
            return JSONResponse(
                status_code=e.status_code,
                content=e.to_dict(),
            )
        except Exception as e:
            logger.exception("Unhandled exception", exc_info=True)

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {"error": str(e)},
                },
            )


def setup_middleware(
    app: FastAPI,
    enable_cors: bool = True,
    cors_origins: list[str] = ["*"],
    enable_logging: bool = True,
    enable_error_handling: bool = True,
) -> None:
    """
    Set up all VelvetEcho middleware on a FastAPI app.

    Example:
        from fastapi import FastAPI
        from velvetecho.api import setup_middleware

        app = FastAPI()
        setup_middleware(app)
    """
    # CORS (if enabled)
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Request ID
    app.add_middleware(RequestIDMiddleware)

    # Logging (if enabled)
    if enable_logging:
        app.add_middleware(LoggingMiddleware)

    # Error handling (if enabled)
    if enable_error_handling:
        app.add_middleware(ErrorHandlerMiddleware)
