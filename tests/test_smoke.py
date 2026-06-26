"""Smoke-тесты: приложение импортируется и базовые ручки отвечают.

Не используем TestClient как context-manager — иначе lifespan попытается
поднять реальный пул к Postgres/Redis. Для smoke достаточно проверить
роутинг и Pydantic-валидацию.
"""

from fastapi.testclient import TestClient

from src.config import WEBAPP_URL
from src.main import app

client = TestClient(app)


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_returns_ok():
    r = client.get("/")
    assert r.status_code == 200


def test_create_job_validates_body():
    """Pydantic должен вернуть 422 на пустом теле — до похода в БД."""
    r = client.post("/jobs", json={})
    assert r.status_code == 422


def test_create_job_rejects_non_telegram_url():
    """car_url/wheel_url должны начинаться с https://api.telegram.org/file/."""
    r = client.post(
        "/jobs",
        json={
            "telegram_user_id": 1,
            "car_url": "https://evil.example.com/car.jpg",
            "wheel_url": "https://api.telegram.org/file/bot123/wheel.jpg",
        },
    )
    assert r.status_code == 422


def test_topup_rejects_invalid_email():
    """Email валидируется до auth и похода в БД."""
    r = client.post("/payments/topups", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_topup_rejects_amount_below_minimum():
    """Сумма валидируется до флага PAYMENTS_ENABLED и похода в БД."""
    r = client.post(
        "/payments/topups",
        json={"amount_rub": "99.00", "telegram_user_id": 1},
    )
    assert r.status_code == 422


def test_topup_requires_init_data_when_dev_auth_disabled():
    """Raw telegram_user_id недопустим без dev auth fallback."""
    r = client.post(
        "/payments/topups",
        json={
            "amount_rub": "200.00",
            "pricing_version": "credits-v1",
            "source_screen": "cabinet",
            "email": "user@example.com",
            "telegram_user_id": 1,
        },
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "initData required"


def test_feedback_rejects_invalid_vote_before_db():
    r = client.post(
        "/jobs/00000000-0000-4000-8000-000000000000/feedback",
        json={"vote": "meh"},
    )
    assert r.status_code == 422


def test_bot_feedback_requires_internal_auth_when_no_init_data():
    r = client.post(
        "/jobs/00000000-0000-4000-8000-000000000000/feedback",
        json={"vote": "like", "telegram_user_id": 1},
    )
    assert r.status_code in (401, 503)


def test_robokassa_result_accepts_get_method():
    """ResultURL в кабинете Robokassa может быть настроен как GET."""
    r = client.get("/payments/robokassa/result")
    assert r.status_code == 400
    assert r.json()["detail"] == "Missing Robokassa params"


def test_payment_cabinet_requires_telegram_identity():
    """Кабинет не ходит в БД без Telegram identity."""
    r = client.get("/payments/cabinet")
    assert r.status_code == 400
    assert r.json()["detail"] == "init_data or telegram_user_id is required"


def test_cors_allows_configured_webapp_origin():
    """Mini App origin из конфига должен иметь доступ к API."""
    r = client.options(
        "/payments/topups",
        headers={
            "Origin": WEBAPP_URL,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == WEBAPP_URL
