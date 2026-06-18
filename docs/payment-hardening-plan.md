# Payment Hardening Plan

## Решение

Не переписываем Dream Wheels AI с нуля и не выносим оплату в микросервисы на текущем этапе. Идем через модульный монолит: один FastAPI backend, но с явными границами между Telegram auth, payment providers, credit ledger и job pipeline.

## Этапы

1. Починить текущий `/payments/topups` и пользовательские ошибки в Mini App.
2. Зафиксировать `credit_ledger` как source of truth для движения credits.
3. Оставить `user_credit_accounts` только как derived/cache баланс, обновляемый из ledger.
4. Вынести Robokassa в `PaymentProvider` adapter.
5. Добавить contract tests для Robokassa signature, receipt payload и webhook idempotency.
6. Заменить или сверить Telegram auth validator с библиотекой/официальными test cases.
7. Добавить второй provider, например Telegram Stars или Wallet Pay, чтобы проверить универсальность payment layer.

## Целевая схема модулей

```text
src/auth/
  telegram_webapp.py
  telegram_login.py

src/payments/
  service.py
  providers/
    base.py
    robokassa.py
    telegram_stars.py
    wallet_pay.py
    ton_pay.py

src/credits/
  ledger.py
  accounts.py
  policies.py

src/jobs/
  service.py
  queue.py
```

## Принципы

- Payment provider отвечает только за invoice, redirect URL, callback validation, status и refund.
- Credit ledger отвечает за начисление и списание credits.
- Job pipeline только резервирует credits и создает/обрабатывает generation jobs.
- Frontend показывает состояние payment flow как state machine, а не как набор независимых флагов.
- Все внешние callback-и должны быть идемпотентными.

## Почему не отдельный репозиторий для credits сейчас

Credit ledger пока тесно связан с users, payments и jobs. Отдельный репозиторий имеет смысл только когда ledger станет самостоятельным компонентом с несколькими потребителями и стабильным API.

## Почему не микросервисы сейчас

Микросервисы добавят сетевые сбои, отдельные deploy cycles, трассировку и проблему распределенных транзакций. На текущем масштабе нужную поддерживаемость дает модульный монолит.
