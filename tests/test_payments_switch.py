from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_create_topup_respects_payments_enabled_flag(monkeypatch):
    from src import payments_api

    monkeypatch.setattr(payments_api, "PAYMENTS_ENABLED", False)
    response = client.post(
        "/payments/topups",
        json={
            "amount_rub": "200.00",
            "pricing_version": "2026-06-balance-v1",
            "source_screen": "cabinet_quick_amount",
            "email": "test@example.com",
            "telegram_user_id": 123456789,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Payments are temporarily disabled"
