"""Robokassa payment provider adapter."""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode

from src.payments.providers.base import ProviderInvoice

logger = logging.getLogger(__name__)


class RobokassaProviderConfigError(Exception):
    """Robokassa provider configuration is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class RobokassaConfig:
    merchant_login: str
    password1: str
    password2: str
    test_password1: str
    test_password2: str
    payment_url: str
    hash_algo: str
    is_test: bool


@dataclass(frozen=True, slots=True)
class RobokassaTopUpIntent:
    amount_rub: Decimal
    credits_granted: int
    receipt_email: str


class RobokassaPaymentProvider:
    provider = "robokassa"

    def __init__(self, config: RobokassaConfig) -> None:
        self._config = config

    def build_topup_invoice(
        self,
        *,
        invoice_id: int,
        payment_id: str,
        intent: RobokassaTopUpIntent,
    ) -> ProviderInvoice:
        self._require_payment_config(is_test=self._config.is_test)
        password1, _ = self._active_passwords(is_test=self._config.is_test)
        receipt_payload = self.receipt_payload(intent)
        receipt_json = json.dumps(receipt_payload, ensure_ascii=False, separators=(",", ":"))
        encoded_receipt = quote(receipt_json, safe="")
        signature_parts = [
            self._config.merchant_login,
            f"{intent.amount_rub:.2f}",
            str(invoice_id),
            receipt_json,
            password1,
            f"Shp_payment_id={payment_id}",
        ]
        signature_value = self._digest(":".join(signature_parts))

        params = {
            "MerchantLogin": self._config.merchant_login,
            "OutSum": f"{intent.amount_rub:.2f}",
            "InvId": str(invoice_id),
            "Description": "Dream Wheels AI credits",
            "Email": intent.receipt_email,
            "Shp_payment_id": payment_id,
            "SignatureValue": signature_value,
        }
        if self._config.is_test:
            params["IsTest"] = "1"
        query_string = urlencode(params)
        query_string += f"&Receipt={encoded_receipt}"
        return ProviderInvoice(
            provider=self.provider,
            provider_invoice_payload=payment_id,
            confirmation_url=f"{self._config.payment_url}?{query_string}",
            metadata={"receipt_payload": receipt_payload},
        )

    def verify_result_signature(
        self,
        *,
        out_sum: str,
        invoice_id: int,
        signature_value: str,
        payment_id: str,
        is_test: bool | None,
    ) -> bool:
        if is_test is not None and is_test != self._config.is_test:
            logger.warning(
                "❌ Robokassa callback mode mismatch invoice_id=%s callback_is_test=%s env_is_test=%s",
                invoice_id,
                is_test,
                self._config.is_test,
            )
            return False
        try:
            _, password2 = self._active_passwords(is_test=self._config.is_test)
        except RobokassaProviderConfigError:
            logger.warning(
                "❌ Robokassa callback rejected because credentials are not configured for is_test=%s",
                is_test,
            )
            return False
        expected_parts = [
            out_sum,
            str(invoice_id),
            password2,
            f"Shp_payment_id={payment_id}",
        ]
        expected = self._digest(":".join(expected_parts))
        return hmac.compare_digest(expected.lower(), signature_value.lower())

    @staticmethod
    def receipt_payload(intent: RobokassaTopUpIntent) -> dict[str, Any]:
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

    def _digest(self, value: str) -> str:
        try:
            hasher = hashlib.new(self._config.hash_algo)
        except ValueError as exc:
            raise RobokassaProviderConfigError(
                f"Unsupported ROBOKASSA_HASH_ALGO={self._config.hash_algo}"
            ) from exc
        hasher.update(value.encode("utf-8"))
        return hasher.hexdigest()

    def _require_payment_config(self, *, is_test: bool | None = None) -> None:
        password1, password2 = self._active_passwords(is_test=is_test)
        if not self._config.merchant_login or not password1 or not password2:
            raise RobokassaProviderConfigError("Robokassa credentials are not configured")

    def _active_passwords(self, *, is_test: bool | None = None) -> tuple[str, str]:
        use_test_mode = self._config.is_test if is_test is None else is_test
        if use_test_mode:
            password1 = self._config.test_password1
            password2 = self._config.test_password2
            mode = "test"
        else:
            password1 = self._config.password1
            password2 = self._config.password2
            mode = "live"
        if not password1 or not password2:
            raise RobokassaProviderConfigError(f"Robokassa {mode} credentials are not configured")
        return password1, password2
