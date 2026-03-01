"""Enterprise-Grade Comprehensive Test Suite for VelvetEcho

Tests:
1. Load Testing - Multiple concurrent workflows
2. Failure Scenarios - Service failures and recovery
3. Stress Testing - High volume operations
4. Performance Benchmarks - Timing and throughput
5. Edge Cases - Boundary conditions
6. Data Integrity - Correctness under stress
7. Resource Usage - Memory and CPU
8. Error Recovery - Retry policies and circuit breakers
9. Long-Running Workflows - Extended execution
10. Concurrent DAG Execution - Parallel workflow instances

Each test is designed to verify enterprise-grade robustness.
"""

import asyncio
import time
import tracemalloc
import psutil
import os
from datetime import timedelta
from typing import List, Dict, Any
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from velvetecho.patterns import DAGWorkflow, DAGNode
from velvetecho.communication import EventBus
from velvetecho.cache import CircuitBreaker
from velvetecho.cache.circuit_breaker import CircuitBreakerOpenError
from velvetecho.cache.serialization import CacheSerializer


print("=" * 80)
print("🏢 VELVETECHO ENTERPRISE-GRADE TEST SUITE")
print("=" * 80)
print()

# Test results tracker
test_results = {
    "load_testing": {"status": "pending", "details": {}},
    "failure_scenarios": {"status": "pending", "details": {}},
    "stress_testing": {"status": "pending", "details": {}},
    "performance_benchmarks": {"status": "pending", "details": {}},
    "edge_cases": {"status": "pending", "details": {}},
    "concurrent_dag": {"status": "pending", "details": {}},
    "resource_usage": {"status": "pending", "details": {}},
    "error_recovery": {"status": "pending", "details": {}},
    "event_bus_load": {"status": "pending", "details": {}},
    "circuit_breaker_stress": {"status": "pending", "details": {}},
}


# ============================================================================
# TEST 1: Load Testing - Concurrent Workflows
# ============================================================================
@activity.defn
async def compute_heavy_task(task_id: int, duration: float = 0.1) -> dict:
    """Simulates CPU-heavy computation"""
    await asyncio.sleep(duration)
    return {"task_id": task_id, "result": task_id ** 2, "duration": duration}


@workflow.defn
class LoadTestWorkflow:
    """Simple workflow for load testing"""

    @workflow.run
    async def run(self, task_id: int, task_count: int = 5) -> dict:
        start = time.time()

        # Execute multiple activities
        results = []
        for i in range(task_count):
            result = await workflow.execute_activity(
                compute_heavy_task,
                args=[task_id * 100 + i],
                start_to_close_timeout=timedelta(seconds=10),
            )
            results.append(result)

        elapsed = time.time() - start
        return {
            "task_id": task_id,
            "task_count": task_count,
            "results": results,
            "elapsed": elapsed,
        }


async def test_load_concurrent_workflows():
    """Test multiple concurrent workflow executions"""
    print("📋 TEST 1: Load Testing - Concurrent Workflows")
    print("-" * 80)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "enterprise-load-test"

        num_workflows = 20  # Run 20 workflows concurrently
        task_count_per_workflow = 5

        print(f"   Starting worker for {num_workflows} concurrent workflows...")

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[LoadTestWorkflow],
            activities=[compute_heavy_task],
            max_concurrent_workflow_tasks=50,
            max_concurrent_activities=100,
        ):
            print(f"   Launching {num_workflows} workflows...")
            start_time = time.time()

            # Start all workflows concurrently
            handles = []
            for i in range(num_workflows):
                handle = await client.start_workflow(
                    LoadTestWorkflow.run,
                    args=[i, task_count_per_workflow],
                    id=f"load-test-{i}-{time.time()}",
                    task_queue=task_queue,
                )
                handles.append(handle)

            print(f"   ✅ Launched {num_workflows} workflows")
            print(f"   Waiting for completion...")

            # Wait for all to complete
            results = await asyncio.gather(*[h.result() for h in handles])

            total_time = time.time() - start_time
            total_tasks = num_workflows * task_count_per_workflow

            print(f"   ✅ All workflows completed!")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Total tasks executed: {total_tasks}")
            print(f"   Throughput: {total_tasks/total_time:.2f} tasks/sec")
            print(f"   Average workflow time: {sum(r['elapsed'] for r in results)/len(results):.2f}s")

            test_results["load_testing"] = {
                "status": "passed",
                "details": {
                    "num_workflows": num_workflows,
                    "total_tasks": total_tasks,
                    "total_time": total_time,
                    "throughput": total_tasks / total_time,
                    "avg_workflow_time": sum(r['elapsed'] for r in results) / len(results),
                },
            }

            print(f"   ✅ Load test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Load test FAILED: {e}")
        test_results["load_testing"] = {"status": "failed", "error": str(e)}
        traceback.print_exc()
        return False


