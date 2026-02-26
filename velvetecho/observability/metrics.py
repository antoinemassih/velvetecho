"""
Metrics collection using Prometheus.

Provides counters, histograms, and gauges for monitoring VelvetEcho components.
"""

import time
from typing import Optional, Dict, Any
from functools import wraps
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Create registry
registry = CollectorRegistry()

# ============================================================================
# Workflow Metrics
# ============================================================================

workflow_duration = Histogram(
    "velvetecho_workflow_duration_seconds",
    "Time spent executing workflow",
    ["workflow_name", "status"],
    registry=registry,
)

workflow_executions = Counter(
    "velvetecho_workflow_executions_total",
    "Total workflow executions",
    ["workflow_name", "status"],
    registry=registry,
)

# ============================================================================
# Activity Metrics
# ============================================================================

activity_duration = Histogram(
    "velvetecho_activity_duration_seconds",
    "Time spent executing activity",
    ["activity_name", "status"],
    registry=registry,
)

activity_calls = Counter(
    "velvetecho_activity_calls_total",
    "Total activity calls",
    ["activity_name", "status"],
    registry=registry,
)

activity_retries = Counter(
    "velvetecho_activity_retries_total",
    "Activity retry attempts",
    ["activity_name"],
    registry=registry,
)

# ============================================================================
# Cache Metrics
# ============================================================================

cache_operations = Counter(
    "velvetecho_cache_operations_total",
    "Cache operations",
    ["operation", "status"],
    registry=registry,
)

cache_hit_rate = Gauge(
    "velvetecho_cache_hit_rate",
    "Cache hit rate percentage",
    registry=registry,
)

# ============================================================================
# Queue Metrics
# ============================================================================

queue_operations = Counter(
    "velvetecho_queue_operations_total",
    "Queue operations",
    ["queue_type", "operation"],
    registry=registry,
)

queue_depth = Gauge(
    "velvetecho_queue_depth",
    "Current queue depth",
    ["queue_name"],
    registry=registry,
)

queue_processing_time = Histogram(
    "velvetecho_queue_processing_seconds",
    "Time spent processing queue items",
    ["queue_name"],
    registry=registry,
)

# ============================================================================
# RPC Metrics
# ============================================================================

rpc_calls = Counter(
    "velvetecho_rpc_calls_total",
    "RPC calls",
    ["service", "method", "status"],
    registry=registry,
)

rpc_duration = Histogram(
    "velvetecho_rpc_duration_seconds",
    "RPC call duration",
    ["service", "method"],
    registry=registry,
)

# ============================================================================
# Database Metrics
# ============================================================================

db_operations = Counter(
    "velvetecho_db_operations_total",
    "Database operations",
    ["operation", "model"],
    registry=registry,
)

db_query_duration = Histogram(
    "velvetecho_db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    registry=registry,
)

db_connection_pool_size = Gauge(
    "velvetecho_db_connection_pool_size",
    "Database connection pool size",
    registry=registry,
)

# ============================================================================
# Circuit Breaker Metrics
# ============================================================================

circuit_breaker_state = Gauge(
    "velvetecho_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["name"],
    registry=registry,
)

circuit_breaker_failures = Counter(
    "velvetecho_circuit_breaker_failures_total",
    "Circuit breaker failures",
    ["name"],
    registry=registry,
)


# ============================================================================
# Metrics Collector
# ============================================================================


