import asyncio
import hashlib
import json
from datetime import datetime

import asyncpg
import pytest
from fastapi.testclient import TestClient

from src import auth, payments_api
from src.main import app
from src.payments_service import (
    PaymentConfigError,
    PaymentNotFoundError,
    TopUpIntent,
    build_payment_url,
    calculate_topup_credits,
    create_topup_payment,
    get_payment_status_by_invoice,
    get_starter_grant_for_user,
    normalize_amount_rub,
    serialize_payment_row,
    verify_result_signature,
)

client = TestClient(app)


def test_calculate_topup_credits_matches_frontend_tiers():
    assert calculate_topup_credits(normalize_amount_rub("100.00")) == 3
    assert calculate_topup_credits(normalize_amount_rub("200.00")) == 7
    assert calculate_topup_credits(normalize_amount_rub("500.00")) == 20
    assert calculate_topup_credits(normalize_amount_rub("1000.00")) == 45


def test_create_topup_rejects_invalid_email_before_db():
    response = client.post(
        "/payments/topups",
        json={
            "amount_rub": "200.00",
            "pricing_version": "2026-06-balance-v1",
            "source_screen": "cabinet_quick_amount",
            "email": "not-an-email",
            "telegram_user_id": 123456789,
        },
    )
    assert response.status_code == 422


def test_cabinet_requires_identity_before_db():
    response = client.get("/payments/cabinet")
    assert response.status_code == 400


def test_robokassa_result_requires_required_params_before_db():
    response = client.get("/payments/robokassa/result")
    assert response.status_code == 400


def test_serialize_payment_row_includes_receipt_email():
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "invoice_id": 42,
        "status": "paid",
        "amount_rub": 500,
        "credits_granted": 20,
        "receipt_email": "user@example.com",
        "pricing_version": "credits-v1",
        "created_at": datetime(2026, 6, 19, 9, 0, 0),
        "paid_at": datetime(2026, 6, 19, 9, 1, 0),
        "failed_at": None,
        "updated_at": datetime(2026, 6, 19, 9, 1, 0),
    }

    payload = serialize_payment_row(row)

    assert payload["receipt_email"] == "user@example.com"
    assert payload["confirmation_url"] is None


def test_serialize_payment_row_keeps_confirmation_url_for_pending_invoice():
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "invoice_id": 42,
        "status": "pending",
        "amount_rub": 500,
        "credits_granted": 20,
        "receipt_email": "user@example.com",
        "pricing_version": "credits-v1",
        "source_screen": "cabinet",
        "provider_payment_id": "payment-42",
        "created_at": datetime(2026, 6, 19, 9, 0, 0),
        "paid_at": None,
        "failed_at": None,
        "updated_at": datetime(2026, 6, 19, 9, 1, 0),
    }

    payload = serialize_payment_row(row, confirmation_url="https://stage.example/pay?resume=1")

    assert payload["confirmation_url"] == "https://stage.example/pay?resume=1"


def test_get_starter_grant_for_user_returns_trial_grant_payload():
    class FakeConn:
        async def fetchrow(self, *_args, **_kwargs):
            return {
                "credits_delta": 3,
                "created_at": datetime(2026, 6, 19, 9, 0, 0),
            }

    payload = asyncio.run(get_starter_grant_for_user(FakeConn(), user_id=123))

    assert payload == {"credits": 3, "created_at": "2026-06-19T09:00:00"}


