# Robokassa Reference

This file stores project decisions, not a copy of Robokassa docs. For protocol details, verify official docs before changing behavior:

- https://docs.robokassa.ru/ru/quick-start
- https://docs.robokassa.ru/ru/pay-interface
- https://docs.robokassa.ru/ru/notifications-and-redirects

## Project Rules

- Payment URL generation belongs in `src/robokassa_client.py`.
- API endpoints and callbacks are in `src/payments_api.py`.
- Business state changes belong in `src/payments_service.py` / `src/credits_service.py`, not in low-level client helpers.
- `ResultURL` server callback is the confirmation path.
- `SuccessURL` and `FailURL` are browser/user redirect paths and must not grant credits by themselves.
- Callback response must follow Robokassa expected acknowledgement format for the invoice id.
- Test mode must use test credentials and explicit test flag/config.

## Common Failure Modes

- Signature assembled with fields in the wrong order.
- Test password used with live mode or live password used with test mode.
- Receipt JSON serialized differently before signing than before sending.
- Callback processing not idempotent and grants credits twice on retry.
- Treating a browser redirect as a paid status.
- Logging generated payment URLs with sensitive parameters.

## Change Checklist

- Identify which signature is affected: payment URL, ResultURL callback, or receipt-related signature.
- Check config names in `.env.example` and `src/config.py`.
- Update tests with deterministic amounts, invoice ids, and expected signatures.
- If callback semantics change, add retry/idempotency coverage.
