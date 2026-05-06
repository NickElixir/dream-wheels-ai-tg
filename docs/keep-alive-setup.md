# Keep-alive setup

Один внешний cron, который раз в 6 часов стучится на `/health/full`. Решает три проблемы сразу:

1. **Supabase auto-pause** — Free tier ставит проект на паузу после 7 дней без SQL-запросов
2. **Render free spin-down** — контейнер засыпает после 15 мин без HTTP-трафика
3. **Upstash idle** — на Free лимита по простою нет, но мониторинг полезен

`/health/full` дёргает `SELECT 1` в Postgres и `PING` в Redis — обе системы видят активность.

---

## Endpoint

```
GET https://dream-wheels-ai-tg.onrender.com/health/full
```

Успех:
```json
{"status": "ok", "db": "alive", "redis": "alive"}
```

При ошибке возвращает 503 с описанием — алерт сработает автоматически.

---

## Основной вариант — cron-job.org

Бесплатный, без регистрации требуется только email.

### Регистрация

1. https://cron-job.org/en/signup/
2. Email + пароль → Sign up
3. Подтвердить email из письма

### Создать cron-job

1. **Cronjobs** → **Create cronjob**
2. **Title**: `Dream Wheels keep-alive`
3. **URL**: `https://dream-wheels-ai-tg.onrender.com/health/full`
4. **Schedule**: вкладка **Common** → выбери **Every 6 hours**
   - Если хочется тонко настроить: **Custom** → `0 */6 * * *` (в 00:00, 06:00, 12:00, 18:00 UTC)
5. **Notifications** (вкладка): включи **Notify on failure** — придёт email если endpoint вернёт не-2xx два раза подряд
6. **Save**

### Проверка

После сохранения cron сразу запустится. На странице cron'а появится **History** с результатами:
- Зелёные — 200 OK
- Красные — ошибка (timeout, 503 и т.п.)

Один пинг каждые 6 часов = 4 запроса/день = 120/месяц. Бесплатный лимит cron-job.org — 50 cron'ов на аккаунт, без ограничения по числу запусков.

### Почему 6 часов

- **Supabase**: считает активность за 7 дней. 4 пинга/день — с большим запасом.
- **Render**: spin-down 15 мин. Между пингами 6 часов → контейнер успеет заснуть, и каждый пинг будет «холодным» (50 сек). Это нормально — нам не важна низкая latency keep-alive, важно что хоть один SQL-запрос произошёл.
- **Render free-tier 75 ч/мес**: при 4 пингах × 1 мин активного времени ≈ 4 минуты в день ≈ 2 ч/мес. Запас огромный.

Если станет важно держать контейнер warm для кастдевов — увеличь до **каждые 10 минут в часы интервью** (расписание Custom).

---

## Backup — скрипт на домашнем компьютере

На случай если cron-job.org упадёт или ты захочешь собственный мониторинг.

### macOS — launchd (нативный планировщик)

Создай `~/Library/LaunchAgents/com.dreamwheels.keepalive.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dreamwheels.keepalive</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>curl -s -m 60 -o /tmp/dw-keepalive.log -w "%{http_code} %{time_total}s\n" https://dream-wheels-ai-tg.onrender.com/health/full &gt;&gt; /tmp/dw-keepalive.history</string>
    </array>

    <key>StartInterval</key>
    <integer>21600</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardErrorPath</key>
    <string>/tmp/dw-keepalive.err</string>
</dict>
</plist>
```

Активировать:

```sh
launchctl load ~/Library/LaunchAgents/com.dreamwheels.keepalive.plist
```

Проверить:

```sh
launchctl list | grep dreamwheels
tail -f /tmp/dw-keepalive.history
```

Деактивировать (если потом захочешь убрать):

```sh
launchctl unload ~/Library/LaunchAgents/com.dreamwheels.keepalive.plist
rm ~/Library/LaunchAgents/com.dreamwheels.keepalive.plist
```

Каждые 21600 сек = 6 часов. `RunAtLoad=true` — пинг сразу после загрузки macOS, чтобы не ждать первого интервала.

⚠️ Работает **только когда Mac включён**. Если ноут спит/выключен — пинга не будет. Поэтому это **backup**, а не основной механизм.

### Альтернатива — простой crontab

Если не хочется возиться с launchd:

```sh
crontab -e
```

Добавить строку:

```
0 */6 * * * /usr/bin/curl -s -m 60 https://dream-wheels-ai-tg.onrender.com/health/full > /dev/null 2>&1
```

Сохранить (`:wq` в vim или `Ctrl+X, Y, Enter` в nano).

`crontab -l` — посмотреть что добавилось. `crontab -r` — удалить весь crontab.

⚠️ macOS crontab требует разрешения **Full Disk Access** для приложения `cron` в System Settings → Privacy & Security → Full Disk Access — иначе будет молча падать.

---

## Мониторинг

cron-job.org сам показывает **History** успехов/фейлов. Если хочется красивый дашборд — подключи бесплатный **UptimeRobot** на тот же endpoint, у него Slack/Telegram-нотификации из коробки.

Для нашего масштаба — встроенных уведомлений cron-job.org достаточно.

---

## Что делать если Supabase всё-таки уснёт

1. Зайти в https://supabase.com/dashboard/project/qmgyccghsbdpehiybjae
2. Кнопка **Restore project** (большая, на главном экране проекта)
3. Подождать ~1-2 минуты
4. Проверить keep-alive cron — почему он не сработал? Скорее всего fail-нотификация уже пришла на почту
