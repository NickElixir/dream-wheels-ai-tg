import asyncio
import logging

import aiohttp
import redis.asyncio as redis
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import (
    API_BASE_URL,
    API_INTERNAL_TOKEN,
    BOT_TOKEN,
    LEGAL_BASE_URL,
    REDIS_URL,
    WEBAPP_URL,
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Подавить INFO-логи httpx/httpcore — каждый запрос содержит BOT_TOKEN в URL
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Бот работает в своём процессе и не разделяет lifespan FastAPI,
# поэтому держит свой Redis-клиент. Создаём лениво, чтобы импорт
# модуля не падал, если REDIS_URL не задан (тесты, локальный запуск).
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


SESSION_TTL_SEC = 600
POLL_INTERVAL_SEC = 3
POLL_MAX_RETRIES = 60  # 60 * 3 = 3 минуты ожидания результата

FEEDBACK_KEYBOARD = {
    "en": {
        "like": "👍 Like",
        "dislike": "👎 Dislike",
        "voted_like": "✅ 👍 Liked",
        "voted_dislike": "✅ 👎 Disliked",
        "failed": "Could not save feedback. Please try again.",
    },
    "ru": {
        "like": "👍 Нравится",
        "dislike": "👎 Не нравится",
        "voted_like": "✅ 👍 Понравилось",
        "voted_dislike": "✅ 👎 Не понравилось",
        "failed": "Не удалось сохранить оценку. Попробуйте ещё раз.",
    },
}

MESSAGES = {
    "en": {
        "open_app": "🚗 Open Dream Wheels",
        "open_support": "💬 Open support",
        "open_document": "📄 Open document",
        "start": (
            "Hi! Tap the button below to open the Mini App, "
            "or send a car photo directly in this chat."
        ),
        "app": "Open the Mini App below.",
        "help": (
            "Send two photos in chat: first the car from the side, "
            "then the wheel from the front. "
            "You can also open the Mini App below."
        ),
        "support": "Open support in the Mini App.",
        "privacy": "Open the privacy policy.",
        "terms": "Open the public offer.",
        "car_received": "Car photo received! 🚗\nNow send a wheel photo.",
        "creating_job": "Creating job... ⏳",
        "api_error": "❌ API server error.",
        "backend_unavailable": "❌ Backend is unavailable.",
        "queued": "Job queued! Waiting for the result... 🎨",
        "done_caption": "Done! Your AI render is ready.",
        "processing_failed": "❌ Processing failed.",
        "timeout": "❌ Timed out while waiting for the result.",
    },
    "ru": {
        "open_app": "🚗 Открыть Dream Wheels",
        "open_support": "💬 Открыть поддержку",
        "open_document": "📄 Открыть документ",
        "start": (
            "Привет! Жми кнопку ниже, чтобы открыть Mini App, или отправь фото машины прямо в чат."
        ),
        "app": "Открываю Mini App.",
        "help": (
            "Отправь 2 фото в чат: сначала машину сбоку, "
            "затем диск анфас. "
            "Или открой Mini App кнопкой ниже."
        ),
        "support": "Открываю поддержку в Mini App.",
        "privacy": "Открываю политику конфиденциальности.",
        "terms": "Открываю публичную оферту.",
        "car_received": "Фото авто получено! 🚗\nТеперь отправь фото диска.",
        "creating_job": "Создаю задачу... ⏳",
        "api_error": "❌ Ошибка сервера API.",
        "backend_unavailable": "❌ Бэкенд недоступен.",
        "queued": "Задача в очереди! Ожидаем результат... 🎨",
        "done_caption": "Готово! Ваш AI-рендер готов.",
        "processing_failed": "❌ Ошибка при обработке.",
        "timeout": "❌ Превышено время ожидания.",
    },
}


def _locale(update: Update) -> str:
    user = update.effective_user
    language_code = ((user.language_code if user else "") or "").lower()
    return "ru" if language_code.startswith("ru") else "en"


def _t(update: Update, key: str) -> str:
    return MESSAGES[_locale(update)][key]


def _webapp_url(section: str | None = None) -> str:
    base_url = WEBAPP_URL.rstrip("/")
    return f"{base_url}/?section={section}" if section else base_url


def _legal_url(path: str) -> str:
    return f"{LEGAL_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


async def _reply_with_webapp_button(update: Update, text: str, url: str, button_text: str) -> None:
    message = update.effective_message
    if message is None:
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(button_text, web_app=WebAppInfo(url=url))]]
    )
    await message.reply_text(text, reply_markup=keyboard)


