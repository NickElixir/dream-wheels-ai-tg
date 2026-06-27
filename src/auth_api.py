"""HTTP API для website Telegram auth поверх backend-issued bearer token."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src import db
from src.auth import (
    WebsiteAuthInvalid,
    build_website_login_nonce,
    issue_website_auth_token,
    verify_telegram_login_id_token,
)
from src.config import TELEGRAM_AUTH_TOKEN_TTL_SEC, TELEGRAM_LOGIN_CLIENT_ID
from src.users_service import ensure_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramLoginVerifyRequest(BaseModel):
    id_token: str
    nonce_token: str | None = None


class TelegramLoginVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    telegram_user_id: int
    username: str | None = None


class TelegramLoginNonceResponse(BaseModel):
    client_id: str
    nonce: str
    nonce_token: str


@router.get("/telegram/nonce", response_model=TelegramLoginNonceResponse)
async def telegram_login_nonce():
    if not TELEGRAM_LOGIN_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Telegram website login is not configured")
    return TelegramLoginNonceResponse(
        client_id=TELEGRAM_LOGIN_CLIENT_ID,
        **build_website_login_nonce(),
    )


@router.post("/telegram/verify-id-token", response_model=TelegramLoginVerifyResponse)
async def telegram_verify_id_token(request: TelegramLoginVerifyRequest):
    try:
        auth_context = await verify_telegram_login_id_token(
            id_token=request.id_token,
            nonce_token=request.nonce_token,
        )
    except WebsiteAuthInvalid as exc:
        logger.warning("⛔ website telegram auth failed reason=%s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await ensure_user(
                conn,
                telegram_user_id=auth_context.telegram_user_id,
                username=auth_context.username,
            )

    return TelegramLoginVerifyResponse(
        access_token=issue_website_auth_token(auth_context),
        expires_in=TELEGRAM_AUTH_TOKEN_TTL_SEC,
        telegram_user_id=auth_context.telegram_user_id,
        username=auth_context.username,
    )
