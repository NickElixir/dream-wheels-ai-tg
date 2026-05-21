"""HTTP-эндпоинты для jobs.

Создание задачи (через бот по URL или из webapp через multipart) +
polling статуса. Воркер (process_jobs_loop) живёт отдельно в src/main.py,
потому что стартует/останавливается в lifespan приложения.
Здесь — только тонкий HTTP-слой.
"""

import json
import logging
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from src import db, redis_client, storage
from src.auth import InitDataInvalid, parse_init_data
from src.rate_limit import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

TELEGRAM_FILE_PREFIX = "https://api.telegram.org/file/"

# Лимит для бота (POST /jobs c URL): защита от спама от одного юзера.
JOBS_RATE_LIMIT = 5
JOBS_RATE_WINDOW_SEC = 60

# Лимит для webapp (POST /jobs/upload): Reve API стоит денег, ставим жёстче.
UPLOAD_RATE_LIMIT = 10
UPLOAD_RATE_WINDOW_SEC = 60 * 60  # 10/час

MAX_RAW_FILE_BYTES = 10 * 1024 * 1024  # 10 MB — синхронно с лимитом raw bucket
ALLOWED_UPLOAD_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

# Идемпотентность: ключ живёт 1 час. Юзер с ретраем (плохой коннект)
# получит тот же job_id вместо дубля рендера.
IDEMPOTENCY_TTL_SEC = 60 * 60


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


class JobStatusDetailedResponse(BaseModel):
    """Расширенный ответ для webapp polling: + url рендера + текст ошибки."""

    job_id: str
    status: str
    result_url: str | None = None
    error: str | None = None


class FeedbackRequest(BaseModel):
    vote: str

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v: str) -> str:
        if v not in ("like", "dislike"):
            raise ValueError("vote must be 'like' or 'dislike'")
        return v


def _download_filename(job_id: str, content_type: str | None) -> str:
    ext = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get((content_type or "").split(";")[0].strip().lower(), "jpg")
    return f"dream-wheels-{job_id}.{ext}"


async def _ensure_user(telegram_user_id: int) -> int:
    """Найти или создать users.id по telegram_user_id."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE telegram_user_id = $1",
            telegram_user_id,
        )
        if not user_id:
            user_id = await conn.fetchval(
                "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id",
                telegram_user_id,
            )
    return user_id


@router.post("", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    """Создание задачи из бота — приходят Telegram file URL'ы."""
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
        user_id = await _ensure_user(request.telegram_user_id)
        async with pool.acquire() as conn:
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


