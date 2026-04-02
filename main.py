import asyncio
import json
import logging
import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import redis.asyncio as redis
import base64
import aiohttp
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

app = FastAPI(title="Dream Wheels MVP")
os.makedirs("static", exist_ok=True) # Создаем папку, если ее нет
app.mount("/static", StaticFiles(directory="static"), name="static")
db_pool = None
redis_client = None
worker_task = None

# Модели данных
class JobCreateRequest(BaseModel):
    telegram_user_id: int
    car_url: str
    wheel_url: str

class JobCreateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    status: str
    output_image_url: str | None = None

# ==========================================
# ФОНОВЫЙ ВОРКЕР
# ==========================================
async def get_base64_from_url(url: str) -> str:
    """Скачивает картинку в память и сразу возвращает Base64, не трогая жесткий диск"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                img_bytes = await resp.read()
                return base64.b64encode(img_bytes).decode('utf-8')
            else:
                raise Exception(f"Ошибка скачивания файла: HTTP {resp.status}")
                
async def process_jobs_loop():
    async def process_jobs_loop():
    logger.info("🟢 ВОРКЕР ЗАПУЩЕН И ЖДЕТ ЗАДАЧУ...")
    while True:
        job_id = None
        try:
            # 1. Читаем из очереди
            result = await redis_client.blpop("job_queue", timeout=10)
            if not result:
                continue
                
            logger.info("📦 Сигнал из Redis получен!")
            
            # 2. Безопасный парсинг данных
            try:
                queue_name, job_data_str = result
                job_data = json.loads(job_data_str)
                job_id = job_data["job_id"]
                logger.info(f"🔥 Воркер извлек задачу: {job_id}")
            except Exception as parse_err:
                logger.error(f"❌ Ошибка расшифровки JSON из Redis: {parse_err}. Сырые данные: {result}")
                continue

            # 3. Обновление статуса в БД
            logger.info(f"🔄 Стучимся в базу данных для смены статуса {job_id}...")
            async with db_pool.acquire() as connection:
                await connection.execute(
                    "UPDATE jobs SET status = 'processing' WHERE id = $1::uuid", 
                    job_id
                )
            logger.info("✅ База данных ответила: статус изменен на processing!")

            # 2. Скачиваем картинки в Base64 (используем функцию, которую мы добавили ранее)
            logger.info(f"📥 [Задача {job_id}] Скачиваем картинки в Base64...")
            car_b64 = await fetch_image_as_base64(job_data["car_url"])
            wheel_b64 = await fetch_image_as_base64(job_data["wheel_url"])

            # 3. Обращение к Reve API
            logger.info(f"🚀 [Задача {job_id}] Отправляем запрос в Reve API...")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as api_session:
                headers = {
                    "Authorization": f"Bearer {os.getenv('REVE_API_KEY', 'ВАШ_ТОКЕН')}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "prompt": "Replace the wheels of the car in <img>0</img> with the wheel design provided in <img>1</img>. Maintain realistic perspective, lighting, shadows, and scale.",
                    "reference_images": [car_b64, wheel_b64],
                    "aspect_ratio": "16:9",
                    "version": "latest"
                }
                
                async with api_session.post("https://api.reve.com/v1/image/remix", json=payload, headers=headers) as reve_resp:
                    response_text = await reve_resp.text()
                    if reve_resp.status != 200:
                        raise Exception(f"Reve API error (HTTP {reve_resp.status}): {response_text}")
                    
                    import json
                    result_data = json.loads(response_text)
                    
                    if result_data.get('content_violation'):
                        raise Exception("Reve API: Нарушение контента")
                        
                    b64_result = result_data.get('image')
                    if not b64_result:
                        raise Exception("Reve API не вернул 'image'")
                        
                    # Сохраняем готовую картинку в папку static
                    output_filename = f"result_{job_id}.jpg"
                    output_path = os.path.join("static", output_filename)
                    import base64
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(b64_result))
                        
                    # Формируем URL результата
                    output_url = f"https://dream-wheels-ai-tg.onrender.com/static/{output_filename}"

            # 4. ОБНОВЛЯЕМ БАЗУ ДАННЫХ НА COMPLETED (То, что я забыл!)
            async with db_pool.acquire() as connection:
                # Атомарная транзакция для надежности
                async with connection.transaction():
                    await connection.execute(
                        "UPDATE jobs SET status = 'completed', output_image_url = $1, completed_at = CURRENT_TIMESTAMP WHERE id = $2::uuid", 
                        output_url, job_id
                    )
                    # Также обновляем счетчик задач пользователя, как требовал MVP
                    await connection.execute(
                        "UPDATE users SET job_count = job_count + 1 WHERE telegram_user_id = $1", 
                        int(job_data["telegram_user_id"])
                    )
                    
            logger.info(f"✅ Задача {job_id} успешно завершена и записана в БД!")

        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА ВОРКЕРА: {e}")
            # Пишем ошибку в БД, чтобы бот не ждал вечно
            if job_id:
                try:
                    async with db_pool.acquire() as connection:
                        await connection.execute(
                            "UPDATE jobs SET status = 'failed', error_message = $1 WHERE id = $2::uuid", 
                            str(e), job_id
                        )
                except Exception as db_err:
                    logger.error(f"Не удалось записать failed в БД: {db_err}")
            await asyncio.sleep(5)
# ==========================================
# ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ
# ==========================================
@app.on_event("startup")
async def startup():
    global db_pool, redis_client, worker_task
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    worker_task = asyncio.create_task(process_jobs_loop())

@app.on_event("shutdown")
async def shutdown():
    if worker_task:
        worker_task.cancel()
    await db_pool.close()
    await redis_client.close()

# ==========================================
# API ЭНДПОИНТЫ (MVP) [cite: 14, 15]
# ==========================================
@app.head("/")
@app.get("/")
@app.head("/health")
@app.get("/health")
async def health_check():
    """Uptime check for deployment health monitoring."""
    return {"status": "ok"}

@app.post("/jobs", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    logger.info(f"📥 Получен запрос на создание задачи. Авто: {request.car_url}, Диск: {request.wheel_url}")
    job_id = str(uuid.uuid4())
    
    try:
        async with db_pool.acquire() as conn:
            # 1. Ищем или создаем пользователя (Таблица users [cite: 8])
            user_id = await conn.fetchval(
                "SELECT id FROM users WHERE telegram_user_id = $1", 
                request.telegram_user_id
            )
            if not user_id:
                user_id = await conn.fetchval(
                    "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id", 
                    request.telegram_user_id
                )
            
            # 2. Создаем задачу с явным указанием типов (Таблица jobs [cite: 10])
            await conn.execute(
                """
                INSERT INTO jobs (id, user_id, status, car_image_url, wheel_image_url) 
                VALUES ($1::uuid, $2, 'queued', $3, $4)
                """,
                job_id, user_id, request.car_url, request.wheel_url
            )
            logger.info(f"✅ Задача {job_id} успешно записана в БД со статусом queued")

    except Exception as db_err:
        logger.error(f"❌ ОШИБКА ЗАПИСИ В БД (INSERT): {db_err}")
        raise HTTPException(status_code=500, detail="Database insert failed")

    # Пушим в Redis
    await redis_client.rpush("job_queue", json.dumps({
        "job_id": job_id,
        "telegram_user_id": request.telegram_user_id,
        "car_url": request.car_url,
        "wheel_url": request.wheel_url  # <-- ДОБАВЛЕНО
    }))
    return JobCreateResponse(job_id=job_id, status="queued")
    
@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll job status. Returns status and output_image_url[cite: 15]."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, output_image_url FROM jobs WHERE id = $1::uuid", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(status=row["status"], output_image_url=row["output_image_url"])
