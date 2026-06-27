"""Robokassa top-up flow и cabinet payment queries."""

import json
import logging
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg

from src.config import (
    ROBOKASSA_HASH_ALGO,
    ROBOKASSA_IS_TEST,
    ROBOKASSA_MERCHANT_LOGIN,
    ROBOKASSA_PASSWORD1,
    ROBOKASSA_PASSWORD2,
    ROBOKASSA_PAYMENT_URL,
    ROBOKASSA_TEST_PASSWORD1,
    ROBOKASSA_TEST_PASSWORD2,
    STARTER_GRANT_CREDITS,
)
from src.credits_service import ensure_credit_account
from src.payments.providers.robokassa import (
    RobokassaConfig,
    RobokassaPaymentProvider,
    RobokassaProviderConfigError,
    RobokassaTopUpIntent,
)

logger = logging.getLogger(__name__)

TWOPLACES = Decimal("0.01")
PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_PROVIDER_ROBOKASSA = "robokassa"
PAYMENT_CURRENCY_RUB = "RUB"
PAYMENT_DELIVERY_CHANNEL_WEBSITE = "website"
TOPUP_TIERS: tuple[tuple[int, Decimal], ...] = (
    (1000, Decimal("1000") / Decimal("45")),
    (500, Decimal("25")),
    (200, Decimal("200") / Decimal("7")),
    (100, Decimal("100") / Decimal("3")),
)


class PaymentConfigError(Exception):
    """Robokassa не настроена."""


class PaymentNotFoundError(Exception):
    """Платеж не найден."""


class PaymentValidationError(Exception):
    """Параметры callback не совпали с ожидаемым платежом."""


@dataclass(slots=True)
class TopUpIntent:
    amount_rub: Decimal
    pricing_version: str
    source_screen: str
    receipt_email: str

    @property
    def credits_granted(self) -> int:
        return calculate_topup_credits(self.amount_rub)


