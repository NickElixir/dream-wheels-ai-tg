# Auth And Upload Boundary

## Current Flow

1. `webapp/app.js` sends car and wheel images as multipart `FormData` to `POST /jobs/upload`.
2. The request includes `init_data` and an idempotency key.
3. `src/auth.py` validates Telegram HMAC and `auth_date`, then extracts the user.
4. `src/jobs_api.py` enforces rate limit, validates MIME/size, uploads raw files, creates the job, reserves credit, and enqueues work.
5. The frontend polls job status and exposes result download/share actions.

## Security Invariants

- Backend-validated `initData` determines Telegram identity.
- Browser-supplied `telegram_user_id` is accepted only behind `WEBAPP_DEV_AUTH_ENABLED`; keep this disabled in production.
- Never send `BOT_TOKEN`, Supabase service-role key, or internal API token to `webapp/`.
- Validate upload MIME, non-empty content, and maximum size on the backend even if frontend validation exists.
- Rate limiting and credit reservation remain backend responsibilities.
- CORS should allow the exact configured `WEBAPP_URL` plus explicitly required Telegram origin behavior.

## Idempotency And Failure Handling

- Retrying upload with the same user/key must return the existing job rather than consume another credit.
- Do not generate a new idempotency key on an automatic retry of the same user action.
- Storage upload, DB insert, credit reservation, queue push, and Redis idempotency state can fail at different points; review partial-failure behavior when touching this flow.
- Network polling failures should remain retryable until deadline; terminal backend failure should surface a stable user-facing error.

## Cross-Skill Routing

- Use `dreamwheels-payments` when changing wallet/top-up/payment UI or API contracts.
- Use `dreamwheels-data-storage` when changing Storage buckets, policies, paths, or DB schema.
- Use `dreamwheels-runtime-release` when changing Vercel/Render env, domains, CORS origins, deploy, or rollback behavior.
- Use `dreamwheels-review` for final change-impact and security review.
