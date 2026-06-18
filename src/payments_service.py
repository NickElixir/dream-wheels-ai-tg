"""Robokassa top-up flow и cabinet payment queries."""

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import quote, urlencode

import asyncpg

from src.config import (
    ROBOKASSA_HASH_ALGO,
    ROBOKASSA_IS_TEST,
    ROBOKASSA_MERCHANT_LOGIN,
    ROBOKASSA_PASSWORD1,
    ROBOKASSA_PASSWORD2,
    ROBOKASSA_TEST_PASSWORD1,
    ROBOKASSA_TEST_PASSWORD2,
)
from src.credits_service import ensure_credit_account

logger = logging.getLogger(__name__)

TWOPLACES = Decimal("0.01")
PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_FAILED = "failed"
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


def _robokassa_digest(value: str) -> str:
    algo = ROBOKASSA_HASH_ALGO
    try:
        hasher = hashlib.new(algo)
    except ValueError as exc:
        raise PaymentConfigError(f"Unsupported ROBOKASSA_HASH_ALGO={algo}") from exc
    hasher.update(value.encode("utf-8"))
    return hasher.hexdigest()


def _receipt_payload(intent: TopUpIntent) -> dict[str, Any]:
    return {
        "items": [
            {
                "name": f"Dream Wheels AI credits ({intent.credits_granted})",
                "quantity": 1,
                "sum": float(intent.amount_rub),
                "tax": "none",
            }
        ],
        "email": intent.receipt_email,
    }


def _require_payment_config() -> None:
    password1, password2 = _active_passwords()
    if not ROBOKASSA_MERCHANT_LOGIN or not password1 or not password2:
        raise PaymentConfigError("Robokassa credentials are not configured")


def _active_passwords() -> tuple[str, str]:
    if ROBOKASSA_IS_TEST:
        return (
            ROBOKASSA_TEST_PASSWORD1 or ROBOKASSA_PASSWORD1,
            ROBOKASSA_TEST_PASSWORD2 or ROBOKASSA_PASSWORD2,
        )
    return ROBOKASSA_PASSWORD1, ROBOKASSA_PASSWORD2


def build_payment_url(*, invoice_id: int, payment_id: str, intent: TopUpIntent) -> str:
    _require_payment_config()
    password1, _ = _active_passwords()
    receipt_json = json.dumps(_receipt_payload(intent), ensure_ascii=False, separators=(",", ":"))
    encoded_receipt = quote(receipt_json, safe="")
    signature_parts = [
        ROBOKASSA_MERCHANT_LOGIN,
        f"{intent.amount_rub:.2f}",
        str(invoice_id),
        receipt_json,
        password1,
        f"Shp_payment_id={payment_id}",
    ]
    if ROBOKASSA_IS_TEST:
        signature_parts.append("IsTest=1")
    signature_value = _robokassa_digest(":".join(signature_parts))

    params = {
        "MerchantLogin": ROBOKASSA_MERCHANT_LOGIN,
        "OutSum": f"{intent.amount_rub:.2f}",
        "InvId": str(invoice_id),
        "Description": "Dream Wheels AI credits",
        "Receipt": encoded_receipt,
        "Email": intent.receipt_email,
        "Shp_payment_id": payment_id,
        "SignatureValue": signature_value,
    }
    if ROBOKASSA_IS_TEST:
        params["IsTest"] = "1"
    return f"https://auth.robokassa.ru/Merchant/Index.aspx?{urlencode(params)}"


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
            provider_payment_id,
            status,
            amount_rub,
            credits_granted,
            receipt_email,
            receipt_payload,
            pricing_version,
            source_screen
        )
        VALUES (
            $1,
            $2,
            'pending',
            $3,
            $4,
            $5,
            $6::jsonb,
            $7,
            $8
        )
        RETURNING id, invoice_id, amount_rub, credits_granted, pricing_version
        """,
        user_id,
        payment_id,
        intent.amount_rub,
        intent.credits_granted,
        intent.receipt_email,
        json.dumps(receipt_payload, ensure_ascii=False),
        intent.pricing_version,
        intent.source_screen,
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
               receipt_email, provider_payment_id, created_at, paid_at, failed_at, updated_at
        FROM payments
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        user_id,
    )
    return [serialize_payment_row(row) for row in rows]


def serialize_payment_row(row: asyncpg.Record) -> dict[str, Any]:
    updated_at = row["paid_at"] or row["failed_at"] or row["updated_at"] or row["created_at"]
    return {
        "payment_id": str(row["id"]),
        "invoice_id": int(row["invoice_id"]),
        "status": row["status"],
        "amount": float(row["amount_rub"]),
        "credits_granted": int(row["credits_granted"]),
        "pricing_version": row["pricing_version"],
        "confirmation_url": None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "paid_at": row["paid_at"].isoformat() if row["paid_at"] else None,
        "tax_receipt_status": "handled_by_robokassa",
    }


async def get_payment_status_by_invoice(
    conn: asyncpg.Connection,
    *,
    invoice_id: int,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        SELECT p.*, a.balance
        FROM payments p
        LEFT JOIN user_credit_accounts a ON a.user_id = p.user_id
        WHERE p.invoice_id = $1
        """,
        invoice_id,
    )
    if row is None:
        raise PaymentNotFoundError(f"invoice_id={invoice_id} not found")
    payload = serialize_payment_row(row)
    payload["balance"] = int(row["balance"] or 0)
    return payload


def verify_result_signature(
    *,
    out_sum: str,
    invoice_id: int,
    signature_value: str,
    payment_id: str,
    is_test: bool,
) -> bool:
    _, password2 = _active_passwords()
    expected_parts = [
        out_sum,
        str(invoice_id),
        password2,
        f"Shp_payment_id={payment_id}",
    ]
    if is_test:
        expected_parts.append("IsTest=1")
    expected = _robokassa_digest(":".join(expected_parts))
    return hmac.compare_digest(expected.lower(), signature_value.lower())


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
