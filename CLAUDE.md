# Инструкции для Claude Code

Этот файл автоматически загружается в контекст Claude Code при работе в этом репозитории.

## Кто я

**Николай Луценко** — Python Backend Developer с 4+ годами production-опыта, параллельно — магистр Сколтеха (Engineering Systems / AI in Robotics).

Релевантный опыт:
- **FastAPI + PostgreSQL + Redis** — стек один-в-один с этим проектом. Работал в НМИЦ Блохина над Medical Data Platform (микросервисы, Pydantic-валидация, JWT, RBAC, Repository pattern).
- **E-commerce backend** 4 года (ООО «Дрим Холдинг») — Python + SQL + REST API, интеграции с маркетплейсами/CRM.
- **Robotics & CV**: ROS/ROS2, OpenCV, ONNX, YOLO fine-tuning, edge deployment на Raspberry Pi.
- **ML/DL**: Keras, PyTorch, TensorFlow (DeepLearning School МФТИ + проекты Сколтеха).
- **DevOps базовый**: Docker, веб-безопасность, адаптивная вёрстка.

## Что это значит для ответов

### НЕ объяснять
- Базовые концепции Python (async/await, type hints, классы, декораторы, контекстные менеджеры)
- Стандартный backend-стек: REST, JWT, ORM, миграции, pooling, prepared statements
- FastAPI/Pydantic/asyncpg — основы
- ML-термины (модели, инференс, fine-tuning, квантизация) — рабочая лексика
- Git/conventional commits/pre-commit — знакомо
- Patterns (Repository, Factory, и т.д.) — рабочая лексика
- Linux/Bash — базовый уровень есть

### Можно сразу технически
- "Asyncpg падает на pgBouncer transaction mode из-за prepared statements — нужен statement_cache_size=0"
- "lifespan заменил on_event с FastAPI 0.93+"
- "RLS на public.* блокирует доступ через PostgREST anon-ключ"
- "Render Free spin-down 15 мин убивает long-poll бота"

### Стоит пояснить (если возникнет)
- Специфика конкретных платформ: **Supabase pooler ports**, **Render rolling deploy quirks**, **Upstash REST vs RPESP**, **Telegram Bot API webhook vs polling trade-offs**
- Новые фичи Python 3.12+ (если использую)
- MCP-протокол (раз с ним только начали работать)
- Эзотерика конкретных libs (например, `pg_hashids`, `pgvector` сетапы)

## Стиль ответов

### Длина
- **Default = 3-7 предложений**
- На "да/нет" вопросы — **одно предложение**
- Развёрнуто — только если явно прошу или это архитектурное решение с trade-offs

### Структура
- Без аналогий из жизни
- Без trailing summary в конце
- Таблицы — только при сравнении опций или показе данных
- Заголовки `##` — только в реально длинных ответах (>15 строк)
- Если спрашиваю "что такое X?" про новый платформенный концепт — ответ всё равно краткий, ссылка на доку лучше длинного объяснения

### Код
- Минимум комментариев (только "почему", не "что")
- Диффом + одной строкой что изменилось
- Если есть ссылка на доку или релевантный issue — давать её, не пересказывать

## Когда отвечать развёрнуто

- Архитектурное решение с неочевидными trade-offs
- Новый платформенный/инфраструктурный концепт (Render-specific, Supabase-specific, MCP)
- Я явно прошу подробностей
- Безопасность/data-loss риски — здесь развёрнуто всегда

## Технические предпочтения

- **OS**: macOS Apple Silicon (M1). Homebrew в `/opt/homebrew`. arm64 native.
- **Stack этого проекта**: Python 3.12, FastAPI, asyncpg, redis-py, python-telegram-bot. Render hosting. Supabase Postgres + Upstash Redis.
- **Языки**: код на Python, общение на русском. Code comments — можно по-русски.
- **Git**: атомарные коммиты + conventional commits (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`).
- **Линтинг**: ruff (формат + лайнт), pre-commit hooks.
- **Идиомы**: type hints всегда, Pydantic для валидации, async везде где можно.

## Безопасность

- **Не вставлять секреты в чат** — credentials, API keys, пароли БД.
- **Не пушить в `main` без явного разрешения** — даже в auto mode. Сначала commit локально.
- **Не выполнять SQL на production** без явного разрешения с указанием цели.
- **Деструктивные действия** (DROP, DELETE без WHERE, force push, rm -rf) — всегда подтверждение.

## Auto mode

Когда auto mode активен — действуй, не переспрашивай по мелочам. Деструктивные/production-write действия — всё равно подтверждение.

## Полезные ссылки

- [docs/TEAM_HANDOFF_CHECKLIST.md](docs/TEAM_HANDOFF_CHECKLIST.md) — что нужно сделать перед передачей репо команде
- [.env.example](.env.example) — переменные окружения с пояснениями
- [pyproject.toml](pyproject.toml) — конфиг ruff
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — git pre-commit хуки
