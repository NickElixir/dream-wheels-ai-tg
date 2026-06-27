# Codex Multi-Agent Workflow

Памятка для работы с несколькими чатами в VSCode Codex extension + ChatGPT Plus.

## Основной принцип

- `DW-00 Coordinator` - постоянный главный чат проекта.
- Остальные чаты создаются заново под конкретную задачу, чтобы не накапливать устаревший контекст.
- `Domain Scan` и `Codebase Scan` работают параллельно и не изменяют файлы.
- Только `Implementation` вносит изменения.
- `Validation` получает готовый diff и независимо проверяет его.
- `Release Docs` подключается только при изменении API, env, migration, Render/Vercel или rollout.

## Быстрый запуск

1. Открой или продолжи чат `DW-00 Coordinator`.
2. Вставь задачу в [coordinator.md](prompts/coordinator.md), заменив `<TASK>`.
3. Coordinator определит сложность и подготовит task packets.
4. Для сложной задачи создай два новых чата: `DW-10 Domain Scan - <task>` и `DW-20 Codebase Scan - <task>`.
5. Передай результаты обоих чатов coordinator-у.
6. Создай `DW-30 Implementation - <task>` с финальным task packet от coordinator-а.
7. После патча создай `DW-40 Validation - <task>` и передай ему diff/ветку.
8. Верни findings coordinator-у. При необходимости он сформирует fix task или release/docs task.

Для небольшой задачи используй сокращённый flow:

```text
Coordinator -> Implementation -> Validation
```

Для payments, migrations, auth, credits и Telegram Mini App upload используй полный flow.

## Диаграмма

`AGENTS.md` не отправляет задачи в Cloud автоматически. Coordinator определяет, подходит ли work item для Cloud, и предлагает delegation; разработчик вручную запускает Cloud task в Codex extension. Задача остаётся локальной, если ей нужны local secrets, production access, интерактивная browser/Telegram проверка или частые уточнения.

```mermaid
flowchart TD
    DEV[Developer] --> COORD["DW-00 Coordinator<br/>Persistent chat"]
    COORD --> CLASSIFY{Task complexity}

    CLASSIFY -->|Small| IPACKET["Implementation task packet"]
    CLASSIFY -->|Medium / High risk| DOMAIN["DW-10 Domain Scan<br/>Read-only work item"]
    CLASSIFY -->|Medium / High risk| SCAN["DW-20 Codebase Scan<br/>Read-only work item"]

    DOMAIN --> PACKET["Coordinator combines findings<br/>and prepares implementation packet"]
    SCAN --> PACKET
    PACKET --> CLOUD
    IPACKET --> CLOUD

    CLOUD{"Cloud suitable?<br/>Well-scoped, async,<br/>no prod write or local secrets"}
    CLOUD -->|Yes| DELEGATE["Developer manually selects<br/>Delegate to Cloud"]
    CLOUD -->|No| LOCAL["Fresh local Codex chat"]

    DELEGATE --> IMPL["DW-30 Implementation<br/>Scoped patch + tests"]
    LOCAL --> IMPL
    IMPL --> VALIDATE["DW-40 Validation<br/>Independent findings-first review"]

    VALIDATE --> RESULT{Findings?}
    RESULT -->|Yes| COORD
    RESULT -->|No| IMPACT{Release impact?}

    IMPACT -->|API / env / migration / deploy| DOCS["DW-50 Release Docs<br/>Docs and rollout notes"]
    IMPACT -->|No| FINAL["Coordinator final review"]
    DOCS --> FINAL

    FINAL --> CHECKS["Local checks / CI"]
    CHECKS --> PROD{Production write?}
    PROD -->|No| DONE["Ready for commit / PR"]
    PROD -->|Yes| APPROVE["Explicit developer approval"]
    APPROVE --> DONE

    subgraph Skills["Repo-local skill sources"]
        PAY["dreamwheels-payments"]
        DATA["dreamwheels-data-storage"]
        WEB["dreamwheels-telegram-webapp"]
        RUN["dreamwheels-runtime-release"]
        REVIEW["dreamwheels-review"]
    end

    COORD -. selects exact SKILL.md path .-> PAY
    COORD -. selects exact SKILL.md path .-> DATA
    COORD -. selects exact SKILL.md path .-> WEB
    COORD -. selects exact SKILL.md path .-> RUN
    VALIDATE -. uses .-> REVIEW
```

## Шаблоны

- [coordinator.md](prompts/coordinator.md) - классификация и orchestration.
- [domain-scan.md](prompts/domain-scan.md) - бизнес-инварианты и внешние ограничения.
- [codebase-scan.md](prompts/codebase-scan.md) - call flow, файлы, тесты и change surface.
- [implementation.md](prompts/implementation.md) - scoped patch и проверки.
- [validation.md](prompts/validation.md) - независимый findings-first review.
- [release-docs.md](prompts/release-docs.md) - env, migrations, deploy и документация.

## Имена чатов

```text
DW-00 Coordinator
DW-10 Domain Scan - <short-task>
DW-20 Codebase Scan - <short-task>
DW-30 Implementation - <short-task>
DW-40 Validation - <short-task>
DW-50 Release Docs - <short-task>
```

## Ограничения

- Не запускай два implementation-чата на одни и те же файлы.
- Не передавай агентам секреты и содержимое `.env`.
- Cloud tasks не должны применять production migrations или изменять live services.
- В каждом task packet указывай branch/base, scope, relevant files, verification commands и точный repo-path `docs/agent-skills/<name>/SKILL.md`.
- Coordinator должен проверить противоречия между результатами до начала implementation.

## Worktrees And Symlinks

Skills устанавливаются глобально в `~/.codex/skills`, но symlinks указывают на конкретный checkout. Если открыть несколько worktrees Dream Wheels одновременно, последний запуск installer переключит все `dreamwheels-*` links на текущий worktree.

После переключения worktree переустанови links из нужного checkout:

```bash
bash scripts/install-agent-skills.sh
```

Проверка текущих targets:

```bash
ls -l ~/.codex/skills/dreamwheels-*
```

Cloud tasks не наследуют локальные symlinks. Поэтому они должны читать skill по repo-path, указанному в task packet.
