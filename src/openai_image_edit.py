"""OpenAI image edit helpers for wheel replacement evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
DEFAULT_OPENAI_IMAGE_SIZE = "auto"
DEFAULT_OPENAI_IMAGE_QUALITY = "medium"
DEFAULT_OPENAI_OUTPUT_FORMAT = "png"


def build_openai_edit_prompt(*, wheel_description: str | None = None) -> str:
    """Build a conservative prompt for masked OpenAI wheel replacement edits."""

    wheel_fragment = wheel_description or "the reference wheel rim design"
    return (
        "Edit only the wheel rim areas indicated by the transparent parts of the mask. "
        f"Replace those visible wheel rims with {wheel_fragment}, using the second input "
        "image as the wheel design reference. Preserve the tires, wheel wells, car body, "
        "paint, windows, road, background, license plates, lighting, shadows, reflections, "
        "camera angle, and all unmasked pixels. The result must remain a photorealistic "
        "automotive photo. Keep black rim spokes readable in low light; do not turn the "
        "wheels into flat black disks."
    )


def make_openai_alpha_mask(*, binary_mask_path: Path, output_path: Path) -> Path:
    """Convert a white-edit binary mask to OpenAI's alpha-mask convention.

    OpenAI image edits use fully transparent areas as editable regions. The Stage
    2 wheel masks are white where wheels should be edited, so this helper makes
    those white pixels transparent and keeps the rest opaque.
    """

    source = Image.open(binary_mask_path).convert("L")
    alpha = source.point(lambda value: 0 if value >= 128 else 255)
    mask = Image.new("RGBA", source.size, (255, 255, 255, 255))
    mask.putalpha(alpha)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(output_path)
    return output_path


def first_b64_image(result: dict[str, Any]) -> str | None:
    """Extract the first base64 image payload from an OpenAI image response."""

    data = result.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("b64_json"), str):
            return first["b64_json"]
    return None


def response_without_b64(result: dict[str, Any]) -> dict[str, Any]:
    """Return response metadata without embedding large base64 image payloads."""

    sanitized = dict(result)
    data = sanitized.get("data")
    if isinstance(data, list):
        sanitized["data"] = [
            {key: value for key, value in item.items() if key != "b64_json"}
            if isinstance(item, dict)
            else item
            for item in data
        ]
    return sanitized
