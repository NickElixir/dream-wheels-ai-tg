import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src import auth


def test_resolve_telegram_auth_requires_identity_when_missing():
    with pytest.raises(HTTPException) as exc_info:
        auth.resolve_telegram_auth(
            init_data=None,
            telegram_user_id=None,
            auth_name="payments",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "init_data or telegram_user_id is required"


def test_resolve_telegram_auth_rejects_raw_telegram_user_id_when_dev_fallback_disabled(
    monkeypatch,
):
    monkeypatch.setattr(auth, "WEBAPP_DEV_AUTH_ENABLED", False)

    with pytest.raises(HTTPException) as exc_info:
        auth.resolve_telegram_auth(
            init_data=None,
            telegram_user_id=123456789,
            auth_name="payments",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "initData required"


def test_resolve_telegram_auth_returns_mini_app_context(monkeypatch):
    monkeypatch.setattr(
        auth,
        "auth_context_from_init_data",
        lambda _raw: auth.AuthContext(
            telegram_user_id=123456789,
            username="dw-user",
            auth_channel="mini_app",
            auth_date=1700000000,
        ),
    )

    resolved = auth.resolve_telegram_auth(
        init_data="query_id=abc",
        telegram_user_id=None,
        auth_name="payments",
    )

    assert resolved.telegram_user_id == 123456789
    assert resolved.username == "dw-user"
    assert resolved.auth_channel == "mini_app"
    assert resolved.auth_date == 1700000000


def test_issue_and_verify_website_auth_token(monkeypatch):
    monkeypatch.setattr(auth, "TELEGRAM_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setattr(auth, "TELEGRAM_AUTH_TOKEN_TTL_SEC", 3600)

    token = auth.issue_website_auth_token(
        auth.AuthContext(
            telegram_user_id=123456789,
            username="dw-user",
            auth_channel="website",
            auth_date=1700000000,
        )
    )

    resolved = auth.verify_website_auth_token(token)

    assert resolved.telegram_user_id == 123456789
    assert resolved.username == "dw-user"
    assert resolved.auth_channel == "website"
    assert resolved.auth_date == 1700000000


def test_resolve_telegram_auth_accepts_bearer_token(monkeypatch):
    monkeypatch.setattr(
        auth,
        "verify_website_auth_token",
        lambda _token: auth.AuthContext(
            telegram_user_id=123456789,
            username="site-user",
            auth_channel="website",
            auth_date=1700000000,
        ),
    )

    resolved = auth.resolve_telegram_auth(
        init_data=None,
        telegram_user_id=None,
        authorization="Bearer website-token",
        auth_name="payments",
    )

    assert resolved.telegram_user_id == 123456789
    assert resolved.username == "site-user"
    assert resolved.auth_channel == "website"


def test_verify_telegram_login_id_token_accepts_valid_claims(monkeypatch):
    monkeypatch.setattr(auth, "TELEGRAM_LOGIN_CLIENT_ID", "123456789")
    monkeypatch.setattr(auth, "TELEGRAM_LOGIN_ISSUER", "https://oauth.telegram.org")
    monkeypatch.setattr(auth, "TELEGRAM_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setattr(auth.time, "time", lambda: 1_700_000_000)

    nonce = auth.build_website_login_nonce()
    claims = {
        "iss": "https://oauth.telegram.org",
        "aud": "123456789",
        "exp": 1_700_003_600,
        "iat": 1_700_000_000,
        "nonce": nonce["nonce"],
        "id": 987654321,
        "preferred_username": "dw-user",
    }

    async def fake_get_telegram_jwks():
        return SimpleNamespace()

    def fake_decode(_id_token, _key_set, algorithms):
        assert algorithms == ["RS256"]
        return SimpleNamespace(claims=claims)

    monkeypatch.setattr(auth, "_get_telegram_jwks", fake_get_telegram_jwks)
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    async def run_case():
        return await auth.verify_telegram_login_id_token(
            id_token="telegram-id-token",
            nonce_token=nonce["nonce_token"],
        )

    resolved = asyncio.run(run_case())

    assert resolved.telegram_user_id == 987654321
    assert resolved.username == "dw-user"
    assert resolved.auth_channel == "website"
    assert resolved.auth_date == 1_700_000_000


@pytest.mark.parametrize(
    ("mutate_claims", "expected_error"),
    [
        (
            lambda claims: claims.__setitem__("iss", "https://evil.example"),
            "Invalid Telegram issuer",
        ),
        (lambda claims: claims.__setitem__("aud", "wrong"), "Invalid Telegram audience"),
        (lambda claims: claims.__setitem__("exp", 1_699_999_999), "Expired Telegram id_token"),
        (lambda claims: claims.__setitem__("nonce", "wrong-nonce"), "Nonce mismatch"),
    ],
)
def test_verify_telegram_login_id_token_rejects_bad_claims(
    monkeypatch,
    mutate_claims,
    expected_error,
):
    monkeypatch.setattr(auth, "TELEGRAM_LOGIN_CLIENT_ID", "123456789")
    monkeypatch.setattr(auth, "TELEGRAM_LOGIN_ISSUER", "https://oauth.telegram.org")
    monkeypatch.setattr(auth, "TELEGRAM_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setattr(auth.time, "time", lambda: 1_700_000_000)

    nonce = auth.build_website_login_nonce()
    claims = {
        "iss": "https://oauth.telegram.org",
        "aud": "123456789",
        "exp": 1_700_003_600,
        "iat": 1_700_000_000,
        "nonce": nonce["nonce"],
        "id": 987654321,
    }
    mutate_claims(claims)

    async def fake_get_telegram_jwks():
        return SimpleNamespace()

    def fake_decode(_id_token, _key_set, algorithms):
        assert algorithms == ["RS256"]
        return SimpleNamespace(claims=claims)

    monkeypatch.setattr(auth, "_get_telegram_jwks", fake_get_telegram_jwks)
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    async def run_case():
        return await auth.verify_telegram_login_id_token(
            id_token="telegram-id-token",
            nonce_token=nonce["nonce_token"],
        )

    with pytest.raises(auth.WebsiteAuthInvalid, match=expected_error):
        asyncio.run(run_case())
