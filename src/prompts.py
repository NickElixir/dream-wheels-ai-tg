"""Промпт-билдер для Reve API.

Reve remix-эндпоинт принимает один `prompt`-стринг — отдельного
поля `negative_prompt` нет. Поэтому негативные элементы инлайнятся
в конец основного промпта секцией `Avoid: ...`. Если поле появится
в API — split тривиальный (BASE_PROMPT_TEMPLATE → prompt, NEGATIVE
→ negative_prompt).
"""

from __future__ import annotations

from src.rim import RimDescription

BASE_PROMPT_TEMPLATE = (
    "Professional automotive photography. Replace ONLY the wheels of the "
    "car shown in <img>0</img> with the wheels from <img>1</img>. "
    "Preserve the car body, paint, lighting, perspective and ground "
    "shadows of <img>0</img> exactly. The new wheels must sit correctly "
    "inside the wheel arches, with realistic contact patches and tyre "
    "shadows. {rim_fragment}"
    "High resolution, photorealistic, sharp focus on the wheels."
)

NEGATIVE_PROMPT = (
    "blurry, low resolution, distorted geometry, floating wheels, "
    "wrong wheel size, mismatched perspective, double wheels, deformed "
    "tyre, missing brake caliper, cartoon, illustration, oversaturated, "
    "watermark, text, logo overlay, changed car body, repainted car, "
    "altered background"
)


def build_prompt(rim: RimDescription | None = None) -> str:
    """Скомпоновать финальный промпт для `Reve /image/remix`.

    rim=None — используем дефолтный RimDescription (Stage 1 stub).
    Возвращает одну строку: base + rim-фрагмент + Avoid-секция.
    """
    rim = rim or RimDescription()
    fragment = rim.to_prompt_fragment()
    base = BASE_PROMPT_TEMPLATE.format(
        rim_fragment=f"{fragment} " if fragment else ""
    )
    return f"{base} Avoid: {NEGATIVE_PROMPT}."
