# generate_search_from_vlm_and_run.py
# pip install requests
#
# Reads:
# - wheel_size_creds.json
# - vlm_results/model_guess.json
#
# Does:
# - iterates VLM search_candidates until Wheel-Size returns a usable vehicle
# - uses cache in wheel_size_debug/ if present
# - saves the found vehicle payload into wheel_size_debug/
# - generates search_settings_generated.json
# - also writes search_settings.json so fitment_test_v3.py can run immediately
# - runs fitment_test_v3.py automatically
# - saves a summary in wheel_fitment_results/generated_from_vlm_summary.json

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

SEARCH_URL = "https://api.wheel-size.com/v2/search/by_model/"
CREDS_PATH = Path("wheel_size_creds.json")
VLM_RESULT_PATH = Path("vlm_results/model_guess.json")
DEBUG_DIR = Path("wheel_size_debug")
RESULTS_DIR = Path("wheel_fitment_results")
OUT_SETTINGS_PATH = Path("search_settings_generated.json")
ACTIVE_SETTINGS_PATH = Path("search_settings.json")
OUT_SUMMARY_PATH = RESULTS_DIR / "generated_from_vlm_summary.json"
FITMENT_SCRIPT = Path("fitment_test_v3.py")


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{path} is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{path} is not valid JSON: {e}")


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(s: str) -> str:
    return str(s).replace(" ", "_").replace("/", "_").replace("\\", "_")


def cache_file_for_car(car: Dict[str, Any]) -> Path:
    return DEBUG_DIR / (
        f"search_{safe_name(car['region'])}_{safe_name(car['make'])}_"
        f"{safe_name(car['model'])}_{car['year']}.json"
    )


def normalize_bolt_pattern(bp: Optional[str]) -> Optional[str]:
    if not bp:
        return None
    return str(bp).lower().replace(" ", "").replace("×", "x")


def to_float(x: Any) -> Optional[float]:
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def extract_vehicle_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = payload.get("data", [])
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first
    return None


def extract_vehicle_level_constraints(vehicle: Dict[str, Any]) -> Dict[str, Optional[float]]:
    technical = vehicle.get("technical", {}) if isinstance(vehicle, dict) else {}

    bolt_pattern = (
        technical.get("bolt_pattern")
        or vehicle.get("bolt_pattern")
        or vehicle.get("stud_holes")
    )

    pcd = technical.get("pcd") or vehicle.get("pcd")

    center_bore = (
        technical.get("centre_bore")
        or technical.get("center_bore")
        or vehicle.get("centre_bore")
        or vehicle.get("center_bore")
        or vehicle.get("cb")
    )

    return {
        "bolt_pattern": normalize_bolt_pattern(bolt_pattern),
        "pcd": to_float(pcd),
        "center_bore": to_float(center_bore),
    }


def extract_allowed_wheels(vehicle: Dict[str, Any]) -> list[Dict[str, Any]]:
    records = []

    for i, item in enumerate(vehicle.get("wheels", [])):
        for axle in ("front", "rear"):
            axle_data = item.get(axle, {})
            if not axle_data:
                continue

            rim_diameter = to_float(axle_data.get("rim_diameter"))
            rim_width = to_float(axle_data.get("rim_width"))

            if rim_diameter is None or rim_width is None:
                continue

            records.append(
                {
                    "source_index": i,
                    "axle": axle,
                    "rim_diameter": rim_diameter,
                    "rim_width": rim_width,
                    "offset": to_float(axle_data.get("offset") or axle_data.get("et")),
                    "raw": axle_data,
                }
            )

    uniq = []
    seen = set()
    for rec in records:
        key = (rec["axle"], rec["rim_diameter"], rec["rim_width"], rec["offset"])
        if key not in seen:
            seen.add(key)
            uniq.append(rec)

    return uniq


