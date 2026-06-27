# Mini App Frontend Lifecycle

Official references:

- https://core.telegram.org/bots/webapps
- https://core.telegram.org/bots/api

## Code Map

- `webapp/app.js`: application state, Telegram SDK integration, localization, upload, polling, wallet, feedback, result download/share.
- `webapp/index.html`: root entry page.
- `webapp/t/index.html`: `/t/` entry page used by configured WebApp URL paths.
- `webapp/style.css`: shared responsive UI.
- `webapp/vercel.json`: redirects and security headers.
- `src/bot.py`: Telegram button that opens `WEBAPP_URL`.

## Lifecycle Invariants

- Call Telegram SDK readiness/expansion behavior only when `window.Telegram.WebApp` exists.
- Keep a normal-browser fallback for local layout and request-flow testing.
- `initDataUnsafe` can supply display hints, language, and convenience data; it is not an authorization proof.
- Preserve `BackButton`, native button, haptics, download/share fallbacks, and viewport behavior when changing navigation.
- Revoke object URLs when replacing image previews.
- Persist selected image bytes in IndexedDB before transitions that may trigger WebView reload; hydrate drafts before reporting missing files.
- Clear draft files only when the workflow has safely completed or the user explicitly resets them.

## UI Change Checklist

- Test narrow mobile viewport and desktop fallback.
- Check safe-area insets and Telegram theme variables.
- Keep `webapp/index.html` and `webapp/t/index.html` markup aligned.
- Update Russian and English strings together.
- Verify loading, empty, error, retry, insufficient-credit, timeout, and completed states.
- Ensure dynamic text and filenames do not break controls or layouts.

## Telegram-Only Checks

Local browser testing does not prove:

- valid `tg.initData`;
- native Main/Back button behavior;
- haptic feedback;
- `Telegram.WebApp.downloadFile` acceptance;
- file-picker/WebView reload behavior;
- Telegram theme and safe-area behavior.
