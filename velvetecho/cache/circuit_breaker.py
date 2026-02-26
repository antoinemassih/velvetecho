"""Circuit breaker pattern for fault tolerance"""

import time
from enum import Enum
from typing import Callable, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests immediately rejected
    - HALF_OPEN: Testing recovery, limited requests allowed

    Example:
        breaker = CircuitBreaker(threshold=5, timeout=60)

        @breaker.call
        async def fetch_data():
            return await external_api_call()

        try:
            result = await fetch_data()
        except CircuitBreakerOpenError:
            # Circuit is open, use fallback
            result = get_cached_data()
    """

    def __init__(
        self,
        threshold: int = 5,
        timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            threshold: Number of failures before opening circuit
            timeout: Seconds to wait before trying half-open
            half_open_max_calls: Max requests in half-open state
        """
        self.threshold = threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def call(self, func: Callable) -> Callable:
        """
        Decorator to wrap function with circuit breaker.

        Example:
            breaker = CircuitBreaker()

            @breaker.call
            async def risky_operation():
                return await external_api()
        """

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if circuit is open
            if self.state == CircuitBreakerState.OPEN:
                # Check if timeout expired
                if (
                    self.last_failure_time
                    and time.time() - self.last_failure_time >= self.timeout
                ):
                    logger.info("Circuit breaker entering half-open state")
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is open")

            # Check if half-open and limit reached
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError("Circuit breaker half-open limit reached")
                self.half_open_calls += 1

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Success - reset or close circuit
                if self.state == CircuitBreakerState.HALF_OPEN:
                    logger.info("Circuit breaker closing (recovery successful)")
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    self.half_open_calls = 0
                elif self.state == CircuitBreakerState.CLOSED:
                    self.failure_count = 0

                return result

            except Exception as e:
                # Failure - increment counter
                self.failure_count += 1
                self.last_failure_time = time.time()

                logger.warning(
                    "Circuit breaker recorded failure",
                    failure_count=self.failure_count,
                    threshold=self.threshold,
                    state=self.state,
                    error=str(e),
                )

                # Open circuit if threshold reached
                if self.failure_count >= self.threshold:
                    if self.state != CircuitBreakerState.OPEN:
                        logger.error("Circuit breaker opening due to failures")
                        self.state = CircuitBreakerState.OPEN

                # If in half-open, go back to open
                if self.state == CircuitBreakerState.HALF_OPEN:
                    logger.warning("Circuit breaker reopening (recovery failed)")
                    self.state = CircuitBreakerState.OPEN

                raise

        return wrapper

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        logger.info("Circuit breaker manually reset")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""

    pass
