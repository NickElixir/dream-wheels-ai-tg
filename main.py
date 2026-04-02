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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

app = FastAPI(title="Dream Wheels API")
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
async def download_image(url: str, save_path: str):
    """Скачивает изображение по ссылке и сохраняет на диск"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(save_path, "wb") as f:
                    f.write(await resp.read())
            else:
                raise Exception(f"Не удалось скачать файл: {resp.status}")
                
async def process_jobs_loop():
    logger.info("🟢 Воркер запущен и ждет задачи...")
    while True:
        try:
            # Паттерн BLPOP (блокирующее чтение из списка). 
            # Таймаут 5 сек нужен, чтобы цикл мог корректно завершиться при выключении сервера.
            result = await redis_client.blpop("job_queue", timeout=9)
            if not result:
                continue
                
            _, job_data_str = result
            job_data = json.loads(job_data_str)
            job_id = job_data["job_id"]
            
            logger.info(f"⚙️ Взята задача в работу: {job_id}")

            # 1. Меняем статус на processing [cite: 13]
            async with db_pool.acquire() as conn:
                await conn.execute("UPDATE jobs SET status = 'processing' WHERE id = $1::uuid", job_id)

            # ==================================================
            # ИНТЕГРАЦИЯ REVE API (БАЗА 64)
            # ==================================================
            logger.info(f"🚀 Подготовка файлов для задачи {job_id}")
            
            os.makedirs("static", exist_ok=True)
            car_path = f"static/car_{job_id}.jpg"
            wheel_path = f"static/wheel_{job_id}.jpg"
            result_url = None
            
            try:
                # 1. Скачиваем картинки на сервер
                await download_image(job_data["car_url"], car_path)
                await download_image(job_data["wheel_url"], wheel_path)
                
                # 2. Кодируем в Base64
                with open(car_path, "rb") as f:
                    car_b64 = base64.b64encode(f.read()).decode('utf-8')
                with open(wheel_path, "rb") as f:
                    wheel_b64 = base64.b64encode(f.read()).decode('utf-8')

                logger.info(f"🧠 Отправка Base64 в Reve API для задачи {job_id}")
                
                # 3. Отправляем в ИИ
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as api_session:
                    headers = {
                        "Authorization": f"Bearer {os.getenv('REVE_API_KEY', 'ВАШ_ТОКЕН')}",
                        "Content-Type": "application/json"
                    }
                    
                    # ВНИМАНИЕ: Если Reve API требует другие названия ключей (не car_image_url), измените их здесь
                    reve_payload = {
                        "car_image_base64": car_b64, 
                        "wheel_image_base64": wheel_b64
                    }
                    
                    # ВНИМАНИЕ: Подставьте точный URL эндпоинта Reve API
                    api_url = "https://api.reve.com/v1/image/remix" 
                    
                    async with api_session.post(api_url, json=reve_payload, headers=headers) as reve_resp:
                        if reve_resp.status != 200:
                            error_text = await reve_resp.text()
                            raise Exception(f"Ошибка Reve API ({reve_resp.status}): {error_text}")
                        
                        reve_data = await reve_resp.json()
                        result_url = reve_data.get("output_image_url") # Убедитесь, что ключ совпадает с ответом Reve
                        
                        if not result_url:
                            raise Exception("Reve API ответил 200 OK, но не вернул output_image_url")
                            
            finally:
                # 4. ОЧИСТКА: Удаляем тяжелые файлы с диска в любом случае (даже при ошибке)
                for file_path in [car_path, wheel_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            # ==================================================

            # 3. Меняем статус на completed и сохраняем URL [cite: 13, 15]
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE jobs 
                    SET status = 'completed', output_image_url = $1, completed_at = CURRENT_TIMESTAMP 
                    WHERE id = $2::uuid
                    """, 
                    mock_output_url, job_id
                )
                # Увеличиваем счетчик задач пользователя [cite: 9]
                await conn.execute("UPDATE users SET job_count = job_count + 1 WHERE telegram_user_id = $1", job_data["telegram_user_id"])
                
            logger.info(f"✅ Задача завершена: {job_id}")

        except Exception as e:
            logger.error(f"❌ Ошибка воркера: {e}")
            await asyncio.sleep(5) # Защита от спама в Redis при падении БД

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
@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Единый и безопасный маршрут, исключающий раздвоение потоков"""
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
