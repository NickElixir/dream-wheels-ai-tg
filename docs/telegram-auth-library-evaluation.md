# Telegram Auth Library Evaluation

Короткий ADR-style документ для следующего auth шага.

## Context

Проекту нужен единый Telegram auth boundary для двух каналов:

- Telegram Mini App (`initData`)
- website login через Telegram

На текущем этапе email/phone login вне scope.

## Decision

### Mini App auth

Пока сохраняем backend validation в коде проекта и усиливаем её тестами.

Причины:

- в текущем Python runtime нет готовой поддерживаемой зависимости для Mini App validation;
- текущая HMAC-валидация уже рабочая и понятная;
- переход на стороннюю библиотеку ради самой библиотеки сейчас не даёт достаточной выгоды.

Что проверить позже перед возможной заменой:

- активность поддержки библиотеки;
- прозрачность security model;
- поддержка `auth_date` freshness;
- поддержка third-party/public-key validation path.

Канонические источники:

- Telegram Mini Apps auth docs: https://core.telegram.org/bots/webapps
- Telegram Mini Apps init data docs: https://docs.telegram-mini-apps.com/platform/init-data

### Website Telegram login

Выбранный путь для website auth — официальный Telegram OIDC flow через `Authlib`.

Причины:

- Telegram официально поддерживает OIDC Authorization Code Flow с PKCE;
- это надёжнее и поддерживаемее, чем самописный website login протокол;
- OIDC лучше отделяет website auth от бизнес-логики payments/jobs.

Почему выбран `Authlib`:

- официальная документация Authlib покрывает Starlette/FastAPI OAuth/OIDC client flow;
- библиотека хорошо ложится на текущий `FastAPI + httpx` стек;
- можно валидировать Telegram `id_token` server-side и не строить самописный website auth протокол.

Что обязательно должно поддерживаться выбранной библиотекой:

- OIDC discovery;
- code exchange;
- JWKS fetching;
- ID token verification;
- validation claims: `iss`, `aud`, `exp`, `iat`, `nonce`;
- интеграция с FastAPI/ASGI без тяжёлой внешней auth-платформы.

Канонический источник:

- Telegram Login / OIDC docs: https://core.telegram.org/bots/telegram-login

## Current rollout decision

1. Сейчас централизуем Mini App/dev fallback auth boundary на текущем стеке.
2. Website Telegram login использует официальную Telegram Login JS library:
   - frontend получает server-generated `nonce` и публичный `client_id` от backend;
   - Telegram возвращает `id_token` только в callback библиотеки;
   - backend валидирует подпись и claims, затем выдаёт собственный short-lived bearer token;
   - bearer хранится в browser `sessionStorage`, не передаётся в URL и не сохраняется между вкладками.
3. `TELEGRAM_LOGIN_CLIENT_SECRET` зарезервирован для будущего Authorization Code Flow. Он не нужен текущей JS library и никогда не передаётся во frontend.
4. Полный authorization-code redirect flow имеет смысл добавлять вместе с website-domain/cookie strategy, если понадобится server-side session или сторонний identity broker.
