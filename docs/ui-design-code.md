# Dream Wheels AI — UI Design Code

> **Status:** approved reference for Sprint 1 Cabinet Dashboard
>
> Canonical interactive prototype: `docs/references/sprint-1-dashboard.html`

## Scope and boundaries

This document defines the approved user-facing design and interaction rules for the Cabinet Dashboard, upload entry, balance/wallet and render history. It is a UI reference, not a replacement for backend contracts.

Fitment UI is intentionally out of scope until **Parallel F2 — Fitment UI integration** in the Dual-Track Product Roadmap. Do not add fitment verdicts to the Sprint 1 dashboard, render cards or history.

## Visual foundation

Use the established dark Dream Wheels AI system:

- background: `#070809` with restrained dark radial glow;
- panels: `#161a22`, `#1b2029`, `#202631`;
- primary text: `#eef2f6`;
- muted text: `#a3adba` and `#7e8896`;
- primary accent: `#ddff00` / `#e7ff3a`;
- semantic colors: success `#27d88a`, warning `#ffcc56`, danger `#ff6666`;
- card radii: 18–28 px; thin translucent borders; soft panel shadows.

Do not allow native browser button text colours to leak into the UI. Interactive cards, upload zones and buttons explicitly inherit the design-system foreground colour.

For this product UI, standalone paragraph-style copy should not end with a period
This applies to ledes, helper text, empty states, support copy, form guidance and similar short interface text
Exceptions are explicit multi-sentence legal text, technical payloads and copy where punctuation is required for clarity

## Buttons and action chips

Use a small, consistent button family across the cabinet:

- primary CTA uses the acid fill, dark foreground, strong weight, and the largest visual priority;
- secondary actions use a dark island chip with a thin border, 44-48 px minimum height, rounded corners, and a restrained hover tint;
- accent secondary chips may keep the same island base while using accent text for actions like open, sign in, or disclose;
- inline panel actions should not appear as naked text links when they compete with other controls in the same block;
- compact actions such as `Открыть`, `Сбросить`, `Обновить счет`, `Пополнить баланс`, download/share, and website Telegram login should stay within the same secondary-chip family;
- buttons should visually align with the panel system, avoid browser-default fills, and preserve comfortable tap targets on mobile.

## Responsive navigation

### Desktop layout rail

Desktop screens must reserve a real layout column for the permanent sidebar.
Do not rely on a visually fixed sidebar floating over the page content.

Rules:

- sidebar has a fixed width and its own viewport inset;
- main content starts only after `sidebar width + sidebar inset + content gutter`;
- use a centered content rail with a bounded max width instead of stretching task screens across the full viewport;
- keep at least 40 px visual gutter between sidebar and the nearest panel at desktop widths;
- topbar, hero panels and content panels align to the same content rail;
- panels and status islands use visible vertical gaps, so warnings, upload zones, cards and forms never touch each other.
- help instruction cards should be centered, with the label and explanation stacked vertically and separated by a visible gap;
- help instruction cards should sit in a two-column row on desktop and collapse to a single column on mobile;
- do not let the label and the explanatory paragraph run into each other on desktop help screens.
- the payment history disclosure title should be visually prominent like the main section headers, without a secondary "collapsed by default" hint in the header.

### Desktop

Permanent left sidebar:

```text
Основное
- Главная
- Примерить диски
- Мои примерки
- Баланс

Помощь
- Поддержка
- Как подготовить фото
- Документы
```

The Dream Wheels AI wordmark is a button that returns to **Главная**. The account block remains at the bottom of the sidebar.

### Mobile

Bottom navigation:

```text
Главная · Создать · История · Баланс · Ещё
```

`Ещё` opens a compact bottom sheet with Support, photo guidance and documents.

### Navigation motion

Use restrained motion only:

- active desktop item: accent vertical indicator, accent-soft background;
- hover: small horizontal shift, no excessive bounce;
- screen transition: fade + `translateY(-6px → 0)` over about 300 ms;
- respect `prefers-reduced-motion`.

## Status islands

Use the established island pattern for asynchronous states and warnings:

