"""Redis client (redis-py async)."""

import redis.asyncio as redis

from src.config import REDIS_KEY_PREFIX, REDIS_URL

_client: redis.Redis | None = None


def init_client() -> redis.Redis:
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL не сконфигурирован")
    global _client
    _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


async def close_client() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None


def get_client() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis client не инициализирован — вызови init_client() в lifespan")
    return _client


def is_initialized() -> bool:
    return _client is not None


def key(name: str) -> str:
    return f"{REDIS_KEY_PREFIX}{name}"
