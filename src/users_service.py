"""Общие операции над пользователями."""

import asyncpg


async def ensure_user(
    conn: asyncpg.Connection,
    telegram_user_id: int,
    username: str | None = None,
) -> int:
    """Найти или создать users.id по telegram_user_id, обновив username при наличии."""
    user_id = await conn.fetchval(
        "SELECT id FROM users WHERE telegram_user_id = $1",
        telegram_user_id,
    )
    if user_id:
        if username:
            await conn.execute(
                "UPDATE users SET username = $1 WHERE id = $2",
                username,
                user_id,
            )
        return int(user_id)

    user_id = await conn.fetchval(
        """
        INSERT INTO users (telegram_user_id, username)
        VALUES ($1, $2)
        RETURNING id
        """,
        telegram_user_id,
        username,
    )
    return int(user_id)
