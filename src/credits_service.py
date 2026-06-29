"""Credit ledger и безопасное списание за рендеры."""

import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from src.config import JOB_CREDIT_COST, STARTER_GRANT_CREDITS, STARTER_GRANT_TTL_DAYS

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Недостаточно credits для запуска рендера."""


def _starter_grant_idempotency_key(user_id: int) -> str:
    return f"starter_grant:{user_id}"


def _starter_grant_expiration_idempotency_key(user_id: int) -> str:
    return f"starter_grant_expire:{user_id}"


def _starter_grant_expires_at(created_at: datetime) -> datetime:
    return created_at + timedelta(days=STARTER_GRANT_TTL_DAYS)


async def _has_starter_grant_ledger_entry(conn: asyncpg.Connection, user_id: int) -> bool:
    try:
        found = await conn.fetchval(
            """
            SELECT 1
            FROM credit_ledger
            WHERE user_id = $1
              AND (
                  metadata->>'kind' = 'starter_grant'
                  OR event_type = 'trial_grant'
                  OR idempotency_key = $2
              )
            LIMIT 1
            """,
            user_id,
            _starter_grant_idempotency_key(user_id),
        )
    except asyncpg.UndefinedColumnError:
        try:
            found = await conn.fetchval(
                """
                SELECT 1
                FROM credit_ledger
                WHERE user_id = $1
                  AND metadata->>'kind' = 'starter_grant'
                LIMIT 1
                """,
                user_id,
            )
        except asyncpg.PostgresError:
            return False
    except asyncpg.PostgresError:
        return False
    return found is not None


async def _get_starter_grant_ledger_entry(
    conn: asyncpg.Connection,
    user_id: int,
) -> asyncpg.Record | None:
    try:
        return await conn.fetchrow(
            """
            SELECT credits_delta, created_at
            FROM credit_ledger
            WHERE user_id = $1
              AND (
                  metadata->>'kind' = 'starter_grant'
                  OR event_type = 'trial_grant'
                  OR idempotency_key = $2
              )
            ORDER BY created_at ASC
            LIMIT 1
            """,
            user_id,
            _starter_grant_idempotency_key(user_id),
        )
    except asyncpg.UndefinedColumnError:
        try:
            return await conn.fetchrow(
                """
                SELECT delta_credits AS credits_delta, created_at
                FROM credit_ledger
                WHERE user_id = $1
                  AND metadata->>'kind' = 'starter_grant'
                ORDER BY created_at ASC
                LIMIT 1
                """,
                user_id,
            )
        except asyncpg.PostgresError:
            return None
    except asyncpg.PostgresError:
        logger.exception(f"❌ starter grant ledger lookup failed for user_id={user_id}")
        return None


async def _has_starter_grant_expiration_ledger_entry(
    conn: asyncpg.Connection, user_id: int
) -> bool:
    try:
        found = await conn.fetchval(
            """
            SELECT 1
            FROM credit_ledger
            WHERE user_id = $1
              AND (
                  metadata->>'kind' = 'starter_grant_expiration'
                  OR event_type = 'expiration'
                  OR idempotency_key = $2
              )
            LIMIT 1
            """,
            user_id,
            _starter_grant_expiration_idempotency_key(user_id),
        )
    except asyncpg.UndefinedColumnError:
        try:
            found = await conn.fetchval(
                """
                SELECT 1
                FROM credit_ledger
                WHERE user_id = $1
                  AND metadata->>'kind' = 'starter_grant_expiration'
                LIMIT 1
                """,
                user_id,
            )
        except asyncpg.PostgresError:
            return False
    except asyncpg.PostgresError:
        logger.exception(f"❌ starter grant expiration lookup failed for user_id={user_id}")
        return False
    return found is not None


def _calculate_remaining_starter_grant_credits(
    ledger_rows: list[Mapping[str, Any]],
    *,
    user_id: int,
    granted_credits: int,
) -> int:
    remaining = granted_credits
    starter_seen = False
    starter_key = _starter_grant_idempotency_key(user_id)

    for row in ledger_rows:
        row_idempotency_key = row.get("idempotency_key")
        row_kind = ((row.get("metadata") or {}).get("kind") if row.get("metadata") else None) or ""
        row_event_type = row.get("event_type")
        credits_delta = int(row.get("credits_delta") or 0)

        if not starter_seen:
            if (
                row_kind == "starter_grant"
                or row_event_type == "trial_grant"
                or row_idempotency_key == starter_key
            ) and credits_delta > 0:
                starter_seen = True
            continue

        if credits_delta < 0:
            remaining = max(0, remaining + credits_delta)
            continue

        if row_event_type == "job_refund":
            remaining = min(granted_credits, remaining + credits_delta)

    return remaining


async def _list_credit_ledger_rows_for_user(
    conn: asyncpg.Connection,
    user_id: int,
) -> list[asyncpg.Record]:
    try:
        return await conn.fetch(
            """
            SELECT event_type, credits_delta, idempotency_key, metadata, created_at
            FROM credit_ledger
            WHERE user_id = $1
            ORDER BY created_at ASC, idempotency_key ASC
            """,
            user_id,
        )
    except asyncpg.UndefinedColumnError:
        return await conn.fetch(
            """
            SELECT operation_type AS event_type,
                   delta_credits AS credits_delta,
                   idempotency_key,
                   metadata,
                   created_at
            FROM credit_ledger
            WHERE user_id = $1
            ORDER BY created_at ASC, idempotency_key ASC
            """,
            user_id,
        )


async def _execute_ledger_insert_with_savepoint(
    conn: asyncpg.Connection,
    query: str,
    *args: object,
) -> None:
    async with conn.transaction():
        await conn.execute(query, *args)


async def _insert_starter_grant_ledger_entry(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    balance_after: int,
) -> None:
    # Ledger is an audit trail. Missing compat columns should not block the user-facing balance flow.
    try:
        await _execute_ledger_insert_with_savepoint(
            conn,
            """
            INSERT INTO credit_ledger (
                user_id,
                event_type,
                credits_delta,
                balance_after,
                idempotency_key,
                metadata
            )
            VALUES (
                $1,
                'trial_grant',
                $2,
                $3,
                $4,
                jsonb_build_object('kind', 'starter_grant')
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            user_id,
            STARTER_GRANT_CREDITS,
            balance_after,
            _starter_grant_idempotency_key(user_id),
        )
        return
    except asyncpg.UndefinedColumnError:
        logger.warning(
            "⚠️ legacy credit_ledger schema detected; using fallback starter grant insert"
        )
    except asyncpg.PostgresError:
        logger.exception(f"❌ starter grant ledger insert failed for user_id={user_id}")
        return

    try:
        await _execute_ledger_insert_with_savepoint(
            conn,
            """
            INSERT INTO credit_ledger (
                user_id,
                operation_type,
                delta_credits,
                amount_value,
                currency,
                idempotency_key,
                metadata
            )
            VALUES (
                $1,
                'manual_adjustment',
                $2,
                NULL,
                'RUB',
                $3,
                jsonb_build_object('kind', 'starter_grant')
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            user_id,
            STARTER_GRANT_CREDITS,
            _starter_grant_idempotency_key(user_id),
        )
    except asyncpg.PostgresError:
        logger.exception(f"❌ legacy starter grant ledger insert failed for user_id={user_id}")


async def _insert_starter_grant_expiration_ledger_entry(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    credits_to_expire: int,
    balance_after: int,
    expires_at: datetime,
) -> bool:
    try:
        async with conn.transaction():
            inserted = await conn.fetchval(
                """
                INSERT INTO credit_ledger (
                    user_id,
                    event_type,
                    credits_delta,
                    balance_after,
                    idempotency_key,
                    metadata
                )
                VALUES (
                    $1,
                    'expiration',
                    $2,
                    $3,
                    $4,
                    jsonb_build_object(
                        'kind', 'starter_grant_expiration',
                        'grant_kind', 'starter_grant',
                        'expired_credits', $5,
                        'expires_at', $6
                    )
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING 1
                """,
                user_id,
                -credits_to_expire,
                balance_after,
                _starter_grant_expiration_idempotency_key(user_id),
                credits_to_expire,
                expires_at.isoformat(),
            )
        return inserted == 1
    except asyncpg.UndefinedColumnError:
        logger.warning(
            "⚠️ legacy credit_ledger schema detected; using fallback starter grant expiration insert"
        )
    except asyncpg.PostgresError:
        logger.exception(f"❌ starter grant expiration insert failed for user_id={user_id}")

    try:
        async with conn.transaction():
            inserted = await conn.fetchval(
                """
                INSERT INTO credit_ledger (
                    user_id,
                    operation_type,
                    delta_credits,
                    amount_value,
                    currency,
                    idempotency_key,
                    metadata
                )
                VALUES (
                    $1,
                    'manual_adjustment',
                    $2,
                    NULL,
                    'RUB',
                    $3,
                    jsonb_build_object(
                        'kind', 'starter_grant_expiration',
                        'grant_kind', 'starter_grant',
                        'expired_credits', $4,
                        'expires_at', $5
                    )
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING 1
                """,
                user_id,
                -credits_to_expire,
                _starter_grant_expiration_idempotency_key(user_id),
                credits_to_expire,
                expires_at.isoformat(),
            )
        return inserted == 1
    except asyncpg.PostgresError:
        logger.exception(f"❌ legacy starter grant expiration insert failed for user_id={user_id}")
        return False


async def _expire_starter_grant_if_due(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    balance: int,
) -> int:
    if STARTER_GRANT_CREDITS <= 0 or STARTER_GRANT_TTL_DAYS <= 0:
        return balance

    starter_grant_row = await _get_starter_grant_ledger_entry(conn, user_id)
    if starter_grant_row is None:
        return balance

    expires_at = _starter_grant_expires_at(starter_grant_row["created_at"])
    if expires_at > datetime.now(UTC):
        return balance

    if await _has_starter_grant_expiration_ledger_entry(conn, user_id):
        return balance

    ledger_rows = await _list_credit_ledger_rows_for_user(conn, user_id)
    remaining_trial_credits = _calculate_remaining_starter_grant_credits(
        ledger_rows,
        user_id=user_id,
        granted_credits=int(starter_grant_row["credits_delta"] or 0),
    )
    credits_to_expire = min(balance, remaining_trial_credits)
    if credits_to_expire <= 0:
        return balance

    balance_after = balance - credits_to_expire
    inserted = await _insert_starter_grant_expiration_ledger_entry(
        conn,
        user_id=user_id,
        credits_to_expire=credits_to_expire,
        balance_after=balance_after,
        expires_at=expires_at,
    )
    if not inserted:
        return balance

    await conn.execute(
        """
        UPDATE user_credit_accounts
        SET balance = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
        """,
        user_id,
        balance_after,
    )
    logger.info(
        "✅ Starter grant expired user_id=%s expired_credits=%s ttl_days=%s",
        user_id,
        credits_to_expire,
        STARTER_GRANT_TTL_DAYS,
    )
    return balance_after


async def ensure_credit_account(conn: asyncpg.Connection, user_id: int) -> int:
    """Создать аккаунт credits и один раз выдать стартовый grant."""
    await conn.execute(
        """
        INSERT INTO user_credit_accounts (user_id)
        VALUES ($1)
        ON CONFLICT (user_id) DO NOTHING
        """,
        user_id,
    )
    has_trial_used_at_column = True
    try:
        account = await conn.fetchrow(
            """
            SELECT balance, trial_used_at
            FROM user_credit_accounts
            WHERE user_id = $1
            FOR UPDATE
            """,
            user_id,
        )
        trial_used_at = account["trial_used_at"] if account is not None else None
    except asyncpg.UndefinedColumnError:
        has_trial_used_at_column = False
        account = await conn.fetchrow(
            """
            SELECT balance
            FROM user_credit_accounts
            WHERE user_id = $1
            FOR UPDATE
            """,
            user_id,
        )
        trial_used_at = None
    if account is None:
        raise RuntimeError(f"user_credit_accounts row missing for user_id={user_id}")

    balance = int(account["balance"])
    balance = await _expire_starter_grant_if_due(conn, user_id=user_id, balance=balance)
    if trial_used_at is None and STARTER_GRANT_CREDITS > 0:
        if await _has_starter_grant_ledger_entry(conn, user_id):
            return balance
        balance_after = balance + STARTER_GRANT_CREDITS
        if has_trial_used_at_column:
            try:
                await conn.execute(
                    """
                    UPDATE user_credit_accounts
                    SET balance = $2,
                        trial_used_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                    """,
                    user_id,
                    balance_after,
                )
            except asyncpg.UndefinedColumnError:
                has_trial_used_at_column = False
                await conn.execute(
                    """
                    UPDATE user_credit_accounts
                    SET balance = $2
                    WHERE user_id = $1
                    """,
                    user_id,
                    balance_after,
                )
        else:
            try:
                await conn.execute(
                    """
                    UPDATE user_credit_accounts
                    SET balance = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                    """,
                    user_id,
                    balance_after,
                )
            except asyncpg.UndefinedColumnError:
                await conn.execute(
                    """
                    UPDATE user_credit_accounts
                    SET balance = $2
                    WHERE user_id = $1
                    """,
                    user_id,
                    balance_after,
                )
        await _insert_starter_grant_ledger_entry(
            conn,
            user_id=user_id,
            balance_after=balance_after,
        )
        logger.info(f"✅ Выдан стартовый grant user_id={user_id}: +{STARTER_GRANT_CREDITS} credits")
        return balance_after
    return balance


async def get_balance(conn: asyncpg.Connection, user_id: int) -> int:
    """Вернуть актуальный баланс, создав grant при первом входе."""
    return await ensure_credit_account(conn, user_id)


async def reserve_job_credit(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    job_id: str,
    credit_cost: int = JOB_CREDIT_COST,
) -> int:
    """Зарезервировать credit за job. Идемпотентно по job_id."""
    job_row = await conn.fetchrow(
        """
        SELECT credit_status, credit_cost
        FROM jobs
        WHERE id = $1::uuid
        FOR UPDATE
        """,
        job_id,
    )
    if job_row is None:
        raise RuntimeError(f"job not found for reserve job_id={job_id}")

    current_status = job_row["credit_status"]
    if current_status in {"reserved", "finalized"}:
        balance = await ensure_credit_account(conn, user_id)
        return balance

    balance = await ensure_credit_account(conn, user_id)
    effective_cost = int(job_row["credit_cost"] or credit_cost)
    if balance < effective_cost:
        raise InsufficientCreditsError(
            f"user_id={user_id} balance={balance} < credit_cost={effective_cost}"
        )

    balance_after = balance - effective_cost
    await conn.execute(
        """
        UPDATE user_credit_accounts
        SET balance = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
        """,
        user_id,
        balance_after,
    )
    await conn.execute(
        """
        INSERT INTO credit_ledger (
            user_id,
            event_type,
            credits_delta,
            balance_after,
            related_job_id,
            idempotency_key,
            metadata
        )
        VALUES (
            $1,
            'job_reserve',
            $2,
            $3,
            $4::uuid,
            $5,
            jsonb_build_object('credit_cost', $6::int)
        )
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        user_id,
        -effective_cost,
        balance_after,
        job_id,
        f"job_reserve:{job_id}",
        effective_cost,
    )
    await conn.execute(
        """
        UPDATE jobs
        SET credit_status = 'reserved',
            credit_cost = $2
        WHERE id = $1::uuid
        """,
        job_id,
        effective_cost,
    )
    return balance_after


async def finalize_job_credit(conn: asyncpg.Connection, *, user_id: int, job_id: str) -> int:
    """Зафиксировать успешное списание после завершения рендера."""
    job_row = await conn.fetchrow(
        """
        SELECT credit_status
        FROM jobs
        WHERE id = $1::uuid
        FOR UPDATE
        """,
        job_id,
    )
    if job_row is None:
        raise RuntimeError(f"job not found for finalize job_id={job_id}")
    if job_row["credit_status"] == "finalized":
        return await ensure_credit_account(conn, user_id)
    if job_row["credit_status"] != "reserved":
        return await ensure_credit_account(conn, user_id)

    balance = await ensure_credit_account(conn, user_id)
    await conn.execute(
        """
        INSERT INTO credit_ledger (
            user_id,
            event_type,
            credits_delta,
            balance_after,
            related_job_id,
            idempotency_key
        )
        VALUES (
            $1,
            'job_finalize',
            0,
            $2,
            $3::uuid,
            $4
        )
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        user_id,
        balance,
        job_id,
        f"job_finalize:{job_id}",
    )
    await conn.execute(
        """
        UPDATE jobs
        SET credit_status = 'finalized'
        WHERE id = $1::uuid
        """,
        job_id,
    )
    return balance


async def refund_job_credit(conn: asyncpg.Connection, *, user_id: int, job_id: str) -> int:
    """Вернуть зарезервированный credit при техническом фейле."""
    job_row = await conn.fetchrow(
        """
        SELECT credit_status, credit_cost
        FROM jobs
        WHERE id = $1::uuid
        FOR UPDATE
        """,
        job_id,
    )
    if job_row is None:
        raise RuntimeError(f"job not found for refund job_id={job_id}")
    if job_row["credit_status"] == "refunded":
        return await ensure_credit_account(conn, user_id)
    if job_row["credit_status"] != "reserved":
        return await ensure_credit_account(conn, user_id)

    balance = await ensure_credit_account(conn, user_id)
    credit_cost = int(job_row["credit_cost"] or JOB_CREDIT_COST)
    balance_after = balance + credit_cost
    await conn.execute(
        """
        UPDATE user_credit_accounts
        SET balance = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
        """,
        user_id,
        balance_after,
    )
    await conn.execute(
        """
        INSERT INTO credit_ledger (
            user_id,
            event_type,
            credits_delta,
            balance_after,
            related_job_id,
            idempotency_key,
            metadata
        )
        VALUES (
            $1,
            'job_refund',
            $2,
            $3,
            $4::uuid,
            $5,
            jsonb_build_object('credit_cost', $6::int)
        )
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        user_id,
        credit_cost,
        balance_after,
        job_id,
        f"job_refund:{job_id}",
        credit_cost,
    )
    await conn.execute(
        """
        UPDATE jobs
        SET credit_status = 'refunded'
        WHERE id = $1::uuid
        """,
        job_id,
    )
    return balance_after