def test_get_starter_grant_for_user_falls_back_to_legacy_delta_columns():
    class FakeConn:
        def __init__(self) -> None:
            self.calls = 0

        async def fetchrow(self, query, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise asyncpg.UndefinedColumnError("event_type missing")
            assert "delta_credits AS credits_delta" in query
            return {
                "credits_delta": 3,
                "created_at": datetime(2026, 6, 19, 9, 0, 0),
            }

    payload = asyncio.run(get_starter_grant_for_user(FakeConn(), user_id=123))

    assert payload == {"credits": 3, "created_at": "2026-06-19T09:00:00"}


def test_get_starter_grant_legacy_fallback_does_not_match_any_manual_adjustment():
    class FakeConn:
        def __init__(self) -> None:
            self.calls = 0

        async def fetchrow(self, query, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise asyncpg.UndefinedColumnError("event_type missing")
            assert "metadata->>'kind' = 'starter_grant'" in query
            assert "operation_type = 'manual_adjustment'" not in query
            return None

    payload = asyncio.run(get_starter_grant_for_user(FakeConn(), user_id=123))

    assert payload is None


def test_create_topup_requires_init_data_when_dev_auth_disabled():
    response = client.post(
        "/payments/topups",
        json={
            "amount_rub": "200.00",
            "pricing_version": "2026-06-balance-v1",
            "source_screen": "cabinet_quick_amount",
            "email": "user@example.com",
            "telegram_user_id": 123456789,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "initData required"


def test_payment_status_requires_init_data_when_dev_auth_disabled():
    response = client.get("/payments/42/status", params={"telegram_user_id": 123456789})
    assert response.status_code == 401
    assert response.json()["detail"] == "initData required"


def test_raw_telegram_user_id_is_allowed_with_dev_auth(monkeypatch):
    monkeypatch.setattr(auth, "WEBAPP_DEV_AUTH_ENABLED", True)

    resolved = auth.resolve_telegram_auth(
        init_data=None,
        telegram_user_id=123456789,
        auth_name="payments",
    )

    assert resolved.telegram_user_id == 123456789
    assert resolved.username is None
    assert resolved.auth_channel == "dev_fallback"


def test_payment_status_is_scoped_to_resolved_user(monkeypatch):
    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTransaction()

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    async def fake_ensure_user(_conn, telegram_user_id: int, username: str | None):
        assert telegram_user_id == 123456789
        assert username == "dw-user"
        return 77

    async def fake_get_status(_conn, *, invoice_id: int, user_id: int | None = None):
        assert invoice_id == 42
        assert user_id == 77
        return {"invoice_id": 42, "status": "pending", "balance": 3}

    monkeypatch.setattr(
        payments_api,
        "resolve_telegram_auth",
        lambda **_kwargs: auth.AuthContext(
            telegram_user_id=123456789,
            username="dw-user",
            auth_channel="mini_app",
            auth_date=1700000000,
        ),
    )
    monkeypatch.setattr(payments_api.db, "get_pool", lambda: FakePool())
    monkeypatch.setattr(payments_api, "ensure_user", fake_ensure_user)
    monkeypatch.setattr(payments_api, "get_payment_status_by_invoice", fake_get_status)

    response = client.get("/payments/42/status")
    assert response.status_code == 200
    assert response.json() == {"invoice_id": 42, "status": "pending", "balance": 3}


def test_payment_status_lookup_rejects_non_owner():
    class FakeConn:
        async def fetchrow(self, query: str, *args):
            assert "AND p.user_id = $2" in query
            assert args == (42, 77)
            return None

    with pytest.raises(PaymentNotFoundError):
        asyncio.run(get_payment_status_by_invoice(FakeConn(), invoice_id=42, user_id=77))


def test_create_topup_persists_robokassa_provider_neutral_fields(monkeypatch):
    monkeypatch.setattr(
        "src.payments_service.uuid.uuid4",
        lambda: "00000000-0000-0000-0000-000000000001",
    )
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PAYMENT_URL", "https://stage.example/pay")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD1", "live-password1")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD2", "live-password2")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_IS_TEST", False)

    class FakeConn:
        async def fetchrow(self, query: str, *args):
            expected_columns = [
                "provider",
                "provider_payment_id",
                "provider_invoice_payload",
                "currency",
                "amount_provider_units",
                "delivery_channel",
            ]
            for column in expected_columns:
                assert column in query
            assert args[:9] == (
                77,
                "robokassa",
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000001",
                "RUB",
                20000,
                normalize_amount_rub("200.00"),
                7,
                "user@example.com",
            )
            assert json.loads(args[9]) == {
                "items": [
                    {
                        "name": "Dream Wheels AI credits (7)",
                        "quantity": 1,
                        "sum": 200.0,
                        "tax": "none",
                    }
                ],
                "email": "user@example.com",
            }
            assert args[10:13] == (
                "credits-v1",
                "cabinet",
                "website",
            )
            return {
                "id": "11111111-1111-1111-1111-111111111111",
                "invoice_id": 42,
                "amount_rub": normalize_amount_rub("200.00"),
                "credits_granted": 7,
                "pricing_version": "credits-v1",
            }

    payload = asyncio.run(
        create_topup_payment(
            FakeConn(),
            user_id=77,
            intent=TopUpIntent(
                amount_rub=normalize_amount_rub("200.00"),
                pricing_version="credits-v1",
                source_screen="cabinet",
                receipt_email="user@example.com",
            ),
        )
    )

    assert payload["invoice_id"] == 42
    assert payload["amount"] == 200.0
    assert payload["credits_granted"] == 7
    assert "Shp_payment_id=00000000-0000-0000-0000-000000000001" in payload["payment_url"]


def test_build_payment_url_uses_configured_payment_url(monkeypatch):
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PAYMENT_URL", "https://stage.example/pay")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD1", "live-password1")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD2", "live-password2")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_IS_TEST", False)

    url = build_payment_url(
        invoice_id=7,
        payment_id="payment-7",
        intent=TopUpIntent(
            amount_rub=normalize_amount_rub("200.00"),
            pricing_version="credits-v1",
            source_screen="cabinet",
            receipt_email="user@example.com",
        ),
    )

    assert url.startswith("https://stage.example/pay?")


def test_build_payment_url_requires_test_credentials_in_test_mode(monkeypatch):
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PAYMENT_URL", "https://stage.example/pay")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD1", "live-password1")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD2", "live-password2")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_TEST_PASSWORD1", "")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_TEST_PASSWORD2", "")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_IS_TEST", True)

    with pytest.raises(PaymentConfigError, match="test credentials"):
        build_payment_url(
            invoice_id=7,
            payment_id="payment-7",
            intent=TopUpIntent(
                amount_rub=normalize_amount_rub("200.00"),
                pricing_version="credits-v1",
                source_screen="cabinet",
                receipt_email="user@example.com",
            ),
        )


def test_verify_result_signature_rejects_mode_mismatch(monkeypatch):
    monkeypatch.setattr("src.payments_service.ROBOKASSA_IS_TEST", False)
    monkeypatch.setattr("src.payments_service.ROBOKASSA_PASSWORD2", "live-password2")

    assert (
        verify_result_signature(
            out_sum="200.00",
            invoice_id=42,
            signature_value="anything",
            payment_id="payment-42",
            is_test=True,
        )
        is False
    )


def test_verify_result_signature_accepts_test_mode_without_is_test_flag(monkeypatch):
    monkeypatch.setattr("src.payments_service.ROBOKASSA_IS_TEST", True)
    monkeypatch.setattr("src.payments_service.ROBOKASSA_TEST_PASSWORD1", "test-password1")
    monkeypatch.setattr("src.payments_service.ROBOKASSA_TEST_PASSWORD2", "test-password2")

    signature = hashlib.md5(b"200.00:42:test-password2:Shp_payment_id=payment-42").hexdigest()

    assert (
        verify_result_signature(
            out_sum="200.00",
            invoice_id=42,
            signature_value=signature,
            payment_id="payment-42",
            is_test=None,
        )
        is True
    )