def query_vehicle(api_key: str, car: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.get(
        SEARCH_URL,
        params={
            "make": car["make"],
            "model": car["model"],
            "year": car["year"],
            "region": car["region"],
            "user_key": api_key,
        },
        timeout=30,
    )

    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}

    payload["_debug"] = {
        "request_params": {
            "make": car["make"],
            "model": car["model"],
            "year": car["year"],
            "region": car["region"],
        },
        "status_code": response.status_code,
        "url": response.url,
    }
    return payload


def load_or_query_vehicle(api_key: str, car: Dict[str, Any]) -> Tuple[Dict[str, Any], Path, str]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = cache_file_for_car(car)

    if cache_path.exists():
        payload = load_json(cache_path)
        return payload, cache_path, "cache"

    payload = query_vehicle(api_key, car)
    save_json(cache_path, payload)
    return payload, cache_path, "api"


def build_candidate_sequence(vlm_result: Dict[str, Any]) -> list[Dict[str, Any]]:
    candidates = []
    seen = set()

    for c in vlm_result.get("search_candidates", []):
        key = (c["make"], c["model"], c["year"], c["region"])
        if key not in seen:
            seen.add(key)
            candidates.append(deepcopy(c))

    parsed = vlm_result.get("parsed", {})
    market_guess = parsed.get("market_guess")
    fallback_region = None
    if market_guess == "russia":
        fallback_region = "chdm"
    elif market_guess == "chdm":
        fallback_region = "russia"

    if fallback_region:
        base = vlm_result.get("search_candidates", [])
        for c in base:
            alt = deepcopy(c)
            alt["region"] = fallback_region
            key = (alt["make"], alt["model"], alt["year"], alt["region"])
            if key not in seen:
                seen.add(key)
                candidates.append(alt)

    return candidates


