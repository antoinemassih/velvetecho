"""Dead letter queue for failed tasks"""

import time
from typing import Optional, List, Any
from dataclasses import dataclass
import structlog

from velvetecho.cache.redis import RedisCache
from velvetecho.cache.serialization import CacheSerializer

logger = structlog.get_logger(__name__)


@dataclass
class FailedTask:
    """Task that failed permanently"""

    id: str
    data: Any
    error: str
    attempts: int
    failed_at: float
    original_queue: str


class DeadLetterQueue:
    """
    Dead letter queue for permanently failed tasks.

    Tasks are moved here after max retry attempts exceeded.

    Example:
        dlq = DeadLetterQueue()
        await dlq.connect()

        # Add failed task
        await dlq.add("task-1", {"action": "process"}, "Connection timeout", attempts=5)

        # List failed tasks
        failed = await dlq.list_failed()

        # Retry a task
        task = await dlq.get("task-1")
        # ... process task ...
        await dlq.remove("task-1")

        await dlq.disconnect()
    """

    def __init__(self, queue_name: str = "dlq", redis_url: Optional[str] = None):
        self.queue_name = queue_name
        self.cache = RedisCache(redis_url)
        self.serializer = CacheSerializer()
        self._key = f"queue:dlq:{queue_name}"

    async def connect(self) -> None:
        """Connect to Redis"""
        await self.cache.connect()

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        await self.cache.disconnect()

    async def add(
        self,
        task_id: str,
        data: Any,
        error: str,
        attempts: int,
        original_queue: str = "unknown",
    ) -> bool:
        """
        Add failed task to dead letter queue.

        Args:
            task_id: Task identifier
            data: Original task data
            error: Error message
            attempts: Number of attempts made
            original_queue: Name of original queue

        Returns:
            True if added, False if failed
        """
        try:
            failed_task = FailedTask(
                id=task_id,
                data=data,
                error=error,
                attempts=attempts,
                failed_at=time.time(),
                original_queue=original_queue,
            )

            # Serialize task
            value = self.serializer.dumps(failed_task.__dict__)

            # Store in hash (key = task_id, value = task data)
            await self.cache.client.hset(self._key, task_id, value)

            logger.error(
                "Task moved to dead letter queue",
                task_id=task_id,
                error=error,
                attempts=attempts,
                original_queue=original_queue,
            )

            return True
        except Exception as e:
            logger.error(
                "Failed to add to dead letter queue",
                task_id=task_id,
                error=str(e),
            )
            return False

    async def get(self, task_id: str) -> Optional[FailedTask]:
        """
        Get failed task by ID.

        Args:
            task_id: Task identifier

        Returns:
            FailedTask or None if not found
        """
        try:
            value = await self.cache.client.hget(self._key, task_id)

            if not value:
                return None

            data = self.serializer.loads(value.decode("utf-8"))
            return FailedTask(**data)
        except Exception as e:
            logger.error(
                "Failed to get from dead letter queue",
                task_id=task_id,
                error=str(e),
            )
            return None

    async def remove(self, task_id: str) -> bool:
        """
        Remove task from dead letter queue.

        Args:
            task_id: Task identifier

        Returns:
            True if removed, False if not found or failed
        """
        try:
            result = await self.cache.client.hdel(self._key, task_id)

            if result > 0:
                logger.info(
                    "Removed task from dead letter queue",
                    task_id=task_id,
                )
                return True

            return False
        except Exception as e:
            logger.error(
                "Failed to remove from dead letter queue",
                task_id=task_id,
                error=str(e),
            )
            return False

    async def list_failed(self, limit: int = 100) -> List[FailedTask]:
        """
        List all failed tasks.

        Args:
            limit: Maximum tasks to return

        Returns:
            List of FailedTasks
        """
        try:
            # Get all tasks from hash
            all_tasks = await self.cache.client.hgetall(self._key)

            tasks = []
            for task_id, value in list(all_tasks.items())[:limit]:
                data = self.serializer.loads(value.decode("utf-8"))
                tasks.append(FailedTask(**data))

            # Sort by failed_at (most recent first)
            tasks.sort(key=lambda t: t.failed_at, reverse=True)

            return tasks
        except Exception as e:
            logger.error(
                "Failed to list dead letter queue",
                error=str(e),
            )
            return []

    async def size(self) -> int:
        """Get number of failed tasks"""
        try:
            return await self.cache.client.hlen(self._key)
        except Exception:
            return 0

    async def clear(self) -> bool:
        """Clear all failed tasks"""
        try:
            await self.cache.client.delete(self._key)
            logger.info("Cleared dead letter queue", queue=self.queue_name)
            return True
        except Exception as e:
            logger.error(
                "Failed to clear dead letter queue",
                queue=self.queue_name,
                error=str(e),
            )
            return False
