# Render Runtime

Check official docs for current platform behavior:

- https://render.com/docs
- https://api-docs.render.com/reference/introduction

## Project Facts

- Render hosts FastAPI and Telegram bot runtime.
- `README.md` contains current deploy and rollback flow.
- Health endpoint is `GET /health`.
- Env vars are configured in Render Dashboard and mirrored in `.env.example` names.

## Expected Checks

- Build/deploy status is live before post-deploy verification.
- Logs include app startup and worker/bot startup events.
- `GET /health` returns ok.
- Telegram bot responds after deploy.
- Rolling deploy can temporarily create Telegram polling conflicts if two instances call `getUpdates`.

## Escalation Points

- Persistent polling conflict after rollout window.
- Missing env vars.
- DB/Redis connection failures.
- Health check fails while process is running.
- Static/runtime file storage assumptions after deploy.
