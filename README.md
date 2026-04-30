# Dream Wheels AI

Telegram-бот для AI-примерки автомобильных дисков. Пользователь шлёт фото машины + фото диска → бот возвращает фото машины с этими дисками через Reve API.

Бот: [@DreamWheelsAI_bot](https://t.me/DreamWheelsAI_bot)

## Стек

- **Python 3.12** + FastAPI + Uvicorn
- **python-telegram-bot 21** (long polling)
- **PostgreSQL** (Supabase, через `asyncpg` + pooler `:6543`)
- **Redis** (Upstash, очередь задач + кэш сессий бота)
- **Reve API** — внешний AI image remix
- **Hosting**: Render (Web Service: FastAPI + бот в одном контейнере через `start.sh`)

## Структура

```
src/
├── config.py        # env vars
├── db.py            # asyncpg pool
├── redis_client.py  # Redis async client
├── reve_client.py   # Reve API wrapper
├── main.py          # FastAPI app + lifespan + worker
└── bot.py           # Telegram bot
migrations/          # SQL-миграции
tests/               # smoke-тесты
.github/workflows/   # CI (ruff + pytest)
```

## Локальный запуск

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # заполнить ключи
uvicorn src.main:app --reload &
python -m src.bot
```

## Тесты и линтинг

```bash
ruff check . && ruff format --check .
pytest -q
```

CI запускает то же самое автоматически на каждый PR в `main` или `dev`.

## Ветки

```
feature/* → dev → test → main
                          └─ Render auto-deploy
```

- `feature/<task>` — атомарные коммиты, ветвишься от `dev`
- `dev` — интеграция, мердж feature через PR с зелёным CI
- `test` — staging для QA (опционально)
- `main` — только release-ready, защищена branch protection

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

**Альтернатива через git:** revert-коммит — чище для истории, но дольше:
```bash
git revert <bad_sha>
git push origin main  # запустит новый деплой
```

Если деплой не стартует и rollback не помогает — проверь Render → **Environment** на сломанные env vars (последнее изменение).

## Health check

`GET /health` → `{"status":"ok"}`. Render Settings → Health & Alerts → **Health Check Path** = `/health` (если включить, Render автоматически рестартует контейнер при недоступности).

## Env vars

См. [.env.example](.env.example) — список всех переменных с пояснениями. На Render задаются через Dashboard → Environment.

## Документация

- [docs/TEAM_HANDOFF_CHECKLIST.md](docs/TEAM_HANDOFF_CHECKLIST.md) — чек-лист передачи репо команде
- [CLAUDE.md](CLAUDE.md) — инструкции для Claude Code
- [pyproject.toml](pyproject.toml) — конфиг ruff