@router.post("/upload", response_model=JobCreateResponse)
async def upload_job(
    car_image: Annotated[UploadFile, File()],
    wheel_image: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Form()],
    init_data: Annotated[str, Form()] = "",
):
    """Создание задачи из webapp — приходят бинарники car/wheel + Telegram initData.

    Flow:
    1. Валидируем initData (HMAC) → достаём telegram_user_id.
    2. Rate limit (10/час на юзера).
    3. Идемпотентность: если ключ уже видели — возвращаем тот же job_id.
    4. Льём оба файла в Storage `raw`.
    5. Создаём job в БД, кидаем в Redis-очередь воркеру.
    """
    try:
        parsed = parse_init_data(init_data)
    except InitDataInvalid as exc:
        logger.warning(f"⛔ initData отклонён: {exc}")
        raise HTTPException(status_code=401, detail=f"initData invalid: {exc}") from exc

    user = parsed.get("user") or {}
    telegram_user_id = user.get("id")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="initData без user.id")
    telegram_user_id = int(telegram_user_id)

    await enforce_rate_limit(
        scope="jobs_upload",
        identifier=telegram_user_id,
        limit=UPLOAD_RATE_LIMIT,
        window_sec=UPLOAD_RATE_WINDOW_SEC,
    )

    rds = redis_client.get_client()
    idem_redis_key = f"idem:jobs_upload:{telegram_user_id}:{idempotency_key}"
    existing_job_id = await rds.get(idem_redis_key)
    if existing_job_id:
        logger.info(
            f"♻️  Idempotent replay: tg_user={telegram_user_id} "
            f"key={idempotency_key} → job={existing_job_id}"
        )
        return JobCreateResponse(job_id=existing_job_id, status="queued")

    for upload, label in ((car_image, "car"), (wheel_image, "wheel")):
        if upload.content_type not in ALLOWED_UPLOAD_MIME:
            raise HTTPException(
                status_code=415,
                detail=f"{label}: неподдерживаемый MIME {upload.content_type}",
            )

    car_bytes = await car_image.read()
    wheel_bytes = await wheel_image.read()
    for data, label in ((car_bytes, "car"), (wheel_bytes, "wheel")):
        if len(data) > MAX_RAW_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{label}: файл больше {MAX_RAW_FILE_BYTES // 1024 // 1024} MB",
            )
        if len(data) == 0:
            raise HTTPException(status_code=400, detail=f"{label}: пустой файл")

    job_id = str(uuid.uuid4())
    logger.info(
        f"📥 /jobs/upload tg_user={telegram_user_id} job={job_id} "
        f"car={len(car_bytes)}B wheel={len(wheel_bytes)}B"
    )

    try:
        car_path, _ = await storage.upload_raw_image(
            job_id=job_id,
            kind="car",
            data=car_bytes,
            content_type=car_image.content_type,
        )
        wheel_path, _ = await storage.upload_raw_image(
            job_id=job_id,
            kind="wheel",
            data=wheel_bytes,
            content_type=wheel_image.content_type,
        )
    except storage.StorageError as exc:
        logger.exception(f"❌ Storage upload failed для job_id={job_id}: {exc}")
        raise HTTPException(status_code=502, detail="Storage upload failed") from exc

    try:
        user_id = await _ensure_user(telegram_user_id)
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (id, user_id, status, car_image_url, wheel_image_url)
                VALUES ($1::uuid, $2, 'queued', $3, $4)
                """,
                job_id,
                user_id,
                car_path,
                wheel_path,
            )
        logger.info(f"✅ Job {job_id} создан в БД (queued)")
    except Exception as db_err:
        logger.exception(f"❌ DB INSERT failed для job_id={job_id}: {db_err}")
        raise HTTPException(status_code=500, detail="Database insert failed") from db_err

    # TODO(backend-integration): воркер process_jobs_loop сейчас умеет только
    # скачивать по URL через aiohttp.get() — для raw-bucket пути нужен другой
    # путь скачивания (storage.download_bytes с service_role auth). Расширить
    # формат payload и логику воркера в следующем коммите.
    await rds.rpush(
        "job_queue",
        json.dumps(
            {
                "job_id": job_id,
                "telegram_user_id": telegram_user_id,
                "source": "webapp",
                "car_storage_path": car_path,
                "wheel_storage_path": wheel_path,
            }
        ),
    )

    await rds.set(idem_redis_key, job_id, ex=IDEMPOTENCY_TTL_SEC)

    return JobCreateResponse(job_id=job_id, status="queued")


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Polling статуса задачи (legacy — для бота)."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, output_image_url FROM jobs WHERE id = $1::uuid",
            job_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(status=row["status"], output_image_url=row["output_image_url"])


@router.get("/{job_id}/status", response_model=JobStatusDetailedResponse)
async def get_job_status_detailed(job_id: str):
    """Расширенный статус для webapp polling: status + result_url + error."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, output_image_url, error_message
            FROM jobs
            WHERE id = $1::uuid
            """,
            job_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusDetailedResponse(
        job_id=job_id,
        status=row["status"],
        result_url=row["output_image_url"],
        error=row["error_message"],
    )


@router.post("/{job_id}/feedback", status_code=204)
async def submit_feedback(job_id: str, request: FeedbackRequest):
    """Сохранить лайк/дизлайк на результат. Повторный вызов перезаписывает."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE jobs SET feedback = $1 WHERE id = $2::uuid",
            request.vote,
            job_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"👍 Feedback '{request.vote}' для job_id={job_id}")


@router.get("/{job_id}/download")
async def download_job_result(job_id: str):
    """Отдать результат как attachment для Telegram.WebApp.downloadFile."""
    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status, output_image_url
            FROM jobs
            WHERE id = $1::uuid
            """,
            job_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["status"] != "completed" or not row["output_image_url"]:
        raise HTTPException(status_code=409, detail="Job result is not ready")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            result_resp = await client.get(row["output_image_url"])
    except httpx.HTTPError as exc:
        logger.exception(f"❌ Result download proxy failed для job_id={job_id}: {exc}")
        raise HTTPException(status_code=502, detail="Result fetch failed") from exc

    if result_resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Result fetch failed: HTTP {result_resp.status_code}",
        )

    content_type = result_resp.headers.get("content-type", "image/jpeg")
    filename = _download_filename(job_id, content_type)
    return Response(
        content=result_resp.content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Allow-Origin": "https://web.telegram.org",
            "Cache-Control": "private, max-age=300",
        },
    )
