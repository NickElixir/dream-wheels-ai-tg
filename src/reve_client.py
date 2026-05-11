"""Клиент Reve API (image remix endpoint)."""

import base64

import aiohttp

from src.config import REVE_API_KEY
from src.prompts import build_prompt
from src.rim import RimDescription

REVE_REMIX_URL = "https://api.reve.com/v1/image/remix"
REQUEST_TIMEOUT_SEC = 90


async def fetch_image_base64(url: str) -> str:
    """Скачать картинку и вернуть её в base64 без записи на диск."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ошибка скачивания файла: HTTP {resp.status}")
            img_bytes = await resp.read()
            return base64.b64encode(img_bytes).decode("utf-8")


async def remix_wheels_on_car(
    car_b64: str,
    wheel_b64: str,
    rim: RimDescription | None = None,
) -> bytes:
    """Подставить диски с одного фото на машину с другого. Вернуть raw-bytes картинки.

    rim=None → дефолтный RimDescription (см. src.rim). Stage 2 будет
    подсовывать сюда auto-extracted описание из фото диска.
    """
    payload = {
        "prompt": build_prompt(rim),
        "reference_images": [car_b64, wheel_b64],
        "aspect_ratio": "16:9",
        "version": "latest",
    }
    headers = {
        "Authorization": f"Bearer {REVE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(REVE_REMIX_URL, json=payload, headers=headers) as resp:
            res_json = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Reve Error: {res_json}")
            return base64.b64decode(res_json["image"])
