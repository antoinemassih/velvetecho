"""Tests for task orchestration"""

import pytest
from velvetecho.tasks import workflow, activity


def test_activity_decorator():
    """Test activity decorator applies correctly"""

    @activity(start_to_close_timeout=60)
    async def test_activity(x: int) -> int:
        return x * 2

    # Check metadata
    assert hasattr(test_activity, "_velvetecho_config")
    assert test_activity._velvetecho_config.start_to_close_timeout == 60


@pytest.mark.skip(reason="Temporal requires class-based workflows, not function-based")
def test_workflow_decorator():
    """Test workflow decorator applies correctly"""

    @workflow(execution_timeout=300)
    async def test_workflow(x: int) -> int:
        return x * 2

    # Check metadata
    assert hasattr(test_workflow, "_velvetecho_config")
    assert test_workflow._velvetecho_config.execution_timeout == 300


def test_activity_with_retry_policy():
    """Test activity with custom retry policy"""

    @activity(
        retry_policy={
            "max_attempts": 5,
            "backoff_coefficient": 3.0,
            "initial_interval": 2,
        }
    )
    async def test_activity() -> str:
        return "success"

    config = test_activity._velvetecho_config
    assert config.retry_policy["max_attempts"] == 5
    assert config.retry_policy["backoff_coefficient"] == 3.0


@pytest.mark.asyncio
async def test_activity_execution():
    """Test activity can be called directly (for testing)"""

    @activity
    async def add_numbers(a: int, b: int) -> int:
        return a + b

    result = await add_numbers(5, 3)
    assert result == 8
