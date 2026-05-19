"""Budgeted fal.ai masked inpainting evaluation runner.

This script expects masks to already be produced by the Stage 1/2 pipeline:
Roboflow/YOLO candidates -> Qwen VLM filter -> final binary wheel mask.

Example dry run:
    .venv/bin/python scripts/fal_inpaint_eval.py cases.jsonl \
      --preset wide \
      --limit 50 \
      --max-estimated-cost 2.50

Paid inference requires an explicit flag:
    FAL_KEY=... .venv/bin/python scripts/fal_inpaint_eval.py cases.jsonl \
      --preset wide \
      --execute

Manifest JSONL format:
    {"id":"case-001","car_image":"data/cars/001.jpg","mask_image":"tmp/masks/001.png",
     "reference_image":"data/rims/ref.png","wheel_description":"matte black 5-spoke rims"}
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.fal_inpaint import (  # noqa: E402
    DEFAULT_FLUX_SWEEP_CONFIGS,
    DEFAULT_MODEL_CANDIDATE_CONFIGS,
    DEFAULT_NIGHT_FLUX_CONFIGS,
    DEFAULT_REFERENCE_CANDIDATE_CONFIGS,
    DEFAULT_TUNING_CONFIGS,
    DEFAULT_WIDE_CONFIGS,
    MODEL_SPECS,
    RUN_CONFIGS,
    FalRunConfig,
    build_arguments,
    build_prompt,
    estimate_cost_usd,
    first_image_url,
)

DEFAULT_OUTPUT_DIR = Path("tmp/fal-inpaint-eval")
DEFAULT_MAX_ESTIMATED_COST = 2.50


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Tiny .env loader so local scripts work without shell `source .env`."""

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

        case_id = str(item.get("id") or f"case-{line_no:04d}")
        for field in ("car_image", "mask_image", "reference_image"):
            if not item.get(field):
                raise SystemExit(f"{path}:{line_no}: missing required field {field!r}")
            resolved = _resolve_path(str(item[field]), manifest_dir=manifest_dir)
            if not resolved.exists():
                raise SystemExit(f"{path}:{line_no}: {field} not found: {resolved}")
            item[field] = str(resolved)
        item["id"] = case_id
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


def _configs_for_args(args: argparse.Namespace) -> list[FalRunConfig]:
    if args.config:
        names = args.config
    elif args.preset == "wide":
        names = list(DEFAULT_WIDE_CONFIGS)
    elif args.preset == "tuning":
        names = list(DEFAULT_TUNING_CONFIGS)
    elif args.preset == "flux-sweep":
        names = list(DEFAULT_FLUX_SWEEP_CONFIGS)
    elif args.preset == "model-candidates":
        names = list(DEFAULT_MODEL_CANDIDATE_CONFIGS)
    elif args.preset == "night-flux":
        names = list(DEFAULT_NIGHT_FLUX_CONFIGS)
    elif args.preset == "reference-candidates":
        names = list(DEFAULT_REFERENCE_CANDIDATE_CONFIGS)
    else:
        raise SystemExit(f"Unknown preset: {args.preset}")

    configs: list[FalRunConfig] = []
    for name in names:
        config = RUN_CONFIGS.get(name)
        if not config:
            valid = ", ".join(sorted(RUN_CONFIGS))
            raise SystemExit(f"Unknown config {name!r}. Valid configs: {valid}")
        configs.append(config)
    return configs