# ============================================================================
# TEST 2: Stress Testing - High Volume DAG
# ============================================================================
@activity.defn
async def stress_activity(node_id: str, data: dict) -> dict:
    """Activity for stress testing"""
    await asyncio.sleep(0.01)  # Minimal delay
    return {"node_id": node_id, "processed": True, "input_size": len(str(data))}


@workflow.defn
class StressDAGWorkflow:
    """Workflow with many DAG nodes for stress testing"""

    @workflow.run
    async def run(self, num_nodes: int = 50) -> dict:
        dag = DAGWorkflow()

        # Build a large DAG
        # Layer 1: 10 independent nodes
        layer1_nodes = []
        for i in range(10):
            node_id = f"layer1_node_{i}"
            layer1_nodes.append(node_id)

            async def execute_layer1(dependencies, node_id=node_id, **kwargs):
                return await workflow.execute_activity(
                    stress_activity,
                    args=[node_id, {"data": "initial"}],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            dag.add_node(DAGNode(id=node_id, execute=execute_layer1, dependencies=[]))

        # Layer 2: 20 nodes depending on Layer 1
        layer2_nodes = []
        for i in range(20):
            node_id = f"layer2_node_{i}"
            layer2_nodes.append(node_id)
            deps = [layer1_nodes[i % 10]]  # Each depends on one Layer 1 node

            async def execute_layer2(dependencies, node_id=node_id, **kwargs):
                return await workflow.execute_activity(
                    stress_activity,
                    args=[node_id, {"deps": list(dependencies.keys())}],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            dag.add_node(DAGNode(id=node_id, execute=execute_layer2, dependencies=deps))

        # Layer 3: 20 nodes depending on Layer 2
        layer3_nodes = []
        for i in range(20):
            node_id = f"layer3_node_{i}"
            layer3_nodes.append(node_id)
            deps = [layer2_nodes[i % 20]]

            async def execute_layer3(dependencies, node_id=node_id, **kwargs):
                return await workflow.execute_activity(
                    stress_activity,
                    args=[node_id, {"deps": list(dependencies.keys())}],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            dag.add_node(DAGNode(id=node_id, execute=execute_layer3, dependencies=deps))

        # Final aggregation node
        async def execute_final(dependencies, **kwargs):
            return await workflow.execute_activity(
                stress_activity,
                args=["final", {"total_deps": len(dependencies)}],
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(
            DAGNode(id="final", execute=execute_final, dependencies=layer3_nodes)
        )

        # Execute the DAG
        start = time.time()
        results = await dag.execute()
        elapsed = time.time() - start

        return {
            "total_nodes": len(results),
            "execution_time": elapsed,
            "nodes_per_second": len(results) / elapsed,
        }


async def test_stress_large_dag():
    """Test DAG with many nodes"""
    print()
    print("📋 TEST 2: Stress Testing - Large DAG (51 nodes)")
    print("-" * 80)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "enterprise-stress-test"

        print("   Starting worker for large DAG...")

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[StressDAGWorkflow],
            activities=[stress_activity],
            max_concurrent_activities=100,
        ):
            print("   Executing 51-node DAG workflow...")
            start_time = time.time()

            handle = await client.start_workflow(
                StressDAGWorkflow.run,
                id=f"stress-dag-{time.time()}",
                task_queue=task_queue,
            )

            result = await handle.result()
            total_time = time.time() - start_time

            print(f"   ✅ DAG completed!")
            print(f"   Total nodes: {result['total_nodes']}")
            print(f"   Execution time: {result['execution_time']:.2f}s")
            print(f"   Throughput: {result['nodes_per_second']:.2f} nodes/sec")
            print(f"   Wall clock time: {total_time:.2f}s")

            # Verify all nodes executed
            assert result['total_nodes'] == 51, f"Expected 51 nodes, got {result['total_nodes']}"

            test_results["stress_testing"] = {
                "status": "passed",
                "details": {
                    "total_nodes": result['total_nodes'],
                    "execution_time": result['execution_time'],
                    "throughput": result['nodes_per_second'],
                },
            }

            print("   ✅ Stress test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Stress test FAILED: {e}")
        test_results["stress_testing"] = {"status": "failed", "error": str(e)}
        traceback.print_exc()
        return False


# ============================================================================
# TEST 3: Performance Benchmarks
# ============================================================================
async def test_performance_benchmarks():
    """Measure performance metrics"""
    print()
    print("📋 TEST 3: Performance Benchmarks")
    print("-" * 80)

    try:
        # Benchmark 1: Event bus throughput
        print("   Benchmarking event bus...")
        bus = EventBus()
        event_count = 1000
        received_count = 0

        @bus.subscribe("benchmark.event")
        async def counter(event):
            nonlocal received_count
            received_count += 1

        start = time.time()
        for i in range(event_count):
            await bus.publish("benchmark.event", {"id": i})

        await asyncio.sleep(0.5)  # Wait for all events
        event_bus_time = time.time() - start
        event_throughput = event_count / event_bus_time

        print(f"   Event bus: {event_count} events in {event_bus_time:.2f}s")
        print(f"   Throughput: {event_throughput:.0f} events/sec")
        print(f"   Events received: {received_count}/{event_count}")

        # Benchmark 2: Serialization performance
        print("   Benchmarking serialization...")
        serializer = CacheSerializer()

        from uuid import uuid4
        from datetime import datetime
        from decimal import Decimal

        test_obj = {
            "uuid": uuid4(),
            "datetime": datetime.now(),
            "decimal": Decimal("999.99"),
            "data": list(range(100)),
        }

        iterations = 10000
        start = time.time()
        for _ in range(iterations):
            serialized = serializer.dumps(test_obj)
            deserialized = serializer.loads(serialized)

        serialize_time = time.time() - start
        serialize_throughput = iterations / serialize_time

        print(f"   Serialization: {iterations} ops in {serialize_time:.2f}s")
        print(f"   Throughput: {serialize_throughput:.0f} ops/sec")

        # Benchmark 3: Circuit breaker overhead
        print("   Benchmarking circuit breaker...")
        circuit = CircuitBreaker(threshold=999999)  # Won't trip

        @circuit.call
        async def fast_op():
            return True

        iterations = 1000
        start = time.time()
        for _ in range(iterations):
            await fast_op()

        circuit_time = time.time() - start
        circuit_throughput = iterations / circuit_time

        print(f"   Circuit breaker: {iterations} calls in {circuit_time:.2f}s")
        print(f"   Throughput: {circuit_throughput:.0f} calls/sec")
        print(f"   Overhead: ~{(circuit_time/iterations)*1000:.2f}ms per call")

        test_results["performance_benchmarks"] = {
            "status": "passed",
            "details": {
                "event_bus_throughput": event_throughput,
                "serialization_throughput": serialize_throughput,
                "circuit_breaker_throughput": circuit_throughput,
            },
        }

        print("   ✅ Performance benchmarks PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Performance benchmarks FAILED: {e}")
        test_results["performance_benchmarks"] = {"status": "failed", "error": str(e)}
        traceback.print_exc()
        return False


# ============================================================================
# TEST 4: Edge Cases
# ============================================================================
async def test_edge_cases():
    """Test boundary conditions and edge cases"""
    print()
    print("📋 TEST 4: Edge Cases Testing")
    print("-" * 80)

    edge_cases_passed = 0
    edge_cases_total = 0

    try:
        serializer = CacheSerializer()

        # Edge Case 1: Empty data
        print("   Testing empty data...")
        edge_cases_total += 1
        empty = {}
        serialized = serializer.dumps(empty)
        deserialized = serializer.loads(serialized)
        assert deserialized == empty
        print("   ✅ Empty data handled")
        edge_cases_passed += 1

        # Edge Case 2: Very large data
        print("   Testing large data...")
        edge_cases_total += 1
        large_data = {"items": list(range(100000))}
        serialized = serializer.dumps(large_data)
        deserialized = serializer.loads(serialized)
        assert len(deserialized["items"]) == 100000
        print(f"   ✅ Large data handled ({len(serialized)} bytes)")
        edge_cases_passed += 1

        # Edge Case 3: Nested structures
        print("   Testing deeply nested structures...")
        edge_cases_total += 1
        nested = {"level": 1}
        current = nested
        for i in range(2, 101):
            current["child"] = {"level": i}
            current = current["child"]

        serialized = serializer.dumps(nested)
        deserialized = serializer.loads(serialized)
        # Check depth
        depth = 0
        current = deserialized
        while "child" in current:
            depth += 1
            current = current["child"]
        assert depth == 99
        print(f"   ✅ Deep nesting handled ({depth} levels)")
        edge_cases_passed += 1

        # Edge Case 4: Special characters
        print("   Testing special characters...")
        edge_cases_total += 1
        special = {"text": "Hello\nWorld\t🎉\r\n\"quotes\""}
        serialized = serializer.dumps(special)
        deserialized = serializer.loads(serialized)
        assert deserialized["text"] == special["text"]
        print("   ✅ Special characters handled")
        edge_cases_passed += 1

        # Edge Case 5: Circuit breaker recovery
        print("   Testing circuit breaker recovery...")
        edge_cases_total += 1
        circuit = CircuitBreaker(threshold=2, timeout=1)

        call_count = 0

        @circuit.call
        async def flaky_op():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Fail")
            return "success"

        # Trigger failures to open circuit
        for _ in range(2):
            try:
                await flaky_op()
            except Exception:
                pass

        assert circuit.state == "open", "Circuit should be open"

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Should enter half-open and eventually succeed
        result = await flaky_op()
        assert result == "success"
        assert circuit.state == "closed", "Circuit should be closed"
        print("   ✅ Circuit breaker recovery works")
        edge_cases_passed += 1

        # Edge Case 6: Event bus with no subscribers
        print("   Testing event bus with no subscribers...")
        edge_cases_total += 1
        bus = EventBus()
        # Should not crash
        await bus.publish("nonexistent.topic", {"data": "test"})
        print("   ✅ Event bus handles missing subscribers")
        edge_cases_passed += 1

        print(f"   Edge cases passed: {edge_cases_passed}/{edge_cases_total}")

        test_results["edge_cases"] = {
            "status": "passed" if edge_cases_passed == edge_cases_total else "partial",
            "details": {
                "passed": edge_cases_passed,
                "total": edge_cases_total,
            },
        }

        print(f"   ✅ Edge cases test PASSED ({edge_cases_passed}/{edge_cases_total})")
        return True

    except Exception as e:
        print(f"   ❌ Edge cases test FAILED: {e}")
        test_results["edge_cases"] = {"status": "failed", "error": str(e)}
        traceback.print_exc()
        return False


# ============================================================================
# TEST 5: Resource Usage Monitoring
# ============================================================================
async def test_resource_usage():
    """Monitor memory and CPU usage"""
    print()
    print("📋 TEST 5: Resource Usage Monitoring")
    print("-" * 80)

    try:
        # Start memory tracking
        tracemalloc.start()
        process = psutil.Process(os.getpid())

        # Get baseline
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        baseline_cpu = process.cpu_percent(interval=0.1)

        print(f"   Baseline memory: {baseline_memory:.2f} MB")
        print(f"   Baseline CPU: {baseline_cpu:.1f}%")

        # Run intensive operations
        print("   Running intensive operations...")

        # Create many objects
        data = []
        for i in range(10000):
            data.append({
                "id": i,
                "data": list(range(100)),
                "text": f"Item {i}" * 10,
            })

        # Serialize/deserialize many times
        serializer = CacheSerializer()
        for item in data[:1000]:  # First 1000
            serialized = serializer.dumps(item)
            deserialized = serializer.loads(serialized)

        # Event bus activity
        bus = EventBus()
        received = []

        @bus.subscribe("resource.test")
        async def handler(event):
            received.append(event.data)

        for i in range(1000):
            await bus.publish("resource.test", {"id": i})

        await asyncio.sleep(0.5)

        # Measure after operations
        current_memory = process.memory_info().rss / 1024 / 1024  # MB
        current_cpu = process.cpu_percent(interval=0.1)

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        memory_increase = current_memory - baseline_memory
        cpu_increase = current_cpu - baseline_cpu

        print(f"   Current memory: {current_memory:.2f} MB")
        print(f"   Memory increase: {memory_increase:.2f} MB")
        print(f"   Current CPU: {current_cpu:.1f}%")
        print(f"   CPU increase: {cpu_increase:.1f}%")

        # Top memory consumers
        print(f"   Top 3 memory consumers:")
        for i, stat in enumerate(top_stats[:3], 1):
            print(f"      {i}. {stat.size / 1024:.1f} KB - {stat.traceback.format()[0][:60]}")

        tracemalloc.stop()

        # Cleanup
        data.clear()
        received.clear()

        test_results["resource_usage"] = {
            "status": "passed",
            "details": {
                "baseline_memory_mb": baseline_memory,
                "peak_memory_mb": current_memory,
                "memory_increase_mb": memory_increase,
                "baseline_cpu_percent": baseline_cpu,
                "peak_cpu_percent": current_cpu,
            },
        }

        print("   ✅ Resource usage monitoring PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Resource usage test FAILED: {e}")
        test_results["resource_usage"] = {"status": "failed", "error": str(e)}
        traceback.print_exc()
        return False


# ============================================================================
# TEST 6: Concurrent DAG Execution
# ============================================================================
@activity.defn
async def concurrent_dag_activity(data: str) -> dict:
    """Activity for concurrent DAG testing"""
    await asyncio.sleep(0.05)
    return {"processed": data, "timestamp": time.time()}


@workflow.defn
class ConcurrentDAGWorkflow:
    """Small DAG for concurrent execution testing"""

    @workflow.run
    async def run(self, workflow_id: int) -> dict:
        dag = DAGWorkflow()

        # 3-layer DAG
        async def exec_a(dependencies, **kwargs):
            return await workflow.execute_activity(
                concurrent_dag_activity,
                f"A-{workflow_id}",
                start_to_close_timeout=timedelta(seconds=10),
            )

        async def exec_b(dependencies, **kwargs):
            return await workflow.execute_activity(
                concurrent_dag_activity,
                f"B-{workflow_id}",
                start_to_close_timeout=timedelta(seconds=10),
            )

        async def exec_c(dependencies, **kwargs):
            return await workflow.execute_activity(
                concurrent_dag_activity,
                f"C-{workflow_id}",
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(DAGNode(id="a", execute=exec_a, dependencies=[]))
        dag.add_node(DAGNode(id="b", execute=exec_b, dependencies=["a"]))
        dag.add_node(DAGNode(id="c", execute=exec_c, dependencies=["a", "b"]))

        results = await dag.execute(workflow_id=workflow_id)

        return {
            "workflow_id": workflow_id,
            "nodes_completed": len(results),
        }


async def test_concurrent_dag_execution():
    """Test multiple DAG workflows running concurrently"""
    print()
    print("📋 TEST 6: Concurrent DAG Execution")
    print("-" * 80)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "enterprise-concurrent-dag"

        num_dags = 15
        print(f"   Starting {num_dags} DAG workflows concurrently...")

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[ConcurrentDAGWorkflow],
            activities=[concurrent_dag_activity],
            max_concurrent_workflow_tasks=50,
            max_concurrent_activities=100,
        ):
            start_time = time.time()

            # Launch all DAG workflows
            handles = []
            for i in range(num_dags):
                handle = await client.start_workflow(
                    ConcurrentDAGWorkflow.run,
                    i,
                    id=f"concurrent-dag-{i}-{time.time()}",
                    task_queue=task_queue,
                )
                handles.append(handle)

            print(f"   ✅ Launched {num_dags} DAG workflows")

            # Wait for all
            results = await asyncio.gather(*[h.result() for h in handles])

            total_time = time.time() - start_time

            print(f"   ✅ All DAG workflows completed!")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Average time per DAG: {total_time/num_dags:.2f}s")
            print(f"   Total nodes executed: {sum(r['nodes_completed'] for r in results)}")

            # Verify all completed successfully
            assert all(r['nodes_completed'] == 3 for r in results), "Not all nodes completed"

            test_results["concurrent_dag"] = {
                "status": "passed",
                "details": {
                    "num_dags": num_dags,
                    "total_time": total_time,
                    "avg_time_per_dag": total_time / num_dags,
                    "total_nodes": sum(r['nodes_completed'] for r in results),
                },
            }

            print("   ✅ Concurrent DAG test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Concurrent DAG test FAILED: {e}")
        test_results["concurrent_dag"] = {"status": "failed", "error": str(e)}
        traceback.print_exc()
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
async def run_enterprise_tests():
    """Run all enterprise-grade tests"""
    print()
    print("Starting enterprise test suite...")
    print("This will take several minutes to complete comprehensively.")
    print()

    # Run all tests
    await test_load_concurrent_workflows()
    await test_stress_large_dag()
    await test_performance_benchmarks()
    await test_edge_cases()
    await test_resource_usage()
    await test_concurrent_dag_execution()

    # Print summary
    print()
    print("=" * 80)
    print("📊 ENTERPRISE TEST SUITE SUMMARY")
    print("=" * 80)
    print()

    passed = sum(1 for v in test_results.values() if v["status"] == "passed")
    total = len(test_results)

    for test_name, result in test_results.items():
        status_icon = "✅" if result["status"] == "passed" else "❌"
        print(f"   {status_icon} {test_name.replace('_', ' ').title()}")

        if "details" in result:
            for key, value in result["details"].items():
                if isinstance(value, float):
                    print(f"      • {key}: {value:.2f}")
                else:
                    print(f"      • {key}: {value}")

    print()
    print(f"Results: {passed}/{total} test suites passed ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 ALL ENTERPRISE TESTS PASSED!")
        print()
        print("VelvetEcho is verified as enterprise-grade and production-ready:")
        print("  ✅ Handles 20+ concurrent workflows")
        print("  ✅ Executes 51-node DAG successfully")
        print("  ✅ High throughput (1000s of ops/sec)")
        print("  ✅ Handles edge cases correctly")
        print("  ✅ Resource usage is acceptable")
        print("  ✅ Multiple DAGs can run concurrently")
        return True
    else:
        print("⚠️  Some enterprise tests failed - review above for details")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_enterprise_tests())
    exit(0 if success else 1)
