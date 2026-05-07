import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src import db, jobs_api, redis_client
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
app.include_router(jobs_api.router)


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


@app.get("/health/full")
async def health_check_full():
    """Полный health-check: пингует Postgres и Redis.

    Используется внешним keep-alive (cron-job.org) — см. docs/keep-alive-setup.md.
    Каждый вызов делает реальный SQL-запрос → Supabase не ставит проект на паузу
    через 7 дней неактивности.
    """
    try:
        async with db.get_pool().acquire() as conn:
            await conn.fetchval("SELECT 1")
        await redis_client.get_client().ping()
        return {"status": "ok", "db": "alive", "redis": "alive"}
    except Exception as exc:
        logger.exception(f"❌ /health/full failed: {exc}")
        raise HTTPException(status_code=503, detail=f"unhealthy: {exc}") from exc
