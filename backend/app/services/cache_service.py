# backend/app/services/cache_service.py
import redis.asyncio as redis
from app.config import get_settings, get_secrets
import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """
    Azure Redis Cache integration.
    Used for:
    - Chat response caching
    - Conversation history caching
    - Rate limiting counters
    - Search result caching
    """

    def __init__(self):
        settings = get_settings()
        secrets = get_secrets()
        self.client = redis.Redis(
            host=settings.azure_redis_host,
            port=6380,
            password=secrets.redis_password,
            ssl=True,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        try:
            value = await self.client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
            else:
                logger.debug(f"Cache MISS: {key}")
            return value
        except redis.RedisError as e:
            logger.warning(f"Redis GET failed for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: int = 300,
    ) -> bool:
        """
        Set a value in cache with TTL.
        
        Args:
            key: Cache key
            value: String value (serialize complex objects first)
            ttl: Time-to-live in seconds (default 5 minutes)
        """
        try:
            await self.client.setex(key, ttl, value)
            logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis SET failed for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            await self.client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis DELETE failed for {key}: {e}")
            return False

    async def increment(
        self,
        key: str,
        ttl: int = 60,
    ) -> int:
        """
        Increment a counter (used for rate limiting).
        Sets TTL on first increment.
        """
        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]  # The incremented value
        except redis.RedisError as e:
            logger.warning(f"Redis INCREMENT failed for {key}: {e}")
            return 0

    async def get_json(self, key: str) -> dict | None:
        """Get and deserialize a JSON value."""
        raw = await self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(
        self, key: str, value: dict, ttl: int = 300
    ) -> bool:
        """Serialize and set a JSON value."""
        return await self.set(key, json.dumps(value), ttl)

    async def close(self):
        """Close the Redis connection."""
        await self.client.close()
