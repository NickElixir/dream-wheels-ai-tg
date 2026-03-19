import asyncio
import json
import logging
import os
import base64
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncpg
import redis.asyncio as redis
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
REVE_API_KEY = os.getenv("REVE_API_KEY", "ВАШ_КЛЮЧ_REVE")

# Папка для раздачи готовых картинок
os.makedirs("static", exist_ok=True)

app = FastAPI(title="Wheel Try-On API (MVP)")
app.mount("/static", StaticFiles(directory="static"), name="static")

db_pool = None
redis_client = None
worker_task = None

# Схемы Pydantic... (те же, что и раньше)
class JobCreateRequest(BaseModel):
    telegram_user_id: int
    car_file_id: str
    wheel_file_id: str

class JobCreateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    status: str
    output_image_url: str | None = None

# ==========================================
# 🛠 ФОНОВЫЙ ВОРКЕР (Background Worker)
# ==========================================
async def download_telegram_file(file_id: str, save_path: str):
    """Скачивает файл из Telegram по file_id."""
    async with aiohttp.ClientSession() as session:
        # 1. Получаем путь к файлу на сервере Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        async with session.get(url) as resp:
            data = await resp.json()
            if not data.get("ok"):
                raise Exception(f"Ошибка получения файла из Telegram: {data}")
            file_path = data["result"]["file_path"]
            
        # 2. Скачиваем сам файл
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        async with session.get(download_url) as resp:
            with open(save_path, "wb") as f:
                f.write(await resp.read())

async def process_jobs_loop():
    """Бесконечный цикл, который опрашивает очередь Redis (BLPOP)."""
    logger.info("Воркер запущен и ждет задачи...")
    
    while True:
        try:
            # BLPOP блокирует выполнение до появления задачи в списке 
            # Возвращает кортеж: (имя_очереди, данные)
            result = await redis_client.blpop("image_processing_queue", timeout=0)
            if not result:
                continue
                
            queue_name, job_data_bytes = result
            job_data = json.loads(job_data_bytes)
            job_id = job_data["job_id"]
            
            logger.info(f"Воркер взял задачу: {job_id}")
            
            # Обновляем статус в БД на 'processing' 
            async with db_pool.acquire() as connection:
                await connection.execute("UPDATE jobs SET status = 'processing' WHERE id = $1", job_id)
            
            # 1. Скачиваем картинки из Telegram 
            car_path = f"static/car_{job_id}.jpg"
            wheel_path = f"static/wheel_{job_id}.jpg"
            await download_telegram_file(job_data["car_file_id"], car_path)
            await download_telegram_file(job_data["wheel_file_id"], wheel_path)
            
            # 2. Подготовка и отправка в Reve v1.1 API 
            with open(car_path, "rb") as f:
                car_b64 = base64.b64encode(f.read()).decode('utf-8')
            with open(wheel_path, "rb") as f:
                wheel_b64 = base64.b64encode(f.read()).decode('utf-8')
                
            reve_payload = {
                "prompt": "Replace the wheels on the car in <img>0</img> with the wheel design shown in <img>1</img>. Photorealistic, 8k.",
                "reference_images": [car_b64, wheel_b64],
                "aspect_ratio": "16:9",
                "version": "latest"
            }
            
            reve_headers = {
                "Authorization": f"Bearer {REVE_API_KEY}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.reve.com/v1/image/remix", json=reve_payload, headers=reve_headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise Exception(f"Reve API error: {err}")
                    
                    reve_data = await resp.json()
                    result_b64 = reve_data.get("image")
                    if not result_b64:
                        raise Exception("Reve не вернул картинку")
            
            # 3. Сохраняем результат
            output_filename = f"result_{job_id}.png"
            output_path = f"static/{output_filename}"
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(result_b64))
                
            # Формируем URL. На Render ваш домен будет храниться в переменной RENDER_EXTERNAL_URL
            base_url = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000")
            output_url = f"{base_url}/static/{output_filename}"
            
            # 4. Обновляем статус на 'completed' 
            async with db_pool.acquire() as connection:
                await connection.execute(
                    """
                    UPDATE jobs 
                    SET status = 'completed', output_image_url = $1, completed_at = CURRENT_TIMESTAMP 
                    WHERE id = $2
                    """, 
                    output_url, job_id
                )
            logger.info(f"Задача {job_id} успешно завершена!")
            
            # Удаляем временные файлы-исходники, чтобы не забивать диск
            os.remove(car_path)
            os.remove(wheel_path)

        except Exception as e:
            logger.error(f"Ошибка в воркере: {e}")
            # В случае ошибки ставим статус 'failed' и записываем текст ошибки [cite: 11, 12, 13]
            if 'job_id' in locals():
                async with db_pool.acquire() as connection:
                    await connection.execute(
                        "UPDATE jobs SET status = 'failed', error_message = $1 WHERE id = $2", 
                        str(e), job_id
                    )

