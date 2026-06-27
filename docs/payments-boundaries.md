# Credits and Payments Boundaries

## Current scope

The cabinet may show balance, packages, invoice summary, receipt email and payment CTA using the existing payment backend. This document does not change provider switching or introduce new payment mechanics.

## Product semantics

- UI term: `credit`.
- Current product mapping: `1 credit = 1 render`.
- A render is charged once for a user-visible request; internal provider retries and quality retries are not charged separately.

## Invariants

- invoice creation and payment callbacks are idempotent;
- balance-changing operations are auditable;
- payment callbacks are verified before crediting;
- UI must reflect backend truth, not optimistic local-only balance;
- payment provider identifiers and raw event references are retained for support and reconciliation.

## Explicitly deferred

Do not display or implement credit expiry until separately approved.

The proposed future design is lot-based grants:

```text
credit_grants: amount, remaining, granted_at, expires_at
credit_ledger: immutable debit/credit/expiration events
account balance: derived or cached projection
spend order: FIFO by nearest expires_at
```

This requires a dedicated ADR, migration plan, service logic, reconciliation tests and user-facing terms review.

## Boundaries with rendering

The render pipeline records charge intent/result but does not own payment-provider logic. A failed internal generation or validation retry must not create extra debit events. Final refund policy is outside this document and requires a separate product decision.
