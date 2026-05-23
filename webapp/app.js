// Dream Wheels AI — Telegram WebApp

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
const SUPPORTS_DOWNLOAD_FILE = tgSupports("8.0") && typeof tg?.downloadFile === "function";

const I18N = {
    en: {
        steps: {
            upload: "Upload",
            result: "Done",
        },
        upload: {
            title: "Upload your car and wheel photos",
            hint: "Full side view of the car, front view of the wheel. JPG or PNG, up to 10 MB.",
            pasteHint: "Tip: copy an image, select a slot, then press Ctrl+V.",
            carPhoto: "Car photo",
            wheelPhoto: "Wheel photo",
            choose: "Tap to choose",
            pastedCar: "Pasted image as car photo",
            pastedWheel: "Pasted image as wheel photo",
            pasteNoImage: "Clipboard does not contain an image",
            replaceCar: "Replace car",
            replaceWheel: "Replace wheel",
            carPreviewAlt: "Car preview",
            wheelPreviewAlt: "Wheel preview",
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
        },
        feedback: {
            label: "How did it turn out?",
            thanks: "Thanks for the feedback!",
            failed: "Could not save feedback. Please try again.",
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
        footer: {
            notTelegram: "Not in Telegram",
        },
    },
    ru: {
        steps: {
            upload: "Загрузка",
            result: "Готово",
        },
        upload: {
            title: "Загрузи фото машины и диска",
            hint: "Машина целиком сбоку, диск анфас. JPG или PNG, до 10 MB.",
            pasteHint: "Можно скопировать фото, выбрать слот и нажать Ctrl+V.",
            carPhoto: "Фото машины",
            wheelPhoto: "Фото диска",
            choose: "Нажми, чтобы выбрать",
            pastedCar: "Вставили изображение как фото машины",
            pastedWheel: "Вставили изображение как фото диска",
            pasteNoImage: "В буфере обмена нет изображения",
            replaceCar: "Заменить машину",
            replaceWheel: "Заменить диск",
            carPreviewAlt: "Превью машины",
            wheelPreviewAlt: "Превью диска",
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
        },
        feedback: {
            label: "Как результат?",
            thanks: "Спасибо за оценку!",
            failed: "Не удалось сохранить оценку. Попробуйте ещё раз.",
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
        footer: {
            notTelegram: "Не в Telegram",
        },
    },
};

function detectLocale() {
    const telegramLanguage = tg?.initDataUnsafe?.user?.language_code;
    const browserLanguage = navigator.language;
    const language = (telegramLanguage || browserLanguage || "en").toLowerCase();
    return language.startsWith("ru") ? "ru" : "en";
}

const locale = detectLocale();

function t(key) {
    return key.split(".").reduce((value, part) => value?.[part], I18N[locale]) ?? key;
}

function applyTranslations() {
    document.documentElement.lang = locale;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-alt]").forEach((el) => {
        el.alt = t(el.dataset.i18nAlt);
    });
}

function localizeErrorMessage(message) {
    if (locale === "en" && /[А-Яа-яЁё]/.test(message || "")) {
        return t("errors.requestFailed");
    }
    return message || t("errors.generic");
}

const SCREENS = ["upload", "result"];
const state = {
    screen: "upload",
    files: { car: null, wheel: null },
    pasteTarget: "car",
    jobId: null,
    resultUrl: null,
    resultDownloadUrl: null,
    resultFileName: null,
    downloading: false,
    sharing: false,
    submitting: false,
    voted: false,
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

    const indicator = document.querySelector("[data-step-indicator]");
    indicator.textContent = name === "result" ? t("steps.result") : t("steps.upload");

    refreshButtonsForScreen();
}

function refreshButtonsForScreen() {
    if (state.screen === "upload") {
        setBackButton(null);
        const ready = Boolean(state.files.car?.blob && state.files.wheel?.blob);
        setMainButton({
            text: t("actions.createRender"),
            enabled: ready && !state.submitting,
            onClick: ready && !state.submitting ? submitJob : null,
        });
    } else if (state.screen === "result") {
        if (state.submitting) {
            setBackButton(null);
            hideMainButton();
        } else {
            setBackButton(() => resetFlow());
            setMainButton({
                text: t("actions.createAnother"),
                enabled: true,
                onClick: resetFlow,
            });
        }
    }
}

