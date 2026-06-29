const tg = window.Telegram?.WebApp;
const HAS_TG = Boolean(tg && typeof tg.expand === "function" && tg.platform && tg.platform !== "unknown");

function tgSupports(version) {
    if (!HAS_TG) return false;
    if (typeof tg.isVersionAtLeast !== "function") return false;
    return tg.isVersionAtLeast(version);
}

const SUPPORTS_BACK_BUTTON = tgSupports("6.1");
const SUPPORTS_HAPTIC = tgSupports("6.1");
const SUPPORTS_DOWNLOAD_FILE = tgSupports("8.0") && typeof tg?.downloadFile === "function";

const PROD_API_BASE_URL = "https://dream-wheels-ai-tg.onrender.com";
const STAGING_API_BASE_URL = "https://dream-wheels-ai-robokassa-staging.onrender.com";
const LOCAL_API_BASE_URL = "http://127.0.0.1:10000";
const API_MODE_STORAGE_KEY = "dreamWheelsApiMode";
const DEV_TELEGRAM_USER_ID_STORAGE_KEY = "dreamWheelsDevTelegramUserId";
const WEBSITE_AUTH_STORAGE_KEY = "dreamWheelsWebsiteAuth";
const RECENT_RENDERS_STORAGE_KEY = "dreamWheelsRecentRenders";
const TELEGRAM_LOGIN_SCRIPT_URL = "https://oauth.telegram.org/js/telegram-login.js?5";
const PRICING_VERSION = "credits-v1";
const TOPUP_MIN_AMOUNT = 100;
const TOPUP_MAX_AMOUNT = 3000;
const TOPUP_PACKAGES = [
    { amount: 100, credits: 3, icon: "⚡" },
    { amount: 200, credits: 7, icon: "🏁" },
    { amount: 500, credits: 20, icon: "💎" },
    { amount: 1000, credits: 45, icon: "👑" },
];
const PAYMENT_PENDING_FRESH_MS = 60 * 1000;
const PAYMENT_PENDING_STALE_MS = 15 * 60 * 1000;
const PAYMENT_PENDING_AUTO_REFRESH_DELAY_MS = 10 * 1000;
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 110000;
const DRAFT_DB_NAME = "dream-wheels-upload-draft";
const DRAFT_STORE_NAME = "files";

