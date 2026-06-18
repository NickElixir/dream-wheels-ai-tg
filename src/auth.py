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
import time
from urllib.parse import parse_qsl

from src.config import BOT_TOKEN

logger = logging.getLogger(__name__)

# initData считается просроченным через 24 часа.
INIT_DATA_MAX_AGE_SEC = 24 * 60 * 60


class InitDataInvalid(Exception):
    """initData не прошёл проверку: подделка, истёк или сломан."""


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
    without_signature_pairs = {
        k: v for k, v in raw_pairs.items() if k not in {"hash", "signature"}
    }

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
        "dcs_with_signature_sha": _sha256_prefix(with_signature_dcs)
        if with_signature_dcs
        else "",
        "expected_hash_prefix": (expected_without_signature or "")[:10],
        "expected_with_signature_prefix": (expected_with_signature or "")[:10],
        "matches_without_signature": bool(
            received_hash and expected_without_signature == received_hash
        ),
        "matches_with_signature": bool(
            received_hash and expected_with_signature == received_hash
        ),
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
