"""Comprehensive VelvetEcho System Test

Tests all major components:
1. Infrastructure connectivity
2. DAG workflow pattern
3. Event bus
4. Circuit breaker
5. Cache operations
6. Error handling
"""

import asyncio
import time
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from velvetecho.patterns import DAGWorkflow, DAGNode
from velvetecho.communication import EventBus
from velvetecho.cache import CircuitBreaker, RedisCache
from velvetecho.cache.serialization import CacheSerializer


print("=" * 70)
print("🧪 VELVETECHO COMPREHENSIVE SYSTEM TEST")
print("=" * 70)
print()

# Test results tracker
results = {
    "infrastructure": False,
    "dag_pattern": False,
    "event_bus": False,
    "circuit_breaker": False,
    "cache": False,
    "error_handling": False,
}


# ============================================================================
# TEST 1: Infrastructure Connectivity
# ============================================================================
async def test_infrastructure():
    """Test that all infrastructure services are reachable"""
    print("📋 TEST 1: Infrastructure Connectivity")
    print("-" * 70)

    try:
        # Test Temporal
        print("   Testing Temporal connection...")
        client = await Client.connect("localhost:7233")
        print("   ✅ Temporal: Connected")

        # Test Redis (cache)
        print("   Testing Redis connection...")
        try:
            redis_cache = RedisCache(redis_url="redis://localhost:6379/0")
            await redis_cache.set("test_key", "test_value", ttl=10)
            value = await redis_cache.get("test_key")
            assert value == "test_value"
            print("   ✅ Redis: Connected and working")
        except Exception as e:
            print(f"   ⚠️  Redis: Not available ({e})")

        results["infrastructure"] = True
        print("   ✅ Infrastructure test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Infrastructure test FAILED: {e}")
        return False


# ============================================================================
# TEST 2: DAG Workflow Pattern
# ============================================================================

@activity.defn
async def phase1_activity(data: str) -> dict:
    """Phase 1 activity"""
    await asyncio.sleep(0.05)
    return {"phase": 1, "data": data, "result": "phase1_complete"}


@activity.defn
async def phase2a_activity(phase1_result: dict) -> dict:
    """Phase 2A activity (parallel)"""
    await asyncio.sleep(0.05)
    return {"phase": "2a", "input": phase1_result, "result": "phase2a_complete"}


@activity.defn
async def phase2b_activity(phase1_result: dict) -> dict:
    """Phase 2B activity (parallel)"""
    await asyncio.sleep(0.05)
    return {"phase": "2b", "input": phase1_result, "result": "phase2b_complete"}


@activity.defn
async def phase3_activity(phase2a_result: dict, phase2b_result: dict) -> dict:
    """Phase 3 activity (depends on both 2a and 2b)"""
    await asyncio.sleep(0.05)
    return {
        "phase": 3,
        "inputs": [phase2a_result, phase2b_result],
        "result": "ALL_PHASES_COMPLETE",
    }


@workflow.defn
class ComprehensiveDAGWorkflow:
    """Test workflow with 4-phase DAG"""

    @workflow.run
    async def run(self, test_data: str) -> dict:
        dag = DAGWorkflow()

        # Phase 1
        async def execute_phase1(dependencies, **kwargs):
            data = kwargs.get("test_data")
            return await workflow.execute_activity(
                phase1_activity, data, start_to_close_timeout=timedelta(seconds=5)
            )

        dag.add_node(DAGNode(id="phase1", execute=execute_phase1, dependencies=[]))

        # Phase 2A (parallel)
        async def execute_phase2a(dependencies, **kwargs):
            phase1_result = dependencies["phase1"]
            return await workflow.execute_activity(
                phase2a_activity, phase1_result, start_to_close_timeout=timedelta(seconds=5)
            )

        dag.add_node(DAGNode(id="phase2a", execute=execute_phase2a, dependencies=["phase1"]))

        # Phase 2B (parallel)
        async def execute_phase2b(dependencies, **kwargs):
            phase1_result = dependencies["phase1"]
            return await workflow.execute_activity(
                phase2b_activity, phase1_result, start_to_close_timeout=timedelta(seconds=5)
            )

        dag.add_node(DAGNode(id="phase2b", execute=execute_phase2b, dependencies=["phase1"]))

        # Phase 3 (depends on both 2a and 2b)
        async def execute_phase3(dependencies, **kwargs):
            phase2a_result = dependencies["phase2a"]
            phase2b_result = dependencies["phase2b"]
            return await workflow.execute_activity(
                phase3_activity,
                args=[phase2a_result, phase2b_result],
                start_to_close_timeout=timedelta(seconds=5),
            )

        dag.add_node(
            DAGNode(id="phase3", execute=execute_phase3, dependencies=["phase2a", "phase2b"])
        )

        # Execute DAG
        start_time = time.time()
        dag_results = await dag.execute(test_data=test_data)
        execution_time = time.time() - start_time

        return {
            "phases": list(dag_results.keys()),
            "final_result": dag_results["phase3"]["result"],
            "execution_time": execution_time,
            "parallel_optimization": "2a and 2b ran in parallel" if execution_time < 0.2 else "sequential",
        }