- hidden: `max-height: 0`, zero vertical padding, `opacity: 0`, `translateY(-6px)`;
- shown: content height up to 320 px, normal padding, `opacity: 1`, `translateY(0)`;
- timings: 220–280 ms;
- tones: loading, success, warning, error.

Do not use islands for every interaction. Use them only for meaningful state, validation or account information.

## Dashboard

The dashboard contains:

1. account heading;
2. balance card;
3. latest render card or a first-use empty state;
4. primary CTA: **Создать виртуальную примерку**;
5. quick links: **Мои примерки**, **Нужна помощь?**.

### Dashboard card headers

Dashboard summary cards such as balance and latest result must use a resilient internal header layout:

- use a two-zone header: content block on the left, action chip or status chip on the right;
- do not rely on a raw single-line flex row when the left side contains a large metric or multi-line title;
- the content block must allow shrinking with `min-width: 0`, while the action or status chip remains auto-sized;
- when the card container becomes narrow, the action or status chip should move below the content instead of compressing or overlapping the metric;
- card-internal responsive behavior should follow the card container width, not only the full viewport width.

### Balance terminology

Use **рендеры** in the Russian UI. Avoid exposing `credits` as a primary user-facing term.

### Render-expiry island

When and only when the backend supports grant-level expiry data, show the compact island:

```text
Срок действия рендеров                         Подробнее →

16 рендеров                                    до 15 июля
20 рендеров                                    до 30 июля

⚠ Сначала используются рендеры с ближайшей датой окончания.
```

Layout rules:

- no decorative hourglass icon;
- title and `Подробнее →` share the header row;
- each availability line is a two-column row: quantity left, date right;
- dates use accent colour;
- the warning is a thin bottom line, not a nested card;
- `Подробнее →` opens **Баланс** and expands the purchase/expiry history.

Until immutable grants/expiry backend behaviour is approved and implemented, this island must be omitted rather than populated by mock or local data.

## Upload entry

Use the approved existing upload screen:

```text
Загрузите фото машины и диска
Машина целиком сбоку, диск анфас. JPG или PNG, до 10 МБ.
```

- two large stacked zones: **Фото машины**, **Фото диска**;
- user-facing labels and helper text must remain light-coloured;
- soft warning island may remind the user that wheels should be fully visible;
- this screen does not yet collect vehicle/rim technical data.

## Wallet and top-up

Use the approved existing three-step payment layout rather than a new wallet redesign:

1. choose package;
2. enter receipt email;
3. confirm and open Robokassa.

Keep the package emojis:

```text
⚡ 100 ₽
🏁 200 ₽
💎 500 ₽
👑 1 000 ₽
```

Any package expiry text is subject to the same backend condition as the render-expiry island.

## Render history

Use the title **Мои виртуальные примерки**. Do not expose raw filenames or transport errors.

### Collapsed render card

```text
[ preview ]  Lexus RX · виртуальная примерка
             Сегодня, 14:32
             Готово                         Открыть
```

- completed items: preview, readable car/scenario name, date and `Готово` status;
- processing items: `Создаём результат` and `В обработке`;
- failed items: readable failure copy and `Повторить` that returns to create flow.

### Open action

`Открыть` expands the result inside the same history card:

- only one card may be open at a time;
- transition uses the status-island disclosure pattern;
- full result image uses full card width, `width: 100%`, `height: auto`, no `object-fit: cover` crop;
- action changes to `Скрыть ▲`;
- show **Скачать изображение** and **Создать ещё вариант** beneath the image.

Original/result comparison belongs to Sprint 3 and is intentionally not part of the Sprint 1 reference.

## First-use and visual artwork

Cinematic automotive imagery is appropriate for Launch Screen, landing and first-use empty state, not as persistent decoration on task-heavy screens.

The last-result preview must show a real result image with preserved aspect ratio. It must not use a schematic placeholder or cropped composition that hides the car.

## Implementation handoff

Before implementing Sprint 1, Codex must treat `docs/references/sprint-1-dashboard.html` and this document as the approved visual reference. Preserve the existing application’s API and authentication boundaries; do not convert the prototype’s mock data into a frontend source of truth.