async def _reply_with_url_button(update: Update, text: str, url: str, button_text: str) -> None:
    message = update.effective_message
    if message is None:
        return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=url)]])
    await message.reply_text(text, reply_markup=keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_with_webapp_button(
        update,
        _t(update, "start"),
        _webapp_url(),
        _t(update, "open_app"),
    )


async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_with_webapp_button(
        update,
        _t(update, "app"),
        _webapp_url(),
        _t(update, "open_app"),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_with_webapp_button(
        update,
        _t(update, "help"),
        _webapp_url(),
        _t(update, "open_app"),
    )


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_with_webapp_button(
        update,
        _t(update, "support"),
        _webapp_url("support"),
        _t(update, "open_support"),
    )


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_with_url_button(
        update,
        _t(update, "privacy"),
        _legal_url("/legal/privacy"),
        _t(update, "open_document"),
    )


async def terms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_with_url_button(
        update,
        _t(update, "terms"),
        _legal_url("/legal/offer"),
        _t(update, "open_document"),
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo_file_id = update.message.photo[-1].file_id

    rds = _get_redis()
    session_key = f"session:{user_id}:car_url"
    cached_car_url = await rds.get(session_key)

    telegram_file = await context.bot.get_file(photo_file_id)
    current_photo_url = telegram_file.file_path

    if not cached_car_url:
        await rds.setex(session_key, SESSION_TTL_SEC, current_photo_url)
        await update.message.reply_text(_t(update, "car_received"))
        return

    wheel_url = current_photo_url
    await rds.delete(session_key)

    status_msg = await update.message.reply_text(_t(update, "creating_job"))

    async with aiohttp.ClientSession() as session:
        username = update.effective_user.username if update.effective_user else None
        payload = {
            "telegram_user_id": user_id,
            "username": username,
            "car_url": cached_car_url,
            "wheel_url": wheel_url,
        }
        try:
            async with session.post(f"{API_BASE_URL}/jobs", json=payload) as resp:
                if resp.status != 200:
                    await status_msg.edit_text(_t(update, "api_error"))
                    return
                job_data = await resp.json()
                job_id = job_data["job_id"]
        except Exception as e:
            logger.exception(f"Связь с API потеряна для user_id={user_id}: {e}")
            await status_msg.edit_text(_t(update, "backend_unavailable"))
            return

    await status_msg.edit_text(_t(update, "queued"))
    await poll_job_status(update, status_msg, job_id)


async def poll_job_status(update: Update, status_msg, job_id: str):
    async with aiohttp.ClientSession() as session:
        for _ in range(POLL_MAX_RETRIES):
            await asyncio.sleep(POLL_INTERVAL_SEC)
            try:
                async with session.get(f"{API_BASE_URL}/jobs/{job_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data["status"]

                        if status == "completed":
                            lang = _locale(update)
                            fb = FEEDBACK_KEYBOARD[lang]
                            feedback_markup = InlineKeyboardMarkup(
                                [
                                    [
                                        InlineKeyboardButton(
                                            fb["like"],
                                            callback_data=f"feedback:like:{job_id}",
                                        ),
                                        InlineKeyboardButton(
                                            fb["dislike"],
                                            callback_data=f"feedback:dislike:{job_id}",
                                        ),
                                    ]
                                ]
                            )
                            await update.message.reply_photo(
                                photo=data["output_image_url"],
                                caption=_t(update, "done_caption"),
                                reply_markup=feedback_markup,
                            )
                            await status_msg.delete()
                            return

                        elif status == "failed":
                            await status_msg.edit_text(_t(update, "processing_failed"))
                            return

            except Exception as e:
                logger.exception(f"Ошибка опроса job_id={job_id}: {e}")
                continue

    await status_msg.edit_text(_t(update, "timeout"))


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[0] != "feedback":
        await query.answer()
        return
    _, vote, job_id = parts

    lang = _locale(update)
    fb = FEEDBACK_KEYBOARD[lang]
    telegram_user_id = query.from_user.id if query.from_user else None
    if telegram_user_id is None:
        await query.answer(fb["failed"], show_alert=True)
        return

    try:
        async with aiohttp.ClientSession() as session:
            headers = {}
            if API_INTERNAL_TOKEN:
                headers["X-Internal-Token"] = API_INTERNAL_TOKEN
            async with session.post(
                f"{API_BASE_URL}/jobs/{job_id}/feedback",
                json={"vote": vote, "telegram_user_id": telegram_user_id},
                headers=headers,
            ) as resp:
                if resp.status != 204:
                    body = await resp.text()
                    logger.warning(
                        "Feedback API rejected job_id=%s tg_user=%s status=%s body=%s",
                        job_id,
                        telegram_user_id,
                        resp.status,
                        body[:500],
                    )
                    await query.answer(fb["failed"], show_alert=True)
                    return
    except Exception as e:
        logger.exception(f"Ошибка отправки feedback job_id={job_id}: {e}")
        await query.answer(fb["failed"], show_alert=True)
        return

    voted_label = fb["voted_like"] if vote == "like" else fb["voted_dislike"]
    try:
        await query.answer()
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(voted_label, callback_data="noop")]]
            )
        )
    except Exception:
        pass


def main():
    logger.info("Запуск Telegram-бота...")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", app_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("privacy", privacy_command))
    application.add_handler(CommandHandler("terms", terms_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^feedback:"))
    application.run_polling()


if __name__ == "__main__":
    main()
