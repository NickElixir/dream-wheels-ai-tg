"""HTTP API для пополнения баланса через Robokassa."""

import logging
import re
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator

from src import db
from src.auth import resolve_telegram_auth
from src.config import PAYMENTS_ENABLED, ROBOKASSA_IS_TEST
from src.credits_service import get_balance
from src.payments_service import (
    PaymentConfigError,
    PaymentNotFoundError,
    PaymentValidationError,
    TopUpIntent,
    create_topup_payment,
    get_payment_status_by_invoice,
    get_starter_grant_for_user,
    list_payments_for_user,
    mark_payment_paid,
    normalize_amount_rub,
    verify_result_signature,
)
from src.payments_service import (
    calculate_topup_credits as _calculate_topup_credits,
)
from src.users_service import ensure_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
calculate_topup_credits = _calculate_topup_credits


class TopUpCreateRequest(BaseModel):
    amount_rub: str
    pricing_version: str = "credits-v1"
    source_screen: str = "cabinet"
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


@router.get("/cabinet")
async def get_payment_cabinet(
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    auth = resolve_telegram_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        auth_name="payments",
    )
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
            balance = await get_balance(conn, user_id)
            payments = await list_payments_for_user(conn, user_id=user_id)
            starter_grant = await get_starter_grant_for_user(conn, user_id=user_id)
    return {"balance": balance, "payments": payments, "starter_grant": starter_grant}


@router.get("/{invoice_id}/status")
async def get_payment_status(
    invoice_id: int,
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    auth = resolve_telegram_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        auth_name="payments",
    )
    pool = db.get_pool()
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
                return await get_payment_status_by_invoice(
                    conn,
                    invoice_id=invoice_id,
                    user_id=user_id,
                )
        except PaymentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Payment not found") from exc


@router.post("/topups")
async def create_topup(
    request: TopUpCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    if not PAYMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="Payments are temporarily disabled")

    auth = resolve_telegram_auth(
        init_data=request.init_data,
        telegram_user_id=request.telegram_user_id,
        authorization=authorization,
        auth_name="payments",
    )
    intent = TopUpIntent(
        amount_rub=request.amount_decimal,
        pricing_version=request.pricing_version,
        source_screen=request.source_screen,
        receipt_email=request.email.lower(),
    )
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
            await get_balance(conn, user_id)
            try:
                payload = await create_topup_payment(conn, user_id=user_id, intent=intent)
            except PaymentConfigError as exc:
                logger.exception(
                    f"❌ Robokassa create topup failed tg_user={auth.telegram_user_id}: {exc}"
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
    is_test_raw = payload.get("IsTest")
    is_test = None if is_test_raw is None else str(is_test_raw) == "1"

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
                    is_test=ROBOKASSA_IS_TEST if is_test is None else is_test,
                )
            except PaymentValidationError as exc:
                raise HTTPException(status_code=400, detail="Payment payload mismatch") from exc
            except PaymentNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Payment not found") from exc

    logger.info(f"✅ Robokassa callback invoice_id={invoice_id} payment_id={payment_id}")
    return PlainTextResponse(f"OK{invoice_id}")
