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
