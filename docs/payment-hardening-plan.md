# Payment Hardening Plan

## Решение

Не переписываем Dream Wheels AI с нуля и не выносим оплату в микросервисы на текущем этапе. Идем через модульный монолит: один FastAPI backend, но с явными границами между Telegram auth, payment providers, credit ledger и job pipeline.

## Payment channel decision

Robokassa остается основным внешним fiat/RUB-каналом для website, B2B2C, чеков и сценариев вне Telegram.

Telegram-native оплату добавляем не через обычные Telegram Payments providers как первый шаг, а через Telegram Stars. По официальной модели Telegram, third-party payment providers относятся к physical goods/services, а digital goods/services должны продаваться за Stars с currency `XTR`.

Обычные Telegram Payments providers оставляем как deferred option. Они могут понадобиться позже для физических товаров, регионального card checkout внутри bot invoice или отдельного fiat-flow, но сейчас дублируют Robokassa и добавляют pre-checkout/update сложность без явной бизнес-выгоды.

Telegram Stars рассматриваем как второй provider для B2C внутри Mini App/bot: быстрый native checkout, меньше friction в Telegram, без сбора email/card данных. Это не замена Robokassa для B2B2C, внешнего сайта, RUB-учета и фискальных сценариев.

## Этапы

1. Починить текущий `/payments/topups` и пользовательские ошибки в Mini App.
2. Зафиксировать `credit_ledger` как source of truth для движения credits.
3. Оставить `user_credit_accounts` только как derived/cache баланс, обновляемый из ledger.
4. Нормализовать payment core под несколько каналов: `provider`, `currency`, amount в provider units, invoice payload, provider charge id, delivery channel и единые status transitions.
5. Вынести Robokassa в `PaymentProvider` adapter как первый external fiat/RUB provider.
6. Добавить contract tests для Robokassa signature, receipt payload и webhook idempotency.
7. Добавить Telegram auth для веб-сайта и Mini App fallback как отдельный auth boundary: backend-validated Telegram login/initData, без доверия к frontend-only данным.
8. Заменить или сверить Telegram auth validator с библиотекой/официальными test cases.
9. Добавить Telegram Stars provider для Telegram-native digital credit packs: invoice с `currency=XTR`, pre-checkout handler, successful payment handler, idempotent credit grant и refund path.
10. Вернуться к обычным Telegram Payments providers только если появится отдельная потребность в bot-native fiat checkout, не покрытая Robokassa.

## Целевая схема модулей

```text
src/auth/
  telegram_webapp.py
  telegram_login.py
  web_site.py

src/payments/
  service.py
  models.py
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
- Payment core не должен предполагать, что любой платеж это RUB, email receipt, redirect URL или Robokassa callback.
- Credits начисляются только после server-side provider confirmation: Robokassa ResultURL/webhook или Telegram `successful_payment`.
- Telegram Stars provider обязан отвечать на `pre_checkout_query` быстрее 10 секунд и сохранять `telegram_payment_charge_id` для idempotency/refund.
- Website по умолчанию использует Robokassa; Mini App/bot может предлагать Stars как primary Telegram-native checkout и Robokassa как fallback.

## Official references

- Telegram Bot Payments API: https://core.telegram.org/bots/payments
- Telegram Stars payments for digital goods/services: https://core.telegram.org/bots/payments-stars
- Telegram Bot API payments methods: https://core.telegram.org/bots/api#payments

## Почему не отдельный репозиторий для credits сейчас

Credit ledger пока тесно связан с users, payments и jobs. Отдельный репозиторий имеет смысл только когда ledger станет самостоятельным компонентом с несколькими потребителями и стабильным API.

## Почему не микросервисы сейчас

Микросервисы добавят сетевые сбои, отдельные deploy cycles, трассировку и проблему распределенных транзакций. На текущем масштабе нужную поддерживаемость дает модульный монолит.
