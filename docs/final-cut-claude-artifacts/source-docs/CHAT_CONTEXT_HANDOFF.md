# Контекст проекта Dream Wheels AI — для передачи в Claude Desktop

## Кто пользователь

**Николай Луценко** — Python Backend Developer (4+ года прод-опыт), магистр Сколтеха (Engineering Systems / AI in Robotics).

**Прод-опыт релевантный проекту:**
- НМИЦ Блохина (2025): FastAPI + PostgreSQL + Redis микросервисы, JWT, RBAC, Repository pattern
- Дрим Холдинг (2021–2025): Python e-commerce backend, REST API, маркетплейсы
- ML/Robotics: ROS2, OpenCV, YOLO, ONNX, edge на Raspberry Pi

**Стиль общения:**
- Русский язык, технический. НЕ объяснять основы Python/FastAPI/REST/JWT/ORM
- Default — 3-7 предложений. Yes/no — одно предложение
- Без жизненных аналогий, без trailing summary
- DO объяснять: Render-quirks, Supabase pooler, Upstash, Telegram polling vs webhook
- Watch: иногда спрашивает "что такое X?" чтобы проверить контекст проекта, не потому что не знает

## Что за проект

**Dream Wheels AI** — Telegram-бот для AI-примерки автомобильных дисков. Пользователь шлёт фото машины + фото диска → бот возвращает картинку машины с этими дисками через Reve API.

**Стек:**
- Python 3.12.2
- FastAPI + Uvicorn (бэкенд)
- python-telegram-bot 21 (бот, long polling)
- PostgreSQL (Supabase, через asyncpg, pooler port 6543 + statement_cache_size=0)
- Redis (Upstash, через redis-py async, для очереди задач + сессии бота)
- Reve API (внешний AI image remix endpoint)
- Hosting: Render Free tier (один Web Service запускает FastAPI + бота через `start.sh`)

**Архитектура (после рефакторинга):**
```
dream-wheels-ai-tg/
├── src/
│   ├── config.py        # все env vars в одном месте
│   ├── db.py            # asyncpg pool init/close/get
│   ├── redis_client.py  # redis async client
│   ├── reve_client.py   # обёртка Reve API (fetch_image_base64, remix_wheels_on_car)
│   ├── main.py          # FastAPI app + lifespan + worker loop
│   └── bot.py           # Telegram bot (long polling, ленивый Redis)
├── migrations/
│   ├── 0001_initial.sql       # users + jobs + индексы
│   └── 0002_enable_rls.sql    # RLS на public.*
├── tests/
│   └── test_smoke.py    # 3 теста (health, root, POST /jobs validation)
├── docs/
│   ├── TEAM_HANDOFF_CHECKLIST.md
│   └── CHAT_CONTEXT_HANDOFF.md  # этот файл
├── .github/
│   ├── workflows/ci.yml         # ruff + pytest на PR
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/
├── pyproject.toml       # ruff config (line-length=100, py312)
├── .pre-commit-config.yaml
├── requirements.txt
├── requirements-dev.txt # +pytest, httpx, ruff==0.4.2
├── runtime.txt          # python-3.12.2
├── start.sh             # uvicorn src.main:app + python -m src.bot
└── CLAUDE.md            # инструкции для Claude Code
```

**Поток работы бота:**
1. `/start` → "пришли фото машины"
2. Юзер шлёт первое фото → URL сохраняется в Redis (`session:<user_id>:car_url`, TTL 600s)
3. Юзер шлёт второе фото → бэкенд `POST /jobs` с обоими URL
4. FastAPI создаёт запись в `jobs` (status=queued), пушит в Redis-очередь `job_queue`
5. Воркер (asyncio.task в lifespan) забирает blpop, ставит status=processing
6. Скачивает обе картинки → base64 → Reve API → бинарь → файл `static/res_<job_id>.jpg`
7. Update jobs SET status=completed, output_image_url=...
8. Бот polls `GET /jobs/{id}` каждые 3s до 3 минут → шлёт юзеру результат

## Текущее состояние

**Деплой:** работает на Render, последний деплой live на коммите `c008431`.
**Бот:** @DreamWheelsAI_bot, активен (если не спит на Free spin-down 15 мин).
**CI:** GitHub Actions зелёный (ruff + pytest).

**Ветки:**
- `main` — prod (Render auto-deploy), защищена branch protection (если настроена)
- `dev` — интеграция, текущая активная ветка
- `test` — staging для QA

**Что сделано в последней сессии (Claude Code):**
1. Рефакторинг плоского main.py/bot.py → модульная структура `src/`
2. Создание FastAPI `lifespan` (вместо deprecated `@app.on_event`)
3. Фикс Supabase pooler (`statement_cache_size=0`)
4. Подавление httpx INFO-логов (текли BOT_TOKEN)
5. Извлечение PUBLIC_BASE_URL в env
6. Миграции БД в `migrations/`
7. Smoke-тесты + venv + ruff + pre-commit
8. GitHub Actions CI + PR/issue templates
9. Ленивая инициализация Redis в bot.py (для проходимости тестов)

## Известные проблемы / TODO

**Безопасность:**
- В чате утекали секреты (BOT_TOKEN, Supabase password, Redis password, Upstash API key, Render API key) — нужна ротация всех
- Нет rate limiting на POST /jobs
- Нет аутентификации на API endpoints

**Архитектура:**
- FastAPI и бот в одном процессе — при rolling deploy 30-60s Conflict от Telegram polling. Решение: разнести на 2 Render-сервиса (Starter план)
- `static/` хранится на эфемерном диске Render (теряется при деплое) → нужен Supabase Storage
- Render Free spin-down 15 мин убивает long-poll бота → upgrade до Starter $7/мес

**Качество:**
- Нет mypy / type checking в CI
- Нет интеграционных тестов с реальной БД
- README.md ещё не написан
- Branch protection на main ещё не настроена

## Ссылки

- Repo: https://github.com/NickElixir/dream-wheels-ai-tg (приватный)
- Render Service ID: `srv-d6u344fkijhs73ffnukg`
- Supabase project ref: `qmgyccghsbdpehiybjae`
- Render dashboard: https://dashboard.render.com/web/srv-d6u344fkijhs73ffnukg

## Окружение разработчика

- macOS Apple Silicon M1, Homebrew в `/opt/homebrew`
- Python 3.12 через `/opt/homebrew/opt/python@3.12/bin/python3.12`
- VS Code с Claude Code extension
- `.venv` в проекте, активируется через `source .venv/bin/activate`
- pre-commit включён (ruff format + check, trailing whitespace, private keys)
