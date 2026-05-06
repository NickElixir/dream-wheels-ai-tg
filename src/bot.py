import asyncio
import logging

import aiohttp
import redis.asyncio as redis
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import API_BASE_URL, BOT_TOKEN, REDIS_URL

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне фотографию своего автомобиля.")


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
        await update.message.reply_text("Фото авто получено! 🚗\nТеперь отправь фото диска.")
        return

    wheel_url = current_photo_url
    await rds.delete(session_key)

    status_msg = await update.message.reply_text("Создаю задачу... ⏳")

    async with aiohttp.ClientSession() as session:
        payload = {"telegram_user_id": user_id, "car_url": cached_car_url, "wheel_url": wheel_url}
        try:
            async with session.post(f"{API_BASE_URL}/jobs", json=payload) as resp:
                if resp.status != 200:
                    await status_msg.edit_text("❌ Ошибка сервера API.")
                    return
                job_data = await resp.json()
                job_id = job_data["job_id"]
        except Exception as e:
            logger.exception(f"Связь с API потеряна для user_id={user_id}: {e}")
            await status_msg.edit_text("❌ Бэкенд недоступен.")
            return

    await status_msg.edit_text("Задача в очереди! Ожидаем результат... 🎨")
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
                            await update.message.reply_photo(
                                photo=data["output_image_url"],
                                caption="Готово! (Имитация работы ИИ)",
                            )
                            await status_msg.delete()
                            return

                        elif status == "failed":
                            await status_msg.edit_text("❌ Ошибка при обработке.")
                            return

            except Exception as e:
                logger.exception(f"Ошибка опроса job_id={job_id}: {e}")
                continue

    await status_msg.edit_text("❌ Превышено время ожидания.")


def main():
    logger.info("Запуск Telegram-бота...")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.run_polling()


if __name__ == "__main__":
    main()
