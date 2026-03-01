"""Activity decorator and utilities for Temporal"""

import functools
from typing import Any, Callable, ParamSpec, TypeVar, Optional
from temporalio import activity as temporal_activity

P = ParamSpec("P")
R = TypeVar("R")


class ActivityConfig:
    """Configuration for activity execution"""

    def __init__(
        self,
        name: Optional[str] = None,
        start_to_close_timeout: Optional[int] = None,
        schedule_to_close_timeout: Optional[int] = None,
        heartbeat_timeout: Optional[int] = None,
        retry_policy: Optional[dict] = None,
    ):
        self.name = name
        self.start_to_close_timeout = start_to_close_timeout
        self.schedule_to_close_timeout = schedule_to_close_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.retry_policy = retry_policy


def activity(
    func: Optional[Callable[P, R]] = None,
    *,
    name: Optional[str] = None,
    start_to_close_timeout: int = 300,  # 5 minutes default
    schedule_to_close_timeout: Optional[int] = None,
    heartbeat_timeout: Optional[int] = None,
    retry_policy: Optional[dict] = None,
) -> Callable[P, R]:
    """
    Decorator to mark a function as a Temporal activity.

    Activities are individual units of work that can be retried,
    timed out, and executed across different workers.

    Args:
        name: Activity name (defaults to function name)
        start_to_close_timeout: Max time for single execution (seconds)
        schedule_to_close_timeout: Max time from schedule to completion (seconds)
        heartbeat_timeout: Max time between heartbeats (seconds)
        retry_policy: Retry configuration dict with:
            - max_attempts: Maximum retry attempts (default: unlimited)
            - backoff_coefficient: Multiplier for retry delay (default: 2.0)
            - initial_interval: Initial retry delay in seconds (default: 1)
            - max_interval: Maximum retry delay in seconds (default: 100)

    Example:
        @activity(start_to_close_timeout=60, retry_policy={"max_attempts": 3})
        async def fetch_data(url: str) -> dict:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                return response.json()

        # Called from workflow
        result = await fetch_data.run("https://api.example.com/data")
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        # Apply Temporal's activity decorator
        decorated_activity = temporal_activity.defn(name=name or fn.__name__)(fn)

        # Store config as metadata
        config = ActivityConfig(
            name=name or fn.__name__,
            start_to_close_timeout=start_to_close_timeout,
            schedule_to_close_timeout=schedule_to_close_timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )
        decorated_activity._velvetecho_config = config  # type: ignore

        # Add convenience wrapper
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await decorated_activity(*args, **kwargs)

        # Copy metadata
        wrapper._temporal_activity = decorated_activity  # type: ignore
        wrapper._velvetecho_config = config  # type: ignore

        return wrapper  # type: ignore

    # Support both @activity and @activity()
    if func is None:
        return decorator  # type: ignore
    return decorator(func)


# Activity utilities
def get_activity_info() -> temporal_activity.Info:
    """Get information about the current activity execution"""
    return temporal_activity.info()


def heartbeat(*details: Any) -> None:
    """Send heartbeat from within an activity (prevents timeout)"""
    temporal_activity.heartbeat(*details)


def is_cancelled() -> bool:
    """Check if the current activity has been cancelled"""
    try:
        temporal_activity.info()
        return False
    except Exception:
        return True