const I18N = {
    ru: {
        auth: {
            login: "Войти через Telegram",
            loggingIn: "Входим...",
            logout: "Выйти",
            failed: "Не удалось войти через Telegram",
        },
        menu: {
            create: "Создать рендер",
            wallet: "Кошелек",
            renders: "История рендеров",
            settings: "Настройки",
            support: "Поддержка",
            docs: "Документы",
        },
        caption: {
            create: "Рендер",
            wallet: "Кабинет",
            renders: "Рендеры",
            settings: "Настройки",
            support: "Поддержка",
            docs: "Документы",
        },
        create: {
            eyebrow: "Главный экран",
            title: "Загрузи фото машины и диска",
            lede: "Машина целиком сбоку, диск анфас. JPG или PNG, до 10 MB.",
            carPhoto: "Фото машины",
            wheelPhoto: "Фото диска",
            choose: "Нажми, чтобы выбрать",
            replaceCar: "Заменить машину",
            replaceWheel: "Заменить диск",
            carPreviewAlt: "Превью машины",
            wheelPreviewAlt: "Превью диска",
            footerNotTelegram: "Не в Telegram",
        },
        steps: {
            upload: "Загрузка",
            result: "Готово",
        },
        status: {
            creating: "Создаём задачу...",
            startingServer: "Запускаем сервер...",
            coldStart: "Первый запуск может занять до 40 секунд",
            uploading: "Загружаем файлы...",
            upTo90: "Это может занять до 90 секунд",
            generating: "Генерируем рендер...",
        },
        result: {
            imageAlt: "AI рендер",
            title: "Готово!",
            caption: "Ваш рендер с новыми дисками готов.",
        },
        actions: {
            createRender: "Создать рендер",
            createAnother: "Сделать ещё один",
            download: "Скачать",
            downloadImage: "Скачать изображение",
            requestingDownload: "Запрашиваем скачивание...",
            downloadCanceled: "Скачивание отменено",
            downloadStarted: "Скачивание началось",
            downloadFailed: "Скачать не удалось",
            share: "Поделиться",
            preparing: "Готовим...",
            openingTelegram: "Открываем Telegram",
            sent: "Отправлено",
            linkCopied: "Ссылка скопирована",
            openingLink: "Открываем ссылку",
            canceled: "Отменено",
            failed: "Не удалось",
            openRender: "Открыть",
        },
        errors: {
            generic: "Что-то пошло не так",
            missingFiles: "Файлы не выбраны — вернитесь и загрузите оба фото",
            generationFailed: "Ошибка генерации",
            timeout: "Превышено время ожидания (>110 с)",
            requestFailed: "Запрос не удался. Попробуйте ещё раз.",
        },
        share: {
            text: "Мой рендер в Dream Wheels AI",
        },
        wallet: {
            eyebrow: "Кабинет",
            title: "Мой Dream Wheels AI",
            lede: "Здесь видны баланс, последний счет и быстрый платежный flow в три шага",
            gift: "Подарок",
            lastInvoiceLabel: "Последний счет",
            lastInvoiceTitle: "Статус виден сразу после оплаты",
            lastInvoiceEmpty: "Оплат еще не было. После первой покупки здесь появится последний счет",
            invoiceAmount: "Сумма",
            invoiceNumber: "Счет",
            invoiceEmail: "Email",
            invoiceCredits: "Начисление",
            invoiceState: "Состояние",
            wizardLabel: "Пополнение",
            wizardTitle: "Три шага оплаты",
            reset: "Сбросить",
            stepAmount: "Сумма",
            stepEmail: "Email",
            stepConfirm: "Подтверждение",
            stepChooseTitle: "Выберите пакет",
            stepChooseSub: "Пакетный режим активен по умолчанию",
            chooseAmount: "Выбор суммы",
            nextToEmail: "Продолжить",
            modePackage: "Пакет",
            modeCustom: "Своя сумма",
            customAmountLabel: "Своя сумма",
            emailLabel: "Email для чека",
            emailHint: "Используем его для чека и подтверждения оплаты",
            back: "Назад",
            nextToConfirm: "Продолжить",
            confirmAmount: "Сумма",
            confirmEmail: "Email",
            confirmCredits: "Начисление",
            confirmHint: "Проверьте пакет перед переходом в Robokassa",
            pay: "Оплатить",
            paymentNote: "Оплата откроется через Robokassa. Credits начисляются после подтверждения",
            paymentHistory: "История платежей",
            paymentHistoryHint: "Скрыта по умолчанию",
            openHistory: "Открыть",
            emptyHistory: "Платежей пока нет",
            noPaymentsTitle: "Платежей пока нет",
            noPaymentsMeta: "Первый подарок появится в истории платежей",
            loading: "Загружаем кабинет...",
            refreshInvoice: "Обновить счет",
            refreshingInvoice: "Обновляем статус счета...",
            openingPayment: "Открываем Robokassa...",
            paymentSuccess: "Оплата подтверждена. Обновляем баланс.",
            paymentFail: "Платеж не завершен.",
            pendingFresh: "Счет создан. Если вы вернулись из Robokassa, обновите его через несколько секунд",
            pendingStale: "Счет все еще ждет подтверждения. Если оплата не прошла, он останется в ожидании, пока мы не получим финальный статус. Обновите счет позже",
            authRequired: "Откройте Mini App в Telegram или войдите через Telegram на сайте",
            fallbackDisabled: "Web fallback выключен на backend",
            starterGrantTitle: "Первый подарок",
            starterGrantMeta: "{credits} credits · начислено при первом входе",
            starterGrantBadge: "Подарок",
            summaryEmptyTitle: "Выберите пакет",
            summaryEmptyMeta: "Здесь появится выбранный пакет перед оплатой",
            summaryPackageTitle: "Выбранный пакет",
            summaryCustomTitle: "Своя сумма",
            pendingInvoice: "Счет #{invoiceId} · {amount}",
            paidInvoice: "Счет #{invoiceId} · {amount}",
            failedInvoice: "Счет #{invoiceId} · {amount}",
            packageMetaDays: "{credits} credits · 30 дней",
            packageSummary: "{amount} · {credits} credits · 30 дней",
        },
        renders: {
            eyebrow: "Готовые работы",
            title: "История рендеров",
            lede: "Здесь видны последние сохраненные рендеры на этом устройстве.",
            empty: "Готовых рендеров пока нет. Создайте первый на главном экране.",
            completed: "Готов",
            failed: "Ошибка",
        },
        settings: {
            eyebrow: "Параметры кабинета",
            title: "Настройки",
            lede: "Формальный экран для будущих параметров профиля и уведомлений.",
            profileTitle: "Профиль Telegram",
            profileText: "Связан автоматически с Mini App.",
            notificationsTitle: "Уведомления",
            notificationsText: "Будут добавлены позже.",
            languageTitle: "Язык интерфейса",
            languageText: "Определяется по Telegram.",
            linked: "Подключено",
            soon: "Скоро",
        },
        support: {
            eyebrow: "Связь",
            title: "Поддержка",
            lede: "Короткий и формальный экран контактов без лишнего текста.",
            telegram: "Telegram",
            email: "Email",
            offer: "Оферта",
            refund: "Возврат",
            pdn: "ПДн",
            requisites: "Реквизиты",
        },
        docs: {
            eyebrow: "Документы",
            title: "Документы",
            lede: "Формальный список ссылок на юридические и справочные материалы.",
            offer: "Оферта",
            privacy: "Политика конфиденциальности",
            payments: "Условия оплаты",
        },
        failed: "Сбой",
        starter: "Стартовый грант",
        pending: "В ожидании",
        paid: "Оплачено",
        created: "Создан",
        locale: "RU",
        credits: "credits",
    },
    en: {
        auth: {
            login: "Log in with Telegram",
            loggingIn: "Logging in...",
            logout: "Log out",
            failed: "Telegram login failed",
        },
        menu: {
            create: "Create render",
            wallet: "Wallet",
            renders: "Render history",
            settings: "Settings",
            support: "Support",
            docs: "Documents",
        },
        caption: {
            create: "Render",
            wallet: "Cabinet",
            renders: "Renders",
            settings: "Settings",
            support: "Support",
            docs: "Documents",
        },
        create: {
            eyebrow: "Main screen",
            title: "Upload your car and wheel photos",
            lede: "Full side view of the car, front view of the wheel. JPG or PNG, up to 10 MB.",
            carPhoto: "Car photo",
            wheelPhoto: "Wheel photo",
            choose: "Tap to choose",
            replaceCar: "Replace car",
            replaceWheel: "Replace wheel",
            carPreviewAlt: "Car preview",
            wheelPreviewAlt: "Wheel preview",
            footerNotTelegram: "Not in Telegram",
        },
        steps: {
            upload: "Upload",
            result: "Done",
        },
        status: {
            creating: "Creating job...",
            startingServer: "Starting server...",
            coldStart: "First launch can take up to 40 seconds",
            uploading: "Uploading files...",
            upTo90: "This can take up to 90 seconds",
            generating: "Generating render...",
        },
        result: {
            imageAlt: "AI render",
            title: "Done!",
            caption: "Your render with new wheels is ready.",
        },
        actions: {
            createRender: "Create render",
            createAnother: "Create another",
            download: "Download",
            downloadImage: "Download image",
            requestingDownload: "Requesting download...",
            downloadCanceled: "Download canceled",
            downloadStarted: "Download started",
            downloadFailed: "Download failed",
            share: "Share",
            preparing: "Preparing...",
            openingTelegram: "Opening Telegram",
            sent: "Sent",
            linkCopied: "Link copied",
            openingLink: "Opening link",
            canceled: "Canceled",
            failed: "Failed",
            openRender: "Open",
        },
        errors: {
            generic: "Something went wrong",
            missingFiles: "Files are missing. Go back and upload both photos.",
            generationFailed: "Generation failed",
            timeout: "Timed out after 110 seconds",
            requestFailed: "Request failed. Please try again.",
        },
        share: {
            text: "My Dream Wheels AI render",
        },
        wallet: {
            eyebrow: "Cabinet",
            title: "My Dream Wheels AI",
            lede: "Balance, last invoice, and a three-step payment flow in one place",
            gift: "Gift",
            lastInvoiceLabel: "Last invoice",
            lastInvoiceTitle: "Status appears immediately after payment",
            lastInvoiceEmpty: "No payments yet. The first purchase will show up here as the last invoice",
            invoiceAmount: "Amount",
            invoiceNumber: "Invoice",
            invoiceEmail: "Email",
            invoiceCredits: "Credits",
            invoiceState: "Status",
            wizardLabel: "Top up",
            wizardTitle: "Three payment steps",
            reset: "Reset",
            stepAmount: "Amount",
            stepEmail: "Email",
            stepConfirm: "Confirm",
            stepChooseTitle: "Choose a package",
            stepChooseSub: "Package mode stays enabled by default",
            chooseAmount: "Amount selection",
            nextToEmail: "Continue",
            modePackage: "Package",
            modeCustom: "Custom",
            customAmountLabel: "Custom amount",
            emailLabel: "Receipt email",
            emailHint: "Used for the receipt and payment confirmation",
            back: "Back",
            nextToConfirm: "Continue",
            confirmAmount: "Amount",
            confirmEmail: "Email",
            confirmCredits: "Credits",
            confirmHint: "Review the package before opening Robokassa",
            pay: "Pay",
            paymentNote: "Robokassa opens on tap. Credits are applied after confirmation",
            paymentHistory: "Payment history",
            paymentHistoryHint: "Collapsed by default",
            openHistory: "Open",
            emptyHistory: "No payments yet",
            noPaymentsTitle: "No payments yet",
            noPaymentsMeta: "The first gift will appear in payment history",
            loading: "Loading cabinet...",
            refreshInvoice: "Refresh invoice",
            refreshingInvoice: "Refreshing invoice status...",
            openingPayment: "Opening Robokassa...",
            paymentSuccess: "Payment confirmed. Refreshing balance.",
            paymentFail: "Payment was not completed.",
            pendingFresh: "Invoice created. If you returned from Robokassa, refresh it in a few seconds",
            pendingStale: "The invoice is still waiting for confirmation. If the payment did not go through, it may stay pending until a final status arrives. Refresh it later",
            authRequired: "Open the Mini App in Telegram or log in with Telegram on the website",
            fallbackDisabled: "Web fallback is disabled on the backend",
            starterGrantTitle: "Starter gift",
            starterGrantMeta: "{credits} credits · added on first launch",
            starterGrantBadge: "Gift",
            summaryEmptyTitle: "Choose a package",
            summaryEmptyMeta: "The selected package will appear here before payment",
            summaryPackageTitle: "Selected package",
            summaryCustomTitle: "Custom amount",
            pendingInvoice: "Invoice #{invoiceId} · {amount}",
            paidInvoice: "Invoice #{invoiceId} · {amount}",
            failedInvoice: "Invoice #{invoiceId} · {amount}",
            packageMetaDays: "{credits} credits · 30 days",
            packageSummary: "{amount} · {credits} credits · 30 days",
        },
        renders: {
            eyebrow: "Finished work",
            title: "Render history",
            lede: "Recent renders saved on this device.",
            empty: "No renders yet. Create your first one on the main screen.",
            completed: "Done",
            failed: "Failed",
        },
        settings: {
            eyebrow: "Cabinet settings",
            title: "Settings",
            lede: "A formal screen for future profile and notification options.",
            profileTitle: "Telegram profile",
            profileText: "Linked automatically through the Mini App.",
            notificationsTitle: "Notifications",
            notificationsText: "Will be added later.",
            languageTitle: "Interface language",
            languageText: "Detected from Telegram.",
            linked: "Connected",
            soon: "Soon",
        },
        support: {
            eyebrow: "Contact",
            title: "Support",
            lede: "A short formal contact screen without extra content.",
            telegram: "Telegram",
            email: "Email",
            offer: "Offer",
            refund: "Refund",
            pdn: "Privacy",
            requisites: "Details",
        },
        docs: {
            eyebrow: "Documents",
            title: "Documents",
            lede: "A formal list of legal and reference materials.",
            offer: "Offer",
            privacy: "Privacy policy",
            payments: "Payment terms",
        },
        failed: "Failed",
        starter: "Starter grant",
        pending: "Pending",
        paid: "Paid",
        created: "Created",
        locale: "EN",
        credits: "credits",
    },
};

