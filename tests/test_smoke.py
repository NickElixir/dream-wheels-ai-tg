"""Smoke-тесты: приложение импортируется и базовые ручки отвечают.

Не используем TestClient как context-manager — иначе lifespan попытается
поднять реальный пул к Postgres/Redis. Для smoke достаточно проверить
роутинг и Pydantic-валидацию.
"""

from fastapi.testclient import TestClient

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


def test_preorder_rejects_invalid_email():
    """Email валидируется до флага PAYMENTS_ENABLED и похода в БД."""
    r = client.post("/payments/preorders", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_preorder_returns_disabled_when_payments_off():
    """По умолчанию платежи выключены, чтобы случайно не открыть прием денег."""
    r = client.post("/payments/preorders", json={"email": "user@example.com"})
    assert r.status_code == 503
    assert r.json()["detail"] == "payments disabled"


def test_topup_rejects_amount_below_minimum():
    """Сумма валидируется до флага PAYMENTS_ENABLED и похода в БД."""
    r = client.post(
        "/payments/topups",
        json={"amount_rub": "99.00", "telegram_user_id": 1},
    )
    assert r.status_code == 422


def test_topup_returns_disabled_when_payments_off():
    """Новый contract тоже закрыт флагом PAYMENTS_ENABLED по умолчанию."""
    r = client.post(
        "/payments/topups",
        json={"amount_rub": "200.00", "telegram_user_id": 1, "source_screen": "cabinet"},
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "payments disabled"


def test_robokassa_result_accepts_get_method():
    """ResultURL в кабинете Robokassa может быть настроен как GET."""
    r = client.get("/payments/robokassa/result")
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid payment signature"


def test_payment_cabinet_requires_telegram_identity():
    """Кабинет не ходит в БД без Telegram identity."""
    r = client.get("/payments/cabinet")
    assert r.status_code == 422
    assert r.json()["detail"] == "init_data or telegram_user_id is required"
