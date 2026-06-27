from fastapi.testclient import TestClient

from src import auth_api
from src.auth import AuthContext
from src.main import app

client = TestClient(app)


def test_telegram_login_nonce_returns_nonce_and_nonce_token(monkeypatch):
    monkeypatch.setattr(auth_api, "TELEGRAM_LOGIN_CLIENT_ID", "123456789")
    monkeypatch.setattr(
        auth_api,
        "build_website_login_nonce",
        lambda: {"nonce": "nonce-123", "nonce_token": "nonce-token-123"},
    )

    response = client.get("/auth/telegram/nonce")

    assert response.status_code == 200
    assert response.json() == {
        "client_id": "123456789",
        "nonce": "nonce-123",
        "nonce_token": "nonce-token-123",
    }


def test_telegram_login_nonce_requires_client_id(monkeypatch):
    monkeypatch.setattr(auth_api, "TELEGRAM_LOGIN_CLIENT_ID", "")

    response = client.get("/auth/telegram/nonce")

    assert response.status_code == 503
    assert response.json() == {"detail": "Telegram website login is not configured"}


def test_verify_id_token_returns_backend_bearer_token(monkeypatch):
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

    async def fake_verify(*, id_token: str, nonce_token: str | None):
        assert id_token == "telegram-id-token"
        assert nonce_token == "nonce-token-123"
        return AuthContext(
            telegram_user_id=123456789,
            username="dw-user",
            auth_channel="website",
            auth_date=1700000000,
        )

    async def fake_ensure_user(_conn, telegram_user_id: int, username: str | None):
        assert telegram_user_id == 123456789
        assert username == "dw-user"
        return 77

    monkeypatch.setattr(auth_api, "verify_telegram_login_id_token", fake_verify)
    monkeypatch.setattr(auth_api.db, "get_pool", lambda: FakePool())
    monkeypatch.setattr(auth_api, "ensure_user", fake_ensure_user)
    monkeypatch.setattr(auth_api, "issue_website_auth_token", lambda _ctx: "backend-token-123")
    monkeypatch.setattr(auth_api, "TELEGRAM_AUTH_TOKEN_TTL_SEC", 3600)

    response = client.post(
        "/auth/telegram/verify-id-token",
        json={
            "id_token": "telegram-id-token",
            "nonce_token": "nonce-token-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "backend-token-123",
        "token_type": "Bearer",
        "expires_in": 3600,
        "telegram_user_id": 123456789,
        "username": "dw-user",
    }
