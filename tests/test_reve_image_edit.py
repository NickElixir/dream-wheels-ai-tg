import base64
from pathlib import Path

from src.reve_image_edit import (
    build_reve_edit_prompt,
    first_reve_image_b64,
    image_file_to_base64,
    response_without_image,
)


def test_build_reve_edit_prompt_references_car_rim_and_mask():
    prompt = build_reve_edit_prompt()

    assert "<img>0</img>" in prompt
    assert "<img>1</img>" in prompt
    assert "<img>2</img>" in prompt
    assert "white pixels mark" in prompt
    assert "exact wheel design, color, finish" in prompt
    assert "Preserve original scene lighting" in prompt
    assert "studio lighting" not in prompt.lower()


def test_image_file_to_base64_reads_file(tmp_path: Path):
    image_path = tmp_path / "sample.bin"
    image_path.write_bytes(b"abc")

    assert image_file_to_base64(image_path) == base64.b64encode(b"abc").decode("utf-8")


def test_first_reve_image_b64_supports_known_response_shapes():
    assert first_reve_image_b64({"image": "abc"}) == "abc"
    assert first_reve_image_b64({"image": "data:image/png;base64,abc"}) == "abc"
    assert first_reve_image_b64({"data": [{"b64_json": "def"}]}) == "def"
    assert first_reve_image_b64({"images": [{"b64_json": "ghi"}]}) == "ghi"
    assert first_reve_image_b64({}) is None


def test_response_without_image_omits_large_base64_payloads():
    sanitized = response_without_image(
        {"image": "abc", "data": [{"b64_json": "def", "request_id": "1"}]}
    )

    assert sanitized["image"] == "<base64 omitted>"
    assert sanitized["data"][0]["b64_json"] == "<base64 omitted>"
    assert sanitized["data"][0]["request_id"] == "1"