function detectLocale() {
    const telegramLanguage = tg?.initDataUnsafe?.user?.language_code;
    const browserLanguage = navigator.language;
    const language = (telegramLanguage || browserLanguage || "en").toLowerCase();
    return language.startsWith("ru") ? "ru" : "en";
}

const locale = detectLocale();

function t(path) {
    return path.split(".").reduce((value, key) => value?.[key], I18N[locale]) ?? path;
}

function resolveApiBaseUrl() {
    const params = new URLSearchParams(window.location.search);
    const apiBase = params.get("apiBase");
    const apiMode = params.get("api");

    if (apiBase) {
        return apiBase.replace(/\/+$/, "");
    }
    if (apiMode) {
        localStorage.setItem(API_MODE_STORAGE_KEY, apiMode);
    }

    const storedMode = localStorage.getItem(API_MODE_STORAGE_KEY) || apiMode || "";
    if (storedMode === "local") return LOCAL_API_BASE_URL;
    if (storedMode === "staging") return STAGING_API_BASE_URL;
    if (storedMode === "prod") return PROD_API_BASE_URL;
    if (window.location.hostname.includes("staging")) return STAGING_API_BASE_URL;
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        return LOCAL_API_BASE_URL;
    }
    return PROD_API_BASE_URL;
}

function resolveDevTelegramUserId() {
    const params = new URLSearchParams(window.location.search);
    const value = params.get("tgUser");
    if (value) {
        localStorage.setItem(DEV_TELEGRAM_USER_ID_STORAGE_KEY, value);
        return value;
    }
    if (!["localhost", "127.0.0.1"].includes(window.location.hostname)) {
        localStorage.removeItem(DEV_TELEGRAM_USER_ID_STORAGE_KEY);
        return "";
    }
    return localStorage.getItem(DEV_TELEGRAM_USER_ID_STORAGE_KEY) || "";
}

function loadWebsiteAuth() {
    try {
        const parsed = JSON.parse(sessionStorage.getItem(WEBSITE_AUTH_STORAGE_KEY) || "null");
        if (!parsed?.accessToken || Number(parsed.expiresAt || 0) <= Date.now()) {
            sessionStorage.removeItem(WEBSITE_AUTH_STORAGE_KEY);
            return null;
        }
        return parsed;
    } catch {
        sessionStorage.removeItem(WEBSITE_AUTH_STORAGE_KEY);
        return null;
    }
}

function loadRecentRenders() {
    try {
        const raw = localStorage.getItem(RECENT_RENDERS_STORAGE_KEY);
        const parsed = JSON.parse(raw || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

const state = {
    apiBaseUrl: resolveApiBaseUrl(),
    devTelegramUserId: resolveDevTelegramUserId(),
    websiteAuth: loadWebsiteAuth(),
    view: "create",
    menuOpen: false,
    paymentStep: 1,
    selectedAmount: 500,
    topUpMode: "package",
    email: "",
    balance: null,
    payments: [],
    starterGrant: null,
    walletBusy: false,
    walletMessage: "",
    paymentReturnState: "",
    pendingRefreshTimer: null,
    createScreen: "upload",
    files: { car: null, wheel: null },
    previewUrls: { car: "", wheel: "" },
    jobId: null,
    resultUrl: null,
    resultDownloadUrl: null,
    resultFileName: null,
    downloading: false,
    sharing: false,
    submitting: false,
    recentRenders: loadRecentRenders(),
};

function applyTranslations() {
    document.documentElement.lang = locale;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-alt]").forEach((el) => {
        el.alt = t(el.dataset.i18nAlt);
    });
}

function initTelegram() {
    const localeLabel = document.querySelector("[data-locale-label]");
    if (localeLabel) localeLabel.textContent = t("locale");

    if (!HAS_TG) {
        updateCreateFooter();
        return;
    }

    tg.ready();
    tg.expand();
    updateCreateFooter();
}

function updateCreateFooter() {
    const userInfo = document.querySelector("[data-user-info]");
    if (!userInfo) return;
    const user = tg?.initDataUnsafe?.user;
    if (!user) {
        const websiteUsername = state.websiteAuth?.username;
        userInfo.textContent = websiteUsername
            ? `Telegram · @${websiteUsername}`
            : t("create.footerNotTelegram");
        return;
    }
    const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || `id ${user.id}`;
    userInfo.textContent = `Telegram · ${name}`;
}

function getWebsiteAuthToken() {
    if (HAS_TG || !state.websiteAuth) return "";
    if (Number(state.websiteAuth.expiresAt || 0) <= Date.now()) {
        state.websiteAuth = null;
        sessionStorage.removeItem(WEBSITE_AUTH_STORAGE_KEY);
        updateWebsiteAuthUi();
        return "";
    }
    return state.websiteAuth.accessToken || "";
}

function withAuthHeaders(headers = {}) {
    const accessToken = getWebsiteAuthToken();
    return accessToken ? { ...headers, Authorization: `Bearer ${accessToken}` } : headers;
}

function updateWebsiteAuthUi() {
    const button = document.querySelector("[data-website-auth-button]");
    if (!button) return;
    button.hidden = HAS_TG;
    if (HAS_TG) return;

    const username = state.websiteAuth?.username;
    button.textContent = state.websiteAuth
        ? `${t("auth.logout")}${username ? ` @${username}` : ""}`
        : t("auth.login");
    updateCreateFooter();
}

function loadTelegramLoginLibrary() {
    if (window.Telegram?.Login) return Promise.resolve(window.Telegram.Login);

    function resolveLoginLibrary(resolve, reject) {
        if (window.Telegram?.Login) resolve(window.Telegram.Login);
        else reject(new Error("Telegram Login library is unavailable"));
    }

    return new Promise((resolve, reject) => {
        const existingScript = document.querySelector("script[data-telegram-login-library]");
        if (existingScript) {
            existingScript.addEventListener("load", () => resolveLoginLibrary(resolve, reject), {
                once: true,
            });
            existingScript.addEventListener("error", reject, { once: true });
            return;
        }

        const script = document.createElement("script");
        script.src = TELEGRAM_LOGIN_SCRIPT_URL;
        script.async = true;
        script.dataset.telegramLoginLibrary = "true";
        script.addEventListener("load", () => resolveLoginLibrary(resolve, reject), { once: true });
        script.addEventListener("error", reject, { once: true });
        document.head.append(script);
    });
}

