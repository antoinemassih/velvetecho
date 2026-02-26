"""Tests for DAG workflow pattern"""

import pytest
import asyncio
from velvetecho.patterns import DAGWorkflow, DAGNode


@pytest.mark.asyncio
async def test_dag_simple_execution():
    """Test simple DAG execution with no dependencies"""
    results = []

    async def task_a(dependencies, **kwargs):
        results.append("A")
        return "result_a"

    async def task_b(dependencies, **kwargs):
        results.append("B")
        return "result_b"

    dag = DAGWorkflow()
    dag.add_node(DAGNode(id="a", execute=task_a, dependencies=[]))
    dag.add_node(DAGNode(id="b", execute=task_b, dependencies=[]))

    final_results = await dag.execute()

    assert set(results) == {"A", "B"}
    assert final_results["a"] == "result_a"
    assert final_results["b"] == "result_b"


@pytest.mark.asyncio
async def test_dag_with_dependencies():
    """Test DAG with dependencies"""
    results = []

    async def task_a(dependencies, **kwargs):
        results.append("A")
        return "result_a"

    async def task_b(dependencies, **kwargs):
        assert dependencies["a"] == "result_a"
        results.append("B")
        return "result_b"

    dag = DAGWorkflow()
    dag.add_node(DAGNode(id="a", execute=task_a, dependencies=[]))
    dag.add_node(DAGNode(id="b", execute=task_b, dependencies=["a"]))

    final_results = await dag.execute()

    assert results == ["A", "B"]  # Must be in order
    assert final_results["b"] == "result_b"


@pytest.mark.asyncio
async def test_dag_parallel_execution():
    """Test parallel execution of independent nodes"""
    start_times = {}
    end_times = {}

    async def slow_task(task_id):
        async def _task(dependencies, **kwargs):
            start_times[task_id] = asyncio.get_event_loop().time()
            await asyncio.sleep(0.1)
            end_times[task_id] = asyncio.get_event_loop().time()
            return f"result_{task_id}"
        return _task

    dag = DAGWorkflow()
    dag.add_node(DAGNode(id="a", execute=await slow_task("a"), dependencies=[]))
    dag.add_node(DAGNode(id="b", execute=await slow_task("b"), dependencies=[]))
    dag.add_node(DAGNode(id="c", execute=await slow_task("c"), dependencies=[]))

    await dag.execute()

    # All 3 should start around the same time (parallel)
    start_diff_ab = abs(start_times["a"] - start_times["b"])
    start_diff_bc = abs(start_times["b"] - start_times["c"])

    assert start_diff_ab < 0.05  # Started within 50ms
    assert start_diff_bc < 0.05


@pytest.mark.asyncio
async def test_dag_multi_level_dependencies():
    """Test multi-level dependency chain"""
    results = []

    async def task_a(dependencies, **kwargs):
        results.append("A")
        return "a"

    async def task_b(dependencies, **kwargs):
        assert dependencies["a"] == "a"
        results.append("B")
        return "b"

    async def task_c(dependencies, **kwargs):
        assert dependencies["a"] == "a"
        assert dependencies["b"] == "b"
        results.append("C")
        return "c"

    dag = DAGWorkflow()
    dag.add_node(DAGNode(id="a", execute=task_a, dependencies=[]))
    dag.add_node(DAGNode(id="b", execute=task_b, dependencies=["a"]))
    dag.add_node(DAGNode(id="c", execute=task_c, dependencies=["a", "b"]))

    await dag.execute()

    assert results == ["A", "B", "C"]


def test_dag_detect_missing_dependency():
    """Test DAG detects missing dependencies"""
    async def task(dependencies, **kwargs):
        return "result"

    dag = DAGWorkflow()
    dag.add_node(DAGNode(id="a", execute=task, dependencies=["missing"]))

    with pytest.raises(ValueError, match="depends on unknown node"):
        dag.get_execution_batches()


def test_dag_get_execution_batches():
    """Test DAG groups nodes into execution batches"""
    async def task(dependencies, **kwargs):
        return "result"

    dag = DAGWorkflow()
    # Batch 1: a, b
    dag.add_node(DAGNode(id="a", execute=task, dependencies=[]))
    dag.add_node(DAGNode(id="b", execute=task, dependencies=[]))
    # Batch 2: c (depends on a)
    dag.add_node(DAGNode(id="c", execute=task, dependencies=["a"]))
    # Batch 3: d (depends on b, c)
    dag.add_node(DAGNode(id="d", execute=task, dependencies=["b", "c"]))

    batches = dag.get_execution_batches()

    assert len(batches) == 3
    assert set(n.id for n in batches[0]) == {"a", "b"}
    assert set(n.id for n in batches[1]) == {"c"}
    assert set(n.id for n in batches[2]) == {"d"}


@pytest.mark.asyncio
async def test_dag_progress_callback():
    """Test DAG progress callback"""
    progress = []

    def progress_callback(node_id, status):
        progress.append((node_id, status))

    async def task(dependencies, **kwargs):
        return "result"

    dag = DAGWorkflow()
    dag.add_node(DAGNode(id="a", execute=task, dependencies=[]))
    dag.add_node(DAGNode(id="b", execute=task, dependencies=[]))

    await dag.execute(progress_callback=progress_callback)

    # Should have started and completed events for both
    assert ("a", "started") in progress
    assert ("a", "completed") in progress
    assert ("b", "started") in progress
    assert ("b", "completed") in progress
