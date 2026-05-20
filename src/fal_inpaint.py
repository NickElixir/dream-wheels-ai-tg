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
    "gemini-3-pro-image-edit",
    "qwen-image-edit",
    "reve-remix",
    "sdxl-inpaint",
    "z-image",
]


@dataclass(frozen=True)
class FalModelSpec:
    """Static endpoint metadata used for budget estimates and request building."""

    model_id: FalModelId
    endpoint: str
    price_per_megapixel_usd: float | None
    price_per_image_usd: float | None
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
        price_per_image_usd=None,
        supports_reference_image=True,
    ),
    "z-image": FalModelSpec(
        model_id="z-image",
        endpoint="fal-ai/z-image/turbo/inpaint",
        # fal pages currently show both $0.005/MP and $0.01/MP. Use the
        # conservative value so the budget guard errs on the expensive side.
        price_per_megapixel_usd=0.01,
        price_per_image_usd=None,
        supports_reference_image=False,
    ),
    "flux-lora": FalModelSpec(
        model_id="flux-lora",
        endpoint="fal-ai/flux-lora/inpainting",
        price_per_megapixel_usd=0.035,
        price_per_image_usd=None,
        supports_reference_image=False,
    ),
    "flux-general": FalModelSpec(
        model_id="flux-general",
        endpoint="fal-ai/flux-general/inpainting",
        price_per_megapixel_usd=0.035,
        price_per_image_usd=None,
        supports_reference_image=False,
    ),
    "gemini-3-pro-image-edit": FalModelSpec(
        model_id="gemini-3-pro-image-edit",
        endpoint="fal-ai/gemini-3-pro-image-preview/edit",
        price_per_megapixel_usd=None,
        price_per_image_usd=0.15,
        supports_reference_image=True,
    ),
    "qwen-image-edit": FalModelSpec(
        model_id="qwen-image-edit",
        endpoint="fal-ai/qwen-image-edit/inpaint",
        price_per_megapixel_usd=0.03,
        price_per_image_usd=None,
        supports_reference_image=False,
    ),
    "reve-remix": FalModelSpec(
        model_id="reve-remix",
        endpoint="fal-ai/reve/fast/remix",
        price_per_megapixel_usd=None,
        price_per_image_usd=0.01,
        supports_reference_image=True,
    ),
    "sdxl-inpaint": FalModelSpec(
        model_id="sdxl-inpaint",
        endpoint="fal-ai/inpaint",
        # Conservative local planning estimate for the generic SDXL inpaint endpoint.
        price_per_megapixel_usd=0.02,
        price_per_image_usd=None,
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
    "reve-remix-rim-mask": FalRunConfig(
        name="reve-remix-rim-mask",
        model_id="reve-remix",
        strength=0.0,
    ),
    "gemini-3-pro-rim-mask": FalRunConfig(
        name="gemini-3-pro-rim-mask",
        model_id="gemini-3-pro-image-edit",
        strength=0.0,
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
DEFAULT_FRONTIER_EDIT_CONFIGS = (
    "flux-s085-g25",
    "qwen-edit-default",
    "reve-remix-rim-mask",
    "gemini-3-pro-rim-mask",
)


def image_megapixels(path: Path) -> float:
    """Return image size in megapixels."""

    with Image.open(path) as image:
        width, height = image.size
    return (width * height) / 1_000_000


def estimate_cost_usd(*, image_path: Path, config: FalRunConfig) -> float:
    """Estimate fal.ai generation cost for one request."""

    spec = MODEL_SPECS[config.model_id]
    if spec.price_per_image_usd is not None:
        return spec.price_per_image_usd
    if spec.price_per_megapixel_usd is None:
        raise ValueError(f"No price estimate configured for {config.model_id}")
    return image_megapixels(image_path) * spec.price_per_megapixel_usd


def build_prompt(*, wheel_description: str | None = None) -> str:
    """Build a conservative masked wheel replacement prompt."""

    wheel_fragment = (
        wheel_description
        or "the exact wheel design, color, finish, spoke pattern, center cap, and material "
        "from the reference image"
    )
    return (
        "Replace the existing wheels on the car with the provided alloy wheel design. "
        f"Use {wheel_fragment}. Replace only the visible wheel/rim areas inside the "
        "white mask. Match correct perspective, scale, and alignment with the car hub. "
        "Preserve original scene lighting, realistic reflections, and physically accurate "
        "shadows. Keep brake disc and wheel depth physically plausible. Match tire profile "
        "and maintain correct wheel size relative to the car. Do not alter car body, car "
        "color, background, license plates, windows, road, tires, or any unmasked pixels. "
        "Photorealistic, ultra detailed, automotive photography, high resolution, natural "
        "reflections."
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

    if config.model_id == "reve-remix":
        if not reference_url:
            raise ValueError("reve-remix requires reference_url")
        return {
            "prompt": prompt,
            "image_urls": [car_url, reference_url, mask_url],
            "num_images": 1,
            "sync_mode": False,
        }

    if config.model_id == "gemini-3-pro-image-edit":
        if not reference_url:
            raise ValueError("gemini-3-pro-image-edit requires reference_url")
        return {
            "prompt": prompt,
            "image_urls": [car_url, reference_url, mask_url],
            "num_images": 1,
            "aspect_ratio": "auto",
            "output_format": output_format,
            "safety_tolerance": "4",
            "sync_mode": False,
            "resolution": "1K",
            "limit_generations": True,
            "enable_web_search": False,
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
