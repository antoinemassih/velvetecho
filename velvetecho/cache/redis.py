"""Redis cache implementation with circuit breaker"""

from typing import Optional, Any
import redis.asyncio as aioredis
import structlog

from velvetecho.cache.serialization import CacheSerializer
from velvetecho.cache.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from velvetecho.config import get_config

logger = structlog.get_logger(__name__)


class RedisCache:
    """
    Redis cache client with circuit breaker and JSON serialization.

    Features:
    - Automatic JSON serialization (UUID, datetime support)
    - Circuit breaker (prevents cascade failures)
    - Cache-aside pattern helpers
    - TTL management
    - Batch operations

    Example:
        cache = RedisCache()
        await cache.connect()

        # Set value
        await cache.set("user:123", {"name": "John"}, ttl=3600)

        # Get value
        user = await cache.get("user:123")

        # Delete
        await cache.delete("user:123")

        await cache.disconnect()
    """

    def __init__(self, redis_url: Optional[str] = None):
        config = get_config()
        self.redis_url = redis_url or config.redis_url
        self.serializer = CacheSerializer()
        self.circuit_breaker = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            timeout=config.circuit_breaker_timeout,
        )
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis"""
        if self._client is not None:
            return

        logger.info("Connecting to Redis", url=self.redis_url)

        try:
            self._client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle serialization
            )

            # Test connection
            await self._client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Redis")

    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client (raises if not connected)"""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """

        @self.circuit_breaker.call
        async def _get():
            value = await self.client.get(key)
            if value is None:
                return default
            return self.serializer.loads_bytes(value)

        try:
            return await _get()
        except CircuitBreakerOpenError:
            logger.warning("Cache GET failed (circuit open)", key=key)
            return default
        except Exception as e:
            logger.error("Cache GET failed", key=key, error=str(e))
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (None = no expiration)

        Returns:
            True if successful, False otherwise
        """

        @self.circuit_breaker.call
        async def _set():
            serialized = self.serializer.dumps_bytes(value)
            if ttl:
                await self.client.setex(key, ttl, serialized)
            else:
                await self.client.set(key, serialized)
            return True

        try:
            return await _set()
        except CircuitBreakerOpenError:
            logger.warning("Cache SET failed (circuit open)", key=key)
            return False
        except Exception as e:
            logger.error("Cache SET failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Returns:
            True if key was deleted, False if not found or error
        """

        @self.circuit_breaker.call
        async def _delete():
            result = await self.client.delete(key)
            return result > 0

        try:
            return await _delete()
        except CircuitBreakerOpenError:
            logger.warning("Cache DELETE failed (circuit open)", key=key)
            return False
        except Exception as e:
            logger.error("Cache DELETE failed", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""

        @self.circuit_breaker.call
        async def _exists():
            return await self.client.exists(key) > 0

        try:
            return await _exists()
        except CircuitBreakerOpenError:
            logger.warning("Cache EXISTS failed (circuit open)", key=key)
            return False
        except Exception as e:
            logger.error("Cache EXISTS failed", key=key, error=str(e))
            return False

    async def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Cache-aside pattern: Get from cache or compute and cache.

        Example:
            async def get_user(user_id):
                return await cache.get_or_set(
                    key=f"user:{user_id}",
                    factory=lambda: fetch_user_from_db(user_id),
                    ttl=3600
                )
        """
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute value
        value = await factory()

        # Cache it
        await self.set(key, value, ttl=ttl)

        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "user:*", "session:123:*")

        Returns:
            Number of keys deleted
        """

        @self.circuit_breaker.call
        async def _invalidate():
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.client.delete(*keys)
            return 0

        try:
            return await _invalidate()
        except CircuitBreakerOpenError:
            logger.warning("Cache INVALIDATE failed (circuit open)", pattern=pattern)
            return 0
        except Exception as e:
            logger.error("Cache INVALIDATE failed", pattern=pattern, error=str(e))
            return 0
