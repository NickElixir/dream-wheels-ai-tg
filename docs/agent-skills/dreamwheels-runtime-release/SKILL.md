---
name: dreamwheels-runtime-release
description: Use for Dream Wheels AI runtime, deployment, and release work involving Render, deploys, rollbacks, health checks, env vars, logs, Telegram polling conflicts, keep-alive, Supabase/Upstash runtime connectivity, and production verification.
---

# Dream Wheels Runtime Release

Use this skill for deploy, runtime, and release operations.

## Read First

- `CONTRIBUTING.md`
- `README.md`
- `.env.example`
- `start.sh`
- `src/main.py`
- `src/bot.py`
- `src/config.py`
- `docs/keep-alive-setup.md`
- `docs/TEAM_HANDOFF_CHECKLIST.md`

Load references only when needed:

- `references/render.md` for Render deploy/rollback and runtime checks.
- `references/telegram-runtime.md` for bot polling and webhook/runtime trade-offs.

## Workflow

1. Identify whether the task is local runtime, Render deploy, env var, bot runtime, or post-deploy verification.
2. Check official Render/Telegram/Supabase/Upstash docs before asserting platform behavior.
3. Keep local, staging, and production operations separate.
4. Treat env var changes as release changes; update `.env.example` when adding new variables.
5. For production-impacting actions, ask for explicit confirmation before executing.
6. Report verification as commands/statuses, not assumptions.

## Do Not

- Do not deploy, rollback, mutate Render env vars, or call production APIs without confirmation.
- Do not paste secrets into chat or logs.
- Do not assume Render Free/Starter behavior without checking current docs when it affects a decision.
- Do not ignore Telegram `getUpdates` conflict during rolling deploy; classify it as expected or persistent based on timing/logs.

## Verification

Local code changes:

```bash
ruff check .
ruff format --check .
pytest -q
```

Runtime/deploy verification depends on user-approved environment access.
