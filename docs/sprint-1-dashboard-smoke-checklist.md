# Sprint 1 Cabinet Dashboard — staging smoke checklist

Use staging only: staging Telegram bot, staging Vercel WebApp, staging Render backend,
staging Supabase and staging Redis namespace/prefix.

1. Open the staging Telegram bot.
2. Open the Mini App via `/start` or `/app`.
3. Check Dashboard with no render history.
4. Check Dashboard with a completed render.
5. Check Dashboard with a processing render.
6. Check Dashboard with a failed render.
7. Verify the real latest-result preview is not cropped.
8. Open `Мои примерки`.
9. Expand a completed render card.
10. Verify opening a second render closes the first.
11. Verify `Создать ещё вариант` opens the create flow.
12. Verify mobile bottom navigation.
13. Verify desktop sidebar navigation.
14. Verify website Telegram Login flow.
15. Verify wallet navigation and top-up flow entry.
16. Verify expiry island is hidden unless backend returns real immutable expiry-grant data.
17. Refresh the app and verify dashboard/history still come from backend data.
18. Check owner isolation with another staging test account.
19. Confirm production bot, Render, Vercel, Supabase, Storage and env vars are untouched.
