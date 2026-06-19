# Migration Rules

Source of truth: `migrations/README.md` and migration files.

## Project Rules

- Filename: `0NNN_<short_description>.sql`.
- Numbers should increase monotonically.
- One logical schema change per migration where practical.
- Prefer additive, backward-compatible migrations before code that depends on them.
- For dangerous changes, use two-step rollout: add new path, deploy code, then remove old path later.
- Rollback is a separate reverse migration or backup restore decision, not an implicit downgrade.

## Before Merging Code That Depends On A Migration

- Migration file exists in `migrations/`.
- SQL is idempotent where practical.
- App code handles pre/post migration compatibility when needed.
- `.env.example` updated if new config is required.
- Tests cover changed app behavior.
- Rollout notes mention manual Supabase SQL Editor application if needed.

## Risk Markers

- `DROP`, `DELETE`, `TRUNCATE`, `ALTER COLUMN SET NOT NULL`, type changes, renames.
- Backfills over large tables.
- New unique constraints on existing data.
- Changes to auth/RLS policies.
- Code and DB changes that must land in strict order.
