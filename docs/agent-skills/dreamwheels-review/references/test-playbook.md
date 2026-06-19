# Test Playbook

## Default

```bash
ruff check .
ruff format --check .
pytest -q
```

## Payments

```bash
pytest -q tests/test_robokassa_client.py tests/test_payments_mvp.py tests/test_payments_switch.py
```

Run full `pytest -q` if shared config, DB helpers, credits, auth, or API routing changed.

## Smoke / Routing

```bash
pytest -q tests/test_smoke.py
```

Use for import, FastAPI routing, and basic endpoint regressions.

## SQL / Migrations

No local DB migration runner is currently the source of truth. Inspect SQL manually for:

- monotonic filename ordering;
- idempotency guards;
- destructive statements;
- policy names and bucket/table names;
- compatibility with current app code.

## When A Check Cannot Run

Report:

- command attempted;
- failure reason;
- whether it is environment, dependency, network, or code failure;
- residual risk.
