"""HTTP-эндпоинты для jobs.

Создание задачи (через бот по URL или из webapp через multipart) +
polling статуса. Воркер (process_jobs_loop) живёт отдельно в src/main.py,
потому что стартует/останавливается в lifespan приложения.
Здесь — только тонкий HTTP-слой.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from src import assets_service, db, redis_client, storage
from src.assets_service import AssetKind
from src.auth import AuthContext, resolve_telegram_auth
from src.config import API_INTERNAL_TOKEN, REDIS_JOB_QUEUE, WORKER_ENABLED
from src.credits_service import InsufficientCreditsError, refund_job_credit, reserve_job_credit
from src.rate_limit import enforce_rate_limit
from src.share_api import share_url_for_job
from src.users_service import ensure_user

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


def _get_render_queue_client(endpoint: str, telegram_user_id: int):
    if not WORKER_ENABLED:
        logger.warning(
            "⛔ Render queue disabled: endpoint=%s tg_user=%s", endpoint, telegram_user_id
        )
        raise HTTPException(status_code=503, detail="Render worker disabled")
    try:
        return redis_client.get_client()
    except RuntimeError as exc:
        logger.exception(
            "❌ Render queue unavailable: endpoint=%s tg_user=%s: %s",
            endpoint,
            telegram_user_id,
            exc,
        )
        raise HTTPException(status_code=503, detail="Render queue unavailable") from exc


class JobCreateRequest(BaseModel):
    telegram_user_id: int
    username: str | None = None
    car_url: str
    wheel_url: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        username = v.strip().lstrip("@")
        return username or None

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
    job_id: str | None = None
    status: str
    output_image_url: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    assets: dict[str, "JobAssetResponse"] | None = None


class JobStatusDetailedResponse(BaseModel):
    """Расширенный ответ для webapp polling: + url рендера + текст ошибки."""

    job_id: str
    status: str
    result_url: str | None = None
    share_url: str | None = None
    error: str | None = None
    error_code: str | None = None
    assets: dict[str, "JobAssetResponse"] | None = None


class JobAssetResponse(BaseModel):
    id: str
    kind: str
    content_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    created_at: datetime | None = None
    url: str | None = None
    download_url: str | None = None


class JobHistoryItem(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    result_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    generation_provider: str | None = None
    provider_request_id: str | None = None
    assets: dict[str, JobAssetResponse] = Field(default_factory=dict)


class JobHistoryResponse(BaseModel):
    jobs: list[JobHistoryItem]
    limit: int
    offset: int


class FeedbackRequest(BaseModel):
    vote: str
    init_data: str | None = None
    telegram_user_id: int | None = None

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v: str) -> str:
        if v not in ("like", "dislike"):
            raise ValueError("vote must be 'like' or 'dislike'")
        return v


def _telegram_user_id_from_feedback_request(
    request: FeedbackRequest,
    internal_token: str | None,
) -> int:
    if request.init_data:
        auth = resolve_telegram_auth(
            init_data=request.init_data,
            telegram_user_id=request.telegram_user_id,
            auth_name="feedback",
        )
        return auth.telegram_user_id

    if not API_INTERNAL_TOKEN:
        logger.error("API_INTERNAL_TOKEN не сконфигурирован: bot feedback отключён")
        raise HTTPException(status_code=503, detail="Feedback auth is not configured")
    if not internal_token or internal_token != API_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid internal token")
    if request.telegram_user_id is None:
        raise HTTPException(status_code=400, detail="telegram_user_id required")
    return request.telegram_user_id


def _download_filename(job_id: str, content_type: str | None) -> str:
    ext = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get((content_type or "").split(";")[0].strip().lower(), "jpg")
    return f"dream-wheels-{job_id}.{ext}"


def _has_auth_inputs(
    *,
    init_data: str | None,
    telegram_user_id: int | None,
    authorization: str | None,
) -> bool:
    return bool(init_data or authorization or telegram_user_id is not None)


def _resolve_jobs_auth(
    *,
    init_data: str | None,
    telegram_user_id: int | None,
    authorization: str | None,
    required: bool,
) -> AuthContext | None:
    if not required and not _has_auth_inputs(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
    ):
        return None
    return resolve_telegram_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        auth_name="jobs history",
    )


def _asset_from_row(row, prefix: str, *, job_id: str) -> JobAssetResponse | None:
    asset_id = row[f"{prefix}_asset_id"]
    if not asset_id:
        return None
    kind = row[f"{prefix}_asset_kind"]
    bucket = row[f"{prefix}_asset_bucket"]
    storage_key = row[f"{prefix}_asset_storage_key"]
    is_result = kind == "result" and bucket == storage.RESULTS_BUCKET
    return JobAssetResponse(
        id=str(asset_id),
        kind=kind,
        content_type=row[f"{prefix}_asset_content_type"],
        size_bytes=row[f"{prefix}_asset_size_bytes"],
        width=row[f"{prefix}_asset_width"],
        height=row[f"{prefix}_asset_height"],
        created_at=row[f"{prefix}_asset_created_at"],
        url=storage.public_url(bucket, storage_key) if is_result else None,
        download_url=assets_service.asset_download_path(job_id, kind),
    )


def _assets_from_row(row, *, job_id: str) -> dict[str, JobAssetResponse]:
    assets: dict[str, JobAssetResponse] = {}
    for prefix in ("car", "rim", "result"):
        asset = _asset_from_row(row, prefix, job_id=job_id)
        if asset:
            assets[asset.kind] = asset
    return assets


def _job_assets_select_clause() -> str:
    return """
        car_asset.id AS car_asset_id,
        car_asset.kind AS car_asset_kind,
        car_asset.bucket AS car_asset_bucket,
        car_asset.storage_key AS car_asset_storage_key,
        car_asset.content_type AS car_asset_content_type,
        car_asset.size_bytes AS car_asset_size_bytes,
        car_asset.width AS car_asset_width,
        car_asset.height AS car_asset_height,
        car_asset.created_at AS car_asset_created_at,
        rim_asset.id AS rim_asset_id,
        rim_asset.kind AS rim_asset_kind,
        rim_asset.bucket AS rim_asset_bucket,
        rim_asset.storage_key AS rim_asset_storage_key,
        rim_asset.content_type AS rim_asset_content_type,
        rim_asset.size_bytes AS rim_asset_size_bytes,
        rim_asset.width AS rim_asset_width,
        rim_asset.height AS rim_asset_height,
        rim_asset.created_at AS rim_asset_created_at,
        result_asset.id AS result_asset_id,
        result_asset.kind AS result_asset_kind,
        result_asset.bucket AS result_asset_bucket,
        result_asset.storage_key AS result_asset_storage_key,
        result_asset.content_type AS result_asset_content_type,
        result_asset.size_bytes AS result_asset_size_bytes,
        result_asset.width AS result_asset_width,
        result_asset.height AS result_asset_height,
        result_asset.created_at AS result_asset_created_at
    """


def _job_assets_join_clause() -> str:
    return """
        LEFT JOIN assets AS car_asset ON car_asset.id = jobs.car_asset_id
        LEFT JOIN assets AS rim_asset ON rim_asset.id = jobs.rim_asset_id
        LEFT JOIN assets AS result_asset ON result_asset.id = jobs.result_asset_id
    """


async def _compensate_queue_publish_failure(
    *,
    pool,
    user_id: int,
    job_id: str,
    error_message: str,
) -> None:
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await refund_job_credit(conn, user_id=user_id, job_id=job_id)
                await conn.execute(
                    "UPDATE jobs SET status = 'failed', error_code = $1, error_message = $2, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = $3::uuid",
                    "QUEUE_PUBLISH_FAILED",
                    error_message,
                    job_id,
                )
    except Exception as exc:
        logger.exception(
            "❌ Queue publish compensation failed for job_id=%s user_id=%s: %s",
            job_id,
            user_id,
            exc,
        )


@router.post("", response_model=JobCreateResponse)
async def create_job(request: JobCreateRequest):
    """Создание задачи из бота — приходят Telegram file URL'ы."""
    rds = _get_render_queue_client("/jobs", request.telegram_user_id)
    await enforce_rate_limit(
        scope="jobs",
        identifier=request.telegram_user_id,
        limit=JOBS_RATE_LIMIT,
        window_sec=JOBS_RATE_WINDOW_SEC,
    )

    logger.info(
        f"📥 Получен запрос на создание задачи. Авто: {request.car_url}, Диск: {request.wheel_url}"
    )
    job_id = str(uuid.uuid4())
    pool = db.get_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                user_id = await ensure_user(conn, request.telegram_user_id, request.username)
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
                await reserve_job_credit(conn, user_id=user_id, job_id=job_id)
            logger.info(f"✅ Задача {job_id} успешно записана в БД со статусом queued")
    except InsufficientCreditsError as exc:
        logger.warning(
            f"❌ Недостаточно credits для telegram_user_id={request.telegram_user_id}: {exc}"
        )
        raise HTTPException(status_code=402, detail="Insufficient credits") from exc

    except Exception as db_err:
        logger.exception(
            f"❌ ОШИБКА ЗАПИСИ В БД (INSERT) для "
            f"telegram_user_id={request.telegram_user_id}: {db_err}"
        )
        raise HTTPException(status_code=500, detail="Database insert failed") from db_err

    try:
        await rds.rpush(
            redis_client.key(REDIS_JOB_QUEUE),
            json.dumps(
                {
                    "job_id": job_id,
                    "user_id": user_id,
                    "telegram_user_id": request.telegram_user_id,
                    "car_url": request.car_url,
                    "wheel_url": request.wheel_url,
                }
            ),
        )
    except Exception as queue_err:
        logger.exception(
            "❌ Queue publish failed for job_id=%s user_id=%s telegram_user_id=%s: %s",
            job_id,
            user_id,
            request.telegram_user_id,
            queue_err,
        )
        await _compensate_queue_publish_failure(
            pool=pool,
            user_id=user_id,
            job_id=job_id,
            error_message="Queue publish failed",
        )
        raise HTTPException(
            status_code=503, detail="Job queue is temporarily unavailable"
        ) from queue_err
    return JobCreateResponse(job_id=job_id, status="queued")


