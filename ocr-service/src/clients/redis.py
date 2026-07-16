import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from src.core.config import settings

logger = logging.getLogger("ocr.redis")


class RedisCache:
    def __init__(self) -> None:
        self._client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    async def get(self, key: str) -> Optional[dict[str, Any]]:
        try:
            raw = await self._client.get(key)
        except RedisError as exc:
            logger.warning("Redis GET '%s' failed: %s", key, exc)
            return None
        if raw is None:
            return None
        logger.info("Cache hit for '%s'", key)
        return json.loads(raw)

    async def set(self, key: str, value: dict[str, Any], ttl: Optional[int] = None) -> None:
        try:
            await self._client.set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=ttl if ttl is not None else settings.CACHE_TTL_SECONDS,
            )
            logger.info("Cached '%s'", key)
        except RedisError as exc:
            logger.warning("Redis SET '%s' failed: %s", key, exc)

    async def close(self) -> None:
        await self._client.aclose()
