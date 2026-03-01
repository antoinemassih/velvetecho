"""Enterprise Component Tests (Non-Workflow)

Tests components that don't require Temporal workflows:
1. Performance Benchmarks
2. Edge Cases
3. Resource Usage
4. Event Bus Load Testing
5. Circuit Breaker Stress Testing
"""

import asyncio
import time
import tracemalloc
import psutil
import os
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from velvetecho.communication import EventBus
from velvetecho.cache import CircuitBreaker
from velvetecho.cache.circuit_breaker import CircuitBreakerOpenError
from velvetecho.cache.serialization import CacheSerializer


print("=" * 80)
print("🏢 VELVETECHO ENTERPRISE COMPONENT TESTS")
print("=" * 80)
print()

test_results = {}


# ============================================================================
# TEST 1: Performance Benchmarks
# ============================================================================
async def test_performance_benchmarks():
    """Measure performance metrics"""
    print("📋 TEST 1: Performance Benchmarks")
    print("-" * 80)

    try:
        # Benchmark 1: Event bus throughput
        print("   Benchmarking event bus...")
        bus = EventBus()
        event_count = 10000
        received_count = 0

        @bus.subscribe("benchmark.event")
        async def counter(event):
            nonlocal received_count
            received_count += 1

        start = time.time()
        for i in range(event_count):
            await bus.publish("benchmark.event", {"id": i})

        await asyncio.sleep(1.0)  # Wait for all events
        event_bus_time = time.time() - start
        event_throughput = event_count / event_bus_time

        print(f"   Event bus: {event_count} events in {event_bus_time:.2f}s")
        print(f"   Throughput: {event_throughput:.0f} events/sec")
        print(f"   Events received: {received_count}/{event_count}")

        # Benchmark 2: Serialization performance
        print("   Benchmarking serialization...")
        serializer = CacheSerializer()

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
        print(f"   Avg latency: {(serialize_time/iterations)*1000:.3f}ms")

        # Benchmark 3: Circuit breaker overhead
        print("   Benchmarking circuit breaker...")
        circuit = CircuitBreaker(threshold=999999)  # Won't trip

        @circuit.call
        async def fast_op():
            return True

        iterations = 10000
        start = time.time()
        for _ in range(iterations):
            await fast_op()

        circuit_time = time.time() - start
        circuit_throughput = iterations / circuit_time

        print(f"   Circuit breaker: {iterations} calls in {circuit_time:.2f}s")
        print(f"   Throughput: {circuit_throughput:.0f} calls/sec")
        print(f"   Overhead: {(circuit_time/iterations)*1000:.3f}ms per call")

        # Benchmark 4: Concurrent event bus
        print("   Benchmarking concurrent event publishing...")
        bus2 = EventBus()
        concurrent_count = 0

        @bus2.subscribe("concurrent.test")
        async def concurrent_handler(event):
            nonlocal concurrent_count
            concurrent_count += 1

        num_concurrent = 100
        events_per_task = 100

        start = time.time()
        tasks = []
        for i in range(num_concurrent):
            async def publish_batch(task_id):
                for j in range(events_per_task):
                    await bus2.publish("concurrent.test", {"task": task_id, "event": j})

            tasks.append(publish_batch(i))

        await asyncio.gather(*tasks)
        await asyncio.sleep(1.0)

        concurrent_time = time.time() - start
        total_events = num_concurrent * events_per_task
        concurrent_throughput = total_events / concurrent_time

        print(f"   Concurrent: {total_events} events from {num_concurrent} tasks")
        print(f"   Time: {concurrent_time:.2f}s")
        print(f"   Throughput: {concurrent_throughput:.0f} events/sec")
        print(f"   Received: {concurrent_count}/{total_events}")

        test_results["performance_benchmarks"] = {
            "status": "passed",
            "event_bus_throughput": event_throughput,
            "serialization_throughput": serialize_throughput,
            "circuit_breaker_throughput": circuit_throughput,
            "concurrent_event_throughput": concurrent_throughput,
            "event_delivery_rate": (received_count / event_count) * 100,
            "concurrent_delivery_rate": (concurrent_count / total_events) * 100,
        }

        print("   ✅ Performance benchmarks PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Performance benchmarks FAILED: {e}")
        test_results["performance_benchmarks"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 2: Edge Cases
# ============================================================================
async def test_edge_cases():
    """Test boundary conditions and edge cases"""
    print()
    print("📋 TEST 2: Edge Cases Testing")
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
        print("   Testing large data (100K items)...")
        edge_cases_total += 1
        large_data = {"items": list(range(100000))}
        start = time.time()
        serialized = serializer.dumps(large_data)
        serialize_time = time.time() - start
        start = time.time()
        deserialized = serializer.loads(serialized)
        deserialize_time = time.time() - start
        assert len(deserialized["items"]) == 100000
        print(f"   ✅ Large data handled")
        print(f"      Size: {len(serialized):,} bytes")
        print(f"      Serialize: {serialize_time:.3f}s")
        print(f"      Deserialize: {deserialize_time:.3f}s")
        edge_cases_passed += 1

        # Edge Case 3: Deeply nested structures
        print("   Testing deeply nested structures (100 levels)...")
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

        # Edge Case 4: Special characters and Unicode
        print("   Testing special characters and Unicode...")
        edge_cases_total += 1
        special = {
            "newlines": "Hello\nWorld\t\r\n",
            "quotes": "\"double\" 'single'",
            "unicode": "🎉🚀✅❌⚠️",
            "mixed": "Hello 世界 Мир 🌍",
        }
        serialized = serializer.dumps(special)
        deserialized = serializer.loads(serialized)
        assert deserialized == special
        print("   ✅ Special characters and Unicode handled")
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
                raise Exception("Simulated failure")
            return "success"

        # Trigger failures to open circuit
        for _ in range(2):
            try:
                await flaky_op()
            except Exception:
                pass

        assert circuit.state == "open", f"Circuit should be open, is {circuit.state}"

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Should enter half-open and succeed
        result = await flaky_op()
        assert result == "success"
        assert circuit.state == "closed", f"Circuit should be closed, is {circuit.state}"
        print("   ✅ Circuit breaker recovery works")
        edge_cases_passed += 1

        # Edge Case 6: Event bus with no subscribers
        print("   Testing event bus with no subscribers...")
        edge_cases_total += 1
        bus = EventBus()
        await bus.publish("nonexistent.topic", {"data": "test"})
        print("   ✅ Event bus handles missing subscribers")
        edge_cases_passed += 1

        # Edge Case 7: Multiple circuit breakers
        print("   Testing multiple independent circuit breakers...")
        edge_cases_total += 1
        circuit1 = CircuitBreaker(threshold=2)
        circuit2 = CircuitBreaker(threshold=3)

        @circuit1.call
        async def op1():
            raise Exception("Fail 1")

        @circuit2.call
        async def op2():
            raise Exception("Fail 2")

        # Trip circuit1
        for _ in range(2):
            try:
                await op1()
            except Exception:
                pass

        # Circuit1 should be open, circuit2 should be closed
        assert circuit1.state == "open"
        assert circuit2.state == "closed"
        print("   ✅ Multiple circuit breakers work independently")
        edge_cases_passed += 1

        # Edge Case 8: Null/None handling
        print("   Testing null/None handling...")
        edge_cases_total += 1
        null_data = {"value": None, "items": [None, 1, None, 2]}
        serialized = serializer.dumps(null_data)
        deserialized = serializer.loads(serialized)
        assert deserialized == null_data
        print("   ✅ Null/None values handled correctly")
        edge_cases_passed += 1

        print(f"   Edge cases passed: {edge_cases_passed}/{edge_cases_total}")

        test_results["edge_cases"] = {
            "status": "passed" if edge_cases_passed == edge_cases_total else "partial",
            "passed": edge_cases_passed,
            "total": edge_cases_total,
        }

        print(f"   ✅ Edge cases test PASSED ({edge_cases_passed}/{edge_cases_total})")
        return True

    except Exception as e:
        print(f"   ❌ Edge cases test FAILED: {e}")
        test_results["edge_cases"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 3: Resource Usage
# ============================================================================
async def test_resource_usage():
    """Monitor memory and CPU usage under load"""
    print()
    print("📋 TEST 3: Resource Usage Under Load")
    print("-" * 80)

    try:
        tracemalloc.start()
        process = psutil.Process(os.getpid())

        baseline_memory = process.memory_info().rss / 1024 / 1024
        baseline_cpu = process.cpu_percent(interval=0.1)

        print(f"   Baseline memory: {baseline_memory:.2f} MB")
        print(f"   Baseline CPU: {baseline_cpu:.1f}%")

        # Load test - create many objects and process them
        print("   Running intensive load...")

        # Phase 1: Create large dataset
        data = []
        for i in range(50000):
            data.append({
                "id": i,
                "data": list(range(50)),
                "text": f"Item {i}" * 5,
            })

        memory_after_data = process.memory_info().rss / 1024 / 1024
        print(f"   After creating 50K items: {memory_after_data:.2f} MB (+{memory_after_data-baseline_memory:.2f} MB)")

        # Phase 2: Serialize/deserialize stress
        serializer = CacheSerializer()
        for item in data[:5000]:
            serialized = serializer.dumps(item)
            deserialized = serializer.loads(serialized)

        memory_after_serialize = process.memory_info().rss / 1024 / 1024
        print(f"   After 5K serialize ops: {memory_after_serialize:.2f} MB (+{memory_after_serialize-baseline_memory:.2f} MB)")

        # Phase 3: Event bus stress
        bus = EventBus()
        received = []

        @bus.subscribe("resource.test")
        async def handler(event):
            received.append(event.data)

        for i in range(5000):
            await bus.publish("resource.test", {"id": i})

        await asyncio.sleep(1.0)

        memory_after_events = process.memory_info().rss / 1024 / 1024
        print(f"   After 5K events: {memory_after_events:.2f} MB (+{memory_after_events-baseline_memory:.2f} MB)")

        # Phase 4: Circuit breaker stress
        circuit = CircuitBreaker(threshold=10000)

        @circuit.call
        async def test_op():
            return True

        for _ in range(5000):
            await test_op()

        memory_after_circuit = process.memory_info().rss / 1024 / 1024
        current_cpu = process.cpu_percent(interval=0.1)

        print(f"   After 5K circuit calls: {memory_after_circuit:.2f} MB (+{memory_after_circuit-baseline_memory:.2f} MB)")
        print(f"   Current CPU: {current_cpu:.1f}%")

        # Get memory snapshot
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        print(f"   Top 3 memory consumers:")
        for i, stat in enumerate(top_stats[:3], 1):
            print(f"      {i}. {stat.size / 1024 / 1024:.2f} MB - {stat.count} blocks")

        tracemalloc.stop()

        # Cleanup
        data.clear()
        received.clear()

        # Measure after cleanup
        import gc
        gc.collect()
        await asyncio.sleep(0.5)

        final_memory = process.memory_info().rss / 1024 / 1024
        print(f"   After cleanup: {final_memory:.2f} MB")

        memory_leak = final_memory - baseline_memory
        print(f"   Potential leak: {memory_leak:.2f} MB ({(memory_leak/baseline_memory)*100:.1f}%)")

        test_results["resource_usage"] = {
            "status": "passed",
            "baseline_memory_mb": baseline_memory,
            "peak_memory_mb": memory_after_circuit,
            "final_memory_mb": final_memory,
            "memory_increase_mb": memory_after_circuit - baseline_memory,
            "potential_leak_mb": memory_leak,
            "baseline_cpu_percent": baseline_cpu,
            "peak_cpu_percent": current_cpu,
        }

        if memory_leak > baseline_memory * 0.5:  # More than 50% increase
            print(f"   ⚠️  Warning: Significant memory increase detected ({memory_leak:.2f} MB)")
        else:
            print(f"   ✅ Memory usage acceptable")

        print("   ✅ Resource usage test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Resource usage test FAILED: {e}")
        test_results["resource_usage"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 4: Circuit Breaker Stress Test
# ============================================================================
async def test_circuit_breaker_stress():
    """Stress test circuit breaker with rapid failures"""
    print()
    print("📋 TEST 4: Circuit Breaker Stress Test")
    print("-" * 80)

    try:
        # Test rapid sequential failures
        print("   Testing rapid sequential failures...")
        circuit = CircuitBreaker(threshold=10, timeout=2)

        failure_count = 0

        @circuit.call
        async def failing_op():
            nonlocal failure_count
            failure_count += 1
            raise Exception("Fail")

        # Trigger many failures rapidly
        for i in range(20):
            try:
                await failing_op()
            except CircuitBreakerOpenError:
                # Circuit opened, as expected
                break
            except Exception:
                # Normal failure
                pass

        print(f"   Circuit opened after {failure_count} failures")
        assert circuit.state == "open"
        assert failure_count == 10  # Should stop at threshold

        # Test concurrent failures
        print("   Testing concurrent circuit breaker calls...")
        circuit2 = CircuitBreaker(threshold=5, timeout=1)

        concurrent_failures = 0

        @circuit2.call
        async def concurrent_fail():
            nonlocal concurrent_failures
            concurrent_failures += 1
            await asyncio.sleep(0.01)
            raise Exception("Concurrent fail")

        # Run concurrently
        tasks = [concurrent_fail() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        print(f"   Concurrent failures: {concurrent_failures}")
        print(f"   Errors caught: {len(errors)}")
        assert circuit2.state == "open"

        # Test recovery under load
        print("   Testing recovery under load...")
        circuit3 = CircuitBreaker(threshold=3, timeout=0.5)

        success_count = 0
        recovery_failures = 0

        @circuit3.call
        async def recovering_op():
            nonlocal success_count, recovery_failures
            if circuit3.failure_count < 3:
                recovery_failures += 1
                raise Exception("Initial failures")
            success_count += 1
            return "success"

        # Initial failures
        for _ in range(3):
            try:
                await recovering_op()
            except Exception:
                pass

        assert circuit3.state == "open"

        # Wait for recovery
        await asyncio.sleep(0.6)

        # Should recover
        result = await recovering_op()
        assert result == "success"
        assert circuit3.state == "closed"

        print(f"   Recovery successful after {recovery_failures} failures")

        test_results["circuit_breaker_stress"] = {
            "status": "passed",
            "sequential_failures_before_open": failure_count,
            "concurrent_failures": concurrent_failures,
            "recovery_verified": True,
        }

        print("   ✅ Circuit breaker stress test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Circuit breaker stress test FAILED: {e}")
        test_results["circuit_breaker_stress"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN RUNNER
# ============================================================================
async def run_component_tests():
    """Run all component tests"""
    print()
    print("Starting enterprise component tests...")
    print()

    await test_performance_benchmarks()
    await test_edge_cases()
    await test_resource_usage()
    await test_circuit_breaker_stress()

    # Summary
    print()
    print("=" * 80)
    print("📊 COMPONENT TEST SUMMARY")
    print("=" * 80)
    print()

    passed = sum(1 for v in test_results.values() if v.get("status") == "passed")
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✅" if result.get("status") == "passed" else "❌"
        print(f"   {status} {test_name.replace('_', ' ').title()}")

        if isinstance(result, dict):
            for key, value in result.items():
                if key != "status" and key != "error":
                    if isinstance(value, float):
                        print(f"      • {key}: {value:.2f}")
                    else:
                        print(f"      • {key}: {value}")

    print()
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 ALL COMPONENT TESTS PASSED!")
        return True
    else:
        print("⚠️  Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_component_tests())
    exit(0 if success else 1)
