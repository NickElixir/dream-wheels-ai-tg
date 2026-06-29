import asyncio
import base64
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import (
    assets_service,
    auth_api,
    db,
    jobs_api,
    payments_api,
    redis_client,
    share_api,
    storage,
)
from src.config import REDIS_JOB_QUEUE, REDIS_URL, WEBAPP_URL, WORKER_ENABLED, runtime_env_summary
from src.credits_service import finalize_job_credit, refund_job_credit
from src.reve_client import fetch_image_bytes, remix_wheels_on_car

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

    logger.info("🟢 Runtime env summary: %s", runtime_env_summary())
    await db.init_pool()
    if REDIS_URL:
        redis_client.init_client()
        logger.info("🟢 Redis client initialized")
    elif WORKER_ENABLED:
        logger.warning("⚠️ WORKER_ENABLED=true, но REDIS_URL не задан: worker не запущен")
    else:
        logger.info("🟢 Redis отключён: API-only режим без очереди рендеров")

    if WORKER_ENABLED and REDIS_URL:
        worker_task = asyncio.create_task(process_jobs_loop())
    elif WORKER_ENABLED:
        logger.warning("⚠️ Redis отсутствует: worker loop не запущен")
    else:
        logger.info("🟢 ВОРКЕР ОТКЛЮЧЕН (WORKER_ENABLED=false)")

    yield

    if worker_task:
        worker_task.cancel()
    await db.close_pool()
    if redis_client.is_initialized():
        await redis_client.close_client()


app = FastAPI(title="Dream Wheels MVP", lifespan=lifespan)

# CORS — webapp хостится на Vercel и шлёт fetch с другого домена.
# Telegram-клиент проксирует Mini App тоже как origin: разрешаем т.г-домены
# чтобы preview Mini App в Telegram Web работал без отдельного фикса.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEBAPP_URL, "https://web.telegram.org"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
    max_age=600,
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_api.router)
app.include_router(jobs_api.router)
app.include_router(payments_api.router)
app.include_router(share_api.router)


async def _load_inputs_as_b64(job_data: dict) -> tuple[str, str]:
    """Получить car/wheel в base64. Поддерживает оба источника payload'а:

    - bot:    {car_url, wheel_url}        — Telegram file URLs
    - webapp: {car_storage_path, wheel_storage_path, source: "webapp"}
              — пути в Supabase Storage `raw` bucket
    """
    if job_data.get("source") == "webapp":
        car_bytes = await storage.download_bytes(
            bucket=storage.RAW_BUCKET, path=job_data["car_storage_path"]
        )
        wheel_bytes = await storage.download_bytes(
            bucket=storage.RAW_BUCKET, path=job_data["wheel_storage_path"]
        )
        return (
            base64.b64encode(car_bytes).decode("utf-8"),
            base64.b64encode(wheel_bytes).decode("utf-8"),
        )
    car_bytes, _ = await fetch_image_bytes(job_data["car_url"])
    wheel_bytes, _ = await fetch_image_bytes(job_data["wheel_url"])
    return (
        base64.b64encode(car_bytes).decode("utf-8"),
        base64.b64encode(wheel_bytes).decode("utf-8"),
    )


async def _save_legacy_bot_inputs(pool, job_id: str, user_id: int, job_data: dict) -> None:
    """Persist Telegram bot input URLs into durable raw storage on first processing."""
    if job_data.get("source") == "webapp":
        return

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT car_asset_id, rim_asset_id FROM jobs WHERE id = $1::uuid",
            job_id,
        )
    if row and row["car_asset_id"] and row["rim_asset_id"]:
        return

    car_bytes, car_content_type = await fetch_image_bytes(job_data["car_url"])
    wheel_bytes, wheel_content_type = await fetch_image_bytes(job_data["wheel_url"])
    car_asset = await assets_service.upload_render_asset(
        owner_user_id=user_id,
        job_id=job_id,
        kind="car_original",
        data=car_bytes,
        content_type=car_content_type,
    )
    rim_asset = await assets_service.upload_render_asset(
        owner_user_id=user_id,
        job_id=job_id,
        kind="rim_original",
        data=wheel_bytes,
        content_type=wheel_content_type,
    )

    async with pool.acquire() as conn:
        async with conn.transaction():
            await assets_service.insert_asset(conn, car_asset)
            await assets_service.insert_asset(conn, rim_asset)
            await conn.execute(
                """
                UPDATE jobs
                SET car_asset_id = COALESCE(car_asset_id, $1::uuid),
                    rim_asset_id = COALESCE(rim_asset_id, $2::uuid)
                WHERE id = $3::uuid
                """,
                car_asset.id,
                rim_asset.id,
                job_id,
            )


async def _save_render_output(pool, job_id: str, user_id: int, img_bytes: bytes) -> str:
    """Сохранить рендер в постоянное public-хранилище Supabase results."""
    asset = await assets_service.upload_render_asset(
        owner_user_id=user_id,
        job_id=job_id,
        kind="result",
        data=img_bytes,
        content_type="image/jpeg",
    )
    async with pool.acquire() as conn:
        async with conn.transaction():
            await assets_service.insert_asset(conn, asset)
            await conn.execute(
                """
                UPDATE jobs
                SET result_asset_id = $1::uuid,
                    output_image_url = $2,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $3::uuid
                """,
                asset.id,
                asset.public_url,
                job_id,
            )
    return asset.public_url or storage.public_url(asset.bucket, asset.storage_key)


async def process_jobs_loop():
    logger.info("🟢 ВОРКЕР ЗАПУЩЕН")
    pool = db.get_pool()
    rds = redis_client.get_client()

    while True:
        job_id = None
        job_data = None
        try:
            result = await rds.blpop(redis_client.key(REDIS_JOB_QUEUE), timeout=10)
            if not result:
                continue

            job_data = json.loads(result[1])
            job_id = job_data["job_id"]
            user_id = int(job_data["user_id"])
            source = job_data.get("source", "bot")
            logger.info(f"🔥 Взята задача: {job_id} (source={source})")

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status = 'processing', updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = $1::uuid",
                    job_id,
                )

            await _save_legacy_bot_inputs(pool, job_id, user_id, job_data)
            car_b64, wheel_b64 = await _load_inputs_as_b64(job_data)
            img_bytes = await remix_wheels_on_car(car_b64, wheel_b64)
            output_url = await _save_render_output(pool, job_id, user_id, img_bytes)

            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE jobs SET status = 'completed', output_image_url = $1, "
                        "completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = $2::uuid",
                        output_url,
                        job_id,
                    )
                    await finalize_job_credit(conn, user_id=user_id, job_id=job_id)
            logger.info(f"✅ Задача {job_id} завершена!")

        except Exception as e:
            logger.exception(f"❌ Ошибка воркера на job_id={job_id}: {e}")
            if job_id:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        if job_data and job_data.get("user_id"):
                            await refund_job_credit(
                                conn,
                                user_id=int(job_data["user_id"]),
                                job_id=job_id,
                            )
                        await conn.execute(
                            "UPDATE jobs SET status = 'failed', error_code = $1, error_message = $2, "
                            "updated_at = CURRENT_TIMESTAMP "
                            "WHERE id = $3::uuid",
                            type(e).__name__,
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
        redis_status = "disabled"
        if redis_client.is_initialized():
            await redis_client.get_client().ping()
            redis_status = "alive"
        return {"status": "ok", "db": "alive", "redis": redis_status}
    except Exception as exc:
        logger.exception(f"❌ /health/full failed: {exc}")
        raise HTTPException(status_code=503, detail=f"unhealthy: {exc}") from exc
