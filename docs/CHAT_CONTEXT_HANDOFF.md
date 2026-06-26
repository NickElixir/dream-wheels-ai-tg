# Dream Wheels AI — repository guide for AI assistants

## Product

Dream Wheels AI is a Telegram Mini App and bot for virtual wheel fitting. A user supplies a car image and a rim image, receives a generated visual fitment, and will progressively receive a separate preliminary technical compatibility assessment.

Never present a visual render as proof that a wheel fits technically.

## Current architecture

- Frontend: static Telegram WebApp in `webapp/`, deployed through Vercel.
- Backend: Python 3.12, FastAPI, async I/O, worker loop.
- Telegram: `python-telegram-bot` long polling.
- Database and object storage: Supabase Postgres and Storage.
- Queue, session cache, rate limits: Upstash Redis.
- Hosting: Render.
- Current image generation is behind an external provider adapter; do not spread provider-specific assumptions through routes or domain code.

The current WebApp target flow is documented in [architecture.md](architecture.md).

## Working rules

1. Read [CONTRIBUTING.md](../CONTRIBUTING.md) before code changes.
2. Use feature branches and PRs; never push directly to `main`.
3. Apply all DDL through ordered, idempotent migrations in `migrations/`.
4. Use Pydantic at API boundaries, async for I/O, type hints on public functions, and `logger.exception` in exception handlers.
5. Never log or commit secrets.
6. Treat `jobs` as the current render-job aggregate; evolve it rather than duplicating lifecycle state.

## Documentation map

- [architecture.md](architecture.md) — current WebApp, worker and job flow.
- [product-roadmap.md](product-roadmap.md) — delivery order and dependencies.
- [data-model.md](data-model.md) — target durable data model.
- [ai-rendering-pipeline.md](ai-rendering-pipeline.md) — production AI path and evaluation boundary.
- [fitment-compatibility.md](fitment-compatibility.md) — compatibility engine and UX rules.
- [fitment-provider-discovery.md](fitment-provider-discovery.md) — provider evaluation plan.
- [payments-boundaries.md](payments-boundaries.md) — credits/payment scope.
- [customer-development.md](customer-development.md) — research gates and metrics.
- [adr/](adr/) — accepted architectural decisions.

## Planned architecture constraints

- Original images, generated results and metadata must become durable; do not rely on browser state or ephemeral filesystem storage for history.
- Vehicle recognition is a suggestion; the user confirms vehicle identity.
- Rim SKU/URL/specifications are optional but higher-trust than OCR/VLM guesses.
- Fitment decisions are deterministic over structured data; LLMs can extract or explain but cannot be the source of compatibility truth.
- Input quality checks begin as warnings, not automatic rejection.
- Internal retries do not consume additional credits.
