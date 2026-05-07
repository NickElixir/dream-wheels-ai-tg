"""HTTP-эндпоинты для jobs.

Создание задачи + polling статуса. Воркер (process_jobs_loop) живёт
отдельно в src/main.py, потому что стартует/останавливается в lifespan
приложения. Здесь — только тонкий HTTP-слой.
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from src import db, redis_client
from src.rate_limit import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

TELEGRAM_FILE_PREFIX = "https://api.telegram.org/file/"

JOBS_RATE_LIMIT = 5
JOBS_RATE_WINDOW_SEC = 60


class JobCreateRequest(BaseModel):
    telegram_user_id: int
    car_url: str
    wheel_url: str

    @field_validator("car_url", "wheel_url")
    @classmethod
    def validate_telegram_url(cls, v: str) -> str:
        # Защита от arbitrary URL: воркер скачивает контент по этому URL и шлёт
        # в Reve API. Без проверки можно подставить любой http-эндпоинт.
        if not v.startswith(TELEGRAM_FILE_PREFIX):
            raise ValueError(f"URL должен начинаться с {TELEGRAM_FILE_PREFIX}")
        return v


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    status: str
    output_image_url: str | None = None


@router.post("", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    await enforce_rate_limit(
        scope="jobs",
        identifier=request.telegram_user_id,
        limit=JOBS_RATE_LIMIT,
        window_sec=JOBS_RATE_WINDOW_SEC,
    )

    logger.info(
        f"📥 Получен запрос на создание задачи. "
        f"Авто: {request.car_url}, Диск: {request.wheel_url}"
    )
    job_id = str(uuid.uuid4())
    pool = db.get_pool()
    rds = redis_client.get_client()

    try:
        async with pool.acquire() as conn:
            user_id = await conn.fetchval(
                "SELECT id FROM users WHERE telegram_user_id = $1",
                request.telegram_user_id,
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
            f"❌ ОШИБКА ЗАПИСИ В БД (INSERT) для "
            f"telegram_user_id={request.telegram_user_id}: {db_err}"
        )
        raise HTTPException(status_code=500, detail="Database insert failed") from db_err

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


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Polling статуса задачи."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, output_image_url FROM jobs WHERE id = $1::uuid",
            job_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(status=row["status"], output_image_url=row["output_image_url"])
