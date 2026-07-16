import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config.settings import settings

logger = logging.getLogger("flowops.redis")


class RedisClient:
    _instance: Optional["RedisClient"] = None
    _client: Optional[aioredis.Redis] = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> None:
        if self._client is not None:
            return
        self._client = aioredis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        logger.info("Redis client configured for %s:%d", settings.redis.host, settings.redis.port)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_json(self, key: str) -> Optional[dict[str, Any]]:
        if self._client is None:
            return None
        try:
            raw = await self._client.get(key)
        except RedisError as exc:
            logger.warning("Redis GET '%s' failed: %s", key, exc)
            return None
        return json.loads(raw) if raw is not None else None

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int = 300) -> None:
        if self._client is None:
            return
        try:
            await self._client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
        except RedisError as exc:
            logger.warning("Redis SET '%s' failed: %s", key, exc)

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        if self._client is None:
            return True
        try:
            count = await self._client.incr(key)
            if count == 1:
                await self._client.expire(key, window_seconds)
            return count <= limit
        except RedisError as exc:
            logger.warning("Redis rate-limit check '%s' failed (fail-open): %s", key, exc)
            return True


redis_client = RedisClient()
