"""Prepare a fal.ai evaluation manifest from Pascal VOC wheel boxes.

This is an offline/free manifest builder for the generation bake-off. It uses
the provided XML wheel boxes to create ellipse masks, resizes large source
images to a budget-friendly size, and writes a JSONL manifest accepted by
scripts/fal_inpaint_eval.py.

The masks are a proxy for the final Roboflow/YOLO + Qwen VLM masks. The output
format is the same, so later we can replace `mask_image` paths with real
Stage 2 masks without changing the fal.ai runner.
"""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

DEFAULT_OUTPUT_DIR = Path("tmp/fal-inpaint-eval/cases")
DEFAULT_MANIFEST = Path("tmp/fal-inpaint-eval/cases.jsonl")
DEFAULT_LIMIT = 50
DEFAULT_MAX_LONG_EDGE = 1360
WHEEL_CLASS = "wheel"


def _parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _wheel_boxes(xml_path: Path) -> list[tuple[float, float, float, float]]:
    tree = ET.parse(xml_path)
    boxes: list[tuple[float, float, float, float]] = []
    for obj in tree.findall(".//object"):
        name = (obj.findtext("name") or "").strip().lower()
        if name != WHEEL_CLASS:
            continue
        box = obj.find("bndbox")
        if box is None:
            continue
        xmin = _parse_float(box.findtext("xmin"))
        ymin = _parse_float(box.findtext("ymin"))
        xmax = _parse_float(box.findtext("xmax"))
        ymax = _parse_float(box.findtext("ymax"))
        if None in (xmin, ymin, xmax, ymax):
            continue
        if xmax <= xmin or ymax <= ymin:
            continue
        boxes.append((xmin, ymin, xmax, ymax))
    return boxes


def _image_for_xml(xml_path: Path) -> Path | None:
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = xml_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def _resize_size(size: tuple[int, int], max_long_edge: int) -> tuple[int, int]:
    width, height = size
    long_edge = max(width, height)
    if long_edge <= max_long_edge:
        return size
    scale = max_long_edge / long_edge
    return max(1, round(width * scale)), max(1, round(height * scale))


def _scale_box(
    box: tuple[float, float, float, float], *, scale_x: float, scale_y: float
) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = box
    return xmin * scale_x, ymin * scale_y, xmax * scale_x, ymax * scale_y


