"""Payment endpoints for Robokassa preorder validation."""

import json
import logging
import re
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from src import db
from src.auth import InitDataInvalid, get_telegram_user_id
from src.config import PAYMENTS_ENABLED, PREORDER_AMOUNT_RUB
from src.robokassa_client import (
    CURRENCY_RUB,
    RobokassaConfigError,
    RobokassaSignatureError,
    build_payment_url,
    format_amount,
    verify_result_signature,
)
from src.users_service import ensure_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOPUP_MIN_AMOUNT_RUB = Decimal("100.00")
TOPUP_MAX_AMOUNT_RUB = Decimal("3000.00")
TOPUP_VALID_DAYS = 30
PRICING_VERSION = "2026-06-balance-v1"
TOPUP_TIERS = (
    (Decimal("1000.00"), Decimal("1000.00") / Decimal(45)),
    (Decimal("500.00"), Decimal("25.00")),
    (Decimal("200.00"), Decimal("200.00") / Decimal(7)),
    (Decimal("100.00"), Decimal("100.00") / Decimal(3)),
)


class PreorderCreateRequest(BaseModel):
    email: str
    telegram_user_id: int | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("invalid email")
        return email


class PreorderCreateResponse(BaseModel):
    preorder_id: str
    invoice_id: int
    status: str
    amount: str
    currency: str
    confirmation_url: str


class PreorderStatusResponse(BaseModel):
    preorder_id: str
    invoice_id: int
    status: str
    amount: str
    currency: str
    tax_receipt_status: str
    tax_receipt_url: str | None = None
    confirmation_url: str | None = None


class TopUpCreateRequest(BaseModel):
    amount_rub: Decimal
    credits_requested: int | None = None
    credits_granted: int | None = None
    pricing_version: str = PRICING_VERSION
    source_screen: str = "cabinet"
    init_data: str | None = None
    telegram_user_id: int | None = None
    email: str | None = None

    @field_validator("amount_rub")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        amount = Decimal(format_amount(value))
        if amount < TOPUP_MIN_AMOUNT_RUB or amount > TOPUP_MAX_AMOUNT_RUB:
            raise ValueError("amount_rub must be between 100 and 3000")
        return amount

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip().lower()
        if not email:
            return None
        if not EMAIL_RE.match(email):
            raise ValueError("invalid email")
        return email


class TopUpCreateResponse(BaseModel):
    payment_id: str
    invoice_id: int
    status: str
    amount: str
    currency: str
    credits_granted: int
    credits_expires_in_days: int
    pricing_version: str
    payment_url: str


class PaymentStatusResponse(BaseModel):
    payment_id: str
    invoice_id: int
    status: str
    amount: str
    currency: str
    credits_granted: int | None = None
    credits_expires_at: str | None = None
    pricing_version: str | None = None
    source_screen: str | None = None
    balance: int | None = None
    tax_receipt_status: str
    confirmation_url: str | None = None


def calculate_topup_credits(amount_rub: Decimal) -> int:
    amount = Decimal(format_amount(amount_rub))
    for min_amount, rub_per_credit in TOPUP_TIERS:
        if amount >= min_amount:
            return max(1, int(amount / rub_per_credit))
    return 1


def resolve_request_telegram_user_id(request: TopUpCreateRequest) -> int:
    if request.init_data:
        try:
            return get_telegram_user_id(request.init_data)
        except InitDataInvalid as exc:
            raise HTTPException(status_code=401, detail="invalid telegram initData") from exc
    if request.telegram_user_id is not None:
        return request.telegram_user_id
    raise HTTPException(status_code=422, detail="init_data or telegram_user_id is required")


