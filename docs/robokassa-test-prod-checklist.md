# Robokassa Test/Prod Checklist

## Short Final Smoke

Use this after any Robokassa/payment hardening change on staging.

1. Confirm staging health: `GET /health` returns `200`.
2. Open the cabinet with a valid website or Mini App auth context: `GET /payments/cabinet` returns `200`.
3. Create a test top-up from staging: `POST /payments/topups`.
4. Confirm the new `payments` row has:
   - `provider = robokassa`
   - `currency = RUB`
   - `amount_provider_units = amount_rub * 100`
   - `delivery_channel = website`
5. Confirm `payment_url` opens Robokassa in test mode.
6. Send the callback to `/payments/robokassa/result`.
7. Confirm the payment becomes `paid`, `credit_ledger` gets `purchase_grant`, and cabinet balance increases.

Expected result:

- no `500` in cabinet or payment endpoints
- `payments.status = paid`
- `credit_ledger` contains one idempotent purchase grant
- balance matches the paid credits

## Цель

На staging последовательно проверить:

1. test mode Robokassa
2. prod mode Robokassa
3. возврат staging обратно в test mode

## Что важно до старта

- `Result URL` должен указывать на backend callback:
  `https://dream-wheels-ai-robokassa-staging.onrender.com/payments/robokassa/result`
- `Success URL` и `Fail URL` для staging должны указывать на staging webapp, а не на main:
  `https://dream-wheels-ai-webapp-staging.vercel.app/t/`
- В кабинете Robokassa есть отдельный блок `Параметры проведения тестовых платежей`.
- При `ROBOKASSA_IS_TEST=true` Robokassa валидирует подпись по test-паролям, а не по боевым.

## Env vars

Для staging backend:

- `ROBOKASSA_MERCHANT_LOGIN`
- `ROBOKASSA_PASSWORD1`
- `ROBOKASSA_PASSWORD2`
- `ROBOKASSA_TEST_PASSWORD1`
- `ROBOKASSA_TEST_PASSWORD2`
- `ROBOKASSA_IS_TEST`

## Шаг 1. Проверка test mode

1. В кабинете Robokassa заполнить test `Пароль #1` и test `Пароль #2`.
2. На Render для staging выставить:
   - `ROBOKASSA_TEST_PASSWORD1=<test password #1>`
   - `ROBOKASSA_TEST_PASSWORD2=<test password #2>`
   - `ROBOKASSA_IS_TEST=true`
3. Проверить, что `Success URL`/`Fail URL` указывают на staging webapp.
4. Проверить, что `Result URL` указывает на `/payments/robokassa/result`.
5. Создать платеж в staging Mini App.
6. Убедиться, что открывается Robokassa без ошибки `29`.
7. Пройти тестовую оплату.
8. Проверить callback:
   - `payments.status = paid`
   - в `credit_ledger` появилась запись `purchase_grant`
   - баланс в кабинете вырос

## Шаг 2. Проверка prod mode

1. На Render для staging выставить:
   - `ROBOKASSA_IS_TEST=false`
2. Убедиться, что используются боевые `ROBOKASSA_PASSWORD1/2`.
3. Создать минимальный реальный платеж.
4. Проверить:
   - открытие страницы Robokassa без ошибки
   - успешный callback на `/payments/robokassa/result`
   - начисление credits
   - запись в `payments` и `credit_ledger`

## Шаг 3. Возврат staging в test mode

1. Вернуть `ROBOKASSA_IS_TEST=true`
2. Оставить `ROBOKASSA_TEST_PASSWORD1/2` заполненными
3. Повторить один test payment smoke-check

## Если снова ошибка 29

Проверить по порядку:

1. Совпадает ли `ROBOKASSA_IS_TEST` с ожидаемым режимом
2. Заполнены ли test-пароли в кабинете Robokassa
3. Совпадают ли test-пароли в Render env и в кабинете Robokassa
4. Совпадает ли `ROBOKASSA_HASH_ALGO` с алгоритмом в кабинете
5. Указывает ли `Result URL` именно на `/payments/robokassa/result`
6. Не уходит ли staging на main `Success URL` / `Fail URL`
