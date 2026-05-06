"""Redis-based rate limiter — скользящее окно через INCR + EXPIRE.

Алгоритм fixed window:
- INCR ключа `rl:<scope>:<id>` на каждый запрос
- На первой инкрементации (count == 1) ставим EXPIRE = window_sec
- Если count > limit — отдаём 429

Достаточно для защиты Reve API квоты от одного user_id. Для строгого
sliding window нужен ZSET с timestamp, но это overkill для MVP.
"""

import logging

from fastapi import HTTPException

from src import redis_client

logger = logging.getLogger(__name__)


async def enforce_rate_limit(
    scope: str,
    identifier: int | str,
    limit: int,
    window_sec: int,
) -> None:
    """Поднять HTTPException(429), если в окне `window_sec` уже было `limit` запросов.

    scope: префикс ключа ('jobs', 'login' и т.д.) — чтобы лимиты не пересекались
    identifier: telegram_user_id, IP, и т.п.
    """
    rds = redis_client.get_client()
    key = f"rl:{scope}:{identifier}"

    count = await rds.incr(key)
    if count == 1:
        await rds.expire(key, window_sec)

    if count > limit:
        ttl = await rds.ttl(key)
        logger.warning(
            f"⛔ Rate limit hit: scope={scope} id={identifier} count={count}/{limit} retry_after={ttl}s"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Retry after {ttl}s.",
            headers={"Retry-After": str(max(ttl, 1))},
        )