def _make_plan(
    *,
    cases: list[dict[str, Any]],
    configs: list[FalRunConfig],
    limit: int | None,
) -> list[dict[str, Any]]:
    selected_cases = cases[:limit] if limit else cases
    plan: list[dict[str, Any]] = []
    for case in selected_cases:
        car_path = Path(case["car_image"])
        mask_path = Path(case["mask_image"])
        stats = _mask_stats(car_path=car_path, mask_path=mask_path)
        for config in configs:
            cost = estimate_cost_usd(image_path=car_path, config=config)
            spec = MODEL_SPECS[config.model_id]
            plan.append(
                {
                    "case_id": case["id"],
                    "config": config.name,
                    "model_id": config.model_id,
                    "endpoint": spec.endpoint,
                    "estimated_cost_usd": cost,
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


def _upload_file(fal_module: Any, path: Path) -> str:
    return str(fal_module.upload_file(str(path)))


def _call_fal(
    *,
    fal_module: Any,
    config: FalRunConfig,
    car_path: Path,
    mask_path: Path,
    reference_path: Path,
    prompt: str,
    output_format: str,
    start_timeout: float,
    client_timeout: float,
) -> dict[str, Any]:
    spec = MODEL_SPECS[config.model_id]
    car_url = _upload_file(fal_module, car_path)
    mask_url = _upload_file(fal_module, mask_path)
    reference_url = (
        _upload_file(fal_module, reference_path)
        if spec.supports_reference_image or config.uses_reference_image
        else None
    )
    with Image.open(car_path) as image:
        width, height = image.size
    arguments = build_arguments(
        config=config,
        car_url=car_url,
        mask_url=mask_url,
        reference_url=reference_url,
        prompt=prompt,
        output_format=output_format,
        image_size={"width": width, "height": height},
    )

    def on_enqueue(request_id: str) -> None:
        print(f"  enqueued: {request_id}", flush=True)

    def on_queue_update(update: Any) -> None:
        logs = getattr(update, "logs", None)
        if not logs:
            return
        for log in logs:
            message = log.get("message") if isinstance(log, dict) else getattr(log, "message", None)
            if message:
                print(f"  fal: {message}", flush=True)

    return fal_module.subscribe(
        spec.endpoint,
        arguments=arguments,
        with_logs=True,
        on_enqueue=on_enqueue,
        on_queue_update=on_queue_update,
        start_timeout=start_timeout,
        client_timeout=client_timeout,
    )


def _execute_plan(
    *,
    rows: list[dict[str, Any]],
    output_format: str,
    results_jsonl: Path,
    start_timeout: float,
    client_timeout: float,
) -> list[dict[str, Any]]:
    try:
        import fal_client as fal_module
    except ImportError as exc:
        raise SystemExit(
            "fal_client is not installed. Install it with `.venv/bin/pip install fal-client`."
        ) from exc

    completed: list[dict[str, Any]] = []
    results_jsonl.parent.mkdir(parents=True, exist_ok=True)
    results_jsonl.write_text("", encoding="utf-8")
    for idx, row in enumerate(rows, start=1):
        print(
            f"[{idx}/{len(rows)}] {row['case_id']} {row['config']} "
            f"estimated=${row['estimated_cost_usd']:.4f}",
            flush=True,
        )
        if not row["preflight_ok"]:
            record = {**row, "status": "skipped_preflight", "output_url": "", "error": ""}
            completed.append(record)
            with results_jsonl.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            continue

        config = RUN_CONFIGS[row["config"]]
        prompt = build_prompt(wheel_description=row.get("wheel_description") or None)
        started_at = datetime.now(UTC).isoformat()
        try:
            result = _call_fal(
                fal_module=fal_module,
                config=config,
                car_path=Path(row["car_image"]),
                mask_path=Path(row["mask_image"]),
                reference_path=Path(row["reference_image"]),
                prompt=prompt,
                output_format=output_format,
                start_timeout=start_timeout,
                client_timeout=client_timeout,
            )
            output_url = first_image_url(result) or ""
            record = {
                **row,
                "status": "completed",
                "output_url": output_url,
                "error": "",
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_result": json.dumps(result, ensure_ascii=False),
            }
            completed.append(record)
            print(f"  completed: {output_url or '(no output url)'}", flush=True)
        except Exception as exc:
            record = {
                **row,
                "status": "failed",
                "output_url": "",
                "error": str(exc),
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_result": "",
            }
            completed.append(record)
            print(f"  failed: {exc}", flush=True)
        with results_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, help="JSONL manifest with car/mask/reference paths")
    parser.add_argument(
        "--preset",
        choices=[
            "wide",
            "tuning",
            "flux-sweep",
            "model-candidates",
            "night-flux",
            "reference-candidates",
        ],
        default="wide",
    )
    parser.add_argument(
        "--config",
        action="append",
        help="Explicit run config. Can be repeated. Overrides --preset.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-estimated-cost", type=float, default=DEFAULT_MAX_ESTIMATED_COST)
    parser.add_argument("--output-format", choices=["png", "jpeg", "webp"], default="png")
    parser.add_argument("--start-timeout", type=float, default=60.0)
    parser.add_argument("--client-timeout", type=float, default=180.0)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run paid fal.ai inference. Without this flag only writes the budget plan.",
    )
    args = parser.parse_args()

    _load_dotenv()

    cases = _read_manifest(args.manifest)
    configs = _configs_for_args(args)
    plan = _make_plan(cases=cases, configs=configs, limit=args.limit)
    total_cost = sum(row["estimated_cost_usd"] for row in plan if row["preflight_ok"])
    skipped = sum(1 for row in plan if not row["preflight_ok"])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_jsonl = args.output_dir / "fal_inpaint_plan.jsonl"
    plan_csv = args.output_dir / "fal_inpaint_plan.csv"
    _write_jsonl(plan_jsonl, plan)
    _write_csv(plan_csv, plan)

    print(f"cases: {len({row['case_id'] for row in plan})}")
    print(f"planned requests: {len(plan)}")
    print(f"preflight skipped requests: {skipped}")
    print(f"estimated paid requests cost: ${total_cost:.4f}")
    print(f"plan jsonl: {plan_jsonl}")
    print(f"plan csv: {plan_csv}")

    if total_cost > args.max_estimated_cost:
        raise SystemExit(
            f"Estimated cost ${total_cost:.4f} exceeds --max-estimated-cost "
            f"${args.max_estimated_cost:.2f}"
        )

    if not args.execute:
        print("dry-run only. Add --execute to run paid fal.ai inference.")
        return 0

    if not os.getenv("FAL_KEY"):
        raise SystemExit("FAL_KEY is not set")

    results_jsonl = args.output_dir / "fal_inpaint_results.jsonl"
    completed = _execute_plan(
        rows=plan,
        output_format=args.output_format,
        results_jsonl=results_jsonl,
        start_timeout=args.start_timeout,
        client_timeout=args.client_timeout,
    )
    results_csv = args.output_dir / "fal_inpaint_results.csv"
    _write_csv(results_csv, completed)
    print(f"results jsonl: {results_jsonl}")
    print(f"results csv: {results_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