async function loginWithTelegram() {
    const button = document.querySelector("[data-website-auth-button]");
    if (button) {
        button.disabled = true;
        button.textContent = t("auth.loggingIn");
    }

    try {
        const nonceResponse = await fetch(`${state.apiBaseUrl}/auth/telegram/nonce`);
        if (!nonceResponse.ok) throw new Error(await parseApiError(nonceResponse));
        const { client_id: clientId, nonce, nonce_token: nonceToken } = await nonceResponse.json();
        const numericClientId = Number(clientId);
        if (!Number.isSafeInteger(numericClientId)) throw new Error("Invalid Telegram client_id");

        const telegramLogin = await loadTelegramLoginLibrary();
        const loginResult = await new Promise((resolve, reject) => {
            telegramLogin.auth(
                { client_id: numericClientId, lang: locale, nonce },
                (result) => {
                    if (result?.id_token) resolve(result);
                    else reject(new Error(result?.error || t("auth.failed")));
                }
            );
        });

        const verifyResponse = await fetch(`${state.apiBaseUrl}/auth/telegram/verify-id-token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: loginResult.id_token, nonce_token: nonceToken }),
        });
        if (!verifyResponse.ok) throw new Error(await parseApiError(verifyResponse));
        const verified = await verifyResponse.json();
        state.websiteAuth = {
            accessToken: verified.access_token,
            expiresAt: Date.now() + Number(verified.expires_in || 0) * 1000,
            telegramUserId: verified.telegram_user_id,
            username: verified.username || "",
        };
        sessionStorage.setItem(WEBSITE_AUTH_STORAGE_KEY, JSON.stringify(state.websiteAuth));
        updateWebsiteAuthUi();
        await loadCabinet();
    } catch (error) {
        console.error("[DW] Telegram website login failed", error);
        setWalletMessage(error?.message || t("auth.failed"), "error");
    } finally {
        if (button) button.disabled = false;
        updateWebsiteAuthUi();
    }
}

function logoutWebsiteAuth() {
    state.websiteAuth = null;
    sessionStorage.removeItem(WEBSITE_AUTH_STORAGE_KEY);
    state.balance = null;
    state.payments = [];
    state.starterGrant = null;
    updateWebsiteAuthUi();
    setWalletMessage(t("wallet.authRequired"), "warning");
    renderWallet();
}

function haptic(type) {
    if (!SUPPORTS_HAPTIC) return;
    const h = tg.HapticFeedback;
    if (!h) return;
    if (type === "success") h.notificationOccurred("success");
    else if (type === "error") h.notificationOccurred("error");
    else if (type === "warning") h.notificationOccurred("warning");
    else h.impactOccurred("light");
}

function formatRub(value) {
    return new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US").format(Number(value || 0)) + " ₽";
}

function formatTemplate(template, params) {
    return t(template).replace(/\{(\w+)\}/g, (_, key) => String(params?.[key] ?? ""));
}

function normalizeTopUpAmount(amount) {
    const parsedAmount = Number(amount);
    if (!Number.isFinite(parsedAmount)) return TOPUP_MIN_AMOUNT;
    return Math.min(TOPUP_MAX_AMOUNT, Math.max(TOPUP_MIN_AMOUNT, Math.round(parsedAmount)));
}

function getTopUpPackage(amount) {
    const normalized = normalizeTopUpAmount(amount);
    return TOPUP_PACKAGES.find((item) => item.amount === normalized) || null;
}

function creditsForAmount(amount) {
    const normalized = normalizeTopUpAmount(amount);
    const topUpPackage = getTopUpPackage(normalized);
    if (topUpPackage) return topUpPackage.credits;
    if (normalized >= 1000) return Math.max(1, Math.floor(normalized / (1000 / 45)));
    if (normalized >= 500) return Math.max(1, Math.floor(normalized / 25));
    if (normalized >= 200) return Math.max(1, Math.floor(normalized / (200 / 7)));
    if (normalized >= 100) return Math.max(1, Math.floor(normalized / (100 / 3)));
    return 1;
}

function topUpMeta(credits) {
    return formatTemplate("wallet.packageMetaDays", { credits });
}

function localizeErrorMessage(message) {
    if (locale === "en" && /[А-Яа-яЁё]/.test(message || "")) {
        return t("errors.requestFailed");
    }
    return message || t("errors.generic");
}

function getIdentityPayload({ includeTelegramUserId = false } = {}) {
    if (HAS_TG && tg?.initData) {
        const payload = { init_data: tg.initData };
        if (includeTelegramUserId && tg.initDataUnsafe?.user?.id != null) {
            payload.telegram_user_id = Number(tg.initDataUnsafe.user.id);
        }
        return payload;
    }
    if (state.devTelegramUserId) {
        return { telegram_user_id: Number(state.devTelegramUserId) };
    }
    return {};
}

function getIdentitySearchParams() {
    const params = new URLSearchParams();
    const identity = getIdentityPayload();
    if (identity.init_data) params.set("init_data", identity.init_data);
    if (identity.telegram_user_id) params.set("telegram_user_id", String(identity.telegram_user_id));
    return params;
}

function withIdentityQuery(url) {
    const params = getIdentitySearchParams();
    const query = params.toString();
    return query ? `${url}?${query}` : url;
}

async function fetchRenderHistory({ limit = 20, offset = 0 } = {}) {
    const params = getIdentitySearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    const response = await fetch(`${state.apiBaseUrl}/jobs?${params.toString()}`, {
        headers: withAuthHeaders(),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    return response.json();
}

async function parseApiError(response) {
    let detail = response.statusText || t("failed");
    try {
        const body = await response.json();
        detail = body?.detail || detail;
    } catch {
        // ignore
    }
    if (Array.isArray(detail)) {
        return detail
            .map((item) => item?.msg || item?.message || item?.type || JSON.stringify(item))
            .filter(Boolean)
            .join("; ");
    }
    if (detail && typeof detail === "object") {
        return detail.message || detail.msg || JSON.stringify(detail);
    }
    return String(detail || t("failed"));
}

function persistRecentRenders() {
    localStorage.setItem(RECENT_RENDERS_STORAGE_KEY, JSON.stringify(state.recentRenders.slice(0, 12)));
}

function addRecentRender(item) {
    state.recentRenders = [item, ...state.recentRenders.filter((entry) => entry.jobId !== item.jobId)].slice(0, 12);
    persistRecentRenders();
    renderRenders();
}

function updateTopbarCaption() {
    const caption = document.querySelector("[data-topbar-caption]");
    if (caption) caption.textContent = t(`caption.${state.view}`);
}

function setMenuOpen(open) {
    state.menuOpen = open;
    const layer = document.querySelector("[data-menu-layer]");
    const toggle = document.querySelector("[data-menu-toggle]");
    if (layer) layer.hidden = !open;
    if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
}

function setView(view) {
    state.view = view;
    document.querySelectorAll("[data-view]").forEach((el) => {
        el.hidden = el.dataset.view !== view;
    });
    document.querySelectorAll("[data-nav]").forEach((btn) => {
        const active = btn.dataset.nav === view;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-current", active ? "page" : "false");
    });
    updateTopbarCaption();
    setMenuOpen(false);
    refreshButtonsForCurrentView();
    if (view === "wallet") {
        void loadCabinet({ silent: true });
    }
}

function setPaymentStep(step) {
    state.paymentStep = Math.max(1, Math.min(3, step));
    document.querySelectorAll("[data-step]").forEach((el) => {
        el.hidden = Number(el.dataset.step) !== state.paymentStep;
    });
    document.querySelectorAll("[data-step-tab]").forEach((tab) => {
        tab.classList.toggle("active", Number(tab.dataset.stepTab) === state.paymentStep);
    });
    renderConfirmation();
}

function setSelectedAmount(amount) {
    state.selectedAmount = normalizeTopUpAmount(amount);
    document.querySelectorAll("[data-topup-amount]").forEach((btn) => {
        btn.dataset.selected = String(Number(btn.dataset.topupAmount) === state.selectedAmount);
    });
    renderConfirmation();
}

function setWalletBusy(busy) {
    state.walletBusy = busy;
    document.querySelector("[data-pay-button]")?.toggleAttribute("disabled", busy);
    document.querySelector("[data-reset-wizard]")?.toggleAttribute("disabled", busy);
    document.querySelector("[data-refresh-invoice]")?.toggleAttribute("disabled", busy);
    document.querySelector("[data-topup-email]")?.toggleAttribute("disabled", busy);
    document.querySelectorAll("[data-topup-amount]").forEach((button) => {
        button.toggleAttribute("disabled", busy);
    });
}

function setWalletMessage(message, tone = "neutral") {
    state.walletMessage = message;
    const feedback = document.querySelector("[data-wallet-feedback]");
    if (!feedback) return;
    feedback.hidden = !message;
    feedback.textContent = message;
    feedback.className = `topup-general-error ${tone}`;
}

function getLastInvoice() {
    return state.payments[0] || null;
}

function getHistoryItems() {
    const items = [];
    if (state.starterGrant) {
        items.push({
            type: "starter_grant",
            credits: state.starterGrant.credits,
            createdAt: state.starterGrant.createdAt,
        });
    }
    return items.concat(state.payments);
}

function formatPaymentStatus(status) {
    if (status === "paid") return t("paid");
    if (status === "pending") return t("pending");
    if (status === "failed" || status === "cancelled" || status === "expired") return t("failed");
    return t("created");
}

function statusTone(status) {
    if (status === "paid") return "success";
    if (status === "failed" || status === "cancelled" || status === "expired") return "warning";
    return "neutral";
}

function clearPendingRefreshTimer() {
    if (!state.pendingRefreshTimer) return;
    clearTimeout(state.pendingRefreshTimer);
    state.pendingRefreshTimer = null;
}

function getInvoiceAgeMs(invoice) {
    if (!invoice?.createdAtMs || !Number.isFinite(invoice.createdAtMs)) return null;
    return Math.max(0, Date.now() - invoice.createdAtMs);
}

function getPendingWalletMessage(invoice) {
    if (!invoice || invoice.status !== "pending") return "";
    const ageMs = getInvoiceAgeMs(invoice);
    if (ageMs !== null && ageMs >= PAYMENT_PENDING_STALE_MS) {
        return t("wallet.pendingStale");
    }
    return t("wallet.pendingFresh");
}

function schedulePendingInvoiceRefresh() {
    clearPendingRefreshTimer();
    const invoice = getLastInvoice();
    const ageMs = getInvoiceAgeMs(invoice);
    if (!invoice || invoice.status !== "pending") return;
    if (ageMs !== null && ageMs > PAYMENT_PENDING_FRESH_MS) return;
    state.pendingRefreshTimer = window.setTimeout(() => {
        state.pendingRefreshTimer = null;
        if (state.view === "wallet" && !document.hidden) {
            void loadCabinet({ silent: true });
        }
    }, PAYMENT_PENDING_AUTO_REFRESH_DELAY_MS);
}

function renderWallet() {
    const balanceValue = document.querySelector("[data-balance-value]");
    const balanceNote = document.querySelector("[data-balance-note]");
    const lastInvoice = getLastInvoice();
    const emptyBlock = document.querySelector("[data-last-invoice-empty]");
    const cardBlock = document.querySelector("[data-last-invoice-card]");
    const cardDetails = document.querySelector("[data-last-invoice-details]");
    const history = document.querySelector("[data-payment-history-list]");
    const statusPill = document.querySelector("[data-last-invoice-status]");
    const headingStatus = document.querySelector("[data-payment-status]");
    const refreshButton = document.querySelector("[data-refresh-invoice]");

    if (balanceValue) balanceValue.textContent = String(state.balance ?? "0");
    if (balanceNote) {
        balanceNote.hidden = true;
        balanceNote.textContent = "";
    }

    if (!lastInvoice) {
        if (emptyBlock) emptyBlock.hidden = false;
        if (cardBlock) cardBlock.hidden = true;
        if (cardDetails) cardDetails.hidden = true;
        if (headingStatus) {
            headingStatus.textContent = state.balance === null ? t("wallet.loading") : t("wallet.noPaymentsTitle");
            headingStatus.className = "status-pill neutral";
        }
        if (refreshButton) refreshButton.hidden = true;
    } else {
        if (emptyBlock) emptyBlock.hidden = true;
        if (cardBlock) cardBlock.hidden = false;
        if (cardDetails) cardDetails.hidden = false;
        if (cardBlock) cardBlock.dataset.status = lastInvoice.status;
        if (headingStatus) {
            headingStatus.textContent = formatPaymentStatus(lastInvoice.status);
            headingStatus.className = `status-pill ${statusTone(lastInvoice.status)}`;
        }
        if (statusPill) {
            statusPill.textContent = formatPaymentStatus(lastInvoice.status);
            statusPill.className = `status-pill ${statusTone(lastInvoice.status)}`;
        }
        document.querySelector("[data-last-invoice-amount]")?.replaceChildren(document.createTextNode(formatRub(lastInvoice.amount)));
        document.querySelector("[data-last-invoice-amount-copy]")?.replaceChildren(document.createTextNode(formatRub(lastInvoice.amount)));
        document.querySelector("[data-last-invoice-email]")?.replaceChildren(document.createTextNode(lastInvoice.email || "—"));
        document.querySelector("[data-last-invoice-credits]")?.replaceChildren(document.createTextNode(`${lastInvoice.credits} ${t("credits")}`));
        document.querySelector("[data-last-invoice-state]")?.replaceChildren(document.createTextNode(formatPaymentStatus(lastInvoice.status)));
        document.querySelector("[data-last-invoice-number]")?.replaceChildren(
            document.createTextNode(
                formatTemplate(
                    lastInvoice.status === "paid"
                        ? "wallet.paidInvoice"
                        : lastInvoice.status === "failed" || lastInvoice.status === "cancelled" || lastInvoice.status === "expired"
                          ? "wallet.failedInvoice"
                          : "wallet.pendingInvoice",
                    {
                        invoiceId: String(lastInvoice.invoiceId).padStart(6, "0"),
                        amount: formatRub(lastInvoice.amount),
                    }
                )
            )
        );
        document.querySelector("[data-last-invoice-number-copy]")?.replaceChildren(document.createTextNode(`#${String(lastInvoice.invoiceId).padStart(6, "0")}`));
        document.querySelector("[data-last-invoice-meta]")?.replaceChildren(document.createTextNode(lastInvoice.createdAt));
        if (refreshButton) refreshButton.hidden = lastInvoice.status !== "pending";
    }

    if (!history) return;
    const historyItems = getHistoryItems();
    if (!historyItems.length) {
        history.innerHTML = `<div class="history-empty"><span class="history-empty-icon" aria-hidden="true">🧾</span><span>${t("wallet.emptyHistory")}</span></div>`;
    } else {
        history.innerHTML = historyItems
            .map((item) => {
                if (item.type === "starter_grant") {
                    return `
                        <div class="history-item payment-history-item grant-history-item">
                            <div>
                                <strong>${t("wallet.starterGrantTitle")}</strong>
                                <div class="meta">${formatTemplate("wallet.starterGrantMeta", { credits: item.credits })}</div>
                            </div>
                            <span class="status-pill success">${t("wallet.gift")}</span>
                        </div>
                    `;
                }
                return `
                    <div class="history-item payment-history-item">
                        <div>
                            <strong>#${String(item.invoiceId).padStart(6, "0")} · ${formatRub(item.amount)}</strong>
                            <div class="meta">${item.email || "—"} · ${item.createdAt} · ${item.credits} ${t("credits")}</div>
                        </div>
                        <span class="status-pill ${statusTone(item.status)}">${formatPaymentStatus(item.status)}</span>
                    </div>
                `;
            })
            .join("");
    }

    document.querySelectorAll("[data-topup-amount]").forEach((button) => {
        const amount = normalizeTopUpAmount(button.dataset.topupAmount);
        const credits = Number(button.dataset.topupCredits || creditsForAmount(amount));
        const name = button.querySelector(".package-name");
        const meta = button.querySelector("[data-topup-meta]");
        if (name) name.textContent = formatRub(amount);
        if (meta) meta.textContent = topUpMeta(credits);
        button.dataset.selected = String(amount === state.selectedAmount);
    });
}

function renderConfirmation() {
    const credits = creditsForAmount(state.selectedAmount);
    document.querySelector("[data-topup-summary-title]")?.replaceChildren(
        document.createTextNode(getTopUpPackage(state.selectedAmount) ? t("wallet.summaryPackageTitle") : t("wallet.summaryCustomTitle"))
    );
    document.querySelector("[data-topup-summary-meta]")?.replaceChildren(
        document.createTextNode(
            formatTemplate("wallet.packageSummary", {
                amount: formatRub(state.selectedAmount),
                credits,
            })
        )
    );
}

function syncEmailInput() {
    const emailInput = document.querySelector("[data-topup-email]");
    if (emailInput && emailInput.value !== state.email) {
        emailInput.value = state.email;
    }
}

function renderRenders() {
    const container = document.querySelector("[data-render-history]");
    if (!container) return;
    if (!state.recentRenders.length) {
        container.innerHTML = `
            <div class="history-card render-empty">
                <div>
                    <strong>${t("renders.empty")}</strong>
                    <div class="meta">${state.apiBaseUrl}</div>
                </div>
            </div>
        `;
        return;
    }
    container.innerHTML = state.recentRenders
        .map((render) => `
            <article class="render-card">
                <div class="render-thumb-wrap">
                    ${render.resultUrl ? `<img src="${render.resultUrl}" alt="" class="render-thumb-image">` : `<div class="render-thumb"></div>`}
                </div>
                <div class="render-body">
                    <div class="render-title">${render.fileName || `job ${render.jobId}`}</div>
                    <div class="render-subtitle">${render.createdAt}</div>
                    <div class="meta">${render.status === "completed" ? t("renders.completed") : t("renders.failed")}${render.error ? ` · ${render.error}` : ""}</div>
                </div>
                ${render.resultUrl ? `<button type="button" class="ghost-button compact-button" data-open-render="${render.resultUrl}">${t("actions.openRender")}</button>` : ""}
            </article>
        `)
        .join("");
}

async function loadCabinet({ silent = false } = {}) {
    const identity = getIdentitySearchParams();
    if (!identity.toString() && !getWebsiteAuthToken()) {
        setWalletMessage(t("wallet.authRequired"), "warning");
        renderWallet();
        return;
    }

    clearPendingRefreshTimer();
    setWalletBusy(true);
    if (!silent) {
        setWalletMessage(t("wallet.loading"));
    }
    try {
        const response = await fetch(`${state.apiBaseUrl}/payments/cabinet?${identity.toString()}`, {
            headers: withAuthHeaders(),
        });
        if (!response.ok) {
            const detail = await parseApiError(response);
            if (response.status === 403) {
                setWalletMessage(t("wallet.fallbackDisabled"), "error");
            } else {
                setWalletMessage(detail, "error");
            }
            renderWallet();
            return;
        }
        const cabinet = await response.json();
        state.balance = cabinet.balance ?? 0;
        state.payments = (cabinet.payments || []).map((payment) => ({
            invoiceId: payment.invoice_id,
            amount: payment.amount,
            email: payment.receipt_email || payment.email || "",
            credits: payment.credits_granted || 0,
            createdAtIso: payment.created_at,
            createdAtMs: Date.parse(payment.created_at),
            createdAt: new Date(payment.created_at).toLocaleString(locale === "ru" ? "ru-RU" : "en-US"),
            status: payment.status,
        }));
        state.starterGrant = cabinet.starter_grant
            ? {
                credits: Number(cabinet.starter_grant.credits || 0),
                createdAtIso: cabinet.starter_grant.created_at,
                createdAtMs: Date.parse(cabinet.starter_grant.created_at),
                createdAt: new Date(cabinet.starter_grant.created_at).toLocaleString(locale === "ru" ? "ru-RU" : "en-US"),
            }
            : null;
        const rememberedEmail = state.payments.find((payment) => payment.email)?.email || "";
        if (rememberedEmail && !state.email) {
            state.email = rememberedEmail;
            syncEmailInput();
            renderConfirmation();
        }
        const pendingMessage = getPendingWalletMessage(getLastInvoice());
        if (state.paymentReturnState === "success") {
            setWalletMessage(t("wallet.paymentSuccess"), "success");
        } else if (state.paymentReturnState === "fail") {
            setWalletMessage(t("wallet.paymentFail"), "warning");
        } else if (pendingMessage) {
            setWalletMessage(pendingMessage, "warning");
        } else {
            setWalletMessage("");
        }
        state.paymentReturnState = "";
        renderWallet();
        schedulePendingInvoiceRefresh();
    } catch (error) {
        setWalletMessage(error?.message || t("failed"), "error");
        renderWallet();
    } finally {
        setWalletBusy(false);
    }
}

function openExternal(url) {
    if (HAS_TG && typeof tg?.openLink === "function") {
        tg.openLink(url);
        return;
    }
    window.open(url, "_blank", "noopener");
}

function openPaymentUrl(url) {
    if (HAS_TG && typeof tg?.openLink === "function") {
        tg.openLink(url);
        return;
    }
    window.location.href = url;
}

async function createPayment() {
    const identity = getIdentityPayload();
    if (!identity.init_data && !identity.telegram_user_id && !getWebsiteAuthToken()) {
        setWalletMessage(t("wallet.authRequired"), "warning");
        return;
    }

    setWalletBusy(true);
    setWalletMessage(t("wallet.openingPayment"));
    try {
        const response = await fetch(`${state.apiBaseUrl}/payments/topups`, {
            method: "POST",
            headers: withAuthHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
                amount_rub: normalizeTopUpAmount(state.selectedAmount).toFixed(2),
                email: state.email || null,
                pricing_version: PRICING_VERSION,
                source_screen: "cabinet",
                ...identity,
            }),
        });
        if (!response.ok) {
            const detail = await parseApiError(response);
            if (response.status === 403) {
                setWalletMessage(t("wallet.fallbackDisabled"), "error");
            } else {
                setWalletMessage(detail, "error");
            }
            return;
        }
        const payment = await response.json();
        await loadCabinet();
        openPaymentUrl(payment.payment_url);
    } catch (error) {
        setWalletMessage(error?.message || t("failed"), "error");
    } finally {
        setWalletBusy(false);
    }
}