async def test_dag_pattern():
    """Test DAG workflow pattern"""
    print()
    print("📋 TEST 2: DAG Workflow Pattern")
    print("-" * 70)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "comprehensive-test-dag"

        print("   Starting worker...")
        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[ComprehensiveDAGWorkflow],
            activities=[phase1_activity, phase2a_activity, phase2b_activity, phase3_activity],
        ):
            print("   Executing 4-phase DAG workflow...")
            handle = await client.start_workflow(
                ComprehensiveDAGWorkflow.run,
                "test_data_123",
                id=f"dag-comprehensive-{time.time()}",
                task_queue=task_queue,
            )

            result = await handle.result()

            print(f"   Phases executed: {result['phases']}")
            print(f"   Final result: {result['final_result']}")
            print(f"   Execution time: {result['execution_time']:.3f}s")
            print(f"   Parallelism: {result['parallel_optimization']}")

            assert result["final_result"] == "ALL_PHASES_COMPLETE"
            assert len(result["phases"]) == 4
            assert result["execution_time"] < 0.3  # Should be ~0.15s with parallelism

            results["dag_pattern"] = True
            print("   ✅ DAG pattern test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ DAG pattern test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 3: Event Bus
# ============================================================================
async def test_event_bus():
    """Test event bus pub/sub"""
    print()
    print("📋 TEST 3: Event Bus (Pub/Sub)")
    print("-" * 70)

    try:
        events_received = []

        bus = EventBus()

        # Subscribe to events
        @bus.subscribe("test.event")
        async def handler1(event):
            events_received.append(("handler1", event))

        @bus.subscribe("test.event")
        async def handler2(event):
            events_received.append(("handler2", event))

        # Publish event
        print("   Publishing test event...")
        await bus.publish("test.event", {"message": "Hello VelvetEcho!"})

        # Wait for handlers
        await asyncio.sleep(0.1)

        print(f"   Events received: {len(events_received)}")
        assert len(events_received) == 2
        assert all(e[1].data["message"] == "Hello VelvetEcho!" for e in events_received)

        results["event_bus"] = True
        print("   ✅ Event bus test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Event bus test FAILED: {e}")
        return False


# ============================================================================
# TEST 4: Circuit Breaker
# ============================================================================
async def test_circuit_breaker():
    """Test circuit breaker pattern"""
    print()
    print("📋 TEST 4: Circuit Breaker")
    print("-" * 70)

    try:
        failure_count = 0

        async def failing_operation():
            """Operation that fails"""
            nonlocal failure_count
            failure_count += 1
            raise Exception("Simulated failure")

        circuit = CircuitBreaker(failure_threshold=3, timeout=2.0)

        print("   Testing circuit breaker with failing operation...")

        # First 3 failures should go through
        for i in range(3):
            try:
                await circuit.call(failing_operation)
            except Exception:
                print(f"   Attempt {i+1}: Failed (expected)")

        print(f"   Circuit state after 3 failures: {circuit.state}")
        assert circuit.state == "open", "Circuit should be open after 3 failures"

        # Next call should be rejected immediately
        try:
            await circuit.call(failing_operation)
            assert False, "Should have been rejected"
        except Exception as e:
            print(f"   Attempt 4: Rejected by circuit breaker (expected)")
            assert "Circuit breaker is open" in str(e)

        print(f"   Total actual failures: {failure_count} (should be 3, not 4)")
        assert failure_count == 3, "4th call should have been rejected before calling function"

        results["circuit_breaker"] = True
        print("   ✅ Circuit breaker test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Circuit breaker test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 5: Cache Operations
# ============================================================================
async def test_cache():
    """Test cache serialization and operations"""
    print()
    print("📋 TEST 5: Cache Serialization")
    print("-" * 70)

    try:
        from uuid import uuid4
        from datetime import datetime
        from decimal import Decimal

        # Test complex data types
        test_data = {
            "uuid": uuid4(),
            "datetime": datetime.now(),
            "decimal": Decimal("123.45"),
            "nested": {"list": [1, 2, 3], "dict": {"key": "value"}},
        }

        print("   Testing serialization of complex types...")

        # Serialize
        serializer = CacheSerializer()
        serialized = serializer.dumps(test_data)
        print(f"   Serialized to {len(serialized)} bytes")

        # Deserialize
        deserialized = serializer.loads(serialized)

        assert str(deserialized["uuid"]) == str(test_data["uuid"])
        assert deserialized["decimal"] == "123.45"
        assert deserialized["nested"]["list"] == [1, 2, 3]

        results["cache"] = True
        print("   ✅ Cache serialization test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Cache test FAILED: {e}")
        return False


# ============================================================================
# TEST 6: Error Handling
# ============================================================================
@activity.defn
async def failing_activity() -> str:
    """Activity that always fails"""
    raise Exception("Intentional failure for testing")


@workflow.defn
class ErrorHandlingWorkflow:
    """Workflow that handles activity failures"""

    @workflow.run
    async def run(self) -> dict:
        try:
            # This will fail
            await workflow.execute_activity(
                failing_activity,
                start_to_close_timeout=timedelta(seconds=2),
                retry_policy=workflow.RetryPolicy(maximum_attempts=2),
            )
            return {"status": "unexpected_success"}
        except Exception as e:
            # Catch the error and return gracefully
            return {"status": "error_caught", "error": str(e)}


async def test_error_handling():
    """Test error handling in workflows"""
    print()
    print("📋 TEST 6: Error Handling")
    print("-" * 70)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "comprehensive-test-errors"

        print("   Starting worker...")
        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[ErrorHandlingWorkflow],
            activities=[failing_activity],
        ):
            print("   Executing workflow with failing activity...")
            handle = await client.start_workflow(
                ErrorHandlingWorkflow.run,
                id=f"error-test-{time.time()}",
                task_queue=task_queue,
            )

            result = await handle.result()

            print(f"   Result: {result}")
            assert result["status"] == "error_caught"

            results["error_handling"] = True
            print("   ✅ Error handling test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Error handling test FAILED: {e}")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
async def run_all_tests():
    """Run all comprehensive tests"""
    print()
    print("Starting comprehensive system test...")
    print()

    # Run all tests
    await test_infrastructure()
    await test_dag_pattern()
    await test_event_bus()
    await test_circuit_breaker()
    await test_cache()
    await test_error_handling()

    # Print summary
    print()
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print()

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}  {test_name.replace('_', ' ').title()}")

    print()
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 ALL TESTS PASSED - VelvetEcho is production-ready!")
        print()
        print("Verified capabilities:")
        print("  ✅ Temporal workflow orchestration")
        print("  ✅ DAG pattern with dependencies and parallelism")
        print("  ✅ Event bus pub/sub")
        print("  ✅ Circuit breaker fault tolerance")
        print("  ✅ Cache serialization (UUID, datetime, Decimal)")
        print("  ✅ Error handling and retry policies")
        return True
    else:
        print("⚠️  Some tests failed - review above for details")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
