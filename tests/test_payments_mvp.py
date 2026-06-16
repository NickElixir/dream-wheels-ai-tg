from fastapi.testclient import TestClient

from src.main import app
from src.payments_service import calculate_topup_credits, normalize_amount_rub

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
