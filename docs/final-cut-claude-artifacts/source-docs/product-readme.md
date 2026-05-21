# Dream Wheels AI

Telegram-бот для AI-примерки автомобильных дисков. Пользователь шлёт фото машины + фото диска → бот возвращает фото машины с этими дисками через Reve API.

Бот: [@DreamWheelsAI_bot](https://t.me/DreamWheelsAI_bot)
Прод: https://dream-wheels-ai-tg.onrender.com

## Стек

- **Python 3.12** + FastAPI + Uvicorn
- **python-telegram-bot 21** (long polling)
- **PostgreSQL** (Supabase, через `asyncpg` + pooler `:6543`, `statement_cache_size=0`)
- **Redis** (Upstash, очередь задач + кэш сессий бота + rate-limit counter)
- **Reve API** — внешний AI image remix
- **Hosting**: Render (Web Service: FastAPI + бот в одном контейнере через `start.sh`)
- **CI/CD**: GitHub Actions (ruff + pytest), Render auto-deploy на `main`
- **Lint**: ruff 0.8.4 (форматтер + линтер), pre-commit hooks

## Структура

```
src/
├── config.py        # env vars
├── db.py            # asyncpg pool init/close/get
├── redis_client.py  # Redis async client init/close/get
├── reve_client.py   # Reve API wrapper (fetch + remix)
├── rate_limit.py    # Redis fixed-window rate limiter
├── main.py          # FastAPI app + lifespan + worker loop
└── bot.py           # Telegram bot (long polling)
migrations/
├── README.md            # стратегия применения миграций
├── 0001_initial.sql     # users + jobs + индексы
└── 0002_enable_rls.sql  # RLS на public-таблицах
tests/
└── test_smoke.py    # smoke-тесты (без БД/Redis)
.github/
├── workflows/ci.yml      # CI (ruff + compileall + pytest)
├── PULL_REQUEST_TEMPLATE.md
└── ISSUE_TEMPLATE/       # bug + feature
docs/
├── TEAM_HANDOFF_CHECKLIST.md
└── CHAT_CONTEXT_HANDOFF.md
```

## Архитектура

```
Telegram → bot.py (long polling)
            │
            ├─ Redis (session cache: car_url, TTL 600s)
            │
            └─ POST /jobs → main.py (FastAPI)
                            │
                            ├─ rate_limit (5 req/min на user)
                            ├─ Pydantic validation (URL prefix)
                            ├─ Postgres INSERT users + jobs
                            └─ Redis RPUSH job_queue
                                                │
                                                ▼
                            worker (asyncio task в lifespan)
                            │
                            ├─ BLPOP job_queue
                            ├─ download images → base64
                            ├─ Reve API remix
                            ├─ save static/res_<id>.jpg
                            └─ UPDATE jobs SET status='completed'

bot.py polls GET /jobs/{id} каждые 3 сек → шлёт результат юзеру
```

## API

| Endpoint | Описание |
|---|---|
| `GET /health` | Uptime check, используется Render Health Check Path |
| `POST /jobs` | Создать задачу. Body: `{telegram_user_id, car_url, wheel_url}`. Rate limit 5/мин. URL должны начинаться с `https://api.telegram.org/file/` |
| `GET /jobs/{job_id}` | Polling статуса. Ответ: `{status, output_image_url}` |

## Локальный запуск

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env  # заполнить ключи

# Backend и бот в двух отдельных терминалах:
uvicorn src.main:app --reload
python -m src.bot
```

## Тесты и линтинг

```bash
ruff check .
ruff format --check .
pytest -q
```

CI на GitHub Actions запускает то же самое автоматически на каждый push в `dev` и каждый PR в `main`/`dev`. Pre-commit hooks ловят те же проверки локально перед коммитом.

## Ветки

```
feature/* → dev → test → main
                          └─ Render auto-deploy
```

- `feature/<task>` — атомарные коммиты, ветвишься от `dev`
- `dev` — интеграция, мердж feature через PR с зелёным CI
- `test` — staging для QA (опционально)
- `main` — только release-ready, защищена branch protection (rules применяются после апгрейда на GitHub Team)

Полные правила работы с кодом — в [CONTRIBUTING.md](CONTRIBUTING.md).

## Деплой

**Auto-deploy**: Render слушает ветку `main`. Каждый мердж в `main` → автоматический rolling deploy.

```
git push origin feature/X
→ открыть PR в dev
→ CI зелёный
→ merge в dev
→ открыть PR dev → main
→ review + CI
→ merge в main
→ Render собирает (~2-3 мин)
→ сервис live на https://dream-wheels-ai-tg.onrender.com
```

**Проверка после деплоя:**
1. Render Dashboard → Events → последний deploy = `live`
2. Logs → искать `🟢 ВОРКЕР ЗАПУЩЕН` и `Application startup complete`
3. `curl https://dream-wheels-ai-tg.onrender.com/health` → `{"status":"ok"}`
4. Отправить `/start` боту в Telegram

**Известный нюанс:** rolling deploy запускает новую версию до остановки старой → 30-60 секунд два процесса бота → Telegram отвечает `Conflict: terminated by other getUpdates request`. Самовосстанавливается, ничего делать не надо.

## Rollback

Если деплой сломал прод:

1. **Render Dashboard** → сервис `dream-wheels-ai-tg` → **Events**
2. Найти последний `live` деплой ДО плохого
3. Жми `⋯` → **Rollback to this deploy**
4. Render запустит ту же сборку повторно (~30 сек, build артефакт кэширован)

**Альтернатива через git** — чище для истории, но дольше:
```bash
git revert <bad_sha>
# открыть PR dev → main, мерджнуть
```

Если деплой не стартует и rollback не помогает — проверь Render → **Environment** на сломанные env vars (последнее изменение).

## База данных

- Все DDL-изменения через миграции в [migrations/](migrations/)
- Применяются вручную через Supabase SQL Editor — см. [migrations/README.md](migrations/README.md)
- Не править схему через Supabase UI мимо файлов миграций

## Безопасность

- **RLS** включён на public-таблицах — блокирует anon-доступ через PostgREST. Бэкенд работает через `DATABASE_URL` и RLS обходит
- **Rate limit** на `POST /jobs`: 5 запросов/минуту на `telegram_user_id` через Redis-counter
- **URL whitelist**: принимаем только `https://api.telegram.org/file/...` для `car_url`/`wheel_url` (Pydantic validator)
- **Секреты** только в `.env` / Render Environment, никогда в коде/коммитах/логах

## Логирование

- Формат: `<timestamp> - <module> - <level> - <message>`
- В `except` всегда `logger.exception(...)` — даёт stack trace
- В сообщениях контекст: `job_id`, `user_id`, `telegram_user_id`
- Эмодзи для визуальной фильтрации: 🟢 startup, 🔥 in-progress, ✅ success, ❌ failure, 📥 incoming, ⛔ rate limit

## Env vars

См. [.env.example](.env.example) — список всех переменных с пояснениями. На Render задаются через Dashboard → Environment.

## Документация

- [CONTRIBUTING.md](CONTRIBUTING.md) — code style, бранчинг, логи, безопасность (для команды)
- [CLAUDE.md](CLAUDE.md) — инструкции для Claude Code
- [docs/TEAM_HANDOFF_CHECKLIST.md](docs/TEAM_HANDOFF_CHECKLIST.md) — чек-лист передачи репо команде
- [docs/CHAT_CONTEXT_HANDOFF.md](docs/CHAT_CONTEXT_HANDOFF.md) — снимок контекста для LLM-чатов
- [migrations/README.md](migrations/README.md) — стратегия применения миграций
- [pyproject.toml](pyproject.toml) — конфиг ruff
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — git pre-commit hooks
