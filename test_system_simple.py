"""Simple VelvetEcho System Test - Core Components Only

Tests components that don't require Temporal workflows:
1. Infrastructure connectivity
2. Event bus
3. Circuit breaker
4. Cache serialization

Note: DAG workflow tests require separate execution due to Temporal sandbox restrictions.
See test_dag_fixed.py for DAG testing.
"""

import asyncio
import time
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from temporalio.client import Client


print("=" * 70)
print("🧪 VELVETECHO CORE SYSTEM TEST (Simple)")
print("=" * 70)
print()

# Test results tracker
results = {
    "temporal_connectivity": False,
    "redis_connectivity": False,
    "event_bus": False,
    "circuit_breaker": False,
    "cache_serialization": False,
}


# ============================================================================
# TEST 1: Infrastructure Connectivity
# ============================================================================
async def test_infrastructure():
    """Test that infrastructure services are reachable"""
    print("📋 TEST 1: Infrastructure Connectivity")
    print("-" * 70)

    try:
        # Test Temporal
        print("   Testing Temporal connection...")
        client = await Client.connect("localhost:7233")
        print("   ✅ Temporal: Connected")
        results["temporal_connectivity"] = True

        # Test Redis (cache)
        print("   Testing Redis connection...")
        try:
            from velvetecho.cache import RedisCache
            redis_cache = RedisCache(redis_url="redis://localhost:6379/0")
            await redis_cache.set("test_key", "test_value", ttl=10)
            value = await redis_cache.get("test_key")
            assert value == "test_value", f"Expected 'test_value', got {value}"
            print("   ✅ Redis: Connected and working")
            results["redis_connectivity"] = True
        except Exception as e:
            print(f"   ⚠️  Redis: Not available ({e})")

        print("   ✅ Infrastructure test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Infrastructure test FAILED: {e}")
        return False


# ============================================================================
# TEST 2: Event Bus
# ============================================================================
async def test_event_bus():
    """Test event bus pub/sub"""
    print()
    print("📋 TEST 2: Event Bus (Pub/Sub)")
    print("-" * 70)

    try:
        from velvetecho.communication import EventBus

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
        assert len(events_received) == 2, f"Expected 2 events, got {len(events_received)}"
        assert all(e[1].data["message"] == "Hello VelvetEcho!" for e in events_received)

        results["event_bus"] = True
        print("   ✅ Event bus test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Event bus test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 3: Circuit Breaker
# ============================================================================
async def test_circuit_breaker():
    """Test circuit breaker pattern"""
    print()
    print("📋 TEST 3: Circuit Breaker")
    print("-" * 70)

    try:
        from velvetecho.cache import CircuitBreaker
        from velvetecho.cache.circuit_breaker import CircuitBreakerOpenError

        failure_count = 0

        circuit = CircuitBreaker(threshold=3, timeout=2)

        @circuit.call
        async def failing_operation():
            """Operation that fails"""
            nonlocal failure_count
            failure_count += 1
            raise Exception("Simulated failure")

        print("   Testing circuit breaker with failing operation...")

        # First 3 failures should go through
        for i in range(3):
            try:
                await failing_operation()
            except Exception as e:
                if "Circuit breaker" not in str(e):
                    print(f"   Attempt {i+1}: Failed (expected)")

        print(f"   Circuit state after 3 failures: {circuit.state}")
        assert circuit.state == "open", f"Circuit should be open, but is {circuit.state}"

        # Next call should be rejected immediately
        try:
            await failing_operation()
            assert False, "Should have been rejected by circuit breaker"
        except CircuitBreakerOpenError as e:
            print(f"   Attempt 4: Rejected by circuit breaker (expected)")

        print(f"   Total actual failures: {failure_count} (should be 3, not 4)")
        assert failure_count == 3, f"4th call should have been rejected before calling function, got {failure_count}"

        results["circuit_breaker"] = True
        print("   ✅ Circuit breaker test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Circuit breaker test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 4: Cache Serialization
# ============================================================================
async def test_cache_serialization():
    """Test cache serialization with complex types"""
    print()
    print("📋 TEST 4: Cache Serialization")
    print("-" * 70)

    try:
        from velvetecho.cache.serialization import CacheSerializer

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

        # Validate
        assert str(deserialized["uuid"]) == str(test_data["uuid"]), "UUID mismatch"
        assert deserialized["datetime"] == test_data["datetime"].isoformat(), "Datetime mismatch"
        assert float(deserialized["decimal"]) == float(test_data["decimal"]), "Decimal mismatch"
        assert deserialized["nested"]["list"] == [1, 2, 3], "List mismatch"
        assert deserialized["nested"]["dict"]["key"] == "value", "Dict mismatch"

        results["cache_serialization"] = True
        print("   ✅ Cache serialization test PASSED")
        return True

    except Exception as e:
        print(f"   ❌ Cache serialization test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
async def run_all_tests():
    """Run all core system tests"""
    print()
    print("Starting core system test...")
    print()

    # Run all tests
    await test_infrastructure()
    await test_event_bus()
    await test_circuit_breaker()
    await test_cache_serialization()

    # Print summary
    print()
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print()

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, test_passed in results.items():
        status = "✅ PASS" if test_passed else "❌ FAIL"
        print(f"   {status}  {test_name.replace('_', ' ').title()}")

    print()
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 ALL CORE TESTS PASSED!")
        print()
        print("Verified capabilities:")
        print("  ✅ Temporal connectivity")
        print("  ✅ Redis connectivity")
        print("  ✅ Event bus pub/sub")
        print("  ✅ Circuit breaker fault tolerance")
        print("  ✅ Cache serialization (UUID, datetime, Decimal)")
        print()
        print("Note: DAG workflow pattern tested separately in test_dag_fixed.py")
        return True
    else:
        print("⚠️  Some tests failed - review above for details")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
