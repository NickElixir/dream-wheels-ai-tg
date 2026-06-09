"""Helpers for local user records."""

from src import db


async def ensure_user(telegram_user_id: int) -> int:
    """Найти или создать users.id по telegram_user_id."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )
        if not user_id:
            user_id = await conn.fetchval(
                "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id",
                telegram_user_id,
            )
    return int(user_id)
