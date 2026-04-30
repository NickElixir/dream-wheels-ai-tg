# Contributing

Гайд по работе с кодом в этом репозитории. Распространяется на всю команду — людей и AI-ассистентов.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env  # заполнить секреты
```

## Бранчинг

```
feature/* → dev → test → main
                          └─ Render auto-deploy
```

- `feature/<short-desc>` — новая фича, ветвишься от `dev`
- `fix/<bug-id>` — багфикс
- `chore/<task>` — инфраструктура, конфиг, зависимости
- `hotfix/<critical>` — от `main`, обратно в `main` + `dev` (только для прод-инцидентов)

**Никогда не пушить напрямую в `main`** — только через PR с зелёным CI.

## Коммиты

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <короткое описание в imperative mood>

<пустая строка>
<тело: что изменилось и почему>
```

Допустимые `type`: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `perf`, `style`.

Атомарные коммиты — один логический блок изменений на коммит. Не смешивать рефакторинг с фиксами.

## Pull Requests

1. Открыть PR в `dev` (или `main` для release-PR)
2. Заполнить [PR template](.github/PULL_REQUEST_TEMPLATE.md)
3. Дождаться зелёного CI (ruff + pytest)
4. Получить approve (для PR в `main`)
5. Squash & merge (для feature-веток) или Merge commit (для release-PR в main)

## Code Style

### Python

- **Python 3.12+**, `from __future__ import annotations` не требуется
- **Type hints** обязательны в сигнатурах публичных функций. Для внутренних helpers — желательны
- **`async`** везде где есть I/O. Не смешивать sync DB-вызовы в async-роутах
- **Pydantic** для валидации данных на границах (request/response, config)
- **Ruff** — единственный форматтер и линтер. Конфиг в [pyproject.toml](pyproject.toml). Запуск:
  ```bash
  ruff check .
  ruff format --check .
  ```
- **Pre-commit hooks** обязательны (`pre-commit install` после клона)

### Comments

- Минимум комментариев. Хороший именованный код > комментарий
- Комментарии — про **WHY**, не про **WHAT**. Код сам показывает что делает; комментарий объясняет почему так, а не иначе
- Особенно полезны для:
  - Workarounds платформ (`# statement_cache_size=0 для Supabase pooler`)
  - Неочевидных trade-offs
  - Ссылок на issue/доку

### Imports

- Порядок (ruff isort это делает сам):
  1. stdlib
  2. third-party
  3. local (`from src.config import ...`)
- Абсолютные импорты от `src.*`, не относительные

## Logging

**Правила:**

1. **`logger.exception(...)` в catch-блоках** — добавляет полный stack trace в логи. `logger.error(...)` теряет traceback и оставляет только текст:
   ```python
   # ❌ Плохо
   except Exception as e:
       logger.error(f"Ошибка: {e}")

   # ✅ Хорошо
   except Exception as e:
       logger.exception(f"Ошибка обработки job_id={job_id}: {e}")
   ```

2. **Контекст в сообщениях.** Включать ID/идентификаторы, по которым можно найти событие:
   ```python
   logger.info(f"✅ Задача {job_id} завершена")  # ✅
   logger.info("Done")                           # ❌
   ```

3. **Уровни:**
   - `DEBUG` — детали для разработки (по умолчанию выключено)
   - `INFO` — нормальный ход работы (старт сервиса, обработана задача)
   - `WARNING` — что-то странное, но не блокирующее (retry, deprecated path)
   - `ERROR` — ошибка с восстановлением
   - `CRITICAL` — приложение не может продолжить

4. **Эмодзи в начале** для быстрой визуальной фильтрации в Render UI:
   - 🟢 startup events
   - 🔥 in-progress
   - ✅ success
   - ❌ failure
   - 📥 incoming request

5. **Никогда не логировать секреты.** BOT_TOKEN, пароли, API keys, JWT — только маскированные (`token[:8]+"..."`). Внешние библиотеки могут логировать URL с токеном — глушить:
   ```python
   logging.getLogger("httpx").setLevel(logging.WARNING)
   ```

6. **Формат** задаётся один раз в `src/main.py` через `basicConfig`. Не настраивать локально в модулях.

## Error Handling

- **Не глотать исключения** молча. Минимум — `logger.exception(...)`, потом решение что делать
- **Не ловить `Exception`** там где можно поймать конкретный (`asyncpg.PostgresError`, `aiohttp.ClientError`)
- **На границах** (роуты, воркер) — широкий `except` оправдан, чтобы краш одной задачи не уронил весь воркер
- **Не использовать exceptions для control flow** — это медленно и нечитаемо

## Тестирование

- **Smoke тесты** в [tests/test_smoke.py](tests/test_smoke.py) — без БД/Redis, проверяют импорты и роутинг. Должны быть < 1 сек суммарно
- **Интеграционные тесты** (когда появятся) — отдельная папка `tests/integration/`, не запускаются в обычном `pytest`, помечать `@pytest.mark.integration`
- Запуск: `pytest -q`

## Безопасность

- **Секреты только в `.env`**. Никогда в коде, коммитах, логах, скриншотах
- **`.env.example`** обновлять при добавлении новых переменных
- **Ротация секретов** при любом подозрении на утечку (засветился в чате, в screenshot, в логе)
- **Ничего не пушить в `main`** напрямую
- **Деструктивные SQL** на проде — только с явным подтверждением, бэкап до этого

## База данных

- Все DDL-изменения через миграции в [migrations/](migrations/). См. [migrations/README.md](migrations/README.md)
- **Не править схему в Supabase UI** мимо файлов миграций
- Миграции идемпотентные (`IF NOT EXISTS`), порядок номеров без пропусков

## Зависимости

- **Pinned versions** в `requirements.txt` (`fastapi==0.110.0`, не `fastapi>=0.110`)
- При обновлении — отдельный `chore: bump <package>` коммит
- `requirements-dev.txt` extends `requirements.txt` через `-r requirements.txt`

## Что не делать

- ❌ Прямой push в `main`
- ❌ Force push в shared-ветки (`main`, `dev`, `test`)
- ❌ `git rebase` уже запушенных коммитов в shared-ветках
- ❌ `--no-verify` чтобы пропустить pre-commit/CI
- ❌ Коммитить `.env`, `node_modules`, `__pycache__`, `.venv`
- ❌ Коммитить большие бинарники (есть pre-commit hook на 500КБ)
- ❌ Изменения схемы БД без миграции
- ❌ Pushing secret в чат / Slack / GitHub issue
