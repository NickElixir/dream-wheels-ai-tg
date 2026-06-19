# RLS And Storage

Verify Supabase behavior against official docs when details matter:

- https://supabase.com/docs
- https://supabase.com/docs/guides/storage

## Project Rules

- RLS on public tables is intended to block anonymous PostgREST access.
- Backend uses server-side credentials / database connection and must not expose service role keys to clients.
- Storage buckets and policies are managed through migration files.
- Signed/public URL decisions must be explicit and tied to product behavior.

## Review Points

- Is the access path backend-only, Telegram user-facing, or Mini App user-facing?
- Does a policy expose objects across users?
- Does the app rely on stable URLs across Render deploys?
- Are storage paths deterministic enough for cleanup/audit?
- Are service role keys kept server-side only?
