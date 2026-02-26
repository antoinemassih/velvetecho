"""Event bus for pub/sub communication"""

import asyncio
import time
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import structlog

from velvetecho.cache.redis import RedisCache
from velvetecho.cache.serialization import CacheSerializer

logger = structlog.get_logger(__name__)


@dataclass
class Event:
    """Event published to the bus"""

    topic: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    event_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """
    Event bus for pub/sub communication between services.

    Features:
    - Topic-based routing
    - Multiple subscribers per topic
    - Async event handlers
    - Redis-backed for persistence (optional)
    - In-memory fallback

    Example:
        bus = EventBus()
        await bus.connect()

        # Subscribe to events
        @bus.subscribe("user.created")
        async def on_user_created(event: Event):
            print(f"User created: {event.data}")

        # Publish event
        await bus.publish("user.created", {"id": "123", "name": "John"})

        # Start processing
        await bus.start()
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        use_redis: bool = False,
    ):
        self.use_redis = use_redis
        self.cache = RedisCache(redis_url) if use_redis else None
        self.serializer = CacheSerializer()

        # In-memory handlers
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)

        # Redis pubsub
        self._pubsub = None
        self._listening = False
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Connect to Redis (if enabled)"""
        if self.use_redis and self.cache:
            await self.cache.connect()

            # Create pubsub client
            self._pubsub = self.cache.client.pubsub()

            logger.info("Event bus connected to Redis")

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None

        if self.cache:
            await self.cache.disconnect()

        logger.info("Event bus disconnected")

    def subscribe(self, topic: str):
        """
        Decorator to subscribe a handler to a topic.

        Example:
            @bus.subscribe("user.created")
            async def on_user_created(event: Event):
                print(event.data)
        """

        def decorator(handler: Callable) -> Callable:
            self._handlers[topic].append(handler)
            logger.info("Registered event handler", topic=topic, handler=handler.__name__)
            return handler

        return decorator

    def unsubscribe(self, topic: str, handler: Callable) -> None:
        """Unsubscribe a handler from a topic"""
        if topic in self._handlers:
            self._handlers[topic] = [h for h in self._handlers[topic] if h != handler]
            logger.info("Unregistered event handler", topic=topic, handler=handler.__name__)

    async def publish(
        self,
        topic: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish an event to a topic.

        Args:
            topic: Event topic (e.g., "user.created", "workflow.completed")
            data: Event payload
            metadata: Optional metadata
        """
        event = Event(
            topic=topic,
            data=data,
            metadata=metadata or {},
        )

        logger.info("Publishing event", topic=topic, event_id=event.event_id)

        if self.use_redis and self._pubsub:
            # Publish to Redis
            await self._publish_redis(event)
        else:
            # Process locally
            await self._process_event(event)

    async def _publish_redis(self, event: Event) -> None:
        """Publish event to Redis pub/sub"""
        try:
            serialized = self.serializer.dumps(event.__dict__)
            await self.cache.client.publish(f"events:{event.topic}", serialized)
        except Exception as e:
            logger.error("Failed to publish event to Redis", topic=event.topic, error=str(e))
            # Fallback to local processing
            await self._process_event(event)

    async def _process_event(self, event: Event) -> None:
        """Process event by calling all registered handlers"""
        handlers = self._handlers.get(event.topic, [])

        if not handlers:
            logger.debug("No handlers registered for topic", topic=event.topic)
            return

        # Call all handlers concurrently
        tasks = [self._call_handler(handler, event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_handler(self, handler: Callable, event: Event) -> None:
        """Call a single event handler"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "Event handler failed",
                topic=event.topic,
                handler=handler.__name__,
                error=str(e),
                exc_info=True,
            )

    async def start(self) -> None:
        """
        Start listening for events (Redis mode only).

        This blocks until stop() is called.
        """
        if not self.use_redis or not self._pubsub:
            logger.warning("Event bus not in Redis mode, start() not needed")
            return

        self._listening = True

        # Subscribe to all registered topics
        for topic in self._handlers.keys():
            await self._pubsub.subscribe(f"events:{topic}")
            logger.info("Subscribed to Redis topic", topic=topic)

        # Listen for messages
        logger.info("Event bus listening for events")

        try:
            while self._listening:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True)

                if message and message["type"] == "message":
                    # Parse event
                    data = self.serializer.loads(message["data"].decode("utf-8"))
                    event = Event(**data)

                    # Process event
                    await self._process_event(event)

                await asyncio.sleep(0.01)  # Yield control
        except asyncio.CancelledError:
            logger.info("Event bus listener cancelled")
        except Exception as e:
            logger.error("Event bus listener error", error=str(e), exc_info=True)

    async def stop(self) -> None:
        """Stop listening for events"""
        self._listening = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        logger.info("Event bus stopped")

    def start_background(self) -> asyncio.Task:
        """
        Start listening in the background (returns task).

        Example:
            task = bus.start_background()
            # ... do other work ...
            await bus.stop()
        """
        self._listener_task = asyncio.create_task(self.start())
        return self._listener_task


# Convenience function for single global bus
_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _global_bus
    if _global_bus is None:
        raise RuntimeError("Event bus not initialized. Call init_event_bus() first.")
    return _global_bus


def init_event_bus(use_redis: bool = False, redis_url: Optional[str] = None) -> EventBus:
    """Initialize global event bus"""
    global _global_bus
    _global_bus = EventBus(use_redis=use_redis, redis_url=redis_url)
    return _global_bus
