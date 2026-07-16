from typing import Awaitable, Callable

from fastapi import Request

from app.core.cache.redis import redis_client
from app.shared.exceptions.base import RateLimitError


def rate_limiter(
    scope: str, limit: int, window_seconds: int
) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        host = request.client.host if request.client else "unknown"
        key = f"ratelimit:{scope}:{host}"
        allowed = await redis_client.hit(key, limit, window_seconds)
        if not allowed:
            raise RateLimitError(
                f"Too many requests for '{scope}'; retry in {window_seconds} seconds"
            )

    return dependency
