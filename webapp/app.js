// Dream Wheels AI — Telegram WebApp prototype
//
// Этот скрипт реализует трёхэкранный flow: машина → диск → результат.
// Backend интеграция (POST /jobs/upload) пока не подключена — это первый
// итеративный деплой, чтобы проверить что Vercel + Telegram WebApp работают
// вместе. Пока fetch заменён на mock-задержку с заглушкой результата.

const tg = window.Telegram?.WebApp;
// SDK-скрипт выставляет window.Telegram.WebApp даже в обычном браузере, но
// репортит platform="unknown". В этом режиме MainButton/BackButton не
// рендерятся (нет Telegram-чрома) — переключаемся на fallback-кнопку.
const HAS_TG = Boolean(
    tg && typeof tg.expand === "function" && tg.platform && tg.platform !== "unknown"
);

// BackButton, HapticFeedback и пр. появились в Bot API 6.1.
// В Telegram-клиентах старых версий SDK сообщает 6.0 — вызовы работают
// с warning'ами в консоли, поэтому гейтим по версии.
function tgSupports(version) {
    if (!HAS_TG) return false;
    if (typeof tg.isVersionAtLeast !== "function") return false;
    return tg.isVersionAtLeast(version);
}

const SUPPORTS_BACK_BUTTON = tgSupports("6.1");
const SUPPORTS_HAPTIC = tgSupports("6.1");

const SCREENS = ["car", "wheel", "result"];
const state = {
    screen: "car",
    files: { car: null, wheel: null },
    jobId: null,
};

/* ---------- Telegram bootstrap ---------- */

function initTelegram() {
    if (!HAS_TG) return;
    tg.ready();
    tg.expand();

    const userInfo = document.querySelector("[data-user-info]");
    const user = tg.initDataUnsafe?.user;
    if (user) {
        const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || `id ${user.id}`;
        userInfo.textContent = `Telegram · ${name}`;
    }
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

/* ---------- Main button (native or fallback) ---------- */

let mainButtonHandler = null;
let fallbackButton = null;

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
        if (enabled) {
            tg.MainButton.enable();
        } else {
            tg.MainButton.disable();
        }
        tg.MainButton.offClick();
        if (onClick) tg.MainButton.onClick(onClick);
        tg.MainButton.show();
    } else {
        const btn = ensureFallbackButton();
        btn.textContent = text;
        btn.disabled = !enabled;
        btn.hidden = !onClick;
    }
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

/* ---------- Back button ---------- */

let backButtonHandler = null;

function setBackButton(onClick) {
    backButtonHandler = onClick;
    // На старых клиентах (или в браузере для дебага) BackButton отсутствует —
    // молча игнорируем. Юзер вернётся через стандартную кнопку Telegram-чата.
    if (!SUPPORTS_BACK_BUTTON) return;
    tg.BackButton.offClick();
    if (onClick) {
        tg.BackButton.onClick(onClick);
        tg.BackButton.show();
    } else {
        tg.BackButton.hide();
    }
}

/* ---------- Screen navigation ---------- */

function showScreen(name) {
    state.screen = name;
    SCREENS.forEach((s) => {
        const el = document.querySelector(`[data-screen="${s}"]`);
        el.hidden = s !== name;
    });

    const stepIndex = SCREENS.indexOf(name) + 1;
    const indicator = document.querySelector("[data-step-indicator]");
    indicator.textContent = name === "result" ? "Готово" : `Шаг ${stepIndex} из ${SCREENS.length}`;

    refreshButtonsForScreen();
}

function refreshButtonsForScreen() {
    if (state.screen === "car") {
        setBackButton(null);
        setMainButton({
            text: "Дальше",
            enabled: Boolean(state.files.car),
            onClick: state.files.car ? () => showScreen("wheel") : null,
        });
    } else if (state.screen === "wheel") {
        setBackButton(() => showScreen("car"));
        setMainButton({
            text: "Создать рендер",
            enabled: Boolean(state.files.wheel),
            onClick: state.files.wheel ? submitJob : null,
        });
    } else if (state.screen === "result") {
        setBackButton(() => resetFlow());
        setMainButton({
            text: "Сделать ещё один",
            enabled: true,
            onClick: resetFlow,
        });
    }
}

function resetFlow() {
    state.files = { car: null, wheel: null };
    state.jobId = null;
    SCREENS.forEach((s) => {
        const preview = document.querySelector(`[data-preview="${s}"]`);
        const zone = document.querySelector(`[data-upload-zone="${s}"]`);
        if (preview) preview.hidden = true;
        if (zone) zone.hidden = false;
    });
    document.querySelectorAll("input[data-input]").forEach((i) => (i.value = ""));
    showScreen("car");
}

/* ---------- File handling ---------- */

function attachFileHandlers() {
    document.querySelectorAll("input[data-input]").forEach((input) => {
        const kind = input.dataset.input;
        input.addEventListener("change", (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            handleFileSelected(kind, file);
        });
    });

    document.querySelectorAll("[data-clear]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const kind = btn.dataset.clear;
            state.files[kind] = null;
            const input = document.querySelector(`input[data-input="${kind}"]`);
            if (input) input.value = "";
            const preview = document.querySelector(`[data-preview="${kind}"]`);
            const zone = document.querySelector(`[data-upload-zone="${kind}"]`);
            if (preview) preview.hidden = true;
            if (zone) zone.hidden = false;
            refreshButtonsForScreen();
        });
    });
}

function handleFileSelected(kind, file) {
    state.files[kind] = file;
    const reader = new FileReader();
    reader.onload = (e) => {
        const img = document.querySelector(`[data-preview-img="${kind}"]`);
        const preview = document.querySelector(`[data-preview="${kind}"]`);
        const zone = document.querySelector(`[data-upload-zone="${kind}"]`);
        if (img) img.src = e.target.result;
        if (preview) preview.hidden = false;
        if (zone) zone.hidden = true;
    };
    reader.readAsDataURL(file);
    haptic("light");
    refreshButtonsForScreen();
}

/* ---------- Submit (заглушка) ----------
 *
 * TODO: подключить к POST /jobs/upload когда backend endpoint будет готов.
 * Сейчас имитируем 4 секунды обработки и показываем фото машины как
 * "результат" — этого достаточно чтобы посмотреть UX flow на кастдеве.
 */

function submitJob() {
    showScreen("result");
    haptic("light");

    const statusBlock = document.querySelector("[data-status]");
    const resultBlock = document.querySelector("[data-result]");
    const errorBlock = document.querySelector("[data-error]");
    const statusText = document.querySelector("[data-status-text]");
    const statusSub = document.querySelector("[data-status-sub]");

    statusBlock.hidden = false;
    resultBlock.hidden = true;
    errorBlock.hidden = true;
    statusText.textContent = "Создаём задачу…";
    statusSub.textContent = "Это может занять до 90 секунд";

    setTimeout(() => {
        statusText.textContent = "Генерируем рендер…";
    }, 1200);

    setTimeout(() => {
        statusBlock.hidden = true;
        resultBlock.hidden = false;
        haptic("success");
    }, 4000);
}

/* ---------- Boot ---------- */

document.addEventListener("DOMContentLoaded", () => {
    initTelegram();
    attachFileHandlers();
    showScreen("car");
});
