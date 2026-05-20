from pathlib import Path

from PIL import Image

from src.fal_inpaint import (
    RUN_CONFIGS,
    build_arguments,
    build_prompt,
    estimate_cost_usd,
    first_image_url,
)


def test_estimate_cost_uses_conservative_model_price(tmp_path: Path):
    image_path = tmp_path / "car.png"
    Image.new("RGB", (1000, 500), "white").save(image_path)

    assert estimate_cost_usd(image_path=image_path, config=RUN_CONFIGS["z-default"]) == 0.005
    assert estimate_cost_usd(image_path=image_path, config=RUN_CONFIGS["flux-default"]) == 0.0175
    assert (
        estimate_cost_usd(image_path=image_path, config=RUN_CONFIGS["reve-remix-rim-mask"]) == 0.01
    )
    assert (
        estimate_cost_usd(image_path=image_path, config=RUN_CONFIGS["gemini-3-pro-rim-mask"])
        == 0.15
    )


def test_build_flux_arguments_include_reference_and_mask():
    args = build_arguments(
        config=RUN_CONFIGS["flux-default"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url="https://example.com/rim.png",
        prompt="replace wheels",
        output_format="png",
    )

    assert args["image_url"] == "https://example.com/car.png"
    assert args["reference_image_url"] == "https://example.com/rim.png"
    assert args["mask_url"] == "https://example.com/mask.png"
    assert args["strength"] == 0.88
    assert args["guidance_scale"] == 2.5


def test_build_z_image_arguments_use_mask_image_url_without_reference():
    args = build_arguments(
        config=RUN_CONFIGS["z-default"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url=None,
        prompt="replace wheels",
        output_format="png",
    )

    assert args["image_url"] == "https://example.com/car.png"
    assert args["mask_image_url"] == "https://example.com/mask.png"
    assert "reference_image_url" not in args
    assert args["strength"] == 0.75
    assert args["control_scale"] == 0.75


def test_build_flux_lora_arguments_use_prompt_mask_and_image_size():
    args = build_arguments(
        config=RUN_CONFIGS["flux-dev-s085-g35"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url=None,
        prompt="replace wheels",
        output_format="png",
        image_size={"width": 1024, "height": 594},
    )

    assert args["image_url"] == "https://example.com/car.png"
    assert args["mask_url"] == "https://example.com/mask.png"
    assert args["image_size"] == {"width": 1024, "height": 594}
    assert "reference_image_url" not in args
    assert args["strength"] == 0.85
    assert args["guidance_scale"] == 3.5


def test_build_flux_general_reference_arguments_include_rim_reference():
    args = build_arguments(
        config=RUN_CONFIGS["flux-general-reference-rim"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url="https://example.com/rim.png",
        prompt="replace wheels",
        output_format="png",
        image_size={"width": 1024, "height": 594},
    )

    assert args["image_url"] == "https://example.com/car.png"
    assert args["mask_url"] == "https://example.com/mask.png"
    assert args["reference_image_url"] == "https://example.com/rim.png"
    assert args["reference_strength"] == 0.65
    assert args["reference_end"] == 0.8
    assert args["strength"] == 0.8


def test_build_qwen_image_edit_arguments_use_mask_url():
    args = build_arguments(
        config=RUN_CONFIGS["qwen-edit-default"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url=None,
        prompt="replace wheels",
        output_format="png",
    )

    assert args["image_url"] == "https://example.com/car.png"
    assert args["mask_url"] == "https://example.com/mask.png"
    assert "reference_image_url" not in args
    assert args["strength"] == 0.75
    assert args["guidance_scale"] == 3.5


def test_build_reve_remix_arguments_use_car_reference_and_mask_urls():
    args = build_arguments(
        config=RUN_CONFIGS["reve-remix-rim-mask"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url="https://example.com/rim.png",
        prompt="replace wheels",
        output_format="png",
    )

    assert args["image_urls"] == [
        "https://example.com/car.png",
        "https://example.com/rim.png",
        "https://example.com/mask.png",
    ]
    assert args["num_images"] == 1
    assert args["sync_mode"] is False


def test_build_gemini_edit_arguments_use_car_reference_and_mask_urls():
    args = build_arguments(
        config=RUN_CONFIGS["gemini-3-pro-rim-mask"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url="https://example.com/rim.png",
        prompt="replace wheels",
        output_format="png",
    )

    assert args["image_urls"] == [
        "https://example.com/car.png",
        "https://example.com/rim.png",
        "https://example.com/mask.png",
    ]
    assert args["aspect_ratio"] == "auto"
    assert args["resolution"] == "1K"
    assert args["limit_generations"] is True


def test_build_sdxl_arguments_include_base_model_name():
    args = build_arguments(
        config=RUN_CONFIGS["sdxl-default"],
        car_url="https://example.com/car.png",
        mask_url="https://example.com/mask.png",
        reference_url=None,
        prompt="replace wheels",
        output_format="png",
    )

    assert args["model_name"] == "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    assert args["image_url"] == "https://example.com/car.png"
    assert args["mask_url"] == "https://example.com/mask.png"
    assert args["guidance_scale"] == 7.5


def test_prompt_keeps_unmasked_pixels_explicit():
    prompt = build_prompt()

    assert "exact wheel design, color, finish" in prompt
    assert "Preserve original scene lighting" in prompt
    assert "unmasked pixels" in prompt
    assert "studio lighting" not in prompt.lower()


def test_first_image_url_supports_common_fal_shapes():
    assert (
        first_image_url({"images": [{"url": "https://example.com/out.png"}]})
        == "https://example.com/out.png"
    )
    assert (
        first_image_url({"image": {"url": "https://example.com/single.png"}})
        == "https://example.com/single.png"
    )
    assert first_image_url({"images": []}) is None