@router.post("/upload", response_model=JobCreateResponse)
async def upload_job(
    car_image: Annotated[UploadFile, File()],
    wheel_image: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Form()],
    init_data: Annotated[str, Form()] = "",
    telegram_user_id: Annotated[int | None, Form()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    """Создание задачи из webapp — приходят бинарники car/wheel + Telegram initData.

    Flow:
    1. Валидируем initData (HMAC) → достаём telegram_user_id.
    2. Rate limit (10/час на юзера).
    3. Идемпотентность: если ключ уже видели — возвращаем тот же job_id.
    4. Льём оба файла в Storage `raw`.
    5. Создаём job в БД, кидаем в Redis-очередь воркеру.
    """
    auth = resolve_telegram_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        auth_name="jobs upload",
    )

    rds = _get_render_queue_client("/jobs/upload", auth.telegram_user_id)
    await enforce_rate_limit(
        scope="jobs_upload",
        identifier=auth.telegram_user_id,
        limit=UPLOAD_RATE_LIMIT,
        window_sec=UPLOAD_RATE_WINDOW_SEC,
    )

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

    idem_redis_key = redis_client.key(f"idem:jobs_upload:{auth.telegram_user_id}:{idempotency_key}")
    job_id = str(uuid.uuid4())
    reserved = await rds.set(idem_redis_key, job_id, ex=IDEMPOTENCY_TTL_SEC, nx=True)
    if not reserved:
        existing_job_id = await rds.get(idem_redis_key)
        if not existing_job_id:
            raise HTTPException(status_code=409, detail="Upload retry in progress")
        logger.info(
            f"♻️  Idempotent replay: tg_user={auth.telegram_user_id} "
            f"key={idempotency_key} → job={existing_job_id}"
        )
        return JobCreateResponse(job_id=existing_job_id, status="queued")

    logger.info(
        f"📥 /jobs/upload tg_user={auth.telegram_user_id} job={job_id} "
        f"car={len(car_bytes)}B wheel={len(wheel_bytes)}B"
    )

    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)

    uploaded_assets: list[assets_service.AssetUpload] = []
    try:
        car_asset = await assets_service.upload_render_asset(
            owner_user_id=user_id,
            job_id=job_id,
            kind="car_original",
            data=car_bytes,
            content_type=car_image.content_type or "application/octet-stream",
        )
        uploaded_assets.append(car_asset)
        rim_asset = await assets_service.upload_render_asset(
            owner_user_id=user_id,
            job_id=job_id,
            kind="rim_original",
            data=wheel_bytes,
            content_type=wheel_image.content_type or "application/octet-stream",
        )
        uploaded_assets.append(rim_asset)
    except storage.StorageError as exc:
        await rds.delete(idem_redis_key)
        for uploaded_asset in uploaded_assets:
            try:
                await assets_service.delete_uploaded_asset(uploaded_asset)
            except storage.StorageError as cleanup_exc:
                logger.exception(
                    "❌ Storage cleanup failed для job_id=%s asset_id=%s: %s",
                    job_id,
                    uploaded_asset.id,
                    cleanup_exc,
                )
        logger.exception(f"❌ Storage upload failed для job_id={job_id}: {exc}")
        raise HTTPException(status_code=502, detail="Storage upload failed") from exc

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await assets_service.insert_asset(conn, car_asset)
                await assets_service.insert_asset(conn, rim_asset)
                await conn.execute(
                    """
                    INSERT INTO jobs (
                        id, user_id, status, car_image_url, wheel_image_url,
                        car_asset_id, rim_asset_id
                    )
                    VALUES ($1::uuid, $2, 'queued', $3, $4, $5::uuid, $6::uuid)
                    """,
                    job_id,
                    user_id,
                    car_asset.storage_key,
                    rim_asset.storage_key,
                    car_asset.id,
                    rim_asset.id,
                )
                await reserve_job_credit(conn, user_id=user_id, job_id=job_id)
        logger.info(f"✅ Job {job_id} создан в БД (queued)")
    except InsufficientCreditsError as exc:
        await rds.delete(idem_redis_key)
        for uploaded_asset in uploaded_assets:
            try:
                await assets_service.delete_uploaded_asset(uploaded_asset)
            except storage.StorageError as cleanup_exc:
                logger.exception(
                    "❌ Storage cleanup failed для job_id=%s asset_id=%s: %s",
                    job_id,
                    uploaded_asset.id,
                    cleanup_exc,
                )
        logger.warning(f"❌ Недостаточно credits для tg_user={auth.telegram_user_id}: {exc}")
        raise HTTPException(status_code=402, detail="Insufficient credits") from exc
    except Exception as db_err:
        await rds.delete(idem_redis_key)
        for uploaded_asset in uploaded_assets:
            try:
                await assets_service.delete_uploaded_asset(uploaded_asset)
            except storage.StorageError as cleanup_exc:
                logger.exception(
                    "❌ Storage cleanup failed для job_id=%s asset_id=%s: %s",
                    job_id,
                    uploaded_asset.id,
                    cleanup_exc,
                )
        logger.exception(f"❌ DB INSERT failed для job_id={job_id}: {db_err}")
        raise HTTPException(status_code=500, detail="Database insert failed") from db_err

    try:
        await rds.rpush(
            redis_client.key(REDIS_JOB_QUEUE),
            json.dumps(
                {
                    "job_id": job_id,
                    "user_id": user_id,
                    "telegram_user_id": auth.telegram_user_id,
                    "source": "webapp",
                    "car_storage_path": car_asset.storage_key,
                    "wheel_storage_path": rim_asset.storage_key,
                    "car_asset_id": car_asset.id,
                    "rim_asset_id": rim_asset.id,
                }
            ),
        )
    except Exception as queue_err:
        logger.exception(
            "❌ Queue publish failed for job_id=%s user_id=%s telegram_user_id=%s: %s",
            job_id,
            user_id,
            auth.telegram_user_id,
            queue_err,
        )
        await _compensate_queue_publish_failure(
            pool=pool,
            user_id=user_id,
            job_id=job_id,
            error_message="Queue publish failed",
        )
        await rds.delete(idem_redis_key)
        raise HTTPException(
            status_code=503, detail="Job queue is temporarily unavailable"
        ) from queue_err

    return JobCreateResponse(job_id=job_id, status="queued")