function handlePaymentReturn() {
    const paymentState = new URLSearchParams(window.location.search).get("payment");
    state.paymentReturnState = paymentState || "";
    if (paymentState === "success") {
        setWalletMessage(t("wallet.paymentSuccess"), "success");
        setView("wallet");
    } else if (paymentState === "fail") {
        setWalletMessage(t("wallet.paymentFail"), "warning");
        setView("wallet");
    }
}

function openDraftDb() {
    return new Promise((resolve, reject) => {
        if (!("indexedDB" in window)) {
            resolve(null);
            return;
        }
        const request = indexedDB.open(DRAFT_DB_NAME, 1);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(DRAFT_STORE_NAME)) {
                db.createObjectStore(DRAFT_STORE_NAME, { keyPath: "kind" });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function saveDraftFile(kind, file, bytes) {
    const db = await openDraftDb();
    if (!db) return;
    await new Promise((resolve, reject) => {
        const tx = db.transaction(DRAFT_STORE_NAME, "readwrite");
        tx.objectStore(DRAFT_STORE_NAME).put({
            kind,
            name: file.name,
            size: file.size,
            type: file.type,
            bytes,
        });
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
    db.close();
}

async function loadDraftFile(kind) {
    const db = await openDraftDb();
    if (!db) return null;
    const entry = await new Promise((resolve, reject) => {
        const tx = db.transaction(DRAFT_STORE_NAME, "readonly");
        const request = tx.objectStore(DRAFT_STORE_NAME).get(kind);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(request.error);
    });
    db.close();
    if (!entry?.bytes) return null;
    return {
        blob: new Blob([entry.bytes], { type: entry.type }),
        name: entry.name,
        size: entry.size,
        type: entry.type,
    };
}

async function deleteDraftFile(kind) {
    const db = await openDraftDb();
    if (!db) return;
    await new Promise((resolve, reject) => {
        const tx = db.transaction(DRAFT_STORE_NAME, "readwrite");
        tx.objectStore(DRAFT_STORE_NAME).delete(kind);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
    db.close();
}

async function hydrateFilesFromDraft() {
    for (const kind of ["car", "wheel"]) {
        if (state.files[kind]?.blob) continue;
        try {
            const draft = await loadDraftFile(kind);
            if (draft) {
                state.files[kind] = draft;
                renderPreviewFromFile(kind, draft);
            }
        } catch {
            // ignore
        }
    }
}

function revokePreviewUrl(kind) {
    if (state.previewUrls[kind]) {
        URL.revokeObjectURL(state.previewUrls[kind]);
        state.previewUrls[kind] = "";
    }
}

function renderPreviewFromFile(kind, fileLike) {
    revokePreviewUrl(kind);
    const img = document.querySelector(`[data-preview-img="${kind}"]`);
    const preview = document.querySelector(`[data-preview="${kind}"]`);
    const zone = document.querySelector(`[data-upload-zone="${kind}"]`);
    if (!img || !preview || !zone || !fileLike?.blob) return;
    const objectUrl = URL.createObjectURL(fileLike.blob);
    state.previewUrls[kind] = objectUrl;
    img.src = objectUrl;
    preview.hidden = false;
    zone.hidden = true;
}

function showCreateScreen(name) {
    state.createScreen = name;
    document.querySelectorAll("[data-create-screen]").forEach((el) => {
        el.hidden = el.dataset.createScreen !== name;
    });
    document.querySelector("[data-step-indicator]")?.replaceChildren(document.createTextNode(name === "result" ? t("steps.result") : t("steps.upload")));
    refreshButtonsForCurrentView();
}

let mainButtonHandler = null;
let fallbackButton = null;
let backButtonHandler = null;

function ensureFallbackButton() {
    if (fallbackButton) return fallbackButton;
    fallbackButton = document.createElement("button");
    fallbackButton.type = "button";
    fallbackButton.className = "fallback-button";
    fallbackButton.hidden = true;
    fallbackButton.addEventListener("click", () => {
        if (mainButtonHandler) mainButtonHandler();
    });
    document.body.appendChild(fallbackButton);
    return fallbackButton;
}

function setMainButton({ text, enabled = true, onClick = null }) {
    mainButtonHandler = onClick;
    if (HAS_TG && tg.MainButton) {
        tg.MainButton.setText(text);
        if (enabled) tg.MainButton.enable();
        else tg.MainButton.disable();
        tg.MainButton.offClick();
        if (onClick) tg.MainButton.onClick(onClick);
        tg.MainButton.show();
        return;
    }
    const btn = ensureFallbackButton();
    btn.textContent = text;
    btn.disabled = !enabled;
    btn.hidden = !onClick;
}

function hideMainButton() {
    mainButtonHandler = null;
    if (HAS_TG && tg.MainButton) {
        tg.MainButton.offClick();
        tg.MainButton.hide();
    } else if (fallbackButton) {
        fallbackButton.hidden = true;
    }
}

function setBackButton(onClick) {
    backButtonHandler = onClick;
    if (!SUPPORTS_BACK_BUTTON) return;
    tg.BackButton.offClick();
    if (onClick) {
        tg.BackButton.onClick(onClick);
        tg.BackButton.show();
    } else {
        tg.BackButton.hide();
    }
}

function refreshButtonsForCurrentView() {
    if (state.view !== "create") {
        hideMainButton();
        setBackButton(null);
        return;
    }

    if (state.createScreen === "upload") {
        const ready = Boolean(state.files.car?.blob && state.files.wheel?.blob);
        setBackButton(null);
        setMainButton({
            text: t("actions.createRender"),
            enabled: ready && !state.submitting,
            onClick: ready && !state.submitting ? submitJob : null,
        });
        return;
    }

    if (state.submitting) {
        setBackButton(null);
        hideMainButton();
        return;
    }

    setBackButton(() => resetFlow());
    setMainButton({
        text: t("actions.createAnother"),
        enabled: true,
        onClick: resetFlow,
    });
}

function resetFlow() {
    state.downloading = false;
    state.sharing = false;
    state.submitting = false;
    state.files = { car: null, wheel: null };
    revokePreviewUrl("car");
    revokePreviewUrl("wheel");
    void deleteDraftFile("car");
    void deleteDraftFile("wheel");
    state.jobId = null;
    state.resultUrl = null;
    state.resultDownloadUrl = null;
    state.resultFileName = null;
    document.querySelectorAll("input[data-input]").forEach((input) => {
        input.value = "";
    });
    ["car", "wheel"].forEach((kind) => {
        document.querySelector(`[data-preview="${kind}"]`)?.toggleAttribute("hidden", true);
        document.querySelector(`[data-upload-zone="${kind}"]`)?.toggleAttribute("hidden", false);
    });
    const resultImg = document.querySelector("[data-result-img]");
    if (resultImg) {
        resultImg.hidden = true;
        resultImg.removeAttribute("src");
    }
    document.querySelector("[data-download-result]")?.toggleAttribute("hidden", true);
    document.querySelector("[data-share-result]")?.toggleAttribute("hidden", true);
    setDownloadButtonState();
    setShareButtonState();
    showCreateScreen("upload");
    setView("create");
}

function setDownloadButtonState({ disabled = false, text = t("actions.downloadImage") } = {}) {
    const button = document.querySelector("[data-download-result]");
    if (!button) return;
    button.disabled = disabled;
    button.textContent = text;
}

function setShareButtonState({ disabled = false, text = t("actions.share") } = {}) {
    const button = document.querySelector("[data-share-result]");
    if (!button) return;
    button.disabled = disabled;
    button.textContent = text;
}

function requestTelegramDownload(url, fileName) {
    return new Promise((resolve, reject) => {
        try {
            tg.downloadFile({ url, file_name: fileName }, (accepted) => resolve(Boolean(accepted)));
        } catch (error) {
            reject(error);
        }
    });
}

async function downloadResult() {
    if (!state.resultDownloadUrl || state.downloading) return;
    state.downloading = true;
    setDownloadButtonState({ disabled: true, text: t("actions.requestingDownload") });
    try {
        if (SUPPORTS_DOWNLOAD_FILE) {
            const accepted = await requestTelegramDownload(
                state.resultDownloadUrl,
                state.resultFileName || "dream-wheels-result.jpg"
            );
            if (!accepted) {
                setDownloadButtonState({ text: t("actions.downloadCanceled") });
                haptic("warning");
            } else {
                setDownloadButtonState({ text: t("actions.downloadStarted") });
                haptic("success");
            }
        } else {
            const link = document.createElement("a");
            link.href = state.resultDownloadUrl;
            link.download = state.resultFileName || "dream-wheels-result.jpg";
            link.rel = "noopener";
            document.body.appendChild(link);
            link.click();
            link.remove();
            setDownloadButtonState({ text: t("actions.downloadStarted") });
            haptic("success");
        }
    } catch (error) {
        console.error("[DW] download failed", error);
        setDownloadButtonState({ disabled: false, text: t("actions.downloadFailed") });
        haptic("warning");
        state.downloading = false;
        return;
    }
    setTimeout(() => {
        state.downloading = false;
        setDownloadButtonState();
    }, 1400);
}

function buildTelegramShareUrl() {
    const text = `${t("share.text")}\n${state.resultUrl}`;
    return `https://t.me/share/url?url=${encodeURIComponent(state.resultUrl)}&text=${encodeURIComponent(text)}`;
}

async function copyResultUrl() {
    if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
    }
    await navigator.clipboard.writeText(state.resultUrl);
}

async function shareResult() {
    if (!state.resultUrl || state.sharing) return;
    state.sharing = true;
    setShareButtonState({ disabled: true, text: t("actions.preparing") });
    try {
        const shareData = {
            title: "Dream Wheels AI",
            text: `${t("share.text")}\n${state.resultUrl}`,
            url: state.resultUrl,
        };
        if (HAS_TG && typeof tg.openTelegramLink === "function") {
            tg.openTelegramLink(buildTelegramShareUrl());
            setShareButtonState({ text: t("actions.openingTelegram") });
            haptic("success");
        } else if (HAS_TG && typeof tg.openLink === "function") {
            tg.openLink(buildTelegramShareUrl());
            setShareButtonState({ text: t("actions.openingTelegram") });
            haptic("success");
        } else if (navigator.share) {
            await navigator.share(shareData);
            setShareButtonState({ text: t("actions.sent") });
            haptic("success");
        } else {
            try {
                await copyResultUrl();
                setShareButtonState({ text: t("actions.linkCopied") });
            } catch {
                window.open(buildTelegramShareUrl(), "_blank", "noopener");
                setShareButtonState({ text: t("actions.openingLink") });
            }
            haptic("success");
        }
    } catch (error) {
        if (error?.name === "AbortError") {
            setShareButtonState({ text: t("actions.canceled") });
        } else {
            console.error("[DW] share failed", error);
            setShareButtonState({ disabled: false, text: t("actions.failed") });
        }
        haptic("warning");
    }
    setTimeout(() => {
        state.sharing = false;
        setShareButtonState();
    }, 1600);
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function makeIdempotencyKey() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    return `dw-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function submitJob() {
    if (state.submitting) return;
    state.submitting = true;
    showCreateScreen("result");
    haptic("light");

    const statusBlock = document.querySelector("[data-status]");
    const resultBlock = document.querySelector("[data-result]");
    const errorBlock = document.querySelector("[data-error]");
    const statusText = document.querySelector("[data-status-text]");
    const statusSub = document.querySelector("[data-status-sub]");
    const statusDebug = document.querySelector("[data-status-debug]");
    const resultImg = document.querySelector("[data-result-img]");
    const errorText = document.querySelector("[data-error-text]");
    const debugLines = [];

    function pushDebug(label, extra = null) {
        const line = extra ? `${label}: ${extra}` : label;
        debugLines.push(line);
        console.log("[DW]", line);
        if (statusDebug) {
            statusDebug.hidden = false;
            statusDebug.textContent = debugLines.join("\n");
        }
    }

    function showError(message) {
        state.submitting = false;
        if (statusBlock) statusBlock.hidden = true;
        if (resultBlock) resultBlock.hidden = true;
        if (errorBlock) errorBlock.hidden = false;
        if (errorText) errorText.textContent = localizeErrorMessage(message);
        addRecentRender({
            jobId: state.jobId || makeIdempotencyKey(),
            fileName: state.files.car?.name || "render",
            createdAt: new Date().toLocaleString(locale === "ru" ? "ru-RU" : "en-US"),
            status: "failed",
            error: localizeErrorMessage(message),
            resultUrl: "",
        });
        refreshButtonsForCurrentView();
        pushDebug("showError", message);
        haptic("error");
    }

    if (statusBlock) statusBlock.hidden = false;
    if (resultBlock) resultBlock.hidden = true;
    if (errorBlock) errorBlock.hidden = true;
    if (statusText) statusText.textContent = t("status.startingServer");
    if (statusSub) statusSub.textContent = t("status.coldStart");
    if (statusDebug) {
        statusDebug.hidden = true;
        statusDebug.textContent = "";
    }

    pushDebug("submit:start");
    pushDebug("api:base", state.apiBaseUrl);

    try {
        pushDebug("health:request");
        await fetch(`${state.apiBaseUrl}/health`, { method: "GET" });
        pushDebug("health:ok");
    } catch {
        pushDebug("health:fail");
    }

    if (statusText) statusText.textContent = t("status.uploading");
    if (statusSub) statusSub.textContent = t("status.upTo90");

    if (!state.files.car?.blob || !state.files.wheel?.blob) {
        await hydrateFilesFromDraft();
    }

    pushDebug(
        "files",
        JSON.stringify({
            carName: state.files.car?.name,
            carBlobSize: state.files.car?.blob?.size,
            wheelName: state.files.wheel?.name,
            wheelBlobSize: state.files.wheel?.blob?.size,
            hasTG: HAS_TG,
            initDataLen: HAS_TG ? (tg.initData || "").length : 0,
        })
    );

    if (!state.files.car?.blob || !state.files.wheel?.blob) {
        showError(t("errors.missingFiles"));
        return;
    }

    const formData = new FormData();
    formData.append("car_image", state.files.car.blob, state.files.car.name);
    formData.append("wheel_image", state.files.wheel.blob, state.files.wheel.name);
    const identity = getIdentityPayload({ includeTelegramUserId: true });
    if (identity.init_data) formData.append("init_data", identity.init_data);
    if (identity.telegram_user_id != null) {
        formData.append("telegram_user_id", String(identity.telegram_user_id));
    }
    const idempotencyKey = makeIdempotencyKey();
    formData.append("idempotency_key", idempotencyKey);
    pushDebug("upload:key", idempotencyKey);

    try {
        pushDebug("upload:request");
        const resp = await fetch(`${state.apiBaseUrl}/jobs/upload`, {
            method: "POST",
            headers: withAuthHeaders(),
            body: formData,
        });
        pushDebug("upload:response", `status=${resp.status}`);
        const data = await resp.json().catch(() => ({}));
        pushDebug("upload:body", JSON.stringify(data));
        if (!resp.ok) {
            const detail = Array.isArray(data.detail)
                ? data.detail.map((entry) => entry.msg).join("; ")
                : (data.detail || `HTTP ${resp.status}`);
            throw new Error(detail);
        }
        state.jobId = data.job_id;
        pushDebug("upload:job", state.jobId);
    } catch (error) {
        showError(error.message);
        return;
    }

    if (statusText) statusText.textContent = t("status.generating");
    pushDebug("poll:start");

    const deadline = Date.now() + POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
        await sleep(POLL_INTERVAL_MS);
        let statusData;
        try {
            pushDebug("poll:request", state.jobId);
            const response = await fetch(
                withIdentityQuery(`${state.apiBaseUrl}/jobs/${state.jobId}/status`),
                { headers: withAuthHeaders() }
            );
            statusData = await response.json();
            pushDebug("poll:response", JSON.stringify(statusData));
        } catch {
            pushDebug("poll:network-fail");
            continue;
        }

        if (statusData.status === "completed") {
            state.submitting = false;
            state.resultUrl = statusData.result_url || "";
            state.resultDownloadUrl = `${state.apiBaseUrl}/jobs/${state.jobId}/download`;
            state.resultFileName = `dream-wheels-${state.jobId}.jpg`;
            if (statusBlock) statusBlock.hidden = true;
            if (resultBlock) resultBlock.hidden = false;
            if (resultImg && statusData.result_url) {
                resultImg.src = statusData.result_url;
                resultImg.hidden = false;
            }
            document.querySelector("[data-download-result]")?.toggleAttribute("hidden", !state.resultDownloadUrl);
            document.querySelector("[data-share-result]")?.toggleAttribute("hidden", !state.resultUrl);
            setDownloadButtonState();
            setShareButtonState();
            addRecentRender({
                jobId: state.jobId,
                fileName: state.files.car?.name || `render ${state.jobId}`,
                createdAt: new Date().toLocaleString(locale === "ru" ? "ru-RU" : "en-US"),
                status: "completed",
                resultUrl: state.resultUrl,
                assets: statusData.assets || null,
                error: "",
            });
            refreshButtonsForCurrentView();
            pushDebug("poll:completed");
            haptic("success");
            return;
        }

        if (statusData.status === "failed") {
            showError(statusData.error || t("errors.generationFailed"));
            return;
        }
    }

    pushDebug("poll:timeout");
    showError(t("errors.timeout"));
}

function handleFileSelected(kind, file) {
    file.arrayBuffer().then((buffer) => {
        state.files[kind] = {
            blob: new Blob([buffer], { type: file.type }),
            name: file.name,
            size: file.size,
            type: file.type,
        };
        void saveDraftFile(kind, file, buffer);
        renderPreviewFromFile(kind, state.files[kind]);
        refreshButtonsForCurrentView();
    });
    haptic("light");
}

function bindEvents() {
    document.querySelector("[data-menu-toggle]")?.addEventListener("click", () => {
        setMenuOpen(!state.menuOpen);
    });

    document.querySelector("[data-website-auth-button]")?.addEventListener("click", () => {
        if (state.websiteAuth) logoutWebsiteAuth();
        else void loginWithTelegram();
    });

    document.querySelectorAll("[data-nav]").forEach((button) => {
        button.addEventListener("click", () => setView(button.dataset.nav));
    });

    document.querySelectorAll("[data-topup-amount]").forEach((button) => {
        button.addEventListener("click", () => setSelectedAmount(Number(button.dataset.topupAmount)));
    });

    document.querySelector("[data-topup-email]")?.addEventListener("input", (event) => {
        state.email = event.target.value.trim();
        renderConfirmation();
    });

    document.querySelector("[data-pay-button]")?.addEventListener("click", createPayment);
    document.querySelector("[data-refresh-invoice]")?.addEventListener("click", () => {
        setWalletMessage(t("wallet.refreshingInvoice"));
        void loadCabinet();
    });
    document.querySelector("[data-reset-wizard]")?.addEventListener("click", () => {
        state.paymentStep = 1;
        state.selectedAmount = 500;
        state.email = "";
        const input = document.querySelector("[data-topup-email]");
        if (input) input.value = "";
        setSelectedAmount(state.selectedAmount);
        renderConfirmation();
        setWalletMessage("");
    });

    document.querySelectorAll("input[data-input]").forEach((input) => {
        const kind = input.dataset.input;
        input.addEventListener("change", (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            handleFileSelected(kind, file);
        });
    });

    document.querySelectorAll("[data-clear]").forEach((button) => {
        button.addEventListener("click", () => {
            const kind = button.dataset.clear;
            state.files[kind] = null;
            revokePreviewUrl(kind);
            void deleteDraftFile(kind);
            const input = document.querySelector(`input[data-input="${kind}"]`);
            if (input) input.value = "";
            document.querySelector(`[data-preview="${kind}"]`)?.toggleAttribute("hidden", true);
            document.querySelector(`[data-upload-zone="${kind}"]`)?.toggleAttribute("hidden", false);
            refreshButtonsForCurrentView();
        });
    });

    document.querySelector("[data-download-result]")?.addEventListener("click", downloadResult);
    document.querySelector("[data-share-result]")?.addEventListener("click", shareResult);

    document.addEventListener("click", (event) => {
        const openRenderButton = event.target.closest("[data-open-render]");
        if (openRenderButton) {
            openExternal(openRenderButton.dataset.openRender);
            return;
        }

        const layer = document.querySelector("[data-menu-layer]");
        const toggle = document.querySelector("[data-menu-toggle]");
        if (!state.menuOpen || !layer || !toggle) return;
        if (layer.contains(event.target) || toggle.contains(event.target)) return;
        setMenuOpen(false);
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    applyTranslations();
    initTelegram();
    updateWebsiteAuthUi();
    bindEvents();
    handlePaymentReturn();

    syncEmailInput();

    setSelectedAmount(state.selectedAmount);
    renderWallet();
    renderRenders();
    updateTopbarCaption();
    setMenuOpen(false);
    showCreateScreen("upload");

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden && state.view === "wallet") {
            void loadCabinet({ silent: true });
        }
    });

    await hydrateFilesFromDraft();
    refreshButtonsForCurrentView();
    await loadCabinet();

    if (!new URLSearchParams(window.location.search).get("payment")) {
        setView("create");
    }
});
