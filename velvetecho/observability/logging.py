"""
Structured logging using structlog.

Provides consistent, machine-parseable logs for production debugging.
"""

import logging
import sys
from typing import Optional, Dict, Any

try:
    import structlog
    from structlog.stdlib import LoggerFactory

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    structlog = None


# ============================================================================
# Logging Setup
# ============================================================================


def setup_logging(
    level: str = "INFO",
    format: str = "json",  # json or console
    service_name: Optional[str] = None,
    additional_processors: Optional[list] = None,
) -> None:
    """
    Setup structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Output format (json or console)
        service_name: Service name to include in logs
        additional_processors: Additional log processors

    Example:
        setup_logging(level="INFO", format="json", service_name="velvetecho")

        logger = get_logger()
        logger.info("workflow_started", workflow_id="abc", user_id="123")
    """
    if not STRUCTLOG_AVAILABLE:
        # Fallback to standard logging
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
        )
        return

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Build processors
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add service name processor
    if service_name:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            )
        )

        def add_service_name(logger, method_name, event_dict):
            event_dict["service"] = service_name
            return event_dict

        processors.insert(0, add_service_name)

    # Add custom processors
    if additional_processors:
        processors.extend(additional_processors)

    # Choose renderer
    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None):
    """
    Get a structured logger.

    Example:
        logger = get_logger(__name__)
        logger.info("workflow_started", workflow_id="abc", duration=1.5)
        logger.error("workflow_failed", workflow_id="abc", error="timeout")
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name or "velvetecho")


# ============================================================================
# Log Helpers
# ============================================================================


class LogContext:
    """
    Context manager for adding context to logs.

    Example:
        logger = get_logger()

        with LogContext(workflow_id="abc", user_id="123"):
            logger.info("processing")  # Includes workflow_id and user_id
            do_work()
            logger.info("completed")  # Includes workflow_id and user_id
    """

    def __init__(self, **kwargs):
        self.context = kwargs
        self.token = None

    def __enter__(self):
        if STRUCTLOG_AVAILABLE:
            self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if STRUCTLOG_AVAILABLE and self.token:
            structlog.contextvars.unbind_contextvars(*self.context.keys())


# ============================================================================
# Standard Log Messages
# ============================================================================


def log_workflow_start(logger, workflow_id: str, workflow_name: str, **kwargs):
    """Standard log for workflow start"""
    logger.info(
        "workflow_started",
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        **kwargs,
    )


def log_workflow_complete(logger, workflow_id: str, workflow_name: str, duration: float, **kwargs):
    """Standard log for workflow completion"""
    logger.info(
        "workflow_completed",
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        duration_seconds=duration,
        **kwargs,
    )


def log_workflow_error(logger, workflow_id: str, workflow_name: str, error: str, **kwargs):
    """Standard log for workflow error"""
    logger.error(
        "workflow_failed",
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        error=error,
        **kwargs,
    )


def log_activity_start(logger, activity_name: str, **kwargs):
    """Standard log for activity start"""
    logger.info(
        "activity_started",
        activity_name=activity_name,
        **kwargs,
    )


def log_activity_complete(logger, activity_name: str, duration: float, **kwargs):
    """Standard log for activity completion"""
    logger.info(
        "activity_completed",
        activity_name=activity_name,
        duration_seconds=duration,
        **kwargs,
    )


def log_activity_retry(logger, activity_name: str, attempt: int, error: str, **kwargs):
    """Standard log for activity retry"""
    logger.warning(
        "activity_retry",
        activity_name=activity_name,
        attempt=attempt,
        error=error,
        **kwargs,
    )


def log_rpc_call(logger, service: str, method: str, duration: float, status: str, **kwargs):
    """Standard log for RPC call"""
    logger.info(
        "rpc_call",
        service=service,
        method=method,
        duration_seconds=duration,
        status=status,
        **kwargs,
    )


def log_cache_operation(logger, operation: str, key: str, hit: Optional[bool] = None, **kwargs):
    """Standard log for cache operation"""
    event = f"cache_{operation}"
    if hit is not None:
        event += "_hit" if hit else "_miss"

    logger.debug(
        event,
        operation=operation,
        key=key,
        **kwargs,
    )
