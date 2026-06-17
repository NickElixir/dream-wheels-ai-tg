# AGENTS.md

Инструкции для Codex в этом репозитории. Читается автоматически при старте сессии.

## Code conventions (single source of truth)

**Перед изменениями кода прочитай [CONTRIBUTING.md](CONTRIBUTING.md)** — там полный гайд по стилю, бранчингу, коммитам, логированию, безопасности. Дублировать не буду; основные пункты, актуальные при каждой генерации:

### Logging — обязательно соблюдать

```python
# ❌ НЕ делать
except Exception as e:
    logger.error(f"Ошибка: {e}")

# ✅ Делать
except Exception as e:
    logger.exception(f"Ошибка обработки job_id={job_id}: {e}")
```

- `logger.exception` в catch-блоках (даёт stack trace)
- Контекст в сообщениях: `job_id`, `user_id`, `telegram_user_id`
- Эмодзи в начале: 🟢 startup, 🔥 in-progress, ✅ success, ❌ failure, 📥 incoming
- Никогда не логировать секреты (BOT_TOKEN, пароли)

### Code style

- Python 3.12, type hints в публичных сигнатурах
- Async везде где I/O
- `from src.config import ...` (абсолютные импорты)
- Минимум комментариев. Комментарии — про **WHY**, не **WHAT**
- Pydantic для валидации на границах
- Ruff форматирует и линтит — конфиг в [pyproject.toml](pyproject.toml)

### Коммиты и ветки

- Conventional commits: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`
- Ветви: `feature/* → dev → test → main`
- **НЕ пушить в `main`** напрямую — только через PR
- Атомарные коммиты, не смешивать рефакторинг с фиксами

### Безопасность

- Секреты только в `.env`, никогда в коде/коммитах/чате/логах
- `.env.example` обновлять при новых переменных
- Деструктивные действия (DROP, DELETE без WHERE, force push) — подтверждение

## Профиль пользователя

**Николай Луценко** — Python Backend Developer (4+ года прод-опыт), магистр Сколтеха (Engineering Systems / AI in Robotics).

**Прод-опыт:**
- НМИЦ Блохина (2025): FastAPI + PostgreSQL + Redis микросервисы, JWT, RBAC, Repository pattern
- Дрим Холдинг (2021–2025): Python e-commerce backend, REST API, маркетплейсы
- Robotics & CV: ROS2, OpenCV, ONNX, YOLO fine-tuning, edge на Raspberry Pi
- ML/DL: Keras, PyTorch, TensorFlow (DeepLearning School МФТИ)

## Стиль ответов

### НЕ объяснять (использует профессионально)

- Python: async/await, type hints, классы, декораторы, контекстные менеджеры
- Backend: REST, JWT, ORM, миграции, connection pooling, prepared statements
- FastAPI / Pydantic / asyncpg — основы
- ML-термины: модель, инференс, fine-tuning, квантизация
- Git, conventional commits, pre-commit
- Patterns (Repository, Factory)
- Linux / Bash базы

### Сразу технически

- "Asyncpg падает на pgBouncer transaction mode — нужен `statement_cache_size=0`"
- "lifespan заменил on_event с FastAPI 0.93+"
- "RLS на public.* блокирует PostgREST anon-доступ"
- "Render Free spin-down 15 мин убивает long-poll бота"

### Можно пояснить кратко

- Render-quirks: rolling deploys, Free tier spin-down, port detection, Health Check
- Supabase pooler quirks (port 5432 vs 6543, pool modes)
- Upstash REST vs RESP, free tier limits
- Telegram polling vs webhook trade-offs
- Новые фичи Python 3.12+ если использую
- MCP-протокол

### Длина и формат

- **Default = 3-7 предложений**
- Yes/no — одно предложение
- Развёрнуто только при: архитектурных trade-offs, новых платформенных концепциях, явной просьбе, security/data-loss рисках
- Без жизненных аналогий
- Без trailing summary
- Таблицы — только при сравнении опций или показе данных
- Заголовки `##` — только в реально длинных ответах (>15 строк)
- Эмодзи — только если просит явно

### Watch

Иногда спрашивает "что такое X?" не потому что не знает, а проверяет проектный контекст. Default — концизный технический ответ; если нужна глубина, попросит сам.

## Технические предпочтения

- **OS**: macOS Apple Silicon M1, Homebrew в `/opt/homebrew`, arm64 native
- **Stack**: Python 3.12, FastAPI, asyncpg, redis-py, python-telegram-bot. Render hosting. Supabase Postgres + Upstash Redis
- **Languages**: код на Python, общение по-русски, code comments на русском допустимы
- **Идиомы**: type hints всегда, Pydantic для валидации, async везде где I/O

## Auto mode

Когда auto mode активен — действовать без переспросов по мелочам. Деструктивные/production-write действия — всё равно подтверждение.

## Полезные ссылки

- [CONTRIBUTING.md](CONTRIBUTING.md) — полный гайд по работе с кодом
- [README.md](README.md) — стек, деплой, rollback
- [docs/TEAM_HANDOFF_CHECKLIST.md](docs/TEAM_HANDOFF_CHECKLIST.md) — чек-лист передачи команде
- [migrations/README.md](migrations/README.md) — стратегия миграций БД
- [.env.example](.env.example) — переменные окружения
- [pyproject.toml](pyproject.toml) — ruff config
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — git hooks
