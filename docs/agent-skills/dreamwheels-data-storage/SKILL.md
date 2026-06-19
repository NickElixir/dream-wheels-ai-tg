---
name: dreamwheels-data-storage
description: Use for Dream Wheels AI database and Supabase work involving SQL migrations, RLS, policies, Storage buckets, schema compatibility, Supabase SQL Editor rollout, storage URLs, and data safety.
---

# Dream Wheels Data Storage

Use this skill for database migrations, Supabase RLS, and Storage changes.

## Read First

- `CONTRIBUTING.md`
- `README.md`
- `migrations/README.md`
- `.env.example`
- `src/db.py`
- `src/storage.py`
- Relevant SQL files in `migrations/`

Load references only when needed:

- `references/migrations.md` for migration authoring and rollout.
- `references/rls-storage.md` for RLS and Storage policy work.

## Workflow

1. Determine whether the change is DDL, policy, storage, or application code only.
2. For DDL/policy changes, create a new monotonic migration file; do not modify already-applied migrations unless the user explicitly asks and confirms the environment state.
3. Keep migrations idempotent where possible: `IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, guarded policy creation.
4. Check app code and tests for assumptions about nullability, unique constraints, and status values.
5. For Supabase pooler/asyncpg work, preserve `statement_cache_size=0` where relevant.
6. Document rollout risk when code depends on schema that may not exist yet.

## Do Not

- Do not run destructive SQL without explicit confirmation.
- Do not apply migrations to production from Codex without explicit confirmation.
- Do not change Supabase schema through UI instructions that bypass migration files.
- Do not weaken RLS or Storage policies without naming the exact access path and risk.
- Do not duplicate full schemas in skill files; read `migrations/` as source of truth.

## Verification

```bash
ruff check .
ruff format --check .
pytest -q
```

For SQL-only changes, also manually inspect migration ordering and idempotency.
