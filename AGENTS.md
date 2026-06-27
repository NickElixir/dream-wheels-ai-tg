# AGENTS.md

Router-инструкции для Codex в этом репозитории. Детальные правила живут в `CONTRIBUTING.md` и project skills.

## Project

Dream Wheels AI: Telegram-бот и Mini App backend для AI-примерки автомобильных дисков.

Stack: Python 3.12, FastAPI, asyncpg, Redis/Upstash, Supabase Postgres/Storage, python-telegram-bot, Reve API, Robokassa, Render.

## Hard Rules

- Перед изменениями кода читать `CONTRIBUTING.md`.
- Общение с пользователем на русском, технически и кратко.
- Не объяснять основы Python/FastAPI/async/REST/Git без запроса.
- Type hints в публичных Python-сигнатурах, async для I/O, абсолютные импорты от `src.*`.
- Ruff - единственный formatter/linter; запускать релевантные проверки после правок.
- В `except` использовать `logger.exception(...)` с контекстом (`job_id`, `user_id`, `telegram_user_id`).
- Секреты не логировать, не коммитить, не выводить в чат.
- `.env.example` обновлять при новых env vars.
- Все DDL-изменения только через `migrations/`; не править Supabase schema UI мимо миграций.
- Деструктивные действия, prod-write, SQL `DROP`/массовые `DELETE`, force push, Render/Supabase/Robokassa live операции - только после явного подтверждения.
- Перед утверждениями о внешних сервисах сверяться с official docs.

## Skills

Shared skill sources лежат в `docs/agent-skills/`. Чтобы Codex начал использовать их автоматически, установи symlinks:

```bash
bash scripts/install-agent-skills.sh
```

Используй skills по доменам:

- `dreamwheels-payments`: Robokassa, payments, invoice, receipt, signature, ResultURL, SuccessURL, top-up, credits, ledger, idempotency.
- `dreamwheels-data-storage`: migrations, Supabase, RLS, Storage buckets, policies, SQL rollout, schema compatibility.
- `dreamwheels-telegram-webapp`: Telegram Mini App, `initData`, frontend upload/polling, file picker, IndexedDB drafts, Telegram SDK, Vercel frontend config.
- `dreamwheels-runtime-release`: Render, deploy, rollback, health check, env vars, Telegram polling conflict, keep-alive, runtime logs.
- `dreamwheels-review`: code review, PR review, findings-first, risk scan, test selection, change impact.

Если несколько skills подходят, выбрать основной домен и подключать второй только для конкретного риска: payments + data-storage для платежной миграции, telegram-webapp + payments для UI оплаты, runtime-release + review для релизного review.

## Codex Cloud

Если задача длинная, хорошо ограничена по scope и не требует production-write действий, рекомендовать Codex Cloud из VSCode Codex extension. Хорошие кандидаты: рефакторинг, тесты, review, поиск regressions, документация, подготовка миграции без применения в prod.

`AGENTS.md` не отправляет задачу в Cloud автоматически. Агент должен предложить delegation и подготовить task packet; разработчик вручную запускает Cloud task в Codex extension.

Перед передачей в Cloud сформировать task packet:

```markdown
Goal:
<один конкретный результат>

Repo context:
- Branch/base: <текущая ветка и целевая ветка>
- Relevant files: <пути к ключевым файлам>
- Primary skill path: docs/agent-skills/<skill-name>/SKILL.md
- Read first: AGENTS.md, CONTRIBUTING.md, README.md, <domain docs>

Constraints:
- Follow CONTRIBUTING.md.
- Do not touch secrets or .env.
- Do not apply migrations or call production APIs.
- Keep changes scoped to <modules>.
- Add/update tests for changed behavior.

Verification:
- Run: ruff check .
- Run: ruff format --check .
- Run: pytest -q
- If a command cannot run, report why.

Output:
- Summary of changes.
- Tests run and results.
- Risks, assumptions, and follow-up needed.
```

## Multi-Agent Flow

Для VSCode Codex extension мультиагентность = несколько отдельных Codex чатов/Cloud tasks, координируемых главным coordinator-чатом.

Готовые prompt templates и диаграмма: `docs/agent-workflows/README.md`.

Coordinator:

- классифицирует задачу и выбирает основной skill;
- указывает точный repo-path к `SKILL.md` в каждом Cloud task packet;
- дробит работу на независимые task packets;
- запрещает агентам выходить за scope и трогать одни и те же файлы без причины;
- собирает результаты и принимает финальный diff.

Роли по умолчанию:

- `domain scan`: ищет бизнес/интеграционные ограничения в выбранном skill.
- `codebase scan`: ищет затронутые файлы, call paths, tests.
- `implementation`: делает scoped patch.
- `validation`: проверяет diff в review mindset, findings-first.
- `docs`: подключается только если меняется API, env, rollout, migration или user-facing behavior.

Если в текущем интерфейсе доступен Codex subagents workflow, можно просить: `Spawn one agent per point, wait for all results, then summarize findings`.

## Local MCP / Env

MCP-серверы (`render`, `supabase`, `upstash`) читают токены из env-переменных при старте Codex.

macOS quirk: GUI-приложения, включая VSCode, не читают `~/.zshrc`. Чтобы env подтянулся: закрыть VSCode, открыть Terminal/iTerm, `cd <repo>`, запустить `code .`, затем перезапустить Codex в новом VSCode window.

## Canonical References

- `CONTRIBUTING.md` - code style, logging, branching, security.
- `README.md` - stack, architecture, deploy, rollback.
- `migrations/README.md` - database migration strategy.
- `.env.example` - env vars.
- `docs/TEAM_HANDOFF_CHECKLIST.md` - team handoff.
- `docs/agent-workflows/README.md` - multi-agent prompts and developer flow.
- `docs/CHAT_CONTEXT_HANDOFF.md` - historical project context; use carefully, may be stale.
