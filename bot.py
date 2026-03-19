import logging
import os
import asyncio
import aiohttp
import redis.asyncio as redis
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
# URL вашего запущенного FastAPI приложения (например, на Render)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000") 
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация клиента Redis для сессий
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ==========================================
# 📱 ХЭНДЛЕРЫ
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: Обработка команды /start [cite: 4]"""
    await update.message.reply_text(
        "Привет! Я бот для виртуальной примерки дисков 🛞\n\n"
        "Шаг 1: Отправь мне фотографию своего автомобиля."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех входящих фотографий"""
    user_id = update.effective_user.id
    # Берем фото в самом высоком качестве (последнее в массиве)
    photo_file_id = update.message.photo[-1].file_id
    
    # Проверяем в Redis, присылал ли пользователь фото машины в последние 10 минут
    session_key = f"session:{user_id}:car_file_id"
    car_file_id = await redis_client.get(session_key)
    
    # Шаг 2: Если фото машины еще нет, значит это оно [cite: 4]
    if not car_file_id:
        # Сохраняем file_id в Redis с TTL = 600 секунд (10 минут) 
        await redis_client.setex(session_key, 600, photo_file_id)
        await update.message.reply_text("Отличное фото авто! 🚗\n\nШаг 2: Теперь отправь фото диска.")
        return

    # Шаг 3: Если фото машины есть в Redis, значит сейчас прислали фото диска [cite: 4]
    wheel_file_id = photo_file_id
    
    # Сразу удаляем фото машины из сессии, чтобы диалог начался заново
    await redis_client.delete(session_key)
    
    status_msg = await update.message.reply_text("Принято! Отправляю задачу на сервер... ⏳")
    
    # Шаг 4: Отправляем запрос POST /jobs к FastAPI [cite: 4]
    job_id = None
    async with aiohttp.ClientSession() as session:
        payload = {
            "telegram_user_id": user_id,
            "car_file_id": car_file_id,
            "wheel_file_id": wheel_file_id
        }
        try:
            async with session.post(f"{API_BASE_URL}/jobs", json=payload) as resp:
                if resp.status != 200:
                    logger.error(f"API Error: {await resp.text()}")
                    await status_msg.edit_text("❌ Ошибка при создании задачи на сервере.")
                    return
                
                job_data = await resp.json()
                job_id = job_data["job_id"]
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            await status_msg.edit_text("❌ Нет связи с сервером API.")
            return

    await status_msg.edit_text(f"Задача создана! Ожидаем результат... 🎨")

    # Шаг 5-7: Опрашиваем статус задачи (Polling) каждые 3 секунды 
    await poll_job_status(update, status_msg, job_id)

async def poll_job_status(update: Update, status_msg, job_id: str):
    """Опрашивает GET /jobs/{job_id} каждые 3 секунды """
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(3) # Задержка 3 секунды 
            
            try:
                async with session.get(f"{API_BASE_URL}/jobs/{job_id}") as resp:
                    if resp.status == 200:
                        status_data = await resp.json()
                        current_status = status_data["status"]
                        
                        if current_status == "completed":
                            # Задача выполнена, получаем URL картинки [cite: 5, 15]
                            result_url = status_data["output_image_url"]
                            
                            # Отправляем фото пользователю в Telegram 
                            await update.message.reply_photo(
                                photo=result_url, 
                                caption="Готово! Твой автомобиль на новых дисках 🔥"
                            )
                            # Удаляем сервисное сообщение "Ожидаем результат..."
                            await status_msg.delete()
                            break
                            
                        elif current_status == "failed":
                            # Задача завершилась ошибкой
                            await status_msg.edit_text("❌ Произошла ошибка при генерации изображения. Попробуй еще раз.")
                            break
                        
                        # Если статус 'queued' или 'processing', цикл просто пойдет на следующий круг
            except Exception as e:
                logger.error(f"Polling error: {e}")
                # Если сервер моргнул, просто продолжаем опрос
                continue

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка случайного текста"""
    await update.message.reply_text("Пожалуйста, отправь мне фотографию как картинку (не файлом и не текстом).")

# ==========================================
# 🚀 ЗАПУСК БОТА
# ==========================================
def main():
    logger.info("Бот запускается...")
    # Инициализация приложения
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков (handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запуск поллинга Telegram серверов
    application.run_polling()

if __name__ == "__main__":
    main()