class MetricsCollector:
    """
    Centralized metrics collection.

    Example:
        collector = MetricsCollector()

        # Record workflow execution
        with collector.workflow_timer("my_workflow"):
            await execute_workflow()

        # Record activity call
        collector.record_activity("send_email", status="success", duration=0.5)

        # Get metrics for Prometheus
        metrics = collector.export()
    """

    def __init__(self):
        self.registry = registry
        self._cache_hits = 0
        self._cache_misses = 0

    def workflow_timer(self, workflow_name: str):
        """Context manager for timing workflow execution"""
        return _Timer(workflow_duration, {"workflow_name": workflow_name})

    def activity_timer(self, activity_name: str):
        """Context manager for timing activity execution"""
        return _Timer(activity_duration, {"activity_name": activity_name})

    def record_workflow(self, workflow_name: str, status: str, duration: float):
        """Record workflow execution"""
        workflow_duration.labels(workflow_name=workflow_name, status=status).observe(duration)
        workflow_executions.labels(workflow_name=workflow_name, status=status).inc()

    def record_activity(self, activity_name: str, status: str, duration: float):
        """Record activity execution"""
        activity_duration.labels(activity_name=activity_name, status=status).observe(duration)
        activity_calls.labels(activity_name=activity_name, status=status).inc()

    def record_activity_retry(self, activity_name: str):
        """Record activity retry"""
        activity_retries.labels(activity_name=activity_name).inc()

    def record_cache_hit(self):
        """Record cache hit"""
        self._cache_hits += 1
        cache_operations.labels(operation="hit", status="success").inc()
        self._update_cache_hit_rate()

    def record_cache_miss(self):
        """Record cache miss"""
        self._cache_misses += 1
        cache_operations.labels(operation="miss", status="success").inc()
        self._update_cache_hit_rate()

    def record_cache_operation(self, operation: str, status: str):
        """Record cache operation (get, set, delete)"""
        cache_operations.labels(operation=operation, status=status).inc()

    def record_queue_operation(self, queue_type: str, operation: str):
        """Record queue operation"""
        queue_operations.labels(queue_type=queue_type, operation=operation).inc()

    def set_queue_depth(self, queue_name: str, depth: int):
        """Set current queue depth"""
        queue_depth.labels(queue_name=queue_name).set(depth)

    def record_rpc_call(self, service: str, method: str, status: str, duration: float):
        """Record RPC call"""
        rpc_calls.labels(service=service, method=method, status=status).inc()
        rpc_duration.labels(service=service, method=method).observe(duration)

    def record_db_operation(self, operation: str, model: str, duration: float):
        """Record database operation"""
        db_operations.labels(operation=operation, model=model).inc()
        db_query_duration.labels(operation=operation).observe(duration)

    def set_circuit_breaker_state(self, name: str, state: int):
        """Set circuit breaker state (0=closed, 1=open, 2=half_open)"""
        circuit_breaker_state.labels(name=name).set(state)

    def record_circuit_breaker_failure(self, name: str):
        """Record circuit breaker failure"""
        circuit_breaker_failures.labels(name=name).inc()

    def export(self) -> bytes:
        """Export metrics in Prometheus format"""
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get Prometheus content type"""
        return CONTENT_TYPE_LATEST

    def _update_cache_hit_rate(self):
        """Update cache hit rate gauge"""
        total = self._cache_hits + self._cache_misses
        if total > 0:
            rate = (self._cache_hits / total) * 100
            cache_hit_rate.set(rate)


class _Timer:
    """Context manager for timing operations"""

    def __init__(self, histogram, labels: Dict[str, str]):
        self.histogram = histogram
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        status = "success" if exc_type is None else "error"
        self.histogram.labels(**self.labels, status=status).observe(duration)


# ============================================================================
# Decorators
# ============================================================================


def track_workflow(workflow_name: Optional[str] = None):
    """
    Decorator to automatically track workflow metrics.

    Example:
        @track_workflow("my_workflow")
        @workflow
        async def my_workflow():
            ...
    """

    def decorator(func):
        name = workflow_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                workflow_duration.labels(workflow_name=name, status=status).observe(duration)
                workflow_executions.labels(workflow_name=name, status=status).inc()

        return wrapper

    return decorator


def track_activity(activity_name: Optional[str] = None):
    """
    Decorator to automatically track activity metrics.

    Example:
        @track_activity("send_email")
        @activity
        async def send_email_activity():
            ...
    """

    def decorator(func):
        name = activity_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                activity_duration.labels(activity_name=name, status=status).observe(duration)
                activity_calls.labels(activity_name=name, status=status).inc()

        return wrapper

    return decorator


# ============================================================================
# Global Instance
# ============================================================================

# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
