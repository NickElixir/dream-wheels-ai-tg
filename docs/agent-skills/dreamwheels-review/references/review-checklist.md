# Review Checklist

## Python And Async

- Public function signatures have type hints.
- I/O paths are async where appropriate.
- No blocking DB/HTTP calls inside async handlers.
- Imports use `src.*` absolute style.
- Comments explain why, not what.

## Logging And Errors

- `except` blocks use `logger.exception(...)` when logging exceptions.
- Logs include useful IDs: `job_id`, `user_id`, `telegram_user_id`, `payment_id`, `invoice_id`.
- Secrets, tokens, signed URLs, and credentials are not logged.
- Broad `except Exception` is limited to boundaries where one task/request must not crash the process.

## Payments

- Result/callback path is the source of truth for payment confirmation.
- Success/fail redirect does not grant credits by itself.
- Callback and ledger writes are idempotent.
- Test/live mode and credentials are not mixed.

## Data And Storage

- Schema changes have migrations.
- Migrations are ordered and idempotent where practical.
- RLS/storage policy changes do not widen access accidentally.
- Code handles rollout ordering if DB and app changes are coupled.

## Runtime

- New env vars are in `.env.example`.
- Render/Telegram/Supabase/Upstash behavior is verified against official docs when relevant.
- Bot polling/deploy interactions are considered.
- Health and startup behavior remains observable.

## Telegram Mini App

- Backend validates `initData`; `initDataUnsafe` is not trusted for authorization.
- Dev `telegram_user_id` fallback remains disabled in production.
- Upload MIME, size, rate limit, idempotency, and credit checks remain server-side.
- Root and `/t/` resolve to the same frontend entrypoint through config rather than duplicated HTML.
- Mobile WebView lifecycle, IndexedDB draft recovery, and Telegram-only APIs are considered.
