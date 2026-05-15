"""Payment endpoints for Robokassa preorder validation."""

import json
import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from src import db
from src.config import PAYMENTS_ENABLED, PREORDER_AMOUNT_RUB
from src.robokassa_client import (
    CURRENCY_RUB,
    RobokassaConfigError,
    RobokassaSignatureError,
    build_payment_url,
    format_amount,
    verify_result_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, amount_value, currency
            FROM preorders
            WHERE invoice_id = $1
            """,
            invoice_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="preorder not found")
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

    logger.info(f"Robokassa payment succeeded invoice_id={inv_id}")
    return Response(content=f"OK{inv_id}", media_type="text/plain")
