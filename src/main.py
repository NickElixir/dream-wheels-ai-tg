import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import db, redis_client
from src.config import PUBLIC_BASE_URL
from src.reve_client import fetch_image_base64, remix_wheels_on_car

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Подавить INFO-логи httpx/httpcore — каждый запрос содержит BOT_TOKEN в URL
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown приложения. Заменяет устаревшие @app.on_event с FastAPI 0.93+."""
    global worker_task

    await db.init_pool()
    redis_client.init_client()
    worker_task = asyncio.create_task(process_jobs_loop())

    yield

    if worker_task:
        worker_task.cancel()
    await db.close_pool()
    await redis_client.close_client()


app = FastAPI(title="Dream Wheels MVP", lifespan=lifespan)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


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


async def process_jobs_loop():
    logger.info("🟢 ВОРКЕР ЗАПУЩЕН")
    pool = db.get_pool()
    rds = redis_client.get_client()

    while True:
        job_id = None
        try:
            result = await rds.blpop("job_queue", timeout=10)
            if not result:
                continue

            job_data = json.loads(result[1])
            job_id = job_data["job_id"]
            logger.info(f"🔥 Взята задача: {job_id}")

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status = 'processing' WHERE id = $1::uuid", job_id
                )

            car_b64 = await fetch_image_base64(job_data["car_url"])
            wheel_b64 = await fetch_image_base64(job_data["wheel_url"])

            img_bytes = await remix_wheels_on_car(car_b64, wheel_b64)
            filename = f"res_{job_id}.jpg"
            path = os.path.join("static", filename)
            with open(path, "wb") as f:
                f.write(img_bytes)
            output_url = f"{PUBLIC_BASE_URL}/static/{filename}"

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status = 'completed', output_image_url = $1, "
                    "completed_at = CURRENT_TIMESTAMP WHERE id = $2::uuid",
                    output_url,
                    job_id,
                )
            logger.info(f"✅ Задача {job_id} завершена!")

        except Exception as e:
            logger.exception(f"❌ Ошибка воркера на job_id={job_id}: {e}")
            if job_id:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE jobs SET status = 'failed', error_message = $1 "
                        "WHERE id = $2::uuid",
                        str(e),
                        job_id,
                    )
            await asyncio.sleep(5)


@app.head("/")
@app.get("/")
@app.head("/health")
@app.get("/health")
async def health_check():
    """Uptime check для мониторинга деплоя."""
    return {"status": "ok"}


@app.post("/jobs", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    logger.info(
        f"📥 Получен запрос на создание задачи. Авто: {request.car_url}, Диск: {request.wheel_url}"
    )
    job_id = str(uuid.uuid4())
    pool = db.get_pool()
    rds = redis_client.get_client()

    try:
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM users WHERE telegram_user_id = $1", request.telegram_user_id
            )
            if not user_id:
                user_id = await conn.fetchval(
                    "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id",
                    request.telegram_user_id,
                )

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
        logger.exception(
            f"❌ ОШИБКА ЗАПИСИ В БД (INSERT) для telegram_user_id={request.telegram_user_id}: {db_err}"
        )
        raise HTTPException(status_code=500, detail="Database insert failed")

    await rds.rpush(
        "job_queue",
        json.dumps(
            {
                "job_id": job_id,
                "telegram_user_id": request.telegram_user_id,
                "car_url": request.car_url,
                "wheel_url": request.wheel_url,
            }
        ),
    )
    return JobCreateResponse(job_id=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Polling статуса задачи."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, output_image_url FROM jobs WHERE id = $1::uuid", job_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(status=row["status"], output_image_url=row["output_image_url"])
