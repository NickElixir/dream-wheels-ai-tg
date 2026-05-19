"""fal.ai masked inpainting helpers for wheel replacement evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image

FalModelId = Literal[
    "flux-kontext",
    "flux-lora",
    "flux-general",
    "qwen-image-edit",
    "sdxl-inpaint",
    "z-image",
]


@dataclass(frozen=True)
class FalModelSpec:
    """Static endpoint metadata used for budget estimates and request building."""

    model_id: FalModelId
    endpoint: str
    price_per_megapixel_usd: float
    supports_reference_image: bool


@dataclass(frozen=True)
class FalRunConfig:
    """One concrete parameter set for a fal.ai inpainting request."""

    name: str
    model_id: FalModelId
    strength: float
    guidance_scale: float | None = None
    num_inference_steps: int | None = None
    acceleration: str = "regular"
    control_scale: float | None = None
    control_start: float | None = None
    control_end: float | None = None
    base_model_name: str | None = None
    uses_reference_image: bool = False
    reference_strength: float | None = None
    reference_end: float | None = None


MODEL_SPECS: dict[FalModelId, FalModelSpec] = {
    "flux-kontext": FalModelSpec(
        model_id="flux-kontext",
        endpoint="fal-ai/flux-kontext-lora/inpaint",
        price_per_megapixel_usd=0.035,
        supports_reference_image=True,
    ),
    "z-image": FalModelSpec(
        model_id="z-image",
        endpoint="fal-ai/z-image/turbo/inpaint",
        # fal pages currently show both $0.005/MP and $0.01/MP. Use the
        # conservative value so the budget guard errs on the expensive side.
        price_per_megapixel_usd=0.01,
        supports_reference_image=False,
    ),
    "flux-lora": FalModelSpec(
        model_id="flux-lora",
        endpoint="fal-ai/flux-lora/inpainting",
        price_per_megapixel_usd=0.035,
        supports_reference_image=False,
    ),
    "flux-general": FalModelSpec(
        model_id="flux-general",
        endpoint="fal-ai/flux-general/inpainting",
        price_per_megapixel_usd=0.035,
        supports_reference_image=False,
    ),
    "qwen-image-edit": FalModelSpec(
        model_id="qwen-image-edit",
        endpoint="fal-ai/qwen-image-edit/inpaint",
        price_per_megapixel_usd=0.03,
        supports_reference_image=False,
    ),
    "sdxl-inpaint": FalModelSpec(
        model_id="sdxl-inpaint",
        endpoint="fal-ai/inpaint",
        # Conservative local planning estimate for the generic SDXL inpaint endpoint.
        price_per_megapixel_usd=0.02,
        supports_reference_image=False,
    ),
}


RUN_CONFIGS: dict[str, FalRunConfig] = {
    "flux-default": FalRunConfig(
        name="flux-default",
        model_id="flux-kontext",
        strength=0.88,
        guidance_scale=2.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-s075-g25": FalRunConfig(
        name="flux-s075-g25",
        model_id="flux-kontext",
        strength=0.75,
        guidance_scale=2.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-s080-g25": FalRunConfig(
        name="flux-s080-g25",
        model_id="flux-kontext",
        strength=0.8,
        guidance_scale=2.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-s085-g25": FalRunConfig(
        name="flux-s085-g25",
        model_id="flux-kontext",
        strength=0.85,
        guidance_scale=2.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-s080-g35": FalRunConfig(
        name="flux-s080-g35",
        model_id="flux-kontext",
        strength=0.8,
        guidance_scale=3.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-s085-g35": FalRunConfig(
        name="flux-s085-g35",
        model_id="flux-kontext",
        strength=0.85,
        guidance_scale=3.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-guidance-45": FalRunConfig(
        name="flux-guidance-45",
        model_id="flux-kontext",
        strength=0.88,
        guidance_scale=4.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "flux-quality": FalRunConfig(
        name="flux-quality",
        model_id="flux-kontext",
        strength=0.9,
        guidance_scale=4.5,
        num_inference_steps=30,
        acceleration="none",
    ),
    "z-default": FalRunConfig(
        name="z-default",
        model_id="z-image",
        strength=0.75,
        num_inference_steps=8,
        acceleration="regular",
        control_scale=0.75,
        control_start=0.0,
        control_end=0.8,
    ),
    "z-strong": FalRunConfig(
        name="z-strong",
        model_id="z-image",
        strength=1.0,
        num_inference_steps=8,
        acceleration="regular",
        control_scale=0.9,
        control_start=0.0,
        control_end=1.0,
    ),
    "flux-dev-s085-g35": FalRunConfig(
        name="flux-dev-s085-g35",
        model_id="flux-lora",
        strength=0.85,
        guidance_scale=3.5,
        num_inference_steps=28,
        acceleration="regular",
    ),
    "flux-general-s085-g35": FalRunConfig(
        name="flux-general-s085-g35",
        model_id="flux-general",
        strength=0.85,
        guidance_scale=3.5,
        num_inference_steps=28,
        acceleration="regular",
    ),
    "flux-general-reference-rim": FalRunConfig(
        name="flux-general-reference-rim",
        model_id="flux-general",
        strength=0.8,
        guidance_scale=3.5,
        num_inference_steps=28,
        acceleration="regular",
        uses_reference_image=True,
        reference_strength=0.65,
        reference_end=0.8,
    ),
    "qwen-edit-default": FalRunConfig(
        name="qwen-edit-default",
        model_id="qwen-image-edit",
        strength=0.75,
        guidance_scale=3.5,
        num_inference_steps=30,
        acceleration="regular",
    ),
    "sdxl-default": FalRunConfig(
        name="sdxl-default",
        model_id="sdxl-inpaint",
        strength=0.0,
        guidance_scale=7.5,
        num_inference_steps=30,
        base_model_name="diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
    ),
}

DEFAULT_WIDE_CONFIGS = ("z-default", "flux-s085-g25")
DEFAULT_FLUX_SWEEP_CONFIGS = (
    "flux-s075-g25",
    "flux-s080-g25",
    "flux-s085-g25",
    "flux-s080-g35",
    "flux-default",
)
DEFAULT_TUNING_CONFIGS = (
    "z-default",
    "z-strong",
    "flux-default",
    "flux-guidance-45",
    "flux-quality",
)
DEFAULT_MODEL_CANDIDATE_CONFIGS = (
    "flux-s085-g25",
    "flux-dev-s085-g35",
    "flux-general-s085-g35",
    "z-default",
    "sdxl-default",
)
DEFAULT_NIGHT_FLUX_CONFIGS = (
    "flux-s075-g25",
    "flux-s080-g25",
    "flux-s085-g25",
    "flux-s080-g35",
    "flux-s085-g35",
)
DEFAULT_REFERENCE_CANDIDATE_CONFIGS = (
    "flux-s085-g25",
    "flux-s075-g25",
    "flux-general-reference-rim",
    "qwen-edit-default",
)


def image_megapixels(path: Path) -> float:
    """Return image size in megapixels."""

    with Image.open(path) as image:
        width, height = image.size
    return (width * height) / 1_000_000


def estimate_cost_usd(*, image_path: Path, config: FalRunConfig) -> float:
    """Estimate fal.ai generation cost for one request."""

    spec = MODEL_SPECS[config.model_id]
    return image_megapixels(image_path) * spec.price_per_megapixel_usd


def build_prompt(*, wheel_description: str | None = None) -> str:
    """Build a conservative masked wheel replacement prompt."""

    wheel_fragment = wheel_description or "the reference wheel rim design"
    return (
        "Replace only the visible wheel rims inside the white mask. "
        f"Use {wheel_fragment}. Match each wheel's perspective, scale, shadows, "
        "reflections, and lighting. Preserve tires, car body, paint, windows, road, "
        "background, license plates, and all unmasked pixels. Photorealistic automotive photo."
    )


def build_arguments(
    *,
    config: FalRunConfig,
    car_url: str,
    mask_url: str,
    reference_url: str | None,
    prompt: str,
    output_format: str,
    image_size: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build endpoint-specific fal.ai arguments."""

    if config.model_id == "flux-kontext":
        if not reference_url:
            raise ValueError("flux-kontext requires reference_url")
        return {
            "image_url": car_url,
            "reference_image_url": reference_url,
            "mask_url": mask_url,
            "prompt": prompt,
            "num_inference_steps": config.num_inference_steps,
            "guidance_scale": config.guidance_scale,
            "strength": config.strength,
            "num_images": 1,
            "output_format": output_format,
            "acceleration": config.acceleration,
            "enable_safety_checker": True,
        }

    if config.model_id in {"flux-lora", "flux-general"}:
        arguments: dict[str, Any] = {
            "image_url": car_url,
            "mask_url": mask_url,
            "prompt": prompt,
            "num_inference_steps": config.num_inference_steps,
            "guidance_scale": config.guidance_scale,
            "strength": config.strength,
            "num_images": 1,
            "output_format": output_format,
            "acceleration": config.acceleration,
            "enable_safety_checker": True,
        }
        if image_size:
            arguments["image_size"] = image_size
        if config.uses_reference_image:
            if not reference_url:
                raise ValueError(f"{config.name} requires reference_url")
            arguments["reference_image_url"] = reference_url
            arguments["reference_strength"] = config.reference_strength
            arguments["reference_end"] = config.reference_end
        return arguments

    if config.model_id == "qwen-image-edit":
        return {
            "image_url": car_url,
            "mask_url": mask_url,
            "prompt": prompt,
            "num_inference_steps": config.num_inference_steps,
            "guidance_scale": config.guidance_scale,
            "strength": config.strength,
            "num_images": 1,
            "output_format": output_format,
            "acceleration": config.acceleration,
            "enable_safety_checker": True,
        }

    if config.model_id == "z-image":
        return {
            "image_url": car_url,
            "mask_image_url": mask_url,
            "prompt": prompt,
            "image_size": "auto",
            "num_inference_steps": config.num_inference_steps,
            "strength": config.strength,
            "control_scale": config.control_scale,
            "control_start": config.control_start,
            "control_end": config.control_end,
            "sync_mode": False,
            "num_images": 1,
            "output_format": output_format,
            "acceleration": config.acceleration,
            "enable_prompt_expansion": False,
            "enable_safety_checker": True,
        }

    if config.model_id == "sdxl-inpaint":
        return {
            "model_name": config.base_model_name,
            "image_url": car_url,
            "mask_url": mask_url,
            "prompt": prompt,
            "negative_prompt": "cartoon, painting, illustration, low quality, blurry, distorted wheel",
            "num_inference_steps": config.num_inference_steps,
            "guidance_scale": config.guidance_scale,
        }

    raise ValueError(f"Unsupported fal model: {config.model_id}")


def first_image_url(result: dict[str, Any]) -> str | None:
    """Extract the first output image URL from common fal.ai response shapes."""

    images = result.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            return first["url"]

    image = result.get("image")
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]

    return None