# ==========================================
# 🔄 ЖИЗНЕННЫЙ ЦИКЛ (Startup / Shutdown)
# ==========================================
@app.on_event("startup")
async def startup():
    global db_pool, redis_client, worker_task
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    # Запускаем нашего воркера как фоновую задачу FastAPI 
    worker_task = asyncio.create_task(process_jobs_loop())

@app.on_event("shutdown")
async def shutdown():
    worker_task.cancel() # Останавливаем воркера
    await db_pool.close()
    await redis_client.close()

# Эндпоинты API (POST /jobs, GET /jobs/{job_id}, GET /health) остаются здесь...
# (Код из предыдущего сообщения)from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import redis.asyncio as redis
import os
import json

# Инициализация приложения FastAPI 
app = FastAPI(title="Wheel Try-On API (MVP)")

# ==========================================
# ⚙️ НАСТРОЙКИ ПОДКЛЮЧЕНИЙ
# ==========================================
# Сюда вы вставите ссылки, которые вам выдал Neon/Supabase и ваш Redis-провайдер
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Глобальные переменные для пула соединений
db_pool = None
redis_client = None

# ==========================================
# 📦 Pydantic СХЕМЫ (Валидация данных)
# ==========================================
class JobCreateRequest(BaseModel):
    telegram_user_id: int
    car_file_id: str
    wheel_file_id: str

class JobCreateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    status: str
    output_image_url: str | None = None

# ==========================================
# 🔄 ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ
# ==========================================
@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    # Открываем пул соединений с PostgreSQL
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    # Подключаемся к Redis 
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    # Закрываем соединения при выключении сервера
    await db_pool.close()
    await redis_client.close()

# ==========================================
# 🚀 ЭНДПОИНТЫ (API Routes)
# ==========================================

# 1. Проверка здоровья (Uptime check) [cite: 15]
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 2. Создание задачи (Create job) [cite: 15]
@app.post("/jobs", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    async with db_pool.acquire() as connection:
        # Шаг 1: Проверяем, есть ли пользователь, если нет - создаем
        user_id = await connection.fetchval(
            "SELECT id FROM users WHERE telegram_user_id = $1", 
            request.telegram_user_id
        )
        if not user_id:
            user_id = await connection.fetchval(
                "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id",
                request.telegram_user_id
            )
        
        # Шаг 2: Создаем запись о задаче в БД со статусом 'queued' [cite: 13, 15]
        job_id = await connection.fetchval(
            """
            INSERT INTO jobs (user_id, status) 
            VALUES ($1, 'queued') 
            RETURNING id
            """,
            user_id
        )
        job_id_str = str(job_id)

    # Шаг 3: Формируем полезную нагрузку для очереди
    # В реальном MVP здесь также может быть логика скачивания файлов и загрузки в S3 [cite: 15]
    job_payload = {
        "job_id": job_id_str,
        "telegram_user_id": request.telegram_user_id,
        "car_file_id": request.car_file_id,
        "wheel_file_id": request.wheel_file_id
    }
    
    # Шаг 4: Отправляем задачу в Redis очередь (RPUSH) [cite: 2, 15]
    await redis_client.rpush("image_processing_queue", json.dumps(job_payload))
    
    # Возвращаем ID задачи и статус [cite: 15]
    return JobCreateResponse(job_id=job_id_str, status="queued")

# 3. Проверка статуса задачи (Poll job status) [cite: 15]
@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    async with db_pool.acquire() as connection:
        # Ищем задачу в БД
        row = await connection.fetchrow(
            "SELECT status, output_image_url FROM jobs WHERE id = $1",
            job_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Возвращаем статус и ссылку на готовую картинку (если есть) [cite: 15]
        return JobStatusResponse(
            status=row["status"],
            output_image_url=row["output_image_url"]
        )
