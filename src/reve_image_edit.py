"""Reve direct API helpers for wheel replacement evaluation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

DEFAULT_REVE_REMIX_URL = "https://api.reve.com/v1/image/remix"
DEFAULT_REVE_VERSION = "latest"
DEFAULT_REVE_ASPECT_RATIO = "16:9"


def build_reve_edit_prompt(*, wheel_description: str | None = None) -> str:
    """Build a conservative direct-Reve prompt using car, rim, and mask images."""

    wheel_fragment = (
        wheel_description
        or "the exact wheel design, color, finish, spoke pattern, center cap, and material "
        "from the reference image"
    )
    return (
        "Use <img>0</img> as the source car photo. Use <img>1</img> as the wheel rim "
        "design reference. Use <img>2</img> as a binary edit mask: white pixels mark "
        "the wheel/rim areas to replace and black pixels mark areas to preserve. "
        f"Replace only the visible wheel/rim areas with {wheel_fragment}. If any text "
        "description conflicts with the wheel reference image, the reference image wins. "
        "Match correct perspective, scale, and alignment with the car hub. Preserve "
        "original scene lighting, realistic reflections, and physically accurate shadows. "
        "Keep brake disc and wheel depth physically plausible. Match tire profile and "
        "maintain correct wheel size relative to the car. Do not alter car body, car color, "
        "background, windows, road, tires, license plates, camera angle, or unmasked pixels. "
        "Photorealistic, ultra detailed, automotive photography, high resolution, natural reflections. "
        "Avoid changed car shape, changed background, floating wheels, distorted tires, "
        "cartoon rendering, text, logos, or watermarks."
    )


def image_file_to_base64(path: Path) -> str:
    """Read an image file as base64 text without a data URI prefix."""

    return base64.b64encode(path.read_bytes()).decode("utf-8")


def first_reve_image_b64(result: dict[str, Any]) -> str | None:
    """Extract the generated image from known direct Reve response shapes."""

    image = result.get("image")
    if isinstance(image, str):
        return image.removeprefix("data:image/png;base64,").removeprefix("data:image/jpeg;base64,")

    data = result.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("b64_json"), str):
            return first["b64_json"]
        if isinstance(first, dict) and isinstance(first.get("image"), str):
            return first["image"]

    images = result.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict) and isinstance(first.get("b64_json"), str):
            return first["b64_json"]
    return None


def response_without_image(result: dict[str, Any]) -> dict[str, Any]:
    """Return Reve response metadata without embedding large base64 images."""

    sanitized = dict(result)
    if isinstance(sanitized.get("image"), str):
        sanitized["image"] = "<base64 omitted>"
    for key in ("data", "images"):
        value = sanitized.get(key)
        if isinstance(value, list):
            sanitized[key] = [
                {
                    item_key: "<base64 omitted>"
                    if item_key in {"b64_json", "image"} and isinstance(item_value, str)
                    else item_value
                    for item_key, item_value in item.items()
                }
                if isinstance(item, dict)
                else item
                for item in value
            ]
    return sanitized