function resetFlow() {
    state.downloading = false;
    state.sharing = false;
    state.submitting = false;
    state.voted = false;
    state.files = { car: null, wheel: null };
    state.pasteTarget = "car";
    state.jobId = null;
    state.resultUrl = null;
    state.resultDownloadUrl = null;
    state.resultFileName = null;
    ["car", "wheel"].forEach((s) => {
        const preview = document.querySelector(`[data-preview="${s}"]`);
        const zone = document.querySelector(`[data-upload-zone="${s}"]`);
        if (preview) preview.hidden = true;
        if (zone) zone.hidden = false;
    });
    const downloadButton = document.querySelector("[data-download-result]");
    if (downloadButton) {
        downloadButton.hidden = true;
        setDownloadButtonState();
    }
    const shareButton = document.querySelector("[data-share-result]");
    if (shareButton) {
        shareButton.hidden = true;
        setShareButtonState();
    }
    const feedbackBlock = document.querySelector("[data-feedback-block]");
    if (feedbackBlock) {
        feedbackBlock.hidden = true;
        feedbackBlock.querySelectorAll(".feedback-btn").forEach((btn) => {
            btn.disabled = false;
            btn.classList.remove("selected-like", "selected-dislike");
        });
        const thanks = feedbackBlock.querySelector("[data-feedback-thanks]");
        if (thanks) {
            thanks.textContent = t("feedback.thanks");
            thanks.hidden = true;
        }
    }
    document.querySelectorAll("input[data-input]").forEach((i) => (i.value = ""));
    showScreen("upload");
}

/* ---------- File handling ---------- */

function attachFileHandlers() {
    document.querySelectorAll("[data-upload-zone]").forEach((zone) => {
        zone.addEventListener("click", () => {
            setPasteTarget(zone.dataset.uploadZone);
        });
    });

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
            setPasteTarget(kind);
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

    document.addEventListener("paste", handlePaste);
}

function setPasteTarget(kind) {
    if (kind !== "car" && kind !== "wheel") return;
    state.pasteTarget = kind;
}

function nextPasteTarget() {
    if (!state.files.car?.blob) return "car";
    if (!state.files.wheel?.blob) return "wheel";
    return state.pasteTarget || "wheel";
}

function showPasteStatus(message, isError = false) {
    const status = document.querySelector("[data-paste-status]");
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle("error", isError);
    clearTimeout(showPasteStatus.timer);
    showPasteStatus.timer = setTimeout(() => {
        status.hidden = true;
    }, 2400);
}

function imageFileFromPasteEvent(event) {
    const items = Array.from(event.clipboardData?.items || []);
    for (const item of items) {
        if (item.kind === "file" && item.type.startsWith("image/")) {
            return item.getAsFile();
        }
    }
    return null;
}

function handlePaste(event) {
    if (state.screen !== "upload") return;
    const file = imageFileFromPasteEvent(event);
    if (!file) {
        showPasteStatus(t("upload.pasteNoImage"), true);
        return;
    }
    event.preventDefault();
    const kind = nextPasteTarget();
    const ext = (file.type.split("/")[1] || "png").replace("jpeg", "jpg");
    const namedFile = new File([file], `pasted-${kind}.${ext}`, { type: file.type });
    setPasteTarget(kind === "car" ? "wheel" : "car");
    handleFileSelected(kind, namedFile);
    showPasteStatus(t(kind === "car" ? "upload.pastedCar" : "upload.pastedWheel"));
}

function handleFileSelected(kind, file) {
    setPasteTarget(kind);
    // iOS Telegram WebView теряет File reference при переходах между экранами,
    // поэтому читаем содержимое в Blob сразу и храним его — Blob можно передать
    // в FormData точно так же как File. Параллельно делаем data-URL preview.
    file.arrayBuffer().then((buf) => {
        state.files[kind] = {
            blob: new Blob([buf], { type: file.type }),
            name: file.name,
            size: file.size,
            type: file.type,
        };
        refreshButtonsForScreen();
    });

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
}

function setDownloadButtonState({ disabled = false, text = t("actions.downloadImage") } = {}) {
    const downloadButton = document.querySelector("[data-download-result]");
    if (!downloadButton) return;
    downloadButton.disabled = disabled;
    downloadButton.textContent = text;
}

