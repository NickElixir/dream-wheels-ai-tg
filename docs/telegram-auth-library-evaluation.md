# Telegram Auth Decision

Короткий decision note для website Telegram login и Mini App auth boundary.

## Context

Проекту нужен единый Telegram auth boundary для двух каналов:

- Telegram Mini App через `initData`
- website login через Telegram

Email/phone login сейчас вне scope.

## Decision

### Mini App

Оставляем текущую backend-валидацию `initData` в коде проекта.

Причины:

- поток уже рабочий и тестами покрыт;
- он не требует отдельного auth broker;
- текущая схема хорошо отделяет auth от business logic.

### Website

Для website используем текущий Telegram Login library flow:

- frontend получает `client_id` и server-generated `nonce`;
- Telegram возвращает `id_token`;
- backend валидирует `iss`, `aud`, `exp`, `iat`, `nonce`;
- backend выдаёт свой short-lived bearer token;
- bearer хранится в `sessionStorage` и используется для website requests.

Официальные источники:

- [Telegram Login / OIDC](https://core.telegram.org/bots/telegram-login)
- [Telegram Mini Apps auth](https://core.telegram.org/bots/webapps)

## Why not OIDC yet

OIDC Authorization Code Flow с `client_secret` сейчас не нужен.

Минусы OIDC для текущего этапа:

- больше интеграционной сложности;
- нужен redirect/callback UX вместо простого login callback;
- вероятнее придётся менять session/cookie strategy;
- добавляется лишний слой, который не улучшает текущий website flow с точки зрения продукта.

## Current Trade-offs

Telegram Login library flow имеет ограничения:

- он завязан на browser-side popup/callback UX;
- может конфликтовать с `Cross-Origin-Opener-Policy: same-origin`;
- хуже подходит для server-side sessions и SSO/broker сценариев;
- менее универсален, чем полный OIDC redirect flow.

Для Dream Wheels AI это приемлемо сейчас, потому что:

- website login уже работает;
- backend проверяет токен и claims;
- auth boundary уже отделен от payments/jobs;
- `TELEGRAM_LOGIN_CLIENT_SECRET` можно держать зарезервированным до момента, когда появится реальная потребность в OIDC.

## Revisit Triggers

Пересматриваем решение и переходим на OIDC, если появится хотя бы один из сценариев:

- нужна server-side session/cookie strategy;
- нужен единый auth broker или SSO;
- нужно убрать popup/callback зависимость;
- нужен redirect-based website login flow;
- требуется более жесткая интеграция нескольких веб-приложений.

## Current Rollout

1. Mini App auth остается на `initData` validation.
2. Website auth остается на Telegram Login library callback flow.
3. Backend выдаёт наш bearer token после успешной валидации `id_token`.
4. OIDC остается опцией на будущее, не текущим обязательным шагом.
