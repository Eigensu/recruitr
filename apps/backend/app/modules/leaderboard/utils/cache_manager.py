import hashlib
import json
from typing import Any

from app.common.extras.redis_cache import leaderboard_cache
from app.config import settings

RANKING_ZSET_KEY = leaderboard_cache.build_key("rankings:zset")


def response_key(prefix: str, payload: dict[str, Any] | None = None) -> str:
    raw = json.dumps(payload or {}, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return leaderboard_cache.build_key(prefix, digest)


async def get_cached(key: str) -> Any | None:
    return await leaderboard_cache.get_json(key)


async def set_cached(key: str, payload: Any) -> None:
    await leaderboard_cache.set_json(key, payload, settings.REDIS_CACHE_TTL_SECONDS)


async def update_rank(member: str, score: int) -> None:
    await leaderboard_cache.zadd(RANKING_ZSET_KEY, {member: float(score)})
    await leaderboard_cache.expire(RANKING_ZSET_KEY, settings.REDIS_CACHE_TTL_SECONDS)


async def rankings_window(page: int, limit: int) -> list[str]:
    start = (page - 1) * limit
    end = start + limit - 1
    return await leaderboard_cache.zrevrange(RANKING_ZSET_KEY, start, end)


async def rankings_count() -> int:
    return await leaderboard_cache.zcard(RANKING_ZSET_KEY)


async def invalidate_leaderboard_cache() -> None:
    for prefix in (
        "overview",
        "rankings",
        "monthly-growth",
        "company-progress",
        "activity",
        "badges",
        "recruiter",
    ):
        await leaderboard_cache.delete_pattern(leaderboard_cache.build_key(prefix, "*"))
    await leaderboard_cache.delete(RANKING_ZSET_KEY)
