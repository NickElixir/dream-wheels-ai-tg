"""Обёртка над Supabase Storage REST API через httpx.

Backend использует service_role key — он обходит RLS и пишет в любой
bucket. Webapp/бот напрямую к Storage не ходят.

Buckets:
- `raw`     — private, исходники car/wheel (10 MB лимит)
- `results` — public,  AI-рендеры (5 MB лимит)

Документация: https://supabase.com/docs/reference/api/storage
"""

import logging
from uuid import uuid4

import httpx

from src.config import (
    SUPABASE_PROJECT_REF,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_STORAGE_URL,
)

logger = logging.getLogger(__name__)

RAW_BUCKET = "raw"
RESULTS_BUCKET = "results"

# Префиксы путей внутри bucket'ов — на случай будущей сегментации
# (например, отдельная папка под кастдев-юзеров vs prod).
DEFAULT_RAW_PREFIX = ""
DEFAULT_RESULTS_PREFIX = ""


class StorageError(Exception):
    """Любая ошибка обращения к Supabase Storage."""


def _auth_headers() -> dict[str, str]:
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise StorageError("SUPABASE_SERVICE_ROLE_KEY не сконфигурирован")
    return {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        # Supabase требует apikey-заголовок дублировать для Storage API.
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }


def _ext_for_content_type(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(content_type.lower(), "bin")


def public_url(bucket: str, path: str) -> str:
    """Прямой URL для public bucket (без auth, отдаётся CDN)."""
    return f"{SUPABASE_STORAGE_URL}/object/public/{bucket}/{path}"


async def upload_bytes(
    *,
    bucket: str,
    path: str,
    data: bytes,
    content_type: str,
    upsert: bool = False,
) -> None:
    """Загружает bytes в указанный bucket по указанному пути.

    upsert=True — перезаписать если файл уже есть. По дефолту падаем при
    конфликте (помогает ловить баги дублирования job_id).
    """
    url = f"{SUPABASE_STORAGE_URL}/object/{bucket}/{path}"
    headers = _auth_headers() | {
        "Content-Type": content_type,
        "x-upsert": "true" if upsert else "false",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, content=data, headers=headers)
    if resp.status_code >= 400:
        logger.error(
            f"❌ Storage upload failed: bucket={bucket} path={path} "
            f"status={resp.status_code} body={resp.text[:200]}"
        )
        raise StorageError(f"Upload to {bucket}/{path} failed: HTTP {resp.status_code}")
    logger.info(f"📤 Загружено в Storage: {bucket}/{path} ({len(data)} bytes)")


async def download_bytes(*, bucket: str, path: str) -> bytes:
    """Скачивает файл (для private bucket — нужен service_role)."""
    url = f"{SUPABASE_STORAGE_URL}/object/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers())
    if resp.status_code >= 400:
        raise StorageError(f"Download from {bucket}/{path} failed: HTTP {resp.status_code}")
    return resp.content


async def delete_object(*, bucket: str, path: str) -> None:
    """Удаляет объект. 404 не считается ошибкой (идемпотентность)."""
    url = f"{SUPABASE_STORAGE_URL}/object/{bucket}/{path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.delete(url, headers=_auth_headers())
    if resp.status_code == 404:
        return
    if resp.status_code >= 400:
        raise StorageError(f"Delete {bucket}/{path} failed: HTTP {resp.status_code}")
    logger.info(f"🗑️  Удалён из Storage: {bucket}/{path}")


async def upload_raw_image(
    *,
    job_id: str,
    kind: str,
    data: bytes,
    content_type: str,
) -> tuple[str, str]:
    """Загружает исходник (car/wheel) в raw-bucket.

    Returns: (path внутри bucket, полный URL для backend-загрузки).
    """
    if kind not in ("car", "wheel"):
        raise ValueError(f"kind должен быть 'car' или 'wheel', получено: {kind}")
    ext = _ext_for_content_type(content_type)
    path = f"{job_id}/{kind}.{ext}"
    await upload_bytes(bucket=RAW_BUCKET, path=path, data=data, content_type=content_type)
    # raw — private, прямой URL без auth не работает. Возвращаем для удобства,
    # но воркер должен скачивать через download_bytes(), не через httpx.get().
    return path, f"{SUPABASE_STORAGE_URL}/object/{RAW_BUCKET}/{path}"


async def upload_result_image(
    *,
    job_id: str,
    data: bytes,
    content_type: str = "image/jpeg",
) -> str:
    """Загружает финальный AI-рендер в results-bucket. Возвращает public URL."""
    ext = _ext_for_content_type(content_type)
    # uuid4 в имени — на случай если ретраим job_id и не хотим коллизий с
    # предыдущей попыткой; всё равно DB хранит актуальный URL.
    path = f"{job_id}/render-{uuid4().hex[:8]}.{ext}"
    await upload_bytes(bucket=RESULTS_BUCKET, path=path, data=data, content_type=content_type)
    return public_url(RESULTS_BUCKET, path)


__all__ = [
    "DEFAULT_RAW_PREFIX",
    "DEFAULT_RESULTS_PREFIX",
    "RAW_BUCKET",
    "RESULTS_BUCKET",
    "SUPABASE_PROJECT_REF",
    "StorageError",
    "delete_object",
    "download_bytes",
    "public_url",
    "upload_bytes",
    "upload_raw_image",
    "upload_result_image",
]