function setShareButtonState({ disabled = false, text = t("actions.share") } = {}) {
    const shareButton = document.querySelector("[data-share-result]");
    if (!shareButton) return;
    shareButton.disabled = disabled;
    shareButton.textContent = text;
}

function requestTelegramDownload(url, fileName) {
    return new Promise((resolve, reject) => {
        try {
            tg.downloadFile({ url, file_name: fileName }, (accepted) => {
                resolve(Boolean(accepted));
            });
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
        setTimeout(() => {
            setDownloadButtonState();
        }, 1800);
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
    return `https://t.me/share/url?url=${encodeURIComponent(state.resultUrl)}&text=${encodeURIComponent(t("share.text"))}`;
}

function openTelegramShareUrl() {
    const shareUrl = buildTelegramShareUrl();

    if (HAS_TG && typeof tg.openTelegramLink === "function") {
        tg.openTelegramLink(shareUrl);
        return true;
    }

    if (HAS_TG && typeof tg.openLink === "function") {
        tg.openLink(shareUrl);
        return true;
    }

    window.location.href = shareUrl;
    return true;
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
            text: t("share.text"),
            url: state.resultUrl,
        };

        if (HAS_TG) {
            openTelegramShareUrl();
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
            } catch (_) {
                window.open(buildTelegramShareUrl(), "_blank", "noopener");
                setShareButtonState({ text: t("actions.openingLink") });
            }
            haptic("success");
        }
    } catch (error) {
        if (error?.name === "AbortError") {
            setShareButtonState({ text: t("actions.canceled") });
            haptic("warning");
        } else {
            console.error("[DW] share failed", error);
            setShareButtonState({ disabled: false, text: t("actions.failed") });
            haptic("warning");
        }
    }

    setTimeout(() => {
        state.sharing = false;
        setShareButtonState();
    }, 1600);
}

function attachResultHandlers() {
    const downloadButton = document.querySelector("[data-download-result]");
    if (downloadButton) {
        downloadButton.addEventListener("click", () => {
            downloadResult();
        });
    }

    const shareButton = document.querySelector("[data-share-result]");
    if (shareButton) {
        shareButton.addEventListener("click", () => {
            shareResult();
        });
    }
}

/* ---------- Feedback ---------- */

