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
    "Replace the existing wheels on the car shown in <img>0</img> with the "
    "provided alloy wheel design from <img>1</img>. Use the exact wheel design, "
    "color, finish, spoke pattern, center cap, and material from <img>1</img>. "
    "If any text description conflicts with the wheel reference image, the "
    "reference image wins. Match correct perspective, scale, and alignment with "
    "the car hub. Preserve original scene lighting, realistic reflections, and "
    "physically accurate shadows. Keep brake disc and wheel depth physically "
    "plausible. Match tire profile and maintain correct wheel size relative to "
    "the car. Do not alter car body, car color, background, windows, road, or "
    "license plates. {rim_fragment}"
    "Photorealistic, ultra detailed, automotive photography, high resolution, "
    "natural reflections."
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
    base = BASE_PROMPT_TEMPLATE.format(rim_fragment=f"{fragment} " if fragment else "")
    return f"{base} Avoid: {NEGATIVE_PROMPT}."
