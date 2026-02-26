"""Priority queue implementation using Redis sorted sets"""

import time
from typing import Optional, List, Any
from dataclasses import dataclass
import structlog

from velvetecho.cache.redis import RedisCache
from velvetecho.cache.serialization import CacheSerializer

logger = structlog.get_logger(__name__)


@dataclass
class QueueItem:
    """Item in priority queue"""

    id: str
    data: Any
    priority: int  # Lower = higher priority
    added_at: float


class PriorityQueue:
    """
    Priority queue using Redis sorted sets.

    Features:
    - Priority-based ordering (lower score = higher priority)
    - FIFO within same priority
    - Atomic operations
    - Peek without removing

    Example:
        queue = PriorityQueue("tasks")
        await queue.connect()

        # Add tasks with priority
        await queue.push("task-1", {"action": "process"}, priority=1)  # High priority
        await queue.push("task-2", {"action": "cleanup"}, priority=10)  # Low priority

        # Get highest priority task
        item = await queue.pop()
        print(item.data)  # {"action": "process"}

        await queue.disconnect()
    """

    def __init__(self, queue_name: str, redis_url: Optional[str] = None):
        self.queue_name = queue_name
        self.cache = RedisCache(redis_url)
        self.serializer = CacheSerializer()
        self._key = f"queue:priority:{queue_name}"

    async def connect(self) -> None:
        """Connect to Redis"""
        await self.cache.connect()

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        await self.cache.disconnect()

    async def push(
        self,
        item_id: str,
        data: Any,
        priority: int = 5,
    ) -> bool:
        """
        Add item to queue with priority.

        Args:
            item_id: Unique item identifier
            data: Item data (will be JSON serialized)
            priority: Priority (lower = higher priority, default=5)

        Returns:
            True if added, False if failed
        """
        try:
            item = QueueItem(
                id=item_id,
                data=data,
                priority=priority,
                added_at=time.time(),
            )

            # Score = priority + (timestamp / 1e10) for FIFO within priority
            score = priority + (item.added_at / 1e10)

            # Serialize item
            value = self.serializer.dumps(item.__dict__)

            # Add to sorted set
            await self.cache.client.zadd(self._key, {value: score})

            logger.info(
                "Added item to priority queue",
                queue=self.queue_name,
                item_id=item_id,
                priority=priority,
            )

            return True
        except Exception as e:
            logger.error(
                "Failed to push to priority queue",
                queue=self.queue_name,
                item_id=item_id,
                error=str(e),
            )
            return False

    async def pop(self) -> Optional[QueueItem]:
        """
        Remove and return highest priority item.

        Returns:
            QueueItem or None if queue is empty
        """
        try:
            # Get item with lowest score (highest priority)
            results = await self.cache.client.zpopmin(self._key, count=1)

            if not results:
                return None

            value, score = results[0]
            data = self.serializer.loads(value.decode("utf-8"))

            item = QueueItem(**data)

            logger.info(
                "Popped item from priority queue",
                queue=self.queue_name,
                item_id=item.id,
                priority=item.priority,
            )

            return item
        except Exception as e:
            logger.error(
                "Failed to pop from priority queue",
                queue=self.queue_name,
                error=str(e),
            )
            return None

    async def peek(self) -> Optional[QueueItem]:
        """
        Get highest priority item without removing.

        Returns:
            QueueItem or None if queue is empty
        """
        try:
            results = await self.cache.client.zrange(self._key, 0, 0, withscores=True)

            if not results:
                return None

            value, score = results[0]
            data = self.serializer.loads(value.decode("utf-8"))

            return QueueItem(**data)
        except Exception as e:
            logger.error(
                "Failed to peek priority queue",
                queue=self.queue_name,
                error=str(e),
            )
            return None

    async def size(self) -> int:
        """Get queue size"""
        try:
            return await self.cache.client.zcard(self._key)
        except Exception:
            return 0

    async def clear(self) -> bool:
        """Clear all items from queue"""
        try:
            await self.cache.client.delete(self._key)
            logger.info("Cleared priority queue", queue=self.queue_name)
            return True
        except Exception as e:
            logger.error(
                "Failed to clear priority queue",
                queue=self.queue_name,
                error=str(e),
            )
            return False

    async def list_items(self, limit: int = 100) -> List[QueueItem]:
        """
        List items in queue (by priority).

        Args:
            limit: Maximum items to return

        Returns:
            List of QueueItems (highest priority first)
        """
        try:
            results = await self.cache.client.zrange(self._key, 0, limit - 1, withscores=True)

            items = []
            for value, score in results:
                data = self.serializer.loads(value.decode("utf-8"))
                items.append(QueueItem(**data))

            return items
        except Exception as e:
            logger.error(
                "Failed to list priority queue items",
                queue=self.queue_name,
                error=str(e),
            )
            return []
