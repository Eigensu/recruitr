"""Small async Redis cache wrapper for dashboard read models."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str, enabled: bool, namespace: str = "dashboard") -> None:
        self.enabled = enabled
        self.namespace = namespace
        self._client: Redis | None = None
        if enabled:
            try:
                self._client = Redis.from_url(url, decode_responses=True)
            except (RedisError, OSError) as exc:
                logger.warning(
                    "Redis client initialization failed (namespace=%s): %s",
                    namespace,
                    exc,
                    exc_info=False,
                )
                self._client = None

    def build_key(self, *parts: Any) -> str:
        suffix = ":".join(str(part) for part in parts if part is not None and str(part) != "")
        return f"{self.namespace}:{suffix}" if suffix else self.namespace

    async def get_json(self, key: str) -> Any | None:
        if not self.enabled or self._client is None:
            return None

        try:
            payload = await self._client.get(key)
        except (RedisError, OSError) as exc:
            logger.warning("Redis get failed for key %s: %s", key, exc, exc_info=False)
            return None
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            snippet = payload if len(payload) <= 200 else f"{payload[:200]}…"
            logger.warning(
                "Redis cache JSON decode failed for key %s: %s; payload=%r", key, exc, snippet
            )
            return None

    async def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        if not self.enabled or self._client is None:
            return

        try:
            await self._client.set(key, json.dumps(payload, default=str), ex=ttl_seconds)
        except (RedisError, OSError) as exc:
            logger.warning("Redis set failed for key %s: %s", key, exc, exc_info=False)

    async def delete(self, key: str) -> None:
        if not self.enabled or self._client is None:
            return

        try:
            await self._client.delete(key)
        except (RedisError, OSError) as exc:
            logger.warning("Redis delete failed for key %s: %s", key, exc, exc_info=False)

    async def delete_pattern(self, pattern: str) -> None:
        if not self.enabled or self._client is None:
            return

        try:
            keys = [key async for key in self._client.scan_iter(pattern)]
            if keys:
                await self._client.delete(*keys)
        except (RedisError, OSError) as exc:
            logger.warning("Redis delete pattern failed for %s: %s", pattern, exc, exc_info=False)

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        if not self.enabled or self._client is None:
            return

        try:
            await self._client.zadd(key, mapping)
        except (RedisError, OSError) as exc:
            logger.warning("Redis zadd failed for key %s: %s", key, exc, exc_info=False)

    async def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        if not self.enabled or self._client is None:
            return []

        try:
            return list(await self._client.zrevrange(key, start, end))
        except (RedisError, OSError) as exc:
            logger.warning("Redis zrevrange failed for key %s: %s", key, exc, exc_info=False)
            return []

    async def zcard(self, key: str) -> int:
        if not self.enabled or self._client is None:
            return 0

        try:
            return int(await self._client.zcard(key))
        except (RedisError, OSError) as exc:
            logger.warning("Redis zcard failed for key %s: %s", key, exc, exc_info=False)
            return 0

    async def expire(self, key: str, ttl_seconds: int) -> None:
        if not self.enabled or self._client is None:
            return

        try:
            await self._client.expire(key, ttl_seconds)
        except (RedisError, OSError) as exc:
            logger.warning("Redis expire failed for key %s: %s", key, exc, exc_info=False)

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except (RedisError, OSError) as exc:
                logger.warning("Redis close failed: %s", exc, exc_info=False)


dashboard_cache = RedisCache(
    url=settings.REDIS_URL,
    enabled=settings.REDIS_ENABLED,
    namespace=settings.REDIS_NAMESPACE,
)

leaderboard_cache = RedisCache(
    url=settings.REDIS_URL,
    enabled=settings.REDIS_ENABLED,
    namespace=f"{settings.REDIS_NAMESPACE}:leaderboard",
)
