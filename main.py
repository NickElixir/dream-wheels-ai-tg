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

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
REVE_API_KEY = os.getenv("REVE_API_KEY")

os.makedirs("static", exist_ok=True)

app = FastAPI(title="Wheel Try-On API (MVP)")
app.mount("/static", StaticFiles(directory="static"), name="static")

db_pool = None
redis_client = None
worker_task = None

class JobCreateRequest(BaseModel):
    telegram_user_id: int
    car_url: str      # Изменили car_file_id на car_url
    wheel_url: str    # Изменили wheel_file_id на wheel_url

class JobCreateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    status: str
    output_image_url: str | None = None

async def download_image(url: str, save_path: str):
    """Простое скачивание по прямой ссылке без обращения к API Telegram"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            with open(save_path, "wb") as f:
                f.write(await resp.read())

async def process_jobs_loop():
    logger.info("🟢 Воркер успешно запущен (LPOP режим)!")
    while True:
        job_id = None
        try:
            # LPOP не блокирует соединение, решая проблему зависания Upstash
            result = await redis_client.lpop("image_processing_queue")
            
            if not result:
                await asyncio.sleep(2)
                continue
                
            # ... (начало воркера)
            job_data = json.loads(result)
            job_id = job_data["job_id"]
            
            logger.info(f"🔥 Воркер взял задачу: {job_id}")
            
            async with db_pool.acquire() as connection:
                await connection.execute("UPDATE jobs SET status = 'processing' WHERE id = $1::uuid", job_id)
            
            car_path = f"static/car_{job_id}.jpg"
            wheel_path = f"static/wheel_{job_id}.jpg"
            
            # Используем новую функцию и новые ключи
            await download_image(job_data["car_url"], car_path)
            await download_image(job_data["wheel_url"], wheel_path)
            
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
                # ВНИМАНИЕ: Замените на реальный эндпоинт Reve API, когда он будет готов
                async with session.post("https://api.reve.com/v1/image/remix", json=reve_payload, headers=reve_headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise Exception(f"Reve API error: {err}")
                    reve_data = await resp.json()
                    result_b64 = reve_data.get("image")
                    if not result_b64:
                        raise Exception("Reve не вернул картинку")
            
            output_filename = f"result_{job_id}.png"
            output_path = f"static/{output_filename}"
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(result_b64))
                
            base_url = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000")
            output_url = f"{base_url}/static/{output_filename}"
            
            async with db_pool.acquire() as connection:
                await connection.execute(
                    "UPDATE jobs SET status = 'completed', output_image_url = $1, completed_at = CURRENT_TIMESTAMP WHERE id = $2::uuid", 
                    output_url, job_id
                )
            logger.info(f"✅ Задача {job_id} успешно завершена!")
            
            os.remove(car_path)
            os.remove(wheel_path)

        except Exception as e:
            logger.error(f"❌ Ошибка в воркере: {e}")
            if job_id:
                try:
                    async with db_pool.acquire() as connection:
                        await connection.execute(
                            "UPDATE jobs SET status = 'failed', error_message = $1 WHERE id = $2::uuid", 
                            str(e), job_id
                        )
                except Exception as db_err:
                    logger.error(f"Ошибка БД при записи фейла: {db_err}")
            
            # Спасительная пауза для предотвращения бесконечного цикла перезагрузок
            await asyncio.sleep(5)

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.head("/")
@app.get("/")
async def root():
    """Корневой маршрут, чтобы скрипт не перезагружался из-за 404 ошибки"""
    return {"status": "ok", "message": "Wheel Try-On API is running"}

@app.post("/jobs", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    async with db_pool.acquire() as connection:
        user_id = await connection.fetchval("SELECT id FROM users WHERE telegram_user_id = $1", request.telegram_user_id)
        if not user_id:
            user_id = await connection.fetchval("INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id", request.telegram_user_id)
        job_id = await connection.fetchval("INSERT INTO jobs (user_id, status) VALUES ($1, 'queued') RETURNING id", user_id)
        job_id_str = str(job_id)

    job_payload = {
        "job_id": job_id_str,
        "telegram_user_id": request.telegram_user_id,
        "car_url": request.car_url,
        "wheel_url": request.wheel_url
    }
    
    await redis_client.rpush("image_processing_queue", json.dumps(job_payload))
    return JobCreateResponse(job_id=job_id_str, status="queued")

@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    async with db_pool.acquire() as connection:
        row = await connection.fetchrow("SELECT status, output_image_url FROM jobs WHERE id = $1::uuid", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(status=row["status"], output_image_url=row["output_image_url"])
