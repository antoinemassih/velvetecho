"""Tests for event bus"""

import pytest
import asyncio
from velvetecho.communication.events import EventBus, Event


@pytest.mark.asyncio
async def test_event_bus_subscribe_and_publish():
    """Test basic subscribe and publish"""
    bus = EventBus()
    received_events = []

    @bus.subscribe("test.event")
    async def handler(event: Event):
        received_events.append(event)

    # Publish event
    await bus.publish("test.event", {"message": "Hello"})

    # Wait for processing
    await asyncio.sleep(0.1)

    assert len(received_events) == 1
    assert received_events[0].topic == "test.event"
    assert received_events[0].data == {"message": "Hello"}


@pytest.mark.asyncio
async def test_event_bus_multiple_handlers():
    """Test multiple handlers for same topic"""
    bus = EventBus()
    handler1_called = []
    handler2_called = []

    @bus.subscribe("test.event")
    async def handler1(event: Event):
        handler1_called.append(True)

    @bus.subscribe("test.event")
    async def handler2(event: Event):
        handler2_called.append(True)

    await bus.publish("test.event", {"data": "test"})
    await asyncio.sleep(0.1)

    assert len(handler1_called) == 1
    assert len(handler2_called) == 1


@pytest.mark.asyncio
async def test_event_bus_unsubscribe():
    """Test unsubscribing a handler"""
    bus = EventBus()
    called_count = []

    async def handler(event: Event):
        called_count.append(True)

    # Subscribe
    bus.subscribe("test.event")(handler)

    # Publish
    await bus.publish("test.event", {})
    await asyncio.sleep(0.1)

    assert len(called_count) == 1

    # Unsubscribe
    bus.unsubscribe("test.event", handler)

    # Publish again
    await bus.publish("test.event", {})
    await asyncio.sleep(0.1)

    # Should still be 1 (handler not called again)
    assert len(called_count) == 1


@pytest.mark.asyncio
async def test_event_bus_handler_error():
    """Test that handler errors don't crash bus"""
    bus = EventBus()
    successful_handler_called = []

    @bus.subscribe("test.event")
    async def failing_handler(event: Event):
        raise ValueError("Handler error")

    @bus.subscribe("test.event")
    async def successful_handler(event: Event):
        successful_handler_called.append(True)

    # Publish event
    await bus.publish("test.event", {})
    await asyncio.sleep(0.1)

    # Successful handler should still be called
    assert len(successful_handler_called) == 1


@pytest.mark.asyncio
async def test_event_has_timestamp():
    """Test that events have timestamps"""
    bus = EventBus()
    received_events = []

    @bus.subscribe("test.event")
    async def handler(event: Event):
        received_events.append(event)

    await bus.publish("test.event", {})
    await asyncio.sleep(0.1)

    assert received_events[0].timestamp > 0


@pytest.mark.asyncio
async def test_event_with_metadata():
    """Test events with metadata"""
    bus = EventBus()
    received_events = []

    @bus.subscribe("test.event")
    async def handler(event: Event):
        received_events.append(event)

    await bus.publish("test.event", {"data": "test"}, metadata={"source": "test"})
    await asyncio.sleep(0.1)

    assert received_events[0].metadata == {"source": "test"}
