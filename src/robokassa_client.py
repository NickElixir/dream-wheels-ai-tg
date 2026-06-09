"""Robokassa helpers for preorder payments.

Robokassa's classic payment interface is form/query based. The backend signs
the redirect URL with password #1, and verifies ResultURL notifications with
password #2.
"""

import hashlib
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlencode

from src.config import (
    ROBOKASSA_IS_TEST,
    ROBOKASSA_MERCHANT_LOGIN,
    ROBOKASSA_PASSWORD1,
    ROBOKASSA_PASSWORD2,
    ROBOKASSA_PAYMENT_URL,
)

CURRENCY_RUB = "RUB"


class RobokassaConfigError(RuntimeError):
    pass


class RobokassaSignatureError(RuntimeError):
    pass


def format_amount(value: str | Decimal) -> str:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be positive")
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _required_config() -> tuple[str, str, str]:
    if not ROBOKASSA_MERCHANT_LOGIN or not ROBOKASSA_PASSWORD1 or not ROBOKASSA_PASSWORD2:
        raise RobokassaConfigError(
            "ROBOKASSA_MERCHANT_LOGIN/ROBOKASSA_PASSWORD1/ROBOKASSA_PASSWORD2 are not configured"
        )
    return ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD1, ROBOKASSA_PASSWORD2


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _shp_pairs(params: dict[str, str]) -> list[tuple[str, str]]:
    return sorted((key, value) for key, value in params.items() if key.startswith("Shp_"))


def _shp_signature_tail(params: dict[str, str]) -> str:
    pairs = _shp_pairs(params)
    if not pairs:
        return ""
    return ":" + ":".join(f"{key}={value}" for key, value in pairs)


def build_payment_url(
    *,
    amount_rub: str,
    invoice_id: int,
    preorder_id: str | None = None,
    payment_id: str | None = None,
    email: str | None = None,
    description: str,
) -> str:
    merchant_login, password1, _ = _required_config()
    amount = format_amount(amount_rub)
    shp_params = {}
    if preorder_id:
        shp_params["Shp_preorder_id"] = preorder_id
    if payment_id:
        shp_params["Shp_payment_id"] = payment_id
    if not shp_params:
        raise ValueError("preorder_id or payment_id is required")
    signature = _md5(
        f"{merchant_login}:{amount}:{invoice_id}:{password1}{_shp_signature_tail(shp_params)}"
    )
    query = {
        "MerchantLogin": merchant_login,
        "OutSum": amount,
        "InvId": str(invoice_id),
        "Description": description,
        "Culture": "ru",
        "SignatureValue": signature,
        **shp_params,
    }
    if email:
        query["Email"] = email
    if ROBOKASSA_IS_TEST:
        query["IsTest"] = "1"
    return f"{ROBOKASSA_PAYMENT_URL}?{urlencode(query)}"


def verify_result_signature(params: dict[str, str]) -> None:
    _, _, password2 = _required_config()
    out_sum = params.get("OutSum")
    inv_id = params.get("InvId") or params.get("InvID")
    signature = params.get("SignatureValue", "").lower()
    if not out_sum or not inv_id or not signature:
        raise RobokassaSignatureError("ResultURL params are incomplete")
    expected = _md5(f"{out_sum}:{inv_id}:{password2}{_shp_signature_tail(params)}").lower()
    if signature != expected:
        raise RobokassaSignatureError("ResultURL signature mismatch")
