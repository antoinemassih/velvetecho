"""
Observability module for VelvetEcho.

Provides metrics, tracing, and structured logging for production monitoring.
"""

from velvetecho.observability.metrics import (
    MetricsCollector,
    workflow_duration,
    activity_calls,
    cache_operations,
    queue_operations,
    rpc_calls,
)
from velvetecho.observability.tracing import (
    TracingService,
    trace_workflow,
    trace_activity,
    trace_rpc_call,
)
from velvetecho.observability.logging import (
    setup_logging,
    get_logger,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "workflow_duration",
    "activity_calls",
    "cache_operations",
    "queue_operations",
    "rpc_calls",
    # Tracing
    "TracingService",
    "trace_workflow",
    "trace_activity",
    "trace_rpc_call",
    # Logging
    "setup_logging",
    "get_logger",
]
