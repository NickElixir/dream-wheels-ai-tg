import asyncio
import base64
import json
import logging
import os
import uuid

import aiohttp
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Подавить INFO-логи httpx/httpcore — каждый запрос содержит BOT_TOKEN в URL
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://dream-wheels-ai-tg.onrender.com").rstrip(
    "/"
)

app = FastAPI(title="Dream Wheels MVP")
os.makedirs("static", exist_ok=True)  # Создаем папку, если ее нет
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
                return base64.b64encode(img_bytes).decode("utf-8")
            else:
                raise Exception(f"Ошибка скачивания файла: HTTP {resp.status}")


async def process_jobs_loop():
    logger.info("🟢 ВОРКЕР ЗАПУЩЕН")
    while True:
        job_id = None
        try:
            # Читаем из Redis
            result = await redis_client.blpop("job_queue", timeout=10)
            if not result:
                continue

            job_data = json.loads(result[1])
            job_id = job_data["job_id"]
            logger.info(f"🔥 Взята задача: {job_id}")

            # 1. Смена статуса
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status = 'processing' WHERE id = $1::uuid", job_id
                )

            # 2. Подготовка Base64
            car_b64 = await get_base64_from_url(job_data["car_url"])
            wheel_b64 = await get_base64_from_url(job_data["wheel_url"])

            # 3. Запрос к Reve (Формат: Массив + Теги)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
                payload = {
                    "prompt": "Professional car tuning: take the wheels from <img>1</img> and install them on the car in <img>0</img>. High quality, photorealistic.",
                    "reference_images": [car_b64, wheel_b64],
                    "aspect_ratio": "16:9",
                    "version": "latest",
                }
                headers = {
                    "Authorization": f"Bearer {os.getenv('REVE_API_KEY')}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }

                async with session.post(
                    "https://api.reve.com/v1/image/remix", json=payload, headers=headers
                ) as resp:
                    res_json = await resp.json()
                    if resp.status != 200:
                        raise Exception(f"Reve Error: {res_json}")

                    b64_output = res_json.get("image")

                    # Сохраняем результат в static
                    filename = f"res_{job_id}.jpg"
                    path = os.path.join("static", filename)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(b64_output))

                    output_url = f"{PUBLIC_BASE_URL}/static/{filename}"

            # 4. ФИНАЛЬНОЕ ОБНОВЛЕНИЕ БАЗЫ
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status = 'completed', output_image_url = $1, completed_at = CURRENT_TIMESTAMP WHERE id = $2::uuid",
                    output_url,
                    job_id,
                )
            logger.info(f"✅ Задача {job_id} завершена!")

        except Exception as e:
            logger.error(f"❌ Ошибка воркера: {e}")
            if job_id:
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE jobs SET status = 'failed', error_message = $1 WHERE id = $2::uuid",
                        str(e),
                        job_id,
                    )
            await asyncio.sleep(5)


# ==========================================
# ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ
# ==========================================
@app.on_event("startup")
async def startup():
    global db_pool, redis_client, worker_task
    # statement_cache_size=0 is required when DATABASE_URL points to
    # Supabase pooler (port 6543) running in transaction pool_mode —
    # otherwise asyncpg's prepared statements collide between pool sessions.
    db_pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
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
    logger.info(
        f"📥 Получен запрос на создание задачи. Авто: {request.car_url}, Диск: {request.wheel_url}"
    )
    job_id = str(uuid.uuid4())

    try:
        async with db_pool.acquire() as conn:
            # 1. Ищем или создаем пользователя (Таблица users [cite: 8])
            user_id = await conn.fetchval(
                "SELECT id FROM users WHERE telegram_user_id = $1", request.telegram_user_id
            )
            if not user_id:
                user_id = await conn.fetchval(
                    "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id",
                    request.telegram_user_id,
                )

            # 2. Создаем задачу с явным указанием типов (Таблица jobs [cite: 10])
            await conn.execute(
                """
                INSERT INTO jobs (id, user_id, status, car_image_url, wheel_image_url)
                VALUES ($1::uuid, $2, 'queued', $3, $4)
                """,
                job_id,
                user_id,
                request.car_url,
                request.wheel_url,
            )
            logger.info(f"✅ Задача {job_id} успешно записана в БД со статусом queued")

    except Exception as db_err:
        logger.error(f"❌ ОШИБКА ЗАПИСИ В БД (INSERT): {db_err}")
        raise HTTPException(status_code=500, detail="Database insert failed")

    # Пушим в Redis
    await redis_client.rpush(
        "job_queue",
        json.dumps(
            {
                "job_id": job_id,
                "telegram_user_id": request.telegram_user_id,
                "car_url": request.car_url,
                "wheel_url": request.wheel_url,  # <-- ДОБАВЛЕНО
            }
        ),
    )
    return JobCreateResponse(job_id=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll job status. Returns status and output_image_url[cite: 15]."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, output_image_url FROM jobs WHERE id = $1::uuid", job_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(status=row["status"], output_image_url=row["output_image_url"])
