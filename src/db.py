"""Postgres connection pool (asyncpg).

Pool создаётся в lifespan приложения, через get_pool() — доступ из роутов/воркера.
"""

import asyncpg

from src.config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Инициализация пула. Вызывать один раз на старте приложения.

    statement_cache_size=0 обязателен при работе через Supabase pooler
    (порт 6543, transaction pool_mode) — иначе prepared statements
    конфликтуют между сессиями пула.
    """
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool не инициализирован — вызови init_pool() в lifespan")
    return _pool
