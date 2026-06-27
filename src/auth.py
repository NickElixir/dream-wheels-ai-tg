"""Валидация Telegram WebApp initData через HMAC-SHA256.

Telegram передаёт в `window.Telegram.WebApp.initData` query-string с
параметрами юзера и подписью `hash`. Спека:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

Алгоритм:
1. Распарсить query-string в dict.
2. Извлечь поле `hash` (это подпись).
3. Остальные пары `key=value` отсортировать по ключу, склеить через '\n'
   → data_check_string.
4. secret_key = HMAC_SHA256(key="WebAppData", message=BOT_TOKEN)
5. expected_hash = HMAC_SHA256(key=secret_key, message=data_check_string)
6. Сравнить с переданным hash через `hmac.compare_digest` (constant-time).

Если совпало — данные подлинные, поле `user` — JSON с реальными данными
Telegram-юзера (не подделка от клиента).
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qsl

import httpx
from fastapi import HTTPException
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer
from joserfc import jwt
from joserfc.jwk import KeySet

from src.config import (
    BOT_TOKEN,
    TELEGRAM_AUTH_TOKEN_SECRET,
    TELEGRAM_AUTH_TOKEN_TTL_SEC,
    TELEGRAM_LOGIN_CLIENT_ID,
    TELEGRAM_LOGIN_ISSUER,
    TELEGRAM_LOGIN_JWKS_URL,
    TELEGRAM_LOGIN_NONCE_TTL_SEC,
    WEBAPP_DEV_AUTH_ENABLED,
)

logger = logging.getLogger(__name__)

# initData считается просроченным через 24 часа.
INIT_DATA_MAX_AGE_SEC = 24 * 60 * 60


class InitDataInvalid(Exception):
    """initData не прошёл проверку: подделка, истёк или сломан."""


@dataclass(slots=True)
class AuthContext:
    """Нормализованный Telegram auth context для HTTP handlers."""

    telegram_user_id: int
    username: str | None
    auth_channel: Literal["mini_app", "website", "dev_fallback"]
    auth_date: int | None = None


class WebsiteAuthInvalid(Exception):
    """Website auth token, nonce, или Telegram id_token не прошли проверку."""


_JWKS_CACHE: KeySet | None = None
_JWKS_CACHE_EXPIRES_AT = 0.0
_JWKS_CACHE_TTL_SEC = 300
_WEBSITE_NONCE_SALT = "telegram-login-nonce"
_WEBSITE_AUTH_TOKEN_SALT = "telegram-auth-token"


def _sha256_prefix(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:length]


def get_init_data_debug_context(init_data: str, *, bot_token: str | None = None) -> dict:
    """Безопасный debug-контекст для диагностики initData без утечки секрета."""
    token = bot_token if bot_token is not None else BOT_TOKEN
    if not init_data:
        return {"init_data_len": 0, "has_hash": False, "has_signature": False}

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    raw_pairs = dict(pairs)
    received_hash = raw_pairs.get("hash")
    raw_signature = raw_pairs.get("signature")
    auth_date_raw = raw_pairs.get("auth_date")
    raw_user = raw_pairs.get("user")

    user_id = None
    username = None
    if raw_user:
        try:
            parsed_user = json.loads(raw_user)
            if isinstance(parsed_user, dict):
                if parsed_user.get("id") is not None:
                    user_id = int(parsed_user["id"])
                username_raw = parsed_user.get("username")
                username = username_raw if isinstance(username_raw, str) else None
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    with_signature_pairs = {k: v for k, v in raw_pairs.items() if k != "hash"}
    without_signature_pairs = {k: v for k, v in raw_pairs.items() if k not in {"hash", "signature"}}

    without_signature_dcs = "\n".join(
        f"{k}={without_signature_pairs[k]}" for k in sorted(without_signature_pairs)
    )
    with_signature_dcs = "\n".join(
        f"{k}={with_signature_pairs[k]}" for k in sorted(with_signature_pairs)
    )

    token_fingerprint = _sha256_prefix(token) if token else "missing"
    expected_without_signature = None
    expected_with_signature = None
    if token:
        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        expected_without_signature = hmac.new(
            secret_key, without_signature_dcs.encode(), hashlib.sha256
        ).hexdigest()
        expected_with_signature = hmac.new(
            secret_key, with_signature_dcs.encode(), hashlib.sha256
        ).hexdigest()

    auth_age_sec = None
    if auth_date_raw:
        try:
            auth_age_sec = int(time.time()) - int(auth_date_raw)
        except ValueError:
            auth_age_sec = None

    return {
        "init_data_len": len(init_data),
        "keys": sorted(raw_pairs.keys()),
        "has_hash": received_hash is not None,
        "has_signature": raw_signature is not None,
        "hash_prefix": (received_hash or "")[:10],
        "signature_prefix": (raw_signature or "")[:10],
        "user_id": user_id,
        "username": username,
        "auth_date": auth_date_raw,
        "auth_age_sec": auth_age_sec,
        "query_id_prefix": str(raw_pairs.get("query_id") or "")[:14],
        "chat_type": raw_pairs.get("chat_type"),
        "chat_instance_prefix": str(raw_pairs.get("chat_instance") or "")[:14],
        "dcs_without_signature_sha": _sha256_prefix(without_signature_dcs)
        if without_signature_dcs
        else "",
        "dcs_with_signature_sha": _sha256_prefix(with_signature_dcs) if with_signature_dcs else "",
        "expected_hash_prefix": (expected_without_signature or "")[:10],
        "expected_with_signature_prefix": (expected_with_signature or "")[:10],
        "matches_without_signature": bool(
            received_hash and expected_without_signature == received_hash
        ),
        "matches_with_signature": bool(received_hash and expected_with_signature == received_hash),
        "bot_token_fingerprint": token_fingerprint,
    }


def parse_init_data(init_data: str, *, bot_token: str | None = None) -> dict:
    """Проверяет HMAC-подпись initData и возвращает распарсенные поля.

    Поле `user` декодируется из JSON в dict.

    Raises:
        InitDataInvalid: подпись не совпала, отсутствует hash, истёк auth_date,
        или BOT_TOKEN не сконфигурирован.
    """
    token = bot_token if bot_token is not None else BOT_TOKEN
    if not token:
        raise InitDataInvalid("BOT_TOKEN не сконфигурирован")

    if not init_data:
        raise InitDataInvalid("Пустой initData")

    # parse_qsl сохраняет порядок и не дедуплицирует, но для initData ключи
    # уникальны — превращаем сразу в dict.
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataInvalid("В initData нет поля hash")

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))

    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        logger.warning(
            "⛔ initData HMAC mismatch debug=%s",
            get_init_data_debug_context(init_data, bot_token=token),
        )
        raise InitDataInvalid("HMAC подпись не совпала")

    auth_date_raw = pairs.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError as exc:
            raise InitDataInvalid(f"auth_date не число: {auth_date_raw}") from exc
        age = int(time.time()) - auth_date
        if age > INIT_DATA_MAX_AGE_SEC:
            raise InitDataInvalid(f"initData истёк ({age}s > {INIT_DATA_MAX_AGE_SEC}s)")

    if "user" in pairs:
        try:
            pairs["user"] = json.loads(pairs["user"])
        except json.JSONDecodeError as exc:
            raise InitDataInvalid(f"user не валидный JSON: {exc}") from exc

    return pairs


def get_telegram_user_id(init_data: str) -> int:
    """Кратчайший путь: вернуть telegram_user_id из проверенного initData."""
    parsed = parse_init_data(init_data)
    user = parsed.get("user")
    if not user or "id" not in user:
        raise InitDataInvalid("В initData нет user.id")
    return int(user["id"])


def _require_website_auth_secret() -> str:
    if not TELEGRAM_AUTH_TOKEN_SECRET:
        raise WebsiteAuthInvalid("TELEGRAM_AUTH_TOKEN_SECRET is not configured")
    return TELEGRAM_AUTH_TOKEN_SECRET


def _website_serializer(*, salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_require_website_auth_secret(), salt=salt)


def _decode_timed_payload(*, token: str, salt: str, max_age: int) -> dict:
    serializer = _website_serializer(salt=salt)
    try:
        payload = serializer.loads(token, max_age=max_age)
    except (BadSignature, BadTimeSignature) as exc:
        raise WebsiteAuthInvalid("Invalid or expired auth token") from exc
    if not isinstance(payload, dict):
        raise WebsiteAuthInvalid("Invalid auth token payload")
    return payload


def build_website_login_nonce() -> dict[str, str]:
    nonce = secrets.token_urlsafe(24)
    serializer = _website_serializer(salt=_WEBSITE_NONCE_SALT)
    nonce_token = serializer.dumps({"nonce": nonce})
    return {"nonce": nonce, "nonce_token": nonce_token}


def issue_website_auth_token(auth_context: AuthContext) -> str:
    serializer = _website_serializer(salt=_WEBSITE_AUTH_TOKEN_SALT)
    return serializer.dumps(
        {
            "telegram_user_id": auth_context.telegram_user_id,
            "username": auth_context.username,
            "auth_channel": "website",
            "auth_date": auth_context.auth_date,
        }
    )


def verify_website_auth_token(token: str) -> AuthContext:
    payload = _decode_timed_payload(
        token=token,
        salt=_WEBSITE_AUTH_TOKEN_SALT,
        max_age=TELEGRAM_AUTH_TOKEN_TTL_SEC,
    )
    telegram_user_id = payload.get("telegram_user_id")
    if telegram_user_id is None:
        raise WebsiteAuthInvalid("Missing telegram_user_id in auth token")
    username = payload.get("username")
    auth_date = payload.get("auth_date")
    return AuthContext(
        telegram_user_id=int(telegram_user_id),
        username=username if isinstance(username, str) else None,
        auth_channel="website",
        auth_date=int(auth_date) if auth_date is not None else None,
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return token.strip()


def _validate_website_nonce(*, nonce_token: str | None, token_nonce: object) -> None:
    if not nonce_token:
        raise WebsiteAuthInvalid("Missing nonce_token")
    if not isinstance(token_nonce, str) or not token_nonce:
        raise WebsiteAuthInvalid("Missing nonce claim")
    payload = _decode_timed_payload(
        token=nonce_token,
        salt=_WEBSITE_NONCE_SALT,
        max_age=TELEGRAM_LOGIN_NONCE_TTL_SEC,
    )
    expected_nonce = payload.get("nonce")
    if expected_nonce != token_nonce:
        raise WebsiteAuthInvalid("Nonce mismatch")


async def _get_telegram_jwks() -> KeySet:
    global _JWKS_CACHE, _JWKS_CACHE_EXPIRES_AT

    now = time.time()
    if _JWKS_CACHE is not None and now < _JWKS_CACHE_EXPIRES_AT:
        return _JWKS_CACHE

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(TELEGRAM_LOGIN_JWKS_URL)
        response.raise_for_status()
        jwks = response.json()

    _JWKS_CACHE = KeySet.import_key_set(jwks)
    _JWKS_CACHE_EXPIRES_AT = now + _JWKS_CACHE_TTL_SEC
    return _JWKS_CACHE


async def verify_telegram_login_id_token(
    *,
    id_token: str,
    nonce_token: str | None,
) -> AuthContext:
    if not TELEGRAM_LOGIN_CLIENT_ID:
        raise WebsiteAuthInvalid("TELEGRAM_LOGIN_CLIENT_ID is not configured")

    key_set = await _get_telegram_jwks()
    try:
        token = jwt.decode(id_token, key_set, algorithms=["RS256"])
    except Exception as exc:
        raise WebsiteAuthInvalid("Invalid Telegram id_token signature") from exc

    claims = token.claims
    now = int(time.time())
    issuer = claims.get("iss")
    audience = str(claims.get("aud") or "")
    if issuer != TELEGRAM_LOGIN_ISSUER:
        raise WebsiteAuthInvalid("Invalid Telegram issuer")
    if audience != TELEGRAM_LOGIN_CLIENT_ID:
        raise WebsiteAuthInvalid("Invalid Telegram audience")

    exp = claims.get("exp")
    iat = claims.get("iat")
    if not isinstance(exp, int) or exp < now:
        raise WebsiteAuthInvalid("Expired Telegram id_token")
    if not isinstance(iat, int) or iat > now + 60:
        raise WebsiteAuthInvalid("Invalid Telegram iat")

    _validate_website_nonce(nonce_token=nonce_token, token_nonce=claims.get("nonce"))

    telegram_user_id = claims.get("id")
    if telegram_user_id is None:
        raise WebsiteAuthInvalid("Telegram id_token missing user id")

    username = claims.get("preferred_username")
    return AuthContext(
        telegram_user_id=int(telegram_user_id),
        username=username if isinstance(username, str) else None,
        auth_channel="website",
        auth_date=iat,
    )


def auth_context_from_init_data(init_data: str) -> AuthContext:
    """Построить auth context из валидного Telegram Mini App initData."""
    parsed = parse_init_data(init_data)
    user = parsed.get("user") or {}
    telegram_user_id = user.get("id")
    if not telegram_user_id:
        raise InitDataInvalid("В initData нет user.id")
    username_raw = user.get("username")
    auth_date_raw = parsed.get("auth_date")
    auth_date = int(auth_date_raw) if auth_date_raw is not None else None
    return AuthContext(
        telegram_user_id=int(telegram_user_id),
        username=username_raw if isinstance(username_raw, str) else None,
        auth_channel="mini_app",
        auth_date=auth_date,
    )


def resolve_telegram_auth(
    *,
    init_data: str | None,
    telegram_user_id: int | None,
    authorization: str | None = None,
    auth_name: str,
) -> AuthContext:
    """Единая auth boundary для Mini App и staging/dev fallback.

    - Mini App: валидируем initData и возвращаем нормализованный context.
    - Website: принимаем backend-issued Bearer token.
    - Dev fallback: разрешён только при WEBAPP_DEV_AUTH_ENABLED.
    """
    website_bearer = _extract_bearer_token(authorization)
    if website_bearer:
        try:
            return verify_website_auth_token(website_bearer)
        except WebsiteAuthInvalid as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    if init_data:
        try:
            return auth_context_from_init_data(init_data)
        except InitDataInvalid as exc:
            if WEBAPP_DEV_AUTH_ENABLED and telegram_user_id is not None:
                logger.warning(
                    "⚠️ WEBAPP_DEV_AUTH_ENABLED fallback in %s: "
                    "tg_user=%s accepted without valid initData (%s)",
                    auth_name,
                    telegram_user_id,
                    exc,
                )
                return AuthContext(
                    telegram_user_id=int(telegram_user_id),
                    username=None,
                    auth_channel="dev_fallback",
                )
            logger.warning(
                "⛔ %s auth failed reason=%s debug=%s",
                auth_name,
                exc,
                get_init_data_debug_context(init_data),
            )
            raise HTTPException(status_code=401, detail=f"initData invalid: {exc}") from exc

    if telegram_user_id is None:
        raise HTTPException(status_code=400, detail="init_data or telegram_user_id is required")
    if not WEBAPP_DEV_AUTH_ENABLED:
        raise HTTPException(status_code=401, detail="initData required")
    return AuthContext(
        telegram_user_id=int(telegram_user_id),
        username=None,
        auth_channel="dev_fallback",
    )