async def get_credit_balance(user_id: int) -> int:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        balance = await conn.fetchval(
            """
            SELECT COALESCE(SUM(delta_credits), 0)::int
            FROM credit_ledger
            WHERE user_id = $1
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            user_id,
        )
    return int(balance or 0)


@router.post("/preorders", response_model=PreorderCreateResponse)
async def create_preorder(request: PreorderCreateRequest):
    """Create a local preorder and a signed Robokassa payment URL."""
    if not PAYMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="payments disabled")

    amount = format_amount(PREORDER_AMOUNT_RUB)
    preorder_id = str(uuid.uuid4())
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO preorders (
                id, email, telegram_user_id, amount_value, currency,
                status, tax_receipt_status
            )
            VALUES ($1::uuid, $2, $3, $4::numeric, $5, 'pending', 'pending_payment')
            RETURNING invoice_id
            """,
            preorder_id,
            request.email,
            request.telegram_user_id,
            amount,
            CURRENCY_RUB,
        )

    invoice_id = int(row["invoice_id"])
    description = f"Предоплата Dream Wheels AI #{invoice_id}"
    try:
        confirmation_url = build_payment_url(
            amount_rub=amount,
            invoice_id=invoice_id,
            preorder_id=preorder_id,
            email=request.email,
            description=description,
        )
    except RobokassaConfigError as exc:
        logger.exception(f"Robokassa payment URL failed preorder_id={preorder_id}: {exc}")
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE preorders
                SET status = 'payment_create_failed',
                    robokassa_payload = $2::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1::uuid
                """,
                preorder_id,
                json.dumps({"error": str(exc)}, ensure_ascii=False),
            )
        raise HTTPException(status_code=502, detail="payment create failed") from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE preorders
            SET confirmation_url = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            """,
            preorder_id,
            confirmation_url,
        )

    return PreorderCreateResponse(
        preorder_id=preorder_id,
        invoice_id=invoice_id,
        status="pending",
        amount=amount,
        currency=CURRENCY_RUB,
        confirmation_url=confirmation_url,
    )


@router.post("/topups", response_model=TopUpCreateResponse)
async def create_topup(request: TopUpCreateRequest):
    """Create a Robokassa payment for flexible render-credit balance top-up."""
    if not PAYMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="payments disabled")

    telegram_user_id = resolve_request_telegram_user_id(request)
    await ensure_user(telegram_user_id)

    amount = format_amount(request.amount_rub)
    credits_granted = calculate_topup_credits(request.amount_rub)
    payment_id = str(uuid.uuid4())
    pool = db.get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO preorders (
                id, email, telegram_user_id, amount_value, currency,
                status, tax_receipt_status, credits_granted, credits_expires_at,
                pricing_version, source_screen, payment_kind
            )
            VALUES (
                $1::uuid, $2, $3, $4::numeric, $5,
                'pending', 'pending_payment', $6,
                CURRENT_TIMESTAMP + ($7::text || ' days')::interval,
                $8, $9, 'topup'
            )
            RETURNING invoice_id
            """,
            payment_id,
            request.email,
            telegram_user_id,
            amount,
            CURRENCY_RUB,
            credits_granted,
            str(TOPUP_VALID_DAYS),
            request.pricing_version,
            request.source_screen,
        )

    invoice_id = int(row["invoice_id"])
    description = f"Dream Wheels AI render credits #{invoice_id}"
    try:
        payment_url = build_payment_url(
            amount_rub=amount,
            invoice_id=invoice_id,
            payment_id=payment_id,
            email=request.email,
            description=description,
        )
    except (RobokassaConfigError, ValueError) as exc:
        logger.exception(f"❌ Robokassa topup URL failed payment_id={payment_id}: {exc}")
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE preorders
                SET status = 'payment_create_failed',
                    robokassa_payload = $2::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1::uuid
                """,
                payment_id,
                json.dumps({"error": str(exc)}, ensure_ascii=False),
            )
        raise HTTPException(status_code=502, detail="payment create failed") from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE preorders
            SET confirmation_url = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1::uuid
            """,
            payment_id,
            payment_url,
        )

    return TopUpCreateResponse(
        payment_id=payment_id,
        invoice_id=invoice_id,
        status="pending",
        amount=amount,
        currency=CURRENCY_RUB,
        credits_granted=credits_granted,
        credits_expires_in_days=TOPUP_VALID_DAYS,
        pricing_version=request.pricing_version,
        payment_url=payment_url,
    )


@router.get("/preorders/{preorder_id}", response_model=PreorderStatusResponse)
async def get_preorder(preorder_id: str):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, invoice_id, status, amount_value, currency, tax_receipt_status,
                   tax_receipt_url, confirmation_url
            FROM preorders
            WHERE id = $1::uuid
            """,
            preorder_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="preorder not found")
    return PreorderStatusResponse(
        preorder_id=str(row["id"]),
        invoice_id=int(row["invoice_id"]),
        status=row["status"],
        amount=format_amount(row["amount_value"]),
        currency=row["currency"],
        tax_receipt_status=row["tax_receipt_status"],
        tax_receipt_url=row["tax_receipt_url"],
        confirmation_url=row["confirmation_url"],
    )


