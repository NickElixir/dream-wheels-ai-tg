# Dream Wheels AI — архитектура

Диаграммы рендерятся:
- На **GitHub** автоматически в UI
- В **VS Code** через расширения:
  - `bierner.markdown-mermaid` (Markdown Preview Mermaid Support) — рендерит в стандартном Markdown Preview (`Cmd+Shift+V`)
  - `tomoyukim.vscode-mermaid-editor` — отдельный live-preview
- На https://mermaid.live можно вставить код и экспортнуть PNG/SVG

**Цветовая палитра** (используется во всех диаграммах ниже):
- 🔵 синий — frontend / клиент (WebApp, Telegram client)
- 🟣 фиолетовый — backend (FastAPI, Worker)
- 🟢 зелёный — данные (Postgres, Storage)
- 🟠 оранжевый — Redis (очередь, кэш, rate-limit)
- 🔴 красный — внешние API (Reve)
- ⚪ серый — ops/инфра (keep-alive, monitoring)

---

## 1. Текущий пайплайн (Telegram bot only)

Как сейчас работает прод, до WebApp.

```mermaid
sequenceDiagram
    actor User as Юзер
    participant Bot as bot.py
    participant API as FastAPI
    participant DB as Postgres
    participant Q as Redis
    participant W as Worker
    participant R as Reve API
    participant S as Storage

    User->>Bot: Фото машины
    Bot->>Q: сохранить в session (1)
    Bot-->>User: "Теперь фото диска"
    User->>Bot: Фото диска
    Bot->>API: POST /jobs
    API->>DB: INSERT job (queued)
    API->>Q: RPUSH job_queue
    API-->>Bot: {job_id}
    Bot-->>User: "В очереди..."

    loop poll каждые 3 сек
        Bot->>API: GET /jobs/{id}
        API-->>Bot: status
    end

    W->>Q: BLPOP job_queue
    W->>DB: UPDATE processing
    W->>R: image/remix (2)
    R-->>W: result
    W->>S: PUT result
    W->>DB: UPDATE completed

    Bot-->>User: 📸 Готово
```

**Сноски:**
1. `SETEX session:{user_id}:car_url 600` — TTL 10 минут на сессию между двумя фото.
2. `POST /image/remix` с двумя фото в base64.

---

## 2. Целевая архитектура с WebApp — data plane

После реализации Telegram WebApp на Vercel. Здесь — основной поток запрос→ответ. Ops (keep-alive, мониторинг) вынесен в §2b.

```mermaid
graph TB
    subgraph Client["User device"]
        TG[Telegram client]
        TG -->|opens| WA[WebApp UI]
    end

    subgraph Edge["Vercel"]
        WA[index.html + JS<br/>Telegram SDK]
    end

    subgraph Render["Render: один контейнер"]
        API[FastAPI<br/>main.py]
        Worker[Worker loop]
        API -.same process.- Worker
    end

    subgraph TG_["Telegram"]
        Bot[bot.py<br/>long-poll]
    end

    subgraph Data["Supabase"]
        PG[(Postgres)]
        Storage[Storage<br/>photos + results]
    end

    Redis[(Upstash Redis<br/>queue + sessions + rate-limit)]
    Reve[Reve API]

    WA -->|POST /jobs/upload| API
    WA -->|GET /jobs/:id| API
    Bot -->|POST /jobs| API
    Bot -->|GET /jobs/:id| API

    API --> Redis
    API --> PG
    API --> Storage

    Worker --> Redis
    Worker --> Storage
    Worker --> PG
    Worker --> Reve

    classDef frontend fill:#1a3a52,color:#fff,stroke:#4a7ba8
    classDef backend fill:#3a1a52,color:#fff,stroke:#7b4aa8
    classDef data fill:#1a523a,color:#fff,stroke:#4aa87b
    classDef cache fill:#523a1a,color:#fff,stroke:#a87b4a
    classDef external fill:#521a3a,color:#fff,stroke:#a84a7b

    class TG,WA frontend
    class API,Worker,Bot backend
    class PG,Storage data
    class Redis cache
    class Reve external
```

---

## 2b. Ops plane — keep-alive

Render Free засыпает после 15 минут без запросов. Чтобы бот и API не «лагали» при первом обращении после простоя — внешний пинг каждые 6 часов.

```mermaid
graph LR
    KA[cron-job.org<br/>каждые 6ч]
    Backup[launchd на Mac<br/>backup, при включённом ноуте]
    API[FastAPI<br/>/health/full]
    PG[(Postgres)]
    Redis[(Redis)]

    KA -->|GET /health/full| API
    Backup -.->|GET /health/full| API
    API -->|SELECT 1| PG
    API -->|PING| Redis

    classDef ops fill:#3a3a3a,color:#fff,stroke:#777
    classDef backend fill:#3a1a52,color:#fff,stroke:#7b4aa8
    classDef data fill:#1a523a,color:#fff,stroke:#4aa87b
    classDef cache fill:#523a1a,color:#fff,stroke:#a87b4a

    class KA,Backup ops
    class API backend
    class PG data
    class Redis cache
```

Подробности — [keep-alive-setup.md](keep-alive-setup.md).

---

## 3. Поток создания задачи через WebApp — happy path

Что происходит когда юзер тапает Generate в Mini App. Pre-checks (валидация initData, rate-limit) вынесены в §3b.

