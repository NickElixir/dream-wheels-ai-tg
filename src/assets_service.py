"""Durable render asset persistence helpers."""

import hashlib
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import asyncpg

from src import storage

AssetKind = Literal["car_original", "rim_original", "result"]

RAW_ASSET_KINDS: set[AssetKind] = {"car_original", "rim_original"}
ALL_ASSET_KINDS: set[AssetKind] = {"car_original", "rim_original", "result"}


@dataclass(frozen=True, slots=True)
class AssetUpload:
    id: str
    owner_user_id: int
    job_id: str
    kind: AssetKind
    bucket: str
    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str
    public_url: str | None = None


def _ext_for_content_type(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(content_type.split(";")[0].strip().lower(), "bin")


def build_storage_key(
    *,
    owner_user_id: int,
    job_id: str,
    kind: AssetKind,
    asset_id: str,
    content_type: str,
) -> str:
    ext = _ext_for_content_type(content_type)
    return f"users/{owner_user_id}/jobs/{job_id}/{kind}/{asset_id}.{ext}"


async def upload_render_asset(
    *,
    owner_user_id: int,
    job_id: str,
    kind: AssetKind,
    data: bytes,
    content_type: str,
) -> AssetUpload:
    if kind not in ALL_ASSET_KINDS:
        raise ValueError(f"Unsupported asset kind: {kind}")

    asset_id = str(uuid4())
    bucket = storage.RAW_BUCKET if kind in RAW_ASSET_KINDS else storage.RESULTS_BUCKET
    storage_key = build_storage_key(
        owner_user_id=owner_user_id,
        job_id=job_id,
        kind=kind,
        asset_id=asset_id,
        content_type=content_type,
    )
    await storage.upload_bytes(
        bucket=bucket,
        path=storage_key,
        data=data,
        content_type=content_type,
    )
    public_url = (
        storage.public_url(bucket, storage_key) if bucket == storage.RESULTS_BUCKET else None
    )
    return AssetUpload(
        id=asset_id,
        owner_user_id=owner_user_id,
        job_id=job_id,
        kind=kind,
        bucket=bucket,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        public_url=public_url,
    )


async def insert_asset(conn: asyncpg.Connection, asset: AssetUpload) -> None:
    await conn.execute(
        """
        INSERT INTO assets (
            id, owner_user_id, job_id, kind, bucket, storage_key,
            content_type, size_bytes, sha256
        )
        VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO NOTHING
        """,
        asset.id,
        asset.owner_user_id,
        asset.job_id,
        asset.kind,
        asset.bucket,
        asset.storage_key,
        asset.content_type,
        asset.size_bytes,
        asset.sha256,
    )


async def delete_uploaded_asset(asset: AssetUpload) -> None:
    await storage.delete_object(bucket=asset.bucket, path=asset.storage_key)


def asset_download_path(job_id: str, kind: AssetKind) -> str:
    return f"/jobs/{job_id}/assets/{kind}/download"