async function sendFeedback(vote) {
    if (state.voted || !state.jobId) return;
    state.voted = true;

    const feedbackBlock = document.querySelector("[data-feedback-block]");
    const thanks = document.querySelector("[data-feedback-thanks]");
    const feedbackButtons = feedbackBlock.querySelectorAll(".feedback-btn");
    feedbackButtons.forEach((btn) => {
        btn.disabled = true;
        if (btn.dataset.feedback === vote) {
            btn.classList.add(vote === "like" ? "selected-like" : "selected-dislike");
        }
    });

    haptic("success");

    try {
        const resp = await fetch(`${API_BASE_URL}/jobs/${state.jobId}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ vote, init_data: HAS_TG ? tg.initData : "" }),
        });
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
    } catch (e) {
        console.error("[DW] feedback failed", e);
        state.voted = false;
        feedbackButtons.forEach((btn) => {
            btn.disabled = false;
            btn.classList.remove("selected-like", "selected-dislike");
        });
        if (thanks) {
            thanks.textContent = t("feedback.failed");
            thanks.hidden = false;
        }
        haptic("warning");
        return;
    }

    if (thanks) {
        thanks.textContent = t("feedback.thanks");
        thanks.hidden = false;
    }
}

function attachFeedbackHandlers() {
    document.querySelectorAll("[data-feedback]").forEach((btn) => {
        btn.addEventListener("click", () => sendFeedback(btn.dataset.feedback));
    });
}

/* ---------- Submit ---------- */

const API_BASE_URL = "https://dream-wheels-ai-tg.onrender.com";
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 110000; // Reve timeout 90s + margin

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function makeIdempotencyKey() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `dw-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function submitJob() {
    if (state.submitting) return;
    state.submitting = true;
    showScreen("result");
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

    statusBlock.hidden = false;
    resultBlock.hidden = true;
    errorBlock.hidden = true;
    statusText.textContent = t("status.startingServer");
    statusSub.textContent = t("status.coldStart");
    if (statusDebug) {
        statusDebug.hidden = true;
        statusDebug.textContent = "";
    }

    function showError(msg) {
        state.submitting = false;
        statusBlock.hidden = true;
        resultBlock.hidden = true;
        errorBlock.hidden = false;
        if (errorText) errorText.textContent = localizeErrorMessage(msg);
        refreshButtonsForScreen();
        pushDebug("showError", msg);
        haptic("error");
    }

    pushDebug("submit:start");

    // Render Free tier спит после 15 мин простоя — пингуем /health чтобы
    // разбудить сервис до отправки файлов (cold start ~30с).
    try {
        pushDebug("health:request");
        await fetch(`${API_BASE_URL}/health`, { method: "GET" });
        pushDebug("health:ok");
    } catch (_) {
        pushDebug("health:fail");
        // ignore — if health fails, upload will fail too and show proper error
    }

    statusText.textContent = t("status.uploading");
    statusSub.textContent = t("status.upTo90");

    console.log("[DW] submit state:", {
        carName: state.files.car?.name,
        carBlobSize: state.files.car?.blob?.size,
        carSize: state.files.car?.size,
        wheelName: state.files.wheel?.name,
        wheelBlobSize: state.files.wheel?.blob?.size,
        wheelSize: state.files.wheel?.size,
        hasTG: HAS_TG,
        initDataLen: HAS_TG ? (tg.initData || "").length : 0,
    });
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
    formData.append("init_data", HAS_TG ? tg.initData : "");
    const idempotencyKey = makeIdempotencyKey();
    formData.append("idempotency_key", idempotencyKey);
    pushDebug("upload:key", idempotencyKey);

    let jobId;
    try {
        pushDebug("upload:request");
        const resp = await fetch(`${API_BASE_URL}/jobs/upload`, {
            method: "POST",
            body: formData,
        });
        pushDebug("upload:response", `status=${resp.status}`);
        const data = await resp.json().catch(() => ({}));
        pushDebug("upload:body", JSON.stringify(data));
        if (!resp.ok) {
            const detail = Array.isArray(data.detail)
                ? data.detail.map((e) => e.msg).join("; ")
                : (data.detail || `HTTP ${resp.status}`);
            throw new Error(detail);
        }
        jobId = data.job_id;
        state.jobId = jobId;
        pushDebug("upload:job", jobId);
    } catch (e) {
        showError(e.message);
        return;
    }

    statusText.textContent = t("status.generating");
    pushDebug("poll:start");

    const deadline = Date.now() + POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
        await sleep(POLL_INTERVAL_MS);
        let statusData;
        try {
            pushDebug("poll:request", jobId);
            const r = await fetch(`${API_BASE_URL}/jobs/${jobId}/status`);
            statusData = await r.json();
            pushDebug("poll:response", JSON.stringify(statusData));
        } catch (_) {
            pushDebug("poll:network-fail");
            continue;
        }

        if (statusData.status === "completed") {
            state.submitting = false;
            statusBlock.hidden = true;
            if (resultImg && statusData.result_url) {
                state.resultUrl = statusData.result_url;
                state.resultDownloadUrl = `${API_BASE_URL}/jobs/${jobId}/download`;
                state.resultFileName = `dream-wheels-${jobId}.jpg`;
                resultImg.src = statusData.result_url;
                resultImg.hidden = false;
            }
            const downloadButton = document.querySelector("[data-download-result]");
            if (downloadButton) {
                setDownloadButtonState();
                downloadButton.hidden = !state.resultDownloadUrl;
            }
            const shareButton = document.querySelector("[data-share-result]");
            if (shareButton) {
                setShareButtonState();
                shareButton.hidden = !state.resultUrl;
            }
            const feedbackBlock = document.querySelector("[data-feedback-block]");
            if (feedbackBlock) feedbackBlock.hidden = false;
            resultBlock.hidden = false;
            refreshButtonsForScreen();
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

/* ---------- Boot ---------- */

document.addEventListener("DOMContentLoaded", () => {
    applyTranslations();
    initTelegram();
    attachFileHandlers();
    attachResultHandlers();
    attachFeedbackHandlers();
    showScreen("upload");
});
