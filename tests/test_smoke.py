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
