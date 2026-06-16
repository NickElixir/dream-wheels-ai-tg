"""HTTP API для пополнения баланса через Robokassa."""

import logging
import re
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator

from src import db
from src.auth import InitDataInvalid, parse_init_data
from src.config import PAYMENTS_ENABLED
from src.credits_service import get_balance
from src.payments_service import (
    PaymentConfigError,
    PaymentNotFoundError,
    PaymentValidationError,
    TopUpIntent,
    create_topup_payment,
    get_payment_status_by_invoice,
    list_payments_for_user,
    mark_payment_paid,
    normalize_amount_rub,
    verify_result_signature,
)
from src.users_service import ensure_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class TopUpCreateRequest(BaseModel):
    amount_rub: str
    pricing_version: str
    source_screen: str
    email: str
    init_data: str | None = None
    telegram_user_id: int | None = None

    @field_validator("pricing_version", "source_screen")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized[:128]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_RE.fullmatch(normalized):
            raise ValueError("invalid email")
        return normalized

    @property
    def amount_decimal(self) -> Decimal:
        return normalize_amount_rub(self.amount_rub)


def _resolve_identity(
    init_data: str | None, telegram_user_id: int | None
) -> tuple[int, str | None]:
    if init_data:
        try:
            parsed = parse_init_data(init_data)
        except InitDataInvalid as exc:
            raise HTTPException(status_code=401, detail=f"initData invalid: {exc}") from exc
        user = parsed.get("user") or {}
        resolved_user_id = user.get("id")
        if not resolved_user_id:
            raise HTTPException(status_code=401, detail="initData без user.id")
        username_raw = user.get("username")
        username = username_raw if isinstance(username_raw, str) else None
        return int(resolved_user_id), username

    if telegram_user_id is None:
        raise HTTPException(status_code=400, detail="telegram_user_id required in dev mode")
    return telegram_user_id, None


@router.get("/cabinet")
async def get_payment_cabinet(
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
):
    resolved_tg_user_id, username = _resolve_identity(init_data, telegram_user_id)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await ensure_user(conn, resolved_tg_user_id, username)
            balance = await get_balance(conn, user_id)
            payments = await list_payments_for_user(conn, user_id=user_id)
    return {"balance": balance, "payments": payments}


@router.get("/{invoice_id}/status")
async def get_payment_status(invoice_id: int):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        try:
            return await get_payment_status_by_invoice(conn, invoice_id=invoice_id)
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Payment not found") from exc


@router.post("/topups")
async def create_topup(request: TopUpCreateRequest):
    if not PAYMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="Payments are temporarily disabled")

    resolved_tg_user_id, username = _resolve_identity(request.init_data, request.telegram_user_id)
    intent = TopUpIntent(
        amount_rub=request.amount_decimal,
        pricing_version=request.pricing_version,
        source_screen=request.source_screen,
        receipt_email=request.email.lower(),
    )
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await ensure_user(conn, resolved_tg_user_id, username)
            await get_balance(conn, user_id)
            try:
                payload = await create_topup_payment(conn, user_id=user_id, intent=intent)
            except PaymentConfigError as exc:
                logger.exception(
                    f"❌ Robokassa create topup failed tg_user={resolved_tg_user_id}: {exc}"
                )
                raise HTTPException(
                    status_code=503, detail="Payment provider is not configured"
                ) from exc
    return payload


@router.api_route("/robokassa/result", methods=["GET", "POST"])
async def robokassa_result(request: Request):
    if request.method == "POST":
        payload = dict(await request.form())
    else:
        payload = dict(request.query_params)

    out_sum = str(payload.get("OutSum") or payload.get("out_summ") or "")
    inv_id_raw = payload.get("InvId") or payload.get("inv_id")
    signature_value = str(payload.get("SignatureValue") or payload.get("signature_value") or "")
    payment_id = str(payload.get("Shp_payment_id") or "")
    is_test = str(payload.get("IsTest") or "0") == "1"

    if not out_sum or not inv_id_raw or not signature_value or not payment_id:
        raise HTTPException(status_code=400, detail="Missing Robokassa params")

    try:
        invoice_id = int(inv_id_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="InvId must be integer") from exc

    if not verify_result_signature(
        out_sum=out_sum,
        invoice_id=invoice_id,
        signature_value=signature_value,
        payment_id=payment_id,
        is_test=is_test,
    ):
        logger.warning(
            f"❌ Robokassa signature mismatch invoice_id={invoice_id} payment_id={payment_id}"
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                await mark_payment_paid(
                    conn,
                    invoice_id=invoice_id,
                    provider_payment_id=payment_id,
                    out_sum=out_sum,
                    is_test=is_test,
                )
            except PaymentValidationError as exc:
                raise HTTPException(status_code=400, detail="Payment payload mismatch") from exc
            except PaymentNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Payment not found") from exc

    logger.info(f"✅ Robokassa callback invoice_id={invoice_id} payment_id={payment_id}")
    return PlainTextResponse(f"OK{invoice_id}")
