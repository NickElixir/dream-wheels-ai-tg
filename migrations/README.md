# Миграции БД

SQL-миграции для PostgreSQL (Supabase). Применяются в порядке номеров.

## Файлы

- `0001_initial.sql` — таблицы `users`, `jobs`, индексы по `user_id`/`status`
- `0002_enable_rls.sql` — включение RLS на public-таблицах для блокировки anon-доступа через PostgREST
- `0003_storage_buckets_rls.sql` — buckets/policies для Supabase Storage
- `0004_add_feedback.sql` — поле `jobs.feedback` для лайков/дизлайков результата
- `0005_credit_ledger.sql` — `user_credit_accounts` и `credit_ledger` для учета credits
- `0006_preorders_robokassa.sql` — предоплаты через Robokassa
- `0007_credit_topups_ledger.sql` — гибкие Robokassa top-up платежи и `credit_ledger`
- `0008_nullable_preorder_email.sql` — email необязателен для Telegram top-up платежей
- `0009_payments_mvp.sql` — таблица `payments` и credit status для jobs
- `0010_staging_credit_ledger_conflict_compat.sql` — staging compat для legacy/new `credit_ledger` полей
- `0011_credit_ledger_idempotency_backfill.sql` — backfill и жёсткий invariant для `credit_ledger.idempotency_key`
- `0012_credit_accounts_ledger_schema_align.sql` — `user_credit_accounts`, canonical ledger columns и compat trigger
- `0013_credit_ledger_trial_grant_compat.sql` — compat для `starter grant` / legacy `operation_type` constraint
- `0014_payments_provider_neutral_fields.sql` — provider-neutral поля платежей для Robokassa + будущих Telegram Stars
- `0015_durable_render_assets.sql` — `assets` и ссылки `jobs.*_asset_id` для durable render history

## Стратегия применения

**Сейчас (MVP):** миграции применяются вручную через **Supabase SQL Editor** ([app.supabase.com](https://app.supabase.com) → проект → SQL Editor).

Порядок: всегда последовательно, от меньшего номера к большему. `IF NOT EXISTS` в 0001 защищает от двойного запуска, но новые миграции должны быть идемпотентны (`IF NOT EXISTS` / `ALTER ... IF EXISTS`).

**Кто запускает в проде:** разработчик, мерджащий PR с миграцией. Перед мерджем в `main`:

1. Открыть PR с новым файлом `migrations/000N_*.sql` в репо
2. После approve — применить SQL через Supabase SQL Editor на prod-проекте
3. Проверить через `SELECT * FROM information_schema.tables` что таблица/колонка появилась
4. Только после успешного применения — мерджить PR (код, который зависит от новой схемы, должен попасть в прод **после** миграции)

**Откат:** писать обратную миграцию вручную (`migrations/000N_revert_*.sql`) или через `pg_dump` бэкап перед применением.

## Rollout Notes

- Код credits/payments ожидает наличие `user_credit_accounts` и canonical `credit_ledger` полей (`event_type`, `credits_delta`, `balance_after`, `related_job_id`, `related_payment_id`, `idempotency_key`).
- Перед релизом payment/ledger кода на окружение, где этих объектов ещё нет, сначала применить `0012_credit_accounts_ledger_schema_align.sql`, затем выкатывать код.
- Перед внедрением Telegram Stars применить `0014_payments_provider_neutral_fields.sql`: она добавляет `currency`, `amount_provider_units`, provider payload/charge id и `delivery_channel`, сохраняя совместимость текущих Robokassa inserts через trigger.
- Перед выкладкой durable history кода применить `0015_durable_render_assets.sql`: код пишет в `assets` и `jobs.car_asset_id/rim_asset_id/result_asset_id`, сохраняя legacy поля `car_image_url/wheel_image_url/output_image_url`.
- `0012` не применяется автоматически из Codex; rollout остаётся ручным через Supabase SQL Editor после явного подтверждения.

## Соглашения

- Имя файла: `0NNN_<short_description>.sql`, номера монотонно растут, без пропусков
- Каждая миграция — атомарная (одна логическая правка: новая таблица, новая колонка, новый индекс)
- Идемпотентность: используй `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ADD COLUMN IF NOT EXISTS`
- Большие изменения данных (`UPDATE` миллионов строк) — отдельным файлом, желательно ночью
- DROP / переименование колонок — двухшаговая миграция:
  1. Добавить новую колонку, копировать данные, выкатить новый код
  2. После проверки — отдельная миграция `DROP` старой колонки

## Когда переходить на инструмент

Когда станет тяжело руками — мигрируй на **Alembic** (стандарт Python) или **yoyo-migrations** (легче). Признаки что пора:

- 15+ миграций
- Несколько окружений (dev/staging/prod) с разным состоянием
- Команда из 3+ человек, путаются кто что применил
- Нужны migration в CI

Alembic интегрируется с SQLAlchemy/asyncpg, отслеживает применённые миграции в таблице `alembic_version`, умеет генерить downgrade.

## Применение через MCP

Если работаешь через Claude Code с подключённым Supabase MCP, можно применять миграции через `mcp__supabase__apply_migration` — Claude передаёт SQL в Management API. Это удобно для автоматизации, но **не заменяет ручную проверку** SQL Editor для критичных изменений.
