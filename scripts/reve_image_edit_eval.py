"""Budgeted direct Reve image remix evaluation runner.

This runner uses the first-party Reve remix endpoint instead of fal.ai. It
shares the same JSONL manifest shape as scripts/fal_inpaint_eval.py:

    {"id":"case-001","car_image":"data/cars/001.jpg","mask_image":"tmp/masks/001.png",
     "reference_image":"data/rims/ref.png",
     "wheel_description":"the exact wheel design, color, finish, spoke pattern, center cap, and material from the reference image"}

Paid inference requires an explicit flag:

    REVE_API_KEY=... .venv/bin/python scripts/reve_image_edit_eval.py cases.jsonl --execute
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageChops, ImageStat

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.prompts import build_prompt as build_reve_production_prompt  # noqa: E402
from src.reve_image_edit import (  # noqa: E402
    DEFAULT_REVE_ASPECT_RATIO,
    DEFAULT_REVE_REMIX_URL,
    DEFAULT_REVE_VERSION,
    build_reve_edit_prompt,
    first_reve_image_b64,
    image_file_to_base64,
    response_without_image,
)

DEFAULT_OUTPUT_DIR = Path("tmp/reve-image-edit-eval")


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
    aspect_ratio: str,
    version: str,
    mode: str,
) -> list[dict[str, Any]]:
    selected_cases = cases[:limit] if limit else cases
    plan: list[dict[str, Any]] = []
    for case in selected_cases:
        car_path = Path(case["car_image"])
        mask_path = Path(case["mask_image"])
        stats = _mask_stats(car_path=car_path, mask_path=mask_path)
        plan.append(
            {
                "case_id": case["id"],
                "config": f"reve-direct-{mode}",
                "endpoint": DEFAULT_REVE_REMIX_URL,
                "mode": mode,
                "aspect_ratio": aspect_ratio,
                "version": version,
                "estimated_cost_usd": "",
                "preflight_ok": stats["ok"],
                "preflight_reason": stats["reason"],
                "mask_white_ratio": stats["mask_white_ratio"],
                "mask_is_binary": stats.get("mask_is_binary"),
                "car_image": str(car_path),
                "mask_image": str(mask_path),
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


def _call_reve(
    *, row: dict[str, Any], prompt: str, timeout: float, max_retries: int
) -> dict[str, Any]:
    api_key = os.getenv("REVE_API_KEY")
    if not api_key:
        raise RuntimeError("REVE_API_KEY is not set")

    reference_images = [
        image_file_to_base64(Path(row["car_image"])),
        image_file_to_base64(Path(row["reference_image"])),
    ]
    if row["mode"] == "masked":
        reference_images.append(image_file_to_base64(Path(row["mask_image"])))

    payload = {
        "prompt": prompt,
        "reference_images": reference_images,
        "aspect_ratio": row["aspect_ratio"],
        "version": row["version"],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(http2=False, trust_env=False, timeout=timeout) as client:
                response = client.post(DEFAULT_REVE_REMIX_URL, headers=headers, json=payload)
            break
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"Reve request failed: {last_exc}")

    try:
        result = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Reve returned non-JSON {response.status_code}: {response.text}"
        ) from exc
    if response.status_code >= 400:
        raise RuntimeError(f"Reve remix failed {response.status_code}: {result}")
    return result


def _execute_plan(
    *,
    rows: list[dict[str, Any]],
    output_dir: Path,
    results_jsonl: Path,
    timeout: float,
    max_retries: int,
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

        if row["mode"] == "production":
            prompt = build_reve_production_prompt()
        else:
            prompt = build_reve_edit_prompt(wheel_description=row.get("wheel_description") or None)
        started_at = datetime.now(UTC).isoformat()
        try:
            result = _call_reve(
                row=row,
                prompt=prompt,
                timeout=timeout,
                max_retries=max_retries,
            )
            image_b64 = first_reve_image_b64(result)
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
                "raw_result": json.dumps(response_without_image(result), ensure_ascii=False),
            }
            print(f"  completed: {record['output_image'] or '(no image output)'}", flush=True)
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
    parser.add_argument("--aspect-ratio", default=DEFAULT_REVE_ASPECT_RATIO)
    parser.add_argument("--version", default=DEFAULT_REVE_VERSION)
    parser.add_argument("--mode", choices=["masked", "production"], default="masked")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run paid Reve image remix. Without this flag only writes the plan.",
    )
    args = parser.parse_args()

    _load_dotenv()

    cases = _read_manifest(args.manifest)
    plan = _make_plan(
        cases=cases,
        limit=args.limit,
        aspect_ratio=args.aspect_ratio,
        version=args.version,
        mode=args.mode,
    )
    skipped = sum(1 for row in plan if not row["preflight_ok"])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_jsonl = args.output_dir / "reve_image_edit_plan.jsonl"
    plan_csv = args.output_dir / "reve_image_edit_plan.csv"
    _write_jsonl(plan_jsonl, plan)
    _write_csv(plan_csv, plan)

    print(f"cases: {len({row['case_id'] for row in plan})}")
    print(f"planned requests: {len(plan)}")
    print(f"preflight skipped requests: {skipped}")
    print("estimated paid requests cost: unknown; direct Reve pricing is account dependent")
    print(f"plan jsonl: {plan_jsonl}")
    print(f"plan csv: {plan_csv}")

    if not args.execute:
        print("dry-run only. Add --execute to run paid Reve image remix.")
        return 0

    if not os.getenv("REVE_API_KEY"):
        raise SystemExit("REVE_API_KEY is not set")

    results_jsonl = args.output_dir / "reve_image_edit_results.jsonl"
    completed = _execute_plan(
        rows=plan,
        output_dir=args.output_dir,
        results_jsonl=results_jsonl,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )
    results_csv = args.output_dir / "reve_image_edit_results.csv"
    _write_csv(results_csv, completed)
    print(f"results jsonl: {results_jsonl}")
    print(f"results csv: {results_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
