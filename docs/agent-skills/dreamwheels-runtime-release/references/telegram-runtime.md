# Telegram Runtime

Check official docs for API behavior:

- https://core.telegram.org/bots/api
- https://core.telegram.org/bots/webapps

## Project Rules

- Bot currently uses long polling.
- Rolling deploy can temporarily run two bot processes and produce `getUpdates` conflict.
- Telegram file URLs are accepted only through project validation paths.
- Mini App frontend/auth behavior belongs to `dreamwheels-telegram-webapp`.

## Review Points

- Does a runtime change affect both FastAPI and bot startup?
- Does a deploy change alter process count?
- Does a bot change require webhook vs polling decision?
- Does the bot button still open the configured `WEBAPP_URL`?