def pick_base_wheel(vehicle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = extract_allowed_wheels(vehicle)

    for rec in allowed:
        if rec["offset"] is not None:
            return rec

    if allowed:
        return allowed[0]

    return None


def wrong_bolt_pattern_from(constraints: Dict[str, Any]) -> Tuple[Optional[str], Optional[float]]:
    current = constraints.get("bolt_pattern")
    if current != "5x114.3":
        return "5x114.3", 114.3
    return "5x108", 108.0


def build_demo_wheels(vehicle: Dict[str, Any]) -> list[Dict[str, Any]]:
    constraints = extract_vehicle_level_constraints(vehicle)
    base = pick_base_wheel(vehicle)

    if base is None:
        wrong_bp, wrong_pcd = wrong_bolt_pattern_from(constraints)
        return [
            {
                "label": "wrong_bolt_pattern",
                "diameter": 18,
                "width": 7.0,
                "offset": 40,
                "bolt_pattern": wrong_bp,
                "pcd": wrong_pcd,
                "center_bore": constraints.get("center_bore"),
            },
            {
                "label": "correct_mounting_plausible_size",
                "diameter": 18,
                "width": 7.0,
                "offset": 40,
                "bolt_pattern": constraints.get("bolt_pattern"),
                "pcd": constraints.get("pcd"),
                "center_bore": constraints.get("center_bore"),
            },
            {
                "label": "size_not_approved_candidate",
                "diameter": 20,
                "width": 10.0,
                "offset": 15,
                "bolt_pattern": constraints.get("bolt_pattern"),
                "pcd": constraints.get("pcd"),
                "center_bore": constraints.get("center_bore"),
            },
        ]

    wrong_bp, wrong_pcd = wrong_bolt_pattern_from(constraints)
    exact_offset = base["offset"] if base["offset"] is not None else 40

    exact_candidate = {
        "label": "exact_fit_candidate" if base["offset"] is not None else "plausible_fit_candidate",
        "diameter": base["rim_diameter"],
        "width": base["rim_width"],
        "offset": exact_offset,
        "bolt_pattern": constraints.get("bolt_pattern"),
        "pcd": constraints.get("pcd"),
        "center_bore": constraints.get("center_bore"),
    }

    size_not_approved = {
        "label": "size_not_approved_candidate",
        "diameter": round(base["rim_diameter"] + 2),
        "width": round(base["rim_width"] + 2.0, 1),
        "offset": 15 if base["offset"] is None else max(base["offset"] - 15, 0),
        "bolt_pattern": constraints.get("bolt_pattern"),
        "pcd": constraints.get("pcd"),
        "center_bore": constraints.get("center_bore"),
    }

    wrong_mounting = {
        "label": "wrong_bolt_pattern",
        "diameter": base["rim_diameter"],
        "width": base["rim_width"],
        "offset": exact_offset,
        "bolt_pattern": wrong_bp,
        "pcd": wrong_pcd,
        "center_bore": constraints.get("center_bore"),
    }

    return [wrong_mounting, exact_candidate, size_not_approved]


def main() -> None:
    if not CREDS_PATH.exists():
        raise FileNotFoundError(f"Missing {CREDS_PATH}")
    if not VLM_RESULT_PATH.exists():
        raise FileNotFoundError(f"Missing {VLM_RESULT_PATH}")
    if not FITMENT_SCRIPT.exists():
        raise FileNotFoundError(f"Missing {FITMENT_SCRIPT}")

    creds = load_json(CREDS_PATH)
    api_key = creds.get("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY is missing in wheel_size_creds.json")

    vlm_result = load_json(VLM_RESULT_PATH)
    candidates = build_candidate_sequence(vlm_result)
    if not candidates:
        raise RuntimeError("No search_candidates found in vlm_results/model_guess.json")

    attempts = []
    found = None

    for car in candidates:
        payload, cache_path, source = load_or_query_vehicle(api_key, car)
        vehicle = extract_vehicle_from_payload(payload)

        attempt = {
            "car": car,
            "source": source,
            "cache_path": str(cache_path),
            "status_code": payload.get("_debug", {}).get("status_code"),
            "data_count": len(payload.get("data", [])) if isinstance(payload.get("data"), list) else None,
            "found": vehicle is not None,
        }
        attempts.append(attempt)

        if vehicle is not None:
            found = {
                "car": car,
                "vehicle": vehicle,
                "payload": payload,
                "cache_path": cache_path,
                "source": source,
            }
            break

    if found is None:
        summary = {
            "vlm_result_path": str(VLM_RESULT_PATH),
            "resolved": False,
            "reason": "No Wheel-Size candidate returned usable vehicle data.",
            "attempts": attempts,
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        save_json(OUT_SUMMARY_PATH, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nSaved {OUT_SUMMARY_PATH}")
        return

    demo_wheels = build_demo_wheels(found["vehicle"])
    generated_settings = {
        "car": found["car"],
        "wheels": demo_wheels,
    }
    save_json(OUT_SETTINGS_PATH, generated_settings)
    save_json(ACTIVE_SETTINGS_PATH, generated_settings)

    constraints = extract_vehicle_level_constraints(found["vehicle"])
    allowed = extract_allowed_wheels(found["vehicle"])

    run = subprocess.run(
        [sys.executable, str(FITMENT_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    summary = {
        "vlm_result_path": str(VLM_RESULT_PATH),
        "resolved": True,
        "selected_car": found["car"],
        "vehicle_payload_source": found["source"],
        "vehicle_payload_path": str(found["cache_path"]),
        "vehicle_constraints": constraints,
        "allowed_wheels_preview": allowed[:10],
        "generated_search_settings_path": str(OUT_SETTINGS_PATH),
        "active_search_settings_path": str(ACTIVE_SETTINGS_PATH),
        "generated_wheels": demo_wheels,
        "fitment_script": str(FITMENT_SCRIPT),
        "fitment_return_code": run.returncode,
        "fitment_stdout": run.stdout,
        "fitment_stderr": run.stderr,
        "attempts": attempts,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    save_json(OUT_SUMMARY_PATH, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved {OUT_SETTINGS_PATH}")
    print(f"Saved {ACTIVE_SETTINGS_PATH}")
    print(f"Saved {OUT_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
