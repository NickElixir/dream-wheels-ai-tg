# Dream Wheels AI — WebApp (Vercel)

Telegram Mini App для прототипа кастдева. Статический фронтенд: `index.html` + `style.css` + `app.js`. Хостится на Vercel, открывается в Telegram через кнопку в боте.

## Что внутри

- **`index.html`** — основной entrypoint Mini App
- **`style.css`** — dark theme, использует `--tg-theme-*` CSS-переменные Telegram
- **`app.js`** — Telegram WebApp SDK (MainButton, BackButton, HapticFeedback), file upload, заглушка submit
- **`vercel.json`** — security headers, CSP и rewrite для маршрута `/t/`
- **`README.md`** — этот файл

## Текущее состояние

Этот деплой — **первый итерационный шаг**: проверяем, что Vercel + Telegram WebApp работают вместе. Backend интеграция (`POST /jobs/upload`) **пока не подключена** — submit имитирован 4-секундной задержкой, в качестве "результата" возвращается фото машины. Подключение к настоящему backend будет в следующем PR.

## Локальная разработка

```bash
cd webapp
python3 -m http.server 5173
# открыть http://localhost:5173
```

Telegram-функции (MainButton, initData) работают только внутри Telegram-клиента. Локально страница откроется как обычный сайт с fallback-кнопкой внизу — этого достаточно для проверки вёрстки и логики.

## Первый деплой на Vercel

```bash
cd webapp
vercel              # preview deploy → URL вида dream-wheels-abc123.vercel.app
vercel --prod       # production deploy → постоянный URL
```

CLI спросит:
- **Set up and deploy?** → `Y`
- **Which scope?** → твой Vercel-аккаунт
- **Link to existing project?** → `N` (первый раз)
- **Project name?** → например `dream-wheels-webapp`
- **Directory?** → `./` (мы уже в webapp/)
- **Override settings?** → `N`

После `vercel --prod` получишь URL — его нужно вставить в @BotFather для регистрации Mini App.

## Регистрация Mini App в Telegram

1. Открой [@BotFather](https://t.me/BotFather)
2. `/newapp` → выбери `@DreamWheelsAI_bot`
3. **Title**: `Dream Wheels AI`
4. **Description**: `AI-рендер тюнинга колёс`
5. **Photo**: 640x360 png/jpg
6. **GIF**: пропусти (необязательно)
7. **Web App URL**: `https://<твой-vercel-url>`
8. **Short name**: `dreamwheels` (для прямой ссылки `t.me/DreamWheelsAI_bot/dreamwheels`)

После регистрации в боте появится кнопка `Open App` (если добавить через `/setmenubutton`) или Mini App открывается по прямой ссылке.

## Проверка в Telegram

1. Открой `t.me/DreamWheelsAI_bot/dreamwheels` (или нажми Menu → Open App в боте)
2. Mini App должно открыться на твоём Vercel-URL
3. Нативная нижняя кнопка `MainButton` "Дальше" появляется внизу
4. После загрузки фото машины — кнопка активируется
5. На экране диска — `BackButton` сверху для возврата
6. После submit — заглушка 4 сек → результат

## Auto-deploy из GitHub (опционально)

После первого `vercel --prod`:
1. https://vercel.com/dashboard → твой проект
2. **Settings** → **Git** → Connect Git Repository → выбери `dream-wheels-ai-tg`
3. **Root Directory**: `webapp` (важно — деплой только из этой папки)
4. **Production Branch**: `main`

После этого каждый push в `main` автоматически передеплоит prod. Каждый push в feature-branch создаст preview-URL для PR-ревью.

## Что дальше — не в этом PR

- Backend endpoint `POST /jobs/upload` (multipart, Supabase Storage)
- Валидация Telegram `initData` HMAC на backend
- Идемпотентность через `idempotency_key`
- Rate limiting 10 generations/hour per user
- Реальный polling статуса задачи

См. [../docs/architecture.md](../docs/architecture.md) для целевой архитектуры.
