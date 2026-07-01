---
name: dreamwheels-telegram-webapp
description: Use for Dream Wheels AI Telegram Mini App and webapp work involving Telegram WebApp SDK, initData, frontend auth, file picker and image upload, IndexedDB draft recovery, job polling, result download/share, localization, Vercel frontend config, CORS, and mobile WebView behavior.
---

# Dream Wheels Telegram WebApp

Use this skill for changes spanning `webapp/` and its FastAPI boundary.

## Read First

- `CONTRIBUTING.md`
- `AGENTS.md`
- `docs/architecture.md`
- `webapp/app.js`
- `webapp/index.html`
- `webapp/style.css`
- `webapp/vercel.json`
- `src/auth.py`
- `src/jobs_api.py`
- `src/main.py`
- `.env.example`

`webapp/README.md` contains historical prototype notes and may be stale. Verify behavior in current code before relying on it.

Load references only when needed:

- `references/frontend-lifecycle.md` for Telegram SDK, navigation, file picker, draft recovery, polling, download, and localization.
- `references/auth-upload-boundary.md` for `initData`, dev fallback, multipart upload, idempotency, CORS, and storage boundaries.

## Workflow

1. Classify the change as frontend-only, API-contract, auth, upload/storage, payment UI, or deployment config.
2. Trace the full flow when contracts change: `webapp/app.js` -> FastAPI endpoint -> DB/Redis/Storage -> polling/result UI.
3. Treat `tg.initData` as the client credential and validate it only on the backend; never trust `initDataUnsafe` for authorization.
4. Preserve draft recovery around file selection because Telegram mobile WebViews may reload or lose in-memory state.
5. Preserve the `/t/` entry route through `webapp/vercel.json` rewrites so root and `/t/` resolve to the same frontend entrypoint.
6. Verify desktop fallback and Telegram WebView behavior separately.
7. If external Telegram behavior matters, check official Telegram Bot API / Mini Apps docs before making claims.

## Do Not

- Do not expose `BOT_TOKEN`, service-role keys, internal API tokens, or raw secrets to frontend code.
- Do not enable `WEBAPP_DEV_AUTH_ENABLED` as a production authentication path.
- Do not authorize by `telegram_user_id` supplied by the browser unless the explicitly enabled dev fallback is being used.
- Do not remove idempotency from upload submission or credit-consuming actions.
- Do not log full `initData`, signed URLs, tokens, or uploaded image bytes.
- Do not change CORS/CSP broadly without naming the required origin and threat.

## Verification

Backend-affecting changes:

```bash
ruff check .
ruff format --check .
pytest -q
```

Frontend changes require browser verification at desktop and mobile widths. When Telegram-only APIs are involved, also verify inside a Telegram test/staging Mini App; local browser fallback cannot validate `initData`, native buttons, haptics, download, or WebView lifecycle.