def normalize_amount_rub(raw_amount: str | int | float | Decimal) -> Decimal:
    amount = Decimal(str(raw_amount)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if amount < Decimal("100.00") or amount > Decimal("3000.00"):
        raise ValueError("amount_rub must be between 100 and 3000")
    return amount


def calculate_topup_credits(amount_rub: Decimal) -> int:
    normalized_amount = normalize_amount_rub(amount_rub)
    for min_amount, rub_per_credit in TOPUP_TIERS:
        if normalized_amount >= Decimal(str(min_amount)):
            return max(1, int(normalized_amount / rub_per_credit))
    return 0


def _amount_rub_provider_units(amount_rub: Decimal) -> int:
    return int((amount_rub * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _robokassa_provider() -> RobokassaPaymentProvider:
    return RobokassaPaymentProvider(
        RobokassaConfig(
            merchant_login=ROBOKASSA_MERCHANT_LOGIN,
            password1=ROBOKASSA_PASSWORD1,
            password2=ROBOKASSA_PASSWORD2,
            test_password1=ROBOKASSA_TEST_PASSWORD1,
            test_password2=ROBOKASSA_TEST_PASSWORD2,
            payment_url=ROBOKASSA_PAYMENT_URL,
            hash_algo=ROBOKASSA_HASH_ALGO,
            is_test=ROBOKASSA_IS_TEST,
        )
    )


def _receipt_payload(intent: TopUpIntent) -> dict[str, Any]:
    return RobokassaPaymentProvider.receipt_payload(
        RobokassaTopUpIntent(
            amount_rub=intent.amount_rub,
            credits_granted=intent.credits_granted,
            receipt_email=intent.receipt_email,
        )
    )


def build_payment_url(*, invoice_id: int, payment_id: str, intent: TopUpIntent) -> str:
    try:
        invoice = _robokassa_provider().build_topup_invoice(
            invoice_id=invoice_id,
            payment_id=payment_id,
            intent=RobokassaTopUpIntent(
                amount_rub=intent.amount_rub,
                credits_granted=intent.credits_granted,
                receipt_email=intent.receipt_email,
            ),
        )
    except RobokassaProviderConfigError as exc:
        raise PaymentConfigError(str(exc)) from exc
    if invoice.confirmation_url is None:
        raise PaymentConfigError("Robokassa confirmation URL was not generated")
    return invoice.confirmation_url


async def create_topup_payment(
    conn: asyncpg.Connection,
    *,
    user_id: int,
    intent: TopUpIntent,
) -> dict[str, Any]:
    payment_id = str(uuid.uuid4())
    receipt_payload = _receipt_payload(intent)
    row = await conn.fetchrow(
        """
        INSERT INTO payments (
            user_id,
            provider,
            provider_payment_id,
            provider_invoice_payload,
            status,
            currency,
            amount_provider_units,
            amount_rub,
            credits_granted,
            receipt_email,
            receipt_payload,
            pricing_version,
            source_screen,
            delivery_channel
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            'pending',
            $5,
            $6,
            $7,
            $8,
            $9,
            $10::jsonb,
            $11,
            $12,
            $13
        )
        RETURNING id, invoice_id, amount_rub, credits_granted, pricing_version
        """,
        user_id,
        PAYMENT_PROVIDER_ROBOKASSA,
        payment_id,
        payment_id,
        PAYMENT_CURRENCY_RUB,
        _amount_rub_provider_units(intent.amount_rub),
        intent.amount_rub,
        intent.credits_granted,
        intent.receipt_email,
        json.dumps(receipt_payload, ensure_ascii=False),
        intent.pricing_version,
        intent.source_screen,
        PAYMENT_DELIVERY_CHANNEL_WEBSITE,
    )
    invoice_id = int(row["invoice_id"])
    payment_url = build_payment_url(invoice_id=invoice_id, payment_id=payment_id, intent=intent)
    return {
        "payment_id": str(row["id"]),
        "invoice_id": invoice_id,
        "amount": float(row["amount_rub"]),
        "credits_granted": int(row["credits_granted"]),
        "pricing_version": row["pricing_version"],
        "payment_url": payment_url,
    }


async def list_payments_for_user(conn: asyncpg.Connection, *, user_id: int) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT id, invoice_id, status, amount_rub, credits_granted, pricing_version,
               receipt_email, source_screen, provider_payment_id, created_at, paid_at, failed_at, updated_at
        FROM payments
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        user_id,
    )
    return [serialize_payment_row(row, confirmation_url=_confirmation_url_for_payment(row)) for row in rows]


def _confirmation_url_for_payment(row: asyncpg.Record) -> str | None:
    if row["status"] != PAYMENT_STATUS_PENDING:
        return None
    receipt_email = row["receipt_email"]
    provider_payment_id = row["provider_payment_id"]
    if not receipt_email or not provider_payment_id or row["amount_rub"] is None:
        return None
    try:
        return build_payment_url(
            invoice_id=int(row["invoice_id"]),
            payment_id=str(provider_payment_id),
            intent=TopUpIntent(
                amount_rub=Decimal(str(row["amount_rub"])),
                pricing_version=str(row["pricing_version"] or "credits-v1"),
                source_screen=str(row["source_screen"] or "cabinet"),
                receipt_email=str(receipt_email),
            ),
        )
    except PaymentConfigError:
        logger.warning(
            "⚠️ Robokassa resume URL unavailable for invoice_id=%s",
            row["invoice_id"],
        )
        return None


async def get_starter_grant_for_user(
    conn: asyncpg.Connection,
    *,
    user_id: int,
) -> dict[str, Any] | None:
    try:
        row = await conn.fetchrow(
            """
            SELECT credits_delta, created_at
            FROM credit_ledger
            WHERE user_id = $1
              AND (
                  event_type = 'trial_grant'
                  OR metadata->>'kind' = 'starter_grant'
              )
            ORDER BY created_at ASC
            LIMIT 1
            """,
            user_id,
        )
    except asyncpg.UndefinedColumnError:
        try:
            row = await conn.fetchrow(
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
            logger.warning(
                "⚠️ credit_ledger legacy schema unavailable; starter grant history skipped"
            )
            return None
    except asyncpg.PostgresError:
        logger.warning("⚠️ credit_ledger lookup failed; starter grant history skipped")
        return None
    if row is None:
        try:
            account_row = await conn.fetchrow(
                """
                SELECT trial_used_at, updated_at
                FROM user_credit_accounts
                WHERE user_id = $1
                  AND trial_used_at IS NOT NULL
                """,
                user_id,
            )
        except asyncpg.UndefinedColumnError:
            account_row = None
        except asyncpg.PostgresError:
            logger.warning(
                "⚠️ user_credit_accounts fallback lookup failed; starter grant history skipped"
            )
            account_row = None

        if account_row is None or STARTER_GRANT_CREDITS <= 0:
            return None

        created_at = account_row["trial_used_at"] or account_row["updated_at"]
        if created_at is None:
            return None
        return {
            "credits": STARTER_GRANT_CREDITS,
            "created_at": created_at.isoformat(),
        }
    return {
        "credits": int(row["credits_delta"]),
        "created_at": row["created_at"].isoformat(),
    }


def serialize_payment_row(row: asyncpg.Record, *, confirmation_url: str | None = None) -> dict[str, Any]:
    updated_at = row["paid_at"] or row["failed_at"] or row["updated_at"] or row["created_at"]
    return {
        "payment_id": str(row["id"]),
        "invoice_id": int(row["invoice_id"]),
        "status": row["status"],
        "amount": float(row["amount_rub"]),
        "credits_granted": int(row["credits_granted"]),
        "receipt_email": row["receipt_email"],
        "pricing_version": row["pricing_version"],
        "confirmation_url": confirmation_url,
        "created_at": row["created_at"].isoformat(),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "paid_at": row["paid_at"].isoformat() if row["paid_at"] else None,
        "tax_receipt_status": "handled_by_robokassa",
    }


async def get_payment_status_by_invoice(
    conn: asyncpg.Connection,
    *,
    invoice_id: int,
    user_id: int | None = None,
) -> dict[str, Any]:
    query = """
        SELECT p.*, a.balance
        FROM payments p
        LEFT JOIN user_credit_accounts a ON a.user_id = p.user_id
        WHERE p.invoice_id = $1
    """
    params: list[Any] = [invoice_id]
    if user_id is not None:
        query += " AND p.user_id = $2"
        params.append(user_id)
    row = await conn.fetchrow(
        query,
        *params,
    )
    if row is None:
        raise PaymentNotFoundError(f"invoice_id={invoice_id} not found")
    payload = serialize_payment_row(row, confirmation_url=_confirmation_url_for_payment(row))
    payload["balance"] = int(row["balance"] or 0)
    return payload


def verify_result_signature(
    *,
    out_sum: str,
    invoice_id: int,
    signature_value: str,
    payment_id: str,
    is_test: bool | None,
) -> bool:
    return _robokassa_provider().verify_result_signature(
        out_sum=out_sum,
        invoice_id=invoice_id,
        signature_value=signature_value,
        payment_id=payment_id,
        is_test=is_test,
    )


async def mark_payment_paid(
    conn: asyncpg.Connection,
    *,
    invoice_id: int,
    provider_payment_id: str,
    out_sum: str,
    is_test: bool,
) -> dict[str, Any]:
    await conn.execute(
        """
        INSERT INTO user_credit_accounts (user_id)
        SELECT user_id
        FROM payments
        WHERE invoice_id = $1
        ON CONFLICT (user_id) DO NOTHING
        """,
        invoice_id,
    )
    row = await conn.fetchrow(
        """
        SELECT p.id,
               p.user_id,
               p.invoice_id,
               p.status,
               p.amount_rub,
               p.credits_granted,
               p.provider_payment_id,
               a.balance
        FROM payments p
        JOIN user_credit_accounts a ON a.user_id = p.user_id
        WHERE p.invoice_id = $1
        FOR UPDATE
        """,
        invoice_id,
    )
    if row is None:
        raise PaymentNotFoundError(f"invoice_id={invoice_id} not found")
    if row["provider_payment_id"] != provider_payment_id:
        raise PaymentValidationError(f"invoice_id={invoice_id} provider_payment_id mismatch")
    if normalize_amount_rub(out_sum) != row["amount_rub"]:
        raise PaymentValidationError(f"invoice_id={invoice_id} amount mismatch")

    balance = await ensure_credit_account(conn, int(row["user_id"]))
    row = await conn.fetchrow(
        """
        SELECT p.id,
               p.user_id,
               p.invoice_id,
               p.status,
               p.amount_rub,
               p.credits_granted,
               p.provider_payment_id,
               a.balance
        FROM payments p
        JOIN user_credit_accounts a ON a.user_id = p.user_id
        WHERE p.invoice_id = $1
        FOR UPDATE
        """,
        invoice_id,
    )
    if row["status"] == PAYMENT_STATUS_PAID:
        return await get_payment_status_by_invoice(conn, invoice_id=invoice_id)

    credits_granted = int(row["credits_granted"])
    balance_after = int(row["balance"] or balance) + credits_granted
    await conn.execute(
        """
        UPDATE user_credit_accounts
        SET balance = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
        """,
        int(row["user_id"]),
        balance_after,
    )
    await conn.execute(
        """
        INSERT INTO credit_ledger (
            user_id,
            event_type,
            credits_delta,
            balance_after,
            related_payment_id,
            idempotency_key,
            metadata
        )
        VALUES (
            $1,
            'purchase_grant',
            $2,
            $3,
            $4::uuid,
            $5,
            jsonb_build_object('invoice_id', $6::bigint, 'out_sum', $7::text, 'is_test', $8::boolean)
        )
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        int(row["user_id"]),
        credits_granted,
        balance_after,
        str(row["id"]),
        f"payment_paid:{invoice_id}",
        invoice_id,
        out_sum,
        is_test,
    )
    await conn.execute(
        """
        UPDATE payments
        SET status = 'paid',
            paid_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE invoice_id = $1
        """,
        invoice_id,
    )
    return await get_payment_status_by_invoice(conn, invoice_id=invoice_id)
