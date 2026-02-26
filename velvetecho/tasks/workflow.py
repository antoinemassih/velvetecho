"""Workflow decorator and utilities for Temporal"""

import functools
from typing import Any, Callable, ParamSpec, TypeVar, Optional
from temporalio import workflow

P = ParamSpec("P")
R = TypeVar("R")


class WorkflowConfig:
    """Configuration for workflow execution"""

    def __init__(
        self,
        name: Optional[str] = None,
        execution_timeout: Optional[int] = None,  # seconds
        run_timeout: Optional[int] = None,  # seconds
        task_timeout: Optional[int] = None,  # seconds
        retry_policy: Optional[dict] = None,
    ):
        self.name = name
        self.execution_timeout = execution_timeout
        self.run_timeout = run_timeout
        self.task_timeout = task_timeout
        self.retry_policy = retry_policy


def workflow(
    func: Optional[Callable[P, R]] = None,
    *,
    name: Optional[str] = None,
    execution_timeout: Optional[int] = None,
    run_timeout: Optional[int] = None,
    task_timeout: Optional[int] = None,
    retry_policy: Optional[dict] = None,
) -> Callable[P, R]:
    """
    Decorator to mark a function as a Temporal workflow.

    Workflows orchestrate activities and other workflows. They are durable,
    recoverable, and can run for extended periods.

    Args:
        name: Workflow name (defaults to function name)
        execution_timeout: Total time workflow can execute (seconds)
        run_timeout: Time a single workflow run can execute (seconds)
        task_timeout: Time a single workflow task can execute (seconds)
        retry_policy: Retry configuration dict with:
            - max_attempts: Maximum retry attempts
            - backoff_coefficient: Multiplier for retry delay
            - initial_interval: Initial retry delay (seconds)
            - max_interval: Maximum retry delay (seconds)

    Example:
        @workflow(execution_timeout=3600)
        async def process_data(data_id: str):
            result = await fetch_data.run(data_id)
            transformed = await transform_data.run(result)
            await save_result.run(transformed)
            return transformed

        # Start workflow
        client = get_client()
        handle = await process_data.start("data-123")
        result = await handle.result()
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        # Apply Temporal's workflow decorator
        temporal_workflow = workflow.defn(name=name or fn.__name__)(fn)

        # Store config as metadata
        config = WorkflowConfig(
            name=name or fn.__name__,
            execution_timeout=execution_timeout,
            run_timeout=run_timeout,
            task_timeout=task_timeout,
            retry_policy=retry_policy,
        )
        temporal_workflow._velvetecho_config = config  # type: ignore

        # Add convenience methods
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await temporal_workflow(*args, **kwargs)

        # Copy metadata
        wrapper._temporal_workflow = temporal_workflow  # type: ignore
        wrapper._velvetecho_config = config  # type: ignore

        return wrapper  # type: ignore

    # Support both @workflow and @workflow()
    if func is None:
        return decorator  # type: ignore
    return decorator(func)


# Workflow utilities
def get_workflow_info() -> workflow.Info:
    """Get information about the current workflow execution"""
    return workflow.info()


def is_replaying() -> bool:
    """Check if the current workflow execution is replaying"""
    return workflow.unsafe.is_replaying()


async def sleep(seconds: float) -> None:
    """Sleep within a workflow (durable, survives restarts)"""
    await workflow.sleep(seconds)


def now() -> Any:
    """Get current time within workflow (deterministic)"""
    return workflow.now()
