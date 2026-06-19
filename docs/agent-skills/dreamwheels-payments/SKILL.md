---
name: dreamwheels-payments
description: Use for Dream Wheels AI payment work involving Robokassa, invoices, receipts, signatures, ResultURL/SuccessURL/FailURL, test/live mode, top-ups, credits, credit ledger, idempotency, payment APIs, and payment tests.
---

# Dream Wheels Payments

Use this skill for Robokassa and credit-balance changes.

## Read First

- `CONTRIBUTING.md`
- `README.md`
- `.env.example`
- `src/robokassa_client.py`
- `src/payments_api.py`
- `src/payments_service.py`
- `src/credits_service.py`
- `tests/test_robokassa_client.py`
- `tests/test_payments_mvp.py`
- `tests/test_payments_switch.py`
- `migrations/README.md`
- Relevant migrations: `0004_preorders_robokassa.sql`, `0005_credit_topups_ledger.sql`, `0006_nullable_preorder_email.sql`, `0006_payments_mvp.sql`, `0009_staging_credit_ledger_conflict_compat.sql`, `0010_credit_ledger_idempotency_backfill.sql`

Load references only when needed:

- `references/robokassa.md` for Robokassa request/callback/signature flow.
- `references/credits-ledger.md` for credit balance, ledger, and idempotency invariants.

## Workflow

1. Identify whether the task changes payment URL generation, callback handling, credits, ledger writes, or config.
2. Read the current code and tests before editing; do not rely on old chat context.
3. If external Robokassa behavior matters, verify against official Robokassa docs before making claims.
4. Keep test/live mode explicit; do not mix live and test passwords.
5. Preserve idempotency: callbacks, top-ups, and ledger writes must be safe to retry.
6. Add or update focused tests for every changed payment behavior.

## Do Not

- Do not log Robokassa passwords, API keys, tokens, payment signatures, or raw secrets.
- Do not call live Robokassa endpoints unless the user explicitly asks and confirms.
- Do not apply production migrations from Codex without explicit confirmation.
- Do not update credits without a durable ledger/idempotency story.
- Do not treat successful redirect as payment confirmation; server callback/result processing is the source of truth.

## Verification

Run the narrowest useful set first:

```bash
ruff check .
ruff format --check .
pytest -q tests/test_robokassa_client.py tests/test_payments_mvp.py tests/test_payments_switch.py
```

If migrations or shared services changed, run full `pytest -q`.