def _make_mask(
    *, image_size: tuple[int, int], boxes: list[tuple[float, float, float, float]], expand: float
) -> Image.Image:
    mask = Image.new("L", image_size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = image_size
    for xmin, ymin, xmax, ymax in boxes:
        box_w = xmax - xmin
        box_h = ymax - ymin
        pad_x = box_w * expand
        pad_y = box_h * expand
        left = max(0, xmin - pad_x)
        top = max(0, ymin - pad_y)
        right = min(width, xmax + pad_x)
        bottom = min(height, ymax + pad_y)
        if right <= left or bottom <= top:
            continue
        ellipse_box = (left, top, right, bottom)
        draw.ellipse(ellipse_box, fill=255)
    return mask


def _save_overlay(*, image: Image.Image, mask: Image.Image, output_path: Path) -> None:
    rgba = image.convert("RGBA")
    red = Image.new("RGBA", rgba.size, (255, 0, 0, 0))
    red.putalpha(mask.point(lambda value: 120 if value else 0))
    Image.alpha_composite(rgba, red).save(output_path)


def _select_cases(
    images_dir: Path, limit: int
) -> list[tuple[Path, Path, list[tuple[float, float, float, float]]]]:
    candidates: list[tuple[float, str, Path, Path, list[tuple[float, float, float, float]]]] = []
    for xml_path in sorted(images_dir.glob("*.xml")):
        image_path = _image_for_xml(xml_path)
        if not image_path:
            continue
        boxes = _wheel_boxes(xml_path)
        if not boxes:
            continue
        with Image.open(image_path) as image:
            width, height = image.size
        aspect = width / height if height else 0.0
        # Prefer ordinary car photos with 2-4 visible wheels and landscape-ish framing.
        wheel_count_penalty = abs(len(boxes) - 2)
        aspect_penalty = abs(math.log(max(aspect, 0.01) / 1.6))
        score = wheel_count_penalty + aspect_penalty
        candidates.append((score, image_path.name, image_path, xml_path, boxes))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [
        (image_path, xml_path, boxes)
        for _score, _name, image_path, xml_path, boxes in candidates[:limit]
    ]


def _write_contact_sheet(
    *,
    rows: list[dict[str, str]],
    output_path: Path,
    thumb_size: tuple[int, int] = (280, 180),
    columns: int = 5,
) -> None:
    if not rows:
        return
    thumbs: list[Image.Image] = []
    for row in rows:
        image = Image.open(row["overlay_image"]).convert("RGB")
        image = ImageOps.contain(image, thumb_size)
        canvas = Image.new("RGB", thumb_size, "white")
        canvas.paste(
            image, ((thumb_size[0] - image.width) // 2, (thumb_size[1] - image.height) // 2)
        )
        thumbs.append(canvas)
    sheet_rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * thumb_size[0], sheet_rows * thumb_size[1]), "white")
    for idx, thumb in enumerate(thumbs):
        x = (idx % columns) * thumb_size[0]
        y = (idx // columns) * thumb_size[1]
        sheet.paste(thumb, (x, y))
    sheet.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("images_dir", type=Path, help="Folder with .jpg/.xml pairs")
    parser.add_argument("reference_image", type=Path, help="Wheel reference image")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--max-long-edge", type=int, default=DEFAULT_MAX_LONG_EDGE)
    parser.add_argument("--mask-expand", type=float, default=0.08)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--wheel-description",
        default="the reference wheel rim design",
        help="Text hint included in fal.ai prompt",
    )
    args = parser.parse_args()

    if not args.images_dir.exists():
        raise SystemExit(f"Images dir not found: {args.images_dir}")
    if not args.reference_image.exists():
        raise SystemExit(f"Reference image not found: {args.reference_image}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cars_dir = args.output_dir / "cars"
    masks_dir = args.output_dir / "masks"
    overlays_dir = args.output_dir / "overlays"
    for path in (cars_dir, masks_dir, overlays_dir):
        path.mkdir(parents=True, exist_ok=True)

    selected = _select_cases(args.images_dir, args.limit)
    rows: list[dict[str, str]] = []
    for idx, (image_path, _xml_path, boxes) in enumerate(selected, start=1):
        case_id = f"wheel-labeling-{idx:03d}"
        image = Image.open(image_path).convert("RGB")
        original_size = image.size
        resized_size = _resize_size(original_size, args.max_long_edge)
        if resized_size != original_size:
            image = image.resize(resized_size, Image.LANCZOS)

        scale_x = resized_size[0] / original_size[0]
        scale_y = resized_size[1] / original_size[1]
        scaled_boxes = [_scale_box(box, scale_x=scale_x, scale_y=scale_y) for box in boxes]
        mask = _make_mask(image_size=resized_size, boxes=scaled_boxes, expand=args.mask_expand)

        car_out = cars_dir / f"{case_id}.jpg"
        mask_out = masks_dir / f"{case_id}.mask.png"
        overlay_out = overlays_dir / f"{case_id}.overlay.png"
        image.save(car_out, quality=92)
        mask.save(mask_out)
        _save_overlay(image=image, mask=mask, output_path=overlay_out)

        rows.append(
            {
                "id": case_id,
                "car_image": str(car_out.resolve()),
                "mask_image": str(mask_out.resolve()),
                "reference_image": str(args.reference_image.resolve()),
                "wheel_description": args.wheel_description,
                "source_image": str(image_path),
                "overlay_image": str(overlay_out.resolve()),
            }
        )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8") as handle:
        for row in rows:
            manifest_row = {
                "id": row["id"],
                "car_image": row["car_image"],
                "mask_image": row["mask_image"],
                "reference_image": row["reference_image"],
                "wheel_description": row["wheel_description"],
            }
            handle.write(json.dumps(manifest_row, ensure_ascii=False) + "\n")

    metadata_path = args.output_dir / "cases_metadata.json"
    metadata_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    contact_sheet_path = args.output_dir / "contact_sheet.jpg"
    _write_contact_sheet(rows=rows, output_path=contact_sheet_path)

    print(f"cases: {len(rows)}")
    print(f"manifest: {args.manifest}")
    print(f"metadata: {metadata_path}")
    print(f"contact_sheet: {contact_sheet_path}")
    print(f"reference_image: {args.reference_image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
