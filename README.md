# Dream Wheels AI

Dream Wheels AI is a Telegram Mini App and bot for virtual wheel fitting: a user uploads a car image and a wheel image, receives a generated visual fitment, and will receive a separate preliminary technical compatibility assessment.

> A visual result is not proof that a wheel is technically compatible with a vehicle.

## Current stack

- Python 3.12, FastAPI, Uvicorn
- Telegram Mini App frontend in `webapp/` and `python-telegram-bot`
- Supabase Postgres and Storage
- Upstash Redis for queue, sessions and rate limits
- Render for backend/worker deployment; Vercel for WebApp hosting
- External image-generation provider behind a backend adapter
- GitHub Actions, Ruff, pytest and pre-commit

## Current request flow

```text
Telegram Mini App
  → POST /jobs/upload
  → initData validation, rate limit and idempotency
  → Supabase Storage + Postgres job
  → Redis queue
  → worker + image-generation provider
  → durable result storage
  → GET /jobs/{id} status/result
```

The detailed WebApp and worker diagrams are in [docs/architecture.md](docs/architecture.md).

## Repository layout

```text
src/          Backend, bot, worker and provider integration
webapp/       Static Telegram Mini App
migrations/   Ordered SQL migrations
docs/         Product, architecture, AI, fitment and ADR documentation
tests/        Smoke and future integration tests
```

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env
uvicorn src.main:app --reload
```

Run checks:

```bash
ruff check .
ruff format --check .
pytest -q
```

## Development rules

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before implementation.
- Work through feature branches and PRs; do not push directly to `main`.
- Apply schema changes only via idempotent migrations in `migrations/`.
- Keep secrets out of code, logs and commits.

## Documentation

- [Architecture](docs/architecture.md)
- [Product roadmap](docs/product-roadmap.md)
- [Target data model](docs/data-model.md)
- [AI rendering pipeline](docs/ai-rendering-pipeline.md)
- [Fitment compatibility engine](docs/fitment-compatibility.md)
- [Fitment provider discovery](docs/fitment-provider-discovery.md)
- [Credits and payments boundaries](docs/payments-boundaries.md)
- [Customer development plan](docs/customer-development.md)
- [Architecture decision records](docs/adr/)
- [AI assistant repository guide](docs/CHAT_CONTEXT_HANDOFF.md)
