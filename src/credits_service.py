"""Credit ledger и безопасное списание за рендеры."""

import logging

import asyncpg

from src.config import JOB_CREDIT_COST, STARTER_GRANT_CREDITS

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Недостаточно credits для запуска рендера."""


async def _has_starter_grant_ledger_entry(conn: asyncpg.Connection, user_id: int) -> bool:
    try:
        found = await conn.fetchval(
            """
            SELECT 1
            FROM credit_ledger
            WHERE idempotency_key = $1
            LIMIT 1
            """,
            f"starter_grant:{user_id}",
        )
    except asyncpg.PostgresError:
        return False
    return found is not None


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
    if trial_used_at is None and STARTER_GRANT_CREDITS > 0:
        if await _has_starter_grant_ledger_entry(conn, user_id):
            return balance
        balance_after = balance + STARTER_GRANT_CREDITS
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
        await conn.execute(
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
            f"starter_grant:{user_id}",
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
