"""Budgeted OpenAI image edit evaluation runner.

This is a managed baseline for the same wheel replacement cases used by the
fal.ai inpainting runner. It sends the car image as the first input image, the
rim reference as the second input image, and an alpha mask where transparent
pixels mark the editable wheel areas.

Example dry run:
    .venv/bin/python scripts/openai_image_edit_eval.py cases.jsonl \
      --limit 6

Paid inference requires an explicit flag:
    OPENAI_API_KEY=... .venv/bin/python scripts/openai_image_edit_eval.py cases.jsonl \
      --limit 6 \
      --execute
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageStat

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.openai_image_edit import (  # noqa: E402
    DEFAULT_OPENAI_IMAGE_MODEL,
    DEFAULT_OPENAI_IMAGE_QUALITY,
    DEFAULT_OPENAI_IMAGE_SIZE,
    DEFAULT_OPENAI_OUTPUT_FORMAT,
    build_openai_edit_prompt,
    first_b64_image,
    make_openai_alpha_mask,
    response_without_b64,
)

DEFAULT_OUTPUT_DIR = Path("tmp/openai-image-edit-eval")
OPENAI_IMAGE_EDIT_URL = "https://api.openai.com/v1/images/edits"


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _resolve_path(value: str, *, manifest_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (manifest_dir / path).resolve()


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Manifest not found: {path}")

    manifest_dir = path.parent.resolve()
    cases: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc

        item["id"] = str(item.get("id") or f"case-{line_no:04d}")
        for field in ("car_image", "mask_image", "reference_image"):
            if not item.get(field):
                raise SystemExit(f"{path}:{line_no}: missing required field {field!r}")
            resolved = _resolve_path(str(item[field]), manifest_dir=manifest_dir)
            if not resolved.exists():
                raise SystemExit(f"{path}:{line_no}: {field} not found: {resolved}")
            item[field] = str(resolved)
        cases.append(item)
    return cases


def _mask_stats(*, car_path: Path, mask_path: Path) -> dict[str, Any]:
    with Image.open(car_path) as car_image:
        car_size = car_image.size
    mask = Image.open(mask_path).convert("L")
    if mask.size != car_size:
        return {
            "ok": False,
            "reason": f"mask size {mask.size} does not match car size {car_size}",
            "mask_white_ratio": 0.0,
        }

    binary = mask.point(lambda value: 255 if value >= 128 else 0)
    diff_bbox = ImageChops.difference(mask, binary).getbbox()
    stat = ImageStat.Stat(binary)
    white_ratio = float(stat.mean[0] / 255.0)
    if white_ratio <= 0:
        return {"ok": False, "reason": "mask is empty", "mask_white_ratio": white_ratio}
    if white_ratio > 0.35:
        return {
            "ok": False,
            "reason": "mask covers more than 35% of the image",
            "mask_white_ratio": white_ratio,
        }
    return {
        "ok": True,
        "reason": "ok",
        "mask_white_ratio": white_ratio,
        "mask_is_binary": diff_bbox is None,
    }


def _make_plan(
    *,
    cases: list[dict[str, Any]],
    limit: int | None,
    model: str,
    size: str,
    quality: str,
    output_format: str,
    output_dir: Path,
) -> list[dict[str, Any]]:
    selected_cases = cases[:limit] if limit else cases
    plan: list[dict[str, Any]] = []
    mask_input_dir = output_dir / "openai_masks"
    for case in selected_cases:
        car_path = Path(case["car_image"])
        mask_path = Path(case["mask_image"])
        stats = _mask_stats(car_path=car_path, mask_path=mask_path)
        openai_mask_path = mask_input_dir / f"{case['id']}.openai-alpha-mask.png"
        if stats["ok"]:
            make_openai_alpha_mask(binary_mask_path=mask_path, output_path=openai_mask_path)

        plan.append(
            {
                "case_id": case["id"],
                "config": f"openai-{model}",
                "model": model,
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "estimated_cost_usd": "",
                "preflight_ok": stats["ok"],
                "preflight_reason": stats["reason"],
                "mask_white_ratio": stats["mask_white_ratio"],
                "mask_is_binary": stats.get("mask_is_binary"),
                "car_image": str(car_path),
                "mask_image": str(mask_path),
                "openai_mask_image": str(openai_mask_path),
                "reference_image": case["reference_image"],
                "wheel_description": case.get("wheel_description") or "",
            }
        )
    return plan


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _call_openai_edit(*, row: dict[str, Any], prompt: str, timeout: float) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    car_path = Path(row["car_image"])
    reference_path = Path(row["reference_image"])
    mask_path = Path(row["openai_mask_image"])
    data = {
        "model": row["model"],
        "prompt": prompt,
        "size": row["size"],
        "quality": row["quality"],
        "output_format": row["output_format"],
        "n": "1",
    }
    # The API accepts multiple input images. The first image is the edited image;
    # later images are references for the prompt.
    with (
        car_path.open("rb") as car_handle,
        reference_path.open("rb") as reference_handle,
        mask_path.open("rb") as mask_handle,
    ):
        files = [
            ("image[]", (car_path.name, car_handle, _mime_type(car_path))),
            ("image[]", (reference_path.name, reference_handle, _mime_type(reference_path))),
            ("mask", (mask_path.name, mask_handle, "image/png")),
        ]
        response = httpx.post(
            OPENAI_IMAGE_EDIT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
            timeout=timeout,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI image edit failed {response.status_code}: {response.text}")
    return response.json()


def _execute_plan(
    *, rows: list[dict[str, Any]], output_dir: Path, results_jsonl: Path, timeout: float
) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    outputs_dir = output_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    results_jsonl.parent.mkdir(parents=True, exist_ok=True)
    results_jsonl.write_text("", encoding="utf-8")

    for idx, row in enumerate(rows, start=1):
        print(f"[{idx}/{len(rows)}] {row['case_id']} {row['config']}", flush=True)
        if not row["preflight_ok"]:
            record = {**row, "status": "skipped_preflight", "output_image": "", "error": ""}
            completed.append(record)
            with results_jsonl.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            continue

        prompt = build_openai_edit_prompt(wheel_description=row.get("wheel_description") or None)
        started_at = datetime.now(UTC).isoformat()
        try:
            result = _call_openai_edit(row=row, prompt=prompt, timeout=timeout)
            image_b64 = first_b64_image(result)
            output_path = outputs_dir / f"{row['case_id']}__{row['config']}.png"
            if image_b64:
                output_path.write_bytes(base64.b64decode(image_b64))
            record = {
                **row,
                "status": "completed",
                "output_image": str(output_path) if image_b64 else "",
                "error": "",
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_result": json.dumps(response_without_b64(result), ensure_ascii=False),
            }
            print(f"  completed: {record['output_image'] or '(no b64 output)'}", flush=True)
        except Exception as exc:
            record = {
                **row,
                "status": "failed",
                "output_image": "",
                "error": str(exc),
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_result": "",
            }
            print(f"  failed: {exc}", flush=True)
        completed.append(record)
        with results_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, help="JSONL manifest with car/mask/reference paths")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=DEFAULT_OPENAI_IMAGE_MODEL)
    parser.add_argument("--size", default=DEFAULT_OPENAI_IMAGE_SIZE)
    parser.add_argument("--quality", default=DEFAULT_OPENAI_IMAGE_QUALITY)
    parser.add_argument("--output-format", default=DEFAULT_OPENAI_OUTPUT_FORMAT)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run paid OpenAI image edits. Without this flag only writes the plan.",
    )
    args = parser.parse_args()

    _load_dotenv()

    cases = _read_manifest(args.manifest)
    plan = _make_plan(
        cases=cases,
        limit=args.limit,
        model=args.model,
        size=args.size,
        quality=args.quality,
        output_format=args.output_format,
        output_dir=args.output_dir,
    )
    skipped = sum(1 for row in plan if not row["preflight_ok"])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_jsonl = args.output_dir / "openai_image_edit_plan.jsonl"
    plan_csv = args.output_dir / "openai_image_edit_plan.csv"
    _write_jsonl(plan_jsonl, plan)
    _write_csv(plan_csv, plan)

    print(f"cases: {len({row['case_id'] for row in plan})}")
    print(f"planned requests: {len(plan)}")
    print(f"preflight skipped requests: {skipped}")
    print("estimated paid requests cost: unknown; OpenAI image costs are usage/model dependent")
    print(f"plan jsonl: {plan_jsonl}")
    print(f"plan csv: {plan_csv}")

    if not args.execute:
        print("dry-run only. Add --execute to run paid OpenAI image edits.")
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set")

    results_jsonl = args.output_dir / "openai_image_edit_results.jsonl"
    completed = _execute_plan(
        rows=plan,
        output_dir=args.output_dir,
        results_jsonl=results_jsonl,
        timeout=args.timeout,
    )
    results_csv = args.output_dir / "openai_image_edit_results.csv"
    _write_csv(results_csv, completed)
    print(f"results jsonl: {results_jsonl}")
    print(f"results csv: {results_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
