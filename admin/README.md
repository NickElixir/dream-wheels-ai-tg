# Dream Wheels AI Admin

Internal Next.js dashboard for render/job statistics.

## Local Development

```bash
cp .env.example .env.local
npm install
npm run dev
```

Required env vars:

- `DATABASE_URL` — Supabase Postgres connection string. Use the pooler URL in production.
- `ADMIN_USERNAME` — HTTP Basic Auth username.
- `ADMIN_PASSWORD` — HTTP Basic Auth password.

No secrets are exposed to the browser. The dashboard reads Postgres from Server Components and is protected by middleware Basic Auth.

## Vercel

Deploy this directory as a separate Vercel project with `admin` as the root directory.

Set the same env vars in Vercel Project Settings.