```mermaid
sequenceDiagram
    actor U as Юзер
    participant W as WebApp
    participant A as FastAPI
    participant S as Storage
    participant DB as Postgres
    participant R as Redis
    participant Wk as Worker
    participant Reve as Reve API

    U->>W: Открывает Mini App
    W-->>U: "Загрузи фото машины"
    U->>W: car.jpg
    W-->>U: "Теперь диск"
    U->>W: wheel.jpg + Generate

    W->>A: POST /jobs/upload (1)
    Note over A: pre-checks — см. §3b
    A->>S: PUT car.jpg, wheel.jpg
    A->>DB: INSERT job (queued)
    A->>R: RPUSH job_queue
    A-->>W: {job_id}

    loop poll каждые 3 сек
        W->>A: GET /jobs/{id}
        A-->>W: status
    end

    Wk->>R: BLPOP job_queue
    Wk->>S: GET car.jpg, wheel.jpg
    Wk->>Reve: image/remix
    Reve-->>Wk: result
    Wk->>S: PUT result.jpg
    Wk->>DB: UPDATE completed

    W->>A: GET /jobs/{id}
    A-->>W: completed + url
    W-->>U: результат + HapticFeedback.success
```

**Сноски:**
1. `FormData: car, wheel, idempotency_key` + header `X-Telegram-Init-Data`.

---

## 3b. Pre-checks — auth + rate-limit + idempotency

Что делает FastAPI до того как принять задачу.

```mermaid
flowchart TD
    Req([POST /jobs/upload])
    Auth{HMAC initData<br/>валиден?}
    RL["INCR rate_limit:user_id"]
    Limit{count > 10?}
    Idem{idempotency_key<br/>уже в БД?}
    Existing[вернуть существующий job_id]
    New[INSERT новую job]

    Req --> Auth
    Auth -->|нет| R401([401 Unauthorized])
    Auth -->|да| RL
    RL --> Limit
    Limit -->|да| R429([429 + retry_after])
    Limit -->|нет| Idem
    Idem -->|да| Existing
    Idem -->|нет| New
    New --> OK([200 + job_id queued])
    Existing --> OK

    classDef ok fill:#1a523a,color:#fff,stroke:#4aa87b
    classDef err fill:#521a1a,color:#fff,stroke:#a84a4a
    class OK ok
    class R401,R429 err
```

---

## 4. Структура репозитория

```mermaid
graph LR
    Repo[dream-wheels-ai-tg/]

    Repo --> Backend[main.py · bot.py<br/>requirements.txt · start.sh]
    Repo --> WebApp[webapp/]
    Repo --> Docs[docs/]
    Repo --> Migrations[migrations/]
    Repo --> Config[.gitignore · .mcp.json<br/>.env.example]

    WebApp --> WAFiles[index.html · style.css<br/>app.js · vercel.json]
    Docs --> DocFiles[architecture.md<br/>keep-alive-setup.md<br/>TEAM_HANDOFF_CHECKLIST.md]
    Migrations --> MigFiles[0001_initial.sql<br/>0002_add_idempotency_key.sql]

    classDef frontend fill:#1a3a52,color:#fff,stroke:#4a7ba8
    classDef backend fill:#3a1a52,color:#fff,stroke:#7b4aa8
    classDef data fill:#1a523a,color:#fff,stroke:#4aa87b

    class WebApp,WAFiles frontend
    class Backend backend
    class Docs,DocFiles data
```

---

## 5. Состояния задачи (job lifecycle)

Все возможные переходы статуса в таблице `jobs`.

```mermaid
stateDiagram-v2
    [*] --> queued: POST /jobs/upload
    queued --> processing: воркер взял из BLPOP
    processing --> completed: Reve вернул картинку
    processing --> failed: ошибка / таймаут 90с
    completed --> [*]
    failed --> [*]

    note right of queued
        В Redis job_queue
        UI: "В очереди..."
    end note

    note right of processing
        30-90 сек
        UI: "Генерируем..."
    end note

    note right of failed
        error_message в БД
        UI: ошибка + retry
    end note
```

---

## 6. Rate limiting через Redis

Лимит 10 генераций в час на юзера.

```mermaid
flowchart TD
    Start([POST /jobs/upload<br/>user_id=42]) --> Incr["INCR rate_limit:42"]
    Incr --> Check{count > 10?}
    Check -->|нет| First{count == 1?}
    First -->|да| Expire["EXPIRE 3600"]
    First -->|нет| Process[Создать задачу]
    Expire --> Process
    Process --> Success([200 OK])
    Check -->|да| Reject([429 + retry_after])

    classDef ok fill:#1a523a,color:#fff,stroke:#4aa87b
    classDef err fill:#521a1a,color:#fff,stroke:#a84a4a
    class Success ok
    class Reject err
```

Ключ `rate_limit:{user_id}` живёт 1 час. После истечения — счётчик сбрасывается.

---

## Как просматривать в VS Code

1. Установи **Markdown Preview Mermaid Support** (`bierner.markdown-mermaid`)
2. Открой этот файл, `Cmd+Shift+V` — preview справа

## Как экспортировать в PNG/SVG

1. https://mermaid.live
2. Скопируй содержимое `mermaid` блока без бэктиков
3. **Actions** → PNG или SVG
