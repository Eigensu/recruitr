"""Small async Redis cache wrapper for dashboard read models."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str, enabled: bool, namespace: str = "dashboard") -> None:
        self.enabled = enabled
        self.namespace = namespace
        self._client: Redis | None = Redis.from_url(url, decode_responses=True) if enabled else None

    def build_key(self, *parts: Any) -> str:
        suffix = ":".join(str(part) for part in parts if part is not None and str(part) != "")
        return f"{self.namespace}:{suffix}" if suffix else self.namespace

    async def get_json(self, key: str) -> Any | None:
        if not self.enabled or self._client is None:
            return None

        payload = await self._client.get(key)
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            snippet = payload if len(payload) <= 200 else f"{payload[:200]}…"
            logger.warning("Redis cache JSON decode failed for key %s: %s; payload=%r", key, exc, snippet)
            return None

    async def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        if not self.enabled or self._client is None:
            return

        await self._client.set(key, json.dumps(payload, default=str), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        if not self.enabled or self._client is None:
            return

        await self._client.delete(key)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


dashboard_cache = RedisCache(
    url=settings.REDIS_URL,
    enabled=settings.REDIS_ENABLED,
    namespace=settings.REDIS_NAMESPACE,
)