@router.get("", response_model=JobHistoryResponse)
async def list_jobs(
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """История последних jobs текущего авторизованного пользователя."""
    auth = _resolve_jobs_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        required=True,
    )
    assert auth is not None

    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
        rows = await conn.fetch(
            f"""
            SELECT
                jobs.id::text AS job_id,
                jobs.status,
                jobs.created_at,
                jobs.completed_at,
                jobs.output_image_url,
                jobs.error_code,
                jobs.error_message,
                jobs.generation_provider,
                jobs.provider_request_id,
                {_job_assets_select_clause()}
            FROM jobs
            {_job_assets_join_clause()}
            WHERE jobs.user_id = $1
            ORDER BY jobs.created_at DESC, jobs.id DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )

    history = [
        JobHistoryItem(
            job_id=row["job_id"],
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            result_url=row["output_image_url"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            generation_provider=row["generation_provider"],
            provider_request_id=row["provider_request_id"],
            assets=_assets_from_row(row, job_id=row["job_id"]),
        )
        for row in rows
    ]
    return JobHistoryResponse(jobs=history, limit=limit, offset=offset)


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    """Polling статуса задачи.

    Без auth возвращает legacy contract для бота. С auth проверяет владельца
    и добавляет durable asset metadata.
    """
    auth = _resolve_jobs_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        required=False,
    )
    pool = db.get_pool()
    async with pool.acquire() as conn:
        if auth is None:
            row = await conn.fetchrow(
                "SELECT status, output_image_url FROM jobs WHERE id = $1::uuid",
                job_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
            return {"status": row["status"], "output_image_url": row["output_image_url"]}

        user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
        row = await conn.fetchrow(
            f"""
            SELECT
                jobs.id::text AS job_id,
                jobs.status,
                jobs.created_at,
                jobs.completed_at,
                jobs.output_image_url,
                jobs.error_code,
                jobs.error_message,
                {_job_assets_select_clause()}
            FROM jobs
            {_job_assets_join_clause()}
            WHERE jobs.id = $1::uuid
              AND jobs.user_id = $2
            """,
            job_id,
            user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=row["job_id"],
        status=row["status"],
        output_image_url=row["output_image_url"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        assets=_assets_from_row(row, job_id=row["job_id"]),
    ).model_dump(mode="json", exclude_none=True)


@router.get("/{job_id}/status")
async def get_job_status_detailed(
    job_id: str,
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    """Расширенный статус для webapp polling: status + result_url + error."""
    auth = _resolve_jobs_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        required=False,
    )
    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_id = None
        if auth is not None:
            user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
        row = await conn.fetchrow(
            f"""
            SELECT
                jobs.id::text AS job_id,
                jobs.status,
                jobs.output_image_url,
                jobs.error_code,
                jobs.error_message,
                {_job_assets_select_clause()}
            FROM jobs
            {_job_assets_join_clause()}
            WHERE jobs.id = $1::uuid
              AND ($2::integer IS NULL OR jobs.user_id = $2)
            """,
            job_id,
            user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if auth is None:
        return {
            "job_id": job_id,
            "status": row["status"],
            "result_url": row["output_image_url"],
            "share_url": share_url_for_job(job_id, bust_preview_cache=True)
            if row["output_image_url"]
            else None,
            "error": row["error_message"],
        }
    return JobStatusDetailedResponse(
        job_id=job_id,
        status=row["status"],
        result_url=row["output_image_url"],
        share_url=share_url_for_job(job_id, bust_preview_cache=True)
        if row["output_image_url"]
        else None,
        error=row["error_message"],
        error_code=row["error_code"],
        assets=_assets_from_row(row, job_id=row["job_id"]) if auth is not None else None,
    ).model_dump(mode="json", exclude_none=True)


@router.get("/{job_id}/assets/{kind}/download")
async def download_job_asset(
    job_id: str,
    kind: AssetKind,
    init_data: Annotated[str | None, Query()] = None,
    telegram_user_id: Annotated[int | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
):
    """Proxy download for an authorized user's durable job asset."""
    auth = _resolve_jobs_auth(
        init_data=init_data,
        telegram_user_id=telegram_user_id,
        authorization=authorization,
        required=True,
    )
    assert auth is not None

    pool = db.get_pool()
    async with pool.acquire() as conn:
        user_id = await ensure_user(conn, auth.telegram_user_id, auth.username)
        row = await conn.fetchrow(
            """
            SELECT assets.bucket, assets.storage_key, assets.content_type
            FROM jobs
            JOIN assets
              ON assets.job_id = jobs.id
             AND assets.owner_user_id = jobs.user_id
            WHERE jobs.id = $1::uuid
              AND jobs.user_id = $2
              AND assets.kind = $3
            """,
            job_id,
            user_id,
            kind,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        content = await storage.download_bytes(bucket=row["bucket"], path=row["storage_key"])
    except storage.StorageError as exc:
        logger.exception(
            "❌ Asset download failed для job_id=%s user_id=%s kind=%s: %s",
            job_id,
            user_id,
            kind,
            exc,
        )
        raise HTTPException(status_code=502, detail="Asset fetch failed") from exc

    return Response(
        content=content,
        media_type=row["content_type"] or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/{job_id}/feedback", status_code=204)
async def submit_feedback(
    job_id: str,
    request: FeedbackRequest,
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
):
    """Сохранить лайк/дизлайк на результат. Повторный вызов перезаписывает.

    WebApp подтверждает владельца через Telegram initData. Бот ходит как
    trusted backend client с X-Internal-Token и telegram_user_id из callback.
    """
    telegram_user_id = _telegram_user_id_from_feedback_request(request, x_internal_token)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE jobs
            SET feedback = $1
            FROM users
            WHERE jobs.id = $2::uuid
              AND jobs.user_id = users.id
              AND users.telegram_user_id = $3
            """,
            request.vote,
            job_id,
            telegram_user_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"👍 Feedback '{request.vote}' для job_id={job_id} tg_user={telegram_user_id}")


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
