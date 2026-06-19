# Credits And Ledger

## Invariants

- User-visible credit balance must be explainable from durable payment/ledger state.
- Top-up processing must be idempotent by payment/invoice/callback identity.
- A retry must not create duplicate credit grants.
- A failed or pending payment must not grant credits.
- Ledger rows should contain enough context to audit why credits changed.

## Code Map

- `src/credits_service.py`: credit balance operations and ledger writes.
- `src/payments_service.py`: payment state transitions and top-up orchestration.
- `src/payments_api.py`: HTTP boundary for payment initiation/callbacks.
- `migrations/0005_credit_topups_ledger.sql`: initial top-up and ledger model.
- `migrations/0010_credit_ledger_idempotency_backfill.sql`: idempotency hardening.

## Review Points

- Race safety: two callbacks for the same invoice must converge to one grant.
- Transaction boundaries: payment status update and credit grant should not diverge.
- Compatibility: staging/prod may differ if a migration was added for conflict compatibility.
- Tests: cover duplicate callback, failed callback, and normal success path when behavior changes.
