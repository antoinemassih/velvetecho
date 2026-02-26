"""Tests for circuit breaker"""

import pytest
import asyncio
from velvetecho.cache.circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerOpenError


@pytest.mark.asyncio
async def test_circuit_breaker_closed_state():
    """Test circuit breaker in closed state"""
    breaker = CircuitBreaker(threshold=3, timeout=1)

    @breaker.call
    async def test_func():
        return "success"

    result = await test_func()
    assert result == "success"
    assert breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Test circuit breaker opens after threshold failures"""
    breaker = CircuitBreaker(threshold=3, timeout=1)

    call_count = 0

    @breaker.call
    async def failing_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("Error")

    # First 3 failures
    for i in range(3):
        with pytest.raises(ValueError):
            await failing_func()

    assert call_count == 3
    assert breaker.state == CircuitBreakerState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_rejects_when_open():
    """Test circuit breaker rejects requests when open"""
    breaker = CircuitBreaker(threshold=2, timeout=1)

    @breaker.call
    async def failing_func():
        raise ValueError("Error")

    # Open the circuit
    for i in range(2):
        with pytest.raises(ValueError):
            await failing_func()

    assert breaker.state == CircuitBreakerState.OPEN

    # Next call should be rejected immediately
    with pytest.raises(CircuitBreakerOpenError):
        await failing_func()


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery():
    """Test circuit breaker transitions to half-open and recovers"""
    breaker = CircuitBreaker(threshold=2, timeout=1, half_open_max_calls=2)

    failure_count = 0

    @breaker.call
    async def test_func():
        nonlocal failure_count
        if failure_count < 2:
            failure_count += 1
            raise ValueError("Error")
        return "success"

    # Open the circuit
    for i in range(2):
        with pytest.raises(ValueError):
            await test_func()

    assert breaker.state == CircuitBreakerState.OPEN

    # Wait for timeout
    await asyncio.sleep(1.1)

    # Next call enters half-open
    result = await test_func()
    assert result == "success"
    assert breaker.state == CircuitBreakerState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_reopens():
    """Test circuit breaker reopens if half-open call fails"""
    breaker = CircuitBreaker(threshold=2, timeout=1)

    @breaker.call
    async def failing_func():
        raise ValueError("Error")

    # Open the circuit
    for i in range(2):
        with pytest.raises(ValueError):
            await failing_func()

    assert breaker.state == CircuitBreakerState.OPEN

    # Wait for timeout
    await asyncio.sleep(1.1)

    # Half-open call fails
    with pytest.raises(ValueError):
        await failing_func()

    # Should be back to open
    assert breaker.state == CircuitBreakerState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_reset():
    """Test manual circuit breaker reset"""
    breaker = CircuitBreaker(threshold=2, timeout=1)

    @breaker.call
    async def failing_func():
        raise ValueError("Error")

    # Open the circuit
    for i in range(2):
        with pytest.raises(ValueError):
            await failing_func()

    assert breaker.state == CircuitBreakerState.OPEN

    # Manual reset
    breaker.reset()

    assert breaker.state == CircuitBreakerState.CLOSED
    assert breaker.failure_count == 0
