"""
Distributed tracing using OpenTelemetry.

Provides tracing for workflows, activities, and RPC calls across services.
"""

import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode

    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    trace = None


# ============================================================================
# Tracing Service
# ============================================================================


class TracingService:
    """
    Distributed tracing service.

    Example:
        # Initialize tracing
        tracing = TracingService(
            service_name="velvetecho",
            jaeger_host="localhost",
            jaeger_port=6831
        )
        tracing.setup()

        # Use in code
        with tracing.trace("my_operation", {"user_id": "123"}):
            do_work()
    """

    def __init__(
        self,
        service_name: str = "velvetecho",
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        enabled: bool = True,
    ):
        self.service_name = service_name
        self.jaeger_host = jaeger_host
        self.jaeger_port = jaeger_port
        self.enabled = enabled and TRACING_AVAILABLE
        self.tracer = None

    def setup(self):
        """Setup tracing provider"""
        if not self.enabled:
            print("[Tracing] OpenTelemetry not available, tracing disabled")
            return

        # Create resource
        resource = Resource.create({"service.name": self.service_name})

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Create Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=self.jaeger_host,
            agent_port=self.jaeger_port,
        )

        # Add span processor
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

        # Set provider
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(self.service_name)

        print(f"[Tracing] Enabled for {self.service_name} → {self.jaeger_host}:{self.jaeger_port}")

    @contextmanager
    def trace(self, span_name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Create a traced span.

        Example:
            with tracing.trace("process_order", {"order_id": "123"}):
                process_order()
        """
        if not self.enabled or not self.tracer:
            yield None
            return

        with self.tracer.start_as_current_span(span_name) as span:
            # Set attributes
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))

            try:
                yield span
            except Exception as e:
                # Record exception
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to current span"""
        if not self.enabled or not self.tracer:
            return

        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes=attributes or {})


# ============================================================================
# Decorators
# ============================================================================


def trace_workflow(workflow_name: Optional[str] = None, tracing_service: Optional[TracingService] = None):
    """
    Decorator to trace workflow execution.

    Example:
        @trace_workflow("my_workflow")
        @workflow
        async def my_workflow():
            ...
    """

    def decorator(func):
        name = workflow_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not tracing_service or not tracing_service.enabled:
                return await func(*args, **kwargs)

            with tracing_service.trace(f"workflow.{name}", {"workflow_name": name}):
                result = await func(*args, **kwargs)
                return result

        return wrapper

    return decorator


def trace_activity(activity_name: Optional[str] = None, tracing_service: Optional[TracingService] = None):
    """
    Decorator to trace activity execution.

    Example:
        @trace_activity("send_email")
        @activity
        async def send_email_activity():
            ...
    """

    def decorator(func):
        name = activity_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not tracing_service or not tracing_service.enabled:
                return await func(*args, **kwargs)

            with tracing_service.trace(f"activity.{name}", {"activity_name": name}):
                result = await func(*args, **kwargs)
                return result

        return wrapper

    return decorator


def trace_rpc_call(service: str, method: str, tracing_service: Optional[TracingService] = None):
    """
    Decorator to trace RPC calls.

    Example:
        @trace_rpc_call("urchinspike", "execute_tool")
        async def call_urchinspike():
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not tracing_service or not tracing_service.enabled:
                return await func(*args, **kwargs)

            with tracing_service.trace(
                f"rpc.{service}.{method}",
                {"service": service, "method": method, "rpc.system": "http"},
            ):
                result = await func(*args, **kwargs)
                return result

        return wrapper

    return decorator


# ============================================================================
# Global Instance
# ============================================================================

_tracing_service = None


def get_tracing_service() -> Optional[TracingService]:
    """Get global tracing service instance"""
    return _tracing_service


def init_tracing(
    service_name: str = "velvetecho",
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
    enabled: bool = True,
) -> TracingService:
    """Initialize global tracing service"""
    global _tracing_service
    _tracing_service = TracingService(
        service_name=service_name,
        jaeger_host=jaeger_host,
        jaeger_port=jaeger_port,
        enabled=enabled,
    )
    _tracing_service.setup()
    return _tracing_service
