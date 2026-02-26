"""Delayed task queue (schedule tasks for future execution)"""

import time
from typing import Optional, List, Any
from dataclasses import dataclass
import structlog

from velvetecho.cache.redis import RedisCache
from velvetecho.cache.serialization import CacheSerializer

logger = structlog.get_logger(__name__)


@dataclass
class DelayedTask:
    """Task scheduled for future execution"""

    id: str
    data: Any
    scheduled_at: float  # Unix timestamp
    created_at: float


class DelayedQueue:
    """
    Delayed task queue using Redis sorted sets.

    Tasks are stored with their scheduled time as the score.
    Only tasks with score <= current_time are returned.

    Example:
        queue = DelayedQueue("scheduled-tasks")
        await queue.connect()

        # Schedule task for 1 hour from now
        await queue.schedule("task-1", {"action": "cleanup"}, delay=3600)

        # Get tasks that are ready
        ready_tasks = await queue.get_ready()
        for task in ready_tasks:
            print(task.data)
            await queue.complete(task.id)

        await queue.disconnect()
    """

    def __init__(self, queue_name: str, redis_url: Optional[str] = None):
        self.queue_name = queue_name
        self.cache = RedisCache(redis_url)
        self.serializer = CacheSerializer()
        self._key = f"queue:delayed:{queue_name}"

    async def connect(self) -> None:
        """Connect to Redis"""
        await self.cache.connect()

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        await self.cache.disconnect()

    async def schedule(
        self,
        task_id: str,
        data: Any,
        delay: int,  # Delay in seconds
    ) -> bool:
        """
        Schedule task for future execution.

        Args:
            task_id: Unique task identifier
            data: Task data (will be JSON serialized)
            delay: Delay in seconds from now

        Returns:
            True if scheduled, False if failed
        """
        try:
            scheduled_at = time.time() + delay

            task = DelayedTask(
                id=task_id,
                data=data,
                scheduled_at=scheduled_at,
                created_at=time.time(),
            )

            # Serialize task
            value = self.serializer.dumps(task.__dict__)

            # Add to sorted set (score = scheduled time)
            await self.cache.client.zadd(self._key, {value: scheduled_at})

            logger.info(
                "Scheduled delayed task",
                queue=self.queue_name,
                task_id=task_id,
                delay=delay,
                scheduled_at=scheduled_at,
            )

            return True
        except Exception as e:
            logger.error(
                "Failed to schedule delayed task",
                queue=self.queue_name,
                task_id=task_id,
                error=str(e),
            )
            return False

    async def get_ready(self, limit: int = 100) -> List[DelayedTask]:
        """
        Get tasks that are ready to execute (scheduled_at <= now).

        Args:
            limit: Maximum tasks to return

        Returns:
            List of DelayedTasks ready for execution
        """
        try:
            current_time = time.time()

            # Get tasks with score <= current_time
            results = await self.cache.client.zrangebyscore(
                self._key,
                min=0,
                max=current_time,
                start=0,
                num=limit,
                withscores=True,
            )

            tasks = []
            for value, score in results:
                data = self.serializer.loads(value.decode("utf-8"))
                tasks.append(DelayedTask(**data))

            logger.info(
                "Retrieved ready delayed tasks",
                queue=self.queue_name,
                count=len(tasks),
            )

            return tasks
        except Exception as e:
            logger.error(
                "Failed to get ready delayed tasks",
                queue=self.queue_name,
                error=str(e),
            )
            return []

    async def complete(self, task_id: str) -> bool:
        """
        Mark task as completed (remove from queue).

        Args:
            task_id: Task identifier

        Returns:
            True if removed, False if not found or failed
        """
        try:
            # Find and remove task by ID
            results = await self.cache.client.zrange(self._key, 0, -1)

            for value in results:
                data = self.serializer.loads(value.decode("utf-8"))
                if data["id"] == task_id:
                    await self.cache.client.zrem(self._key, value)
                    logger.info(
                        "Completed delayed task",
                        queue=self.queue_name,
                        task_id=task_id,
                    )
                    return True

            return False
        except Exception as e:
            logger.error(
                "Failed to complete delayed task",
                queue=self.queue_name,
                task_id=task_id,
                error=str(e),
            )
            return False

    async def cancel(self, task_id: str) -> bool:
        """Cancel scheduled task (alias for complete)"""
        return await self.complete(task_id)

    async def size(self) -> int:
        """Get total number of scheduled tasks"""
        try:
            return await self.cache.client.zcard(self._key)
        except Exception:
            return 0

    async def clear(self) -> bool:
        """Clear all scheduled tasks"""
        try:
            await self.cache.client.delete(self._key)
            logger.info("Cleared delayed queue", queue=self.queue_name)
            return True
        except Exception as e:
            logger.error(
                "Failed to clear delayed queue",
                queue=self.queue_name,
                error=str(e),
            )
            return False