@router.get("/invoices/{invoice_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status(invoice_id: int):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.id, p.invoice_id, p.status, p.amount_value, p.currency,
                   p.credits_granted, p.credits_expires_at, p.pricing_version,
                   p.source_screen, p.tax_receipt_status, p.confirmation_url,
                   u.id AS user_id
            FROM preorders p
            LEFT JOIN users u ON u.telegram_user_id = p.telegram_user_id
            WHERE p.invoice_id = $1
            """,
            invoice_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="payment not found")

    balance = await get_credit_balance(int(row["user_id"])) if row["user_id"] else None
    expires_at = row["credits_expires_at"].isoformat() if row["credits_expires_at"] else None
    return PaymentStatusResponse(
        payment_id=str(row["id"]),
        invoice_id=int(row["invoice_id"]),
        status=row["status"],
        amount=format_amount(row["amount_value"]),
        currency=row["currency"],
        credits_granted=row["credits_granted"],
        credits_expires_at=expires_at,
        pricing_version=row["pricing_version"],
        source_screen=row["source_screen"],
        balance=balance,
        tax_receipt_status=row["tax_receipt_status"],
        confirmation_url=row["confirmation_url"],
    )


@router.get("/{invoice_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status_short(invoice_id: int):
    return await get_payment_status(invoice_id)


@router.post("/robokassa/result")
async def robokassa_result(request: Request):
    """Handle Robokassa ResultURL notification.

    Robokassa expects a plain text response: OK + invoice id.
    """
    form = await request.form()
    payload = {key: str(value) for key, value in form.items()}
    if not payload:
        payload = {key: str(value) for key, value in request.query_params.items()}

    try:
        verify_result_signature(payload)
    except (RobokassaConfigError, RobokassaSignatureError) as exc:
        logger.warning(f"Robokassa ResultURL rejected: {exc}")
        raise HTTPException(status_code=400, detail="invalid payment signature") from exc

    inv_id = payload.get("InvId") or payload.get("InvID")
    out_sum = payload.get("OutSum")
    if not inv_id or not out_sum:
        raise HTTPException(status_code=400, detail="payment params missing")
    try:
        invoice_id = int(inv_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid invoice id") from exc

    pool = db.get_pool()
    async with pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT id, telegram_user_id, amount_value, currency, status,
                   credits_granted, credits_expires_at, pricing_version,
                   source_screen, payment_kind
            FROM preorders
            WHERE invoice_id = $1
            FOR UPDATE
            """,
            invoice_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="payment not found")
        if format_amount(row["amount_value"]) != format_amount(out_sum):
            raise HTTPException(status_code=400, detail="amount mismatch")

        await conn.execute(
            """
            UPDATE preorders
            SET status = 'paid',
                robokassa_payment_status = 'paid',
                robokassa_payload = $2::jsonb,
                tax_receipt_status = 'pending_provider',
                paid_at = COALESCE(paid_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE invoice_id = $1
            """,
            invoice_id,
            json.dumps(payload, ensure_ascii=False),
        )

        if row["payment_kind"] == "topup" and row["telegram_user_id"] and row["credits_granted"]:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (telegram_user_id)
                VALUES ($1)
                ON CONFLICT (telegram_user_id) DO UPDATE
                SET telegram_user_id = EXCLUDED.telegram_user_id
                RETURNING id
                """,
                row["telegram_user_id"],
            )
            await conn.execute(
                """
                INSERT INTO credit_ledger (
                    user_id, preorder_id, operation_type, delta_credits,
                    amount_value, currency, pricing_version, source_screen,
                    expires_at, metadata
                )
                VALUES (
                    $1, $2::uuid, 'payment_grant', $3,
                    $4::numeric, $5, $6, $7, $8, $9::jsonb
                )
                ON CONFLICT DO NOTHING
                """,
                user_id,
                row["id"],
                row["credits_granted"],
                format_amount(row["amount_value"]),
                row["currency"],
                row["pricing_version"],
                row["source_screen"],
                row["credits_expires_at"],
                json.dumps({"invoice_id": invoice_id}, ensure_ascii=False),
            )

    logger.info(f"✅ Robokassa payment succeeded invoice_id={inv_id}")
    return Response(content=f"OK{inv_id}", media_type="text/plain")
