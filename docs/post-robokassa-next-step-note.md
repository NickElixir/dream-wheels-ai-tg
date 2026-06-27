# Next Step After Robokassa

Robokassa backend-hardening is done for now, and the website Telegram auth boundary is stable.

The next major step is the cabinet redesign, not Telegram Stars implementation yet.

Why this is the right next move:

- it lets us redesign the UI once instead of twice;
- it gives us a clean place to add a payment selector later;
- it keeps Robokassa as the current production path while leaving room for Stars;
- it prevents scope creep into payment-provider work before the cabinet UX is ready.

What the next phase should contain:

- a redesigned cabinet shell;
- explicit payment-state presentation;
- a reserved slot for future providers, especially Telegram Stars;
- no forced migration to Stars until the new UI is ready.

## Cabinet Redesign Decisions

### Credits Terminology

The wallet UI must keep the term `credits`.

Do not rename wallet balance to `renders`: later product tiers may price different functions, models, or B2B2C workflows differently. A user may spend more or fewer credits depending on the feature, model, or partner-specific use case. This is especially important for B2B2C scenarios with individual creators, freelancers, or contractors producing listing/card assets rather than a single company-wide workflow.

The UI can still explain the current simple rule near checkout:

```text
Сейчас 1 credit = 1 render. Credits действуют 30 дней после покупки.
```

### Pre-Render Checklist

The first redesign iteration should add a checklist/review step before generation.

For now this checklist is a user-facing warning and self-check, not an automated gate. It should help the user confirm:

- the car is fully visible;
- the wheels are not cropped;
- the car photo is bright and sharp enough;
- the wheel photo shows the front side of the rim;
- the wheel photo is not heavily blurred.

Design the checklist boundary so it can later be backed by automated checks from VLMs, CV models, or CNN classifiers. The future automated version should return warnings and confidence, not silently block generation unless the backend explicitly adds a policy for hard rejection.

### Credit Expiration

Purchased credits should expire 30 days after purchase. This must be shown before payment and in the wallet.

Recommended backend direction for approval before implementation:

1. Add lot-based credit grants as the source of truth.
   Each paid grant gets `granted_credits`, `remaining_credits`, `expires_at`, `provider`, `payment_id`, and idempotency metadata.
2. Spend credits FIFO by expiration date.
   Job creation consumes from the earliest expiring non-empty lots first.
3. Keep `user_credit_accounts.balance` as a derived/cache balance.
   Recompute or reconcile it from non-expired lots plus ledger events when needed.
4. Write expiration events to `credit_ledger`.
   Expired credits should be auditable as a ledger movement, not just disappear from the balance.
5. Do not expire starter grants until the product policy is explicitly decided.

Alternative lower-scope option:

- Add `expires_at` to positive purchase ledger rows and compute available balance from non-expired rows minus spends.

This is simpler, but becomes harder once partial spends, refunds, multiple providers, and B2B2C account policies arrive. Prefer the lot-based model unless speed is more important than future accounting clarity.

### Result Comparison UX

The redesign should let users compare the generated result with the original car photo both immediately after rendering and later from history.

User-friendly options to approve before implementation:

1. Side-by-side comparison.
   Best for desktop and wide mobile. Clear and simple, but cramped on narrow Telegram WebView screens.
2. Before/after toggle.
   Best first mobile implementation. One image area, two segmented buttons: `Original` and `Result`.
3. Swipe comparison slider.
   Most expressive, but more implementation and QA work. Better as a second iteration after result storage is stable.

Recommended first iteration:

- result screen: large result image with `Original` / `Result` toggle;
- history: each render card opens a detail view with the same toggle;
- keep a future slot for side-by-side on desktop widths.

This requires preserving enough local or backend state to retrieve the original car photo for a completed render. If the current history only has `resultUrl`, implement the UI shell first and add durable original/result history as a separate backend/storage task.

Revisit this decision when the cabinet redesign starts or when we are ready to add a second payment channel.
