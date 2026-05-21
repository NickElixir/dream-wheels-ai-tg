# fitment_test_v3.py
# pip install requests
#
# Expected files next to this script:
#
# 1) wheel_size_creds.json
# {
#   "API_KEY": "your_key_here"
# }
#
# 2) search_settings.json
# {
#   "car": {
#     "make": "Exeed",
#     "model": "LX",
#     "year": 2024,
#     "region": "russia"
#   },
#   "wheels": [
#     {
#       "label": "wrong_bolt_pattern",
#       "diameter": 18,
#       "width": 7.0,
#       "offset": 40,
#       "bolt_pattern": "5x114.3",
#       "pcd": 114.3,
#       "center_bore": 60.1
#     }
#   ]
# }
#
# Minimal change vs previous version:
# - uses wheel_size_creds.json
# - supports either a single "wheel" dict or a "wheels" list

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests


SEARCH_URL = "https://api.wheel-size.com/v2/search/by_model/"
DEBUG_DIR = Path("wheel_size_debug")
RESULTS_DIR = Path("wheel_fitment_results")
CREDS_PATH = Path("wheel_size_creds.json")
SETTINGS_PATH = Path("search_settings.json")


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{path} is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{path} is not valid JSON: {e}")


def safe_name(s: str) -> str:
    return str(s).replace(" ", "_").replace("/", "_").replace("\\", "_")


def cache_file_for_car(car: Dict[str, Any]) -> Path:
    return DEBUG_DIR / (
        f"search_{safe_name(car['region'])}_{safe_name(car['make'])}_"
        f"{safe_name(car['model'])}_{car['year']}.json"
    )


def result_file_for_fitment(car: Dict[str, Any], wheel: Dict[str, Any], idx: int) -> Path:
    label = wheel.get("label")
    label_part = f"_{safe_name(label)}" if label else f"_wheel{idx + 1}"
    offset = wheel.get("offset")
    offset_part = f"_ET{safe_name(offset)}" if offset is not None else ""
    return RESULTS_DIR / (
        f"fitment_{safe_name(car['region'])}_{safe_name(car['make'])}_{safe_name(car['model'])}_{car['year']}"
        f"{label_part}_{safe_name(wheel.get('diameter'))}x{safe_name(wheel.get('width'))}{offset_part}.json"
    )


def summary_file_for_car(car: Dict[str, Any]) -> Path:
    return RESULTS_DIR / (
        f"fitment_summary_{safe_name(car['region'])}_{safe_name(car['make'])}_{safe_name(car['model'])}_{car['year']}.json"
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


def almost_equal(a: Optional[float], b: Optional[float], tol: float = 0.1) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


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


def validate_wheel_only_v2(vehicle: Dict[str, Any], wheel: Dict[str, Any]) -> Dict[str, Any]:
    constraints = extract_vehicle_level_constraints(vehicle)
    allowed = extract_allowed_wheels(vehicle)

    target = {
        "diameter": to_float(wheel.get("diameter")),
        "width": to_float(wheel.get("width")),
        "offset": to_float(wheel.get("offset")),
        "bolt_pattern": normalize_bolt_pattern(wheel.get("bolt_pattern")),
        "pcd": to_float(wheel.get("pcd")),
        "center_bore": to_float(wheel.get("center_bore")),
    }

    if target["diameter"] is None or target["width"] is None:
        return {
            "fits": False,
            "status": "invalid_input",
            "reason": "Wheel diameter and width are required.",
            "vehicle_constraints": constraints,
        }

    if constraints["bolt_pattern"] and target["bolt_pattern"]:
        if constraints["bolt_pattern"] != target["bolt_pattern"]:
            return {
                "fits": False,
                "status": "mounting_mismatch",
                "reason": (
                    f"Bolt pattern mismatch: "
                    f"car={constraints['bolt_pattern']}, wheel={target['bolt_pattern']}"
                ),
                "vehicle_constraints": constraints,
            }

    if constraints["pcd"] is not None and target["pcd"] is not None:
        if not almost_equal(constraints["pcd"], target["pcd"], tol=0.1):
            return {
                "fits": False,
                "status": "mounting_mismatch",
                "reason": f"PCD mismatch: car={constraints['pcd']}, wheel={target['pcd']}",
                "vehicle_constraints": constraints,
            }

    if constraints["center_bore"] is not None and target["center_bore"] is not None:
        if target["center_bore"] < constraints["center_bore"]:
            return {
                "fits": False,
                "status": "mounting_mismatch",
                "reason": (
                    f"Center bore too small: "
                    f"car={constraints['center_bore']}, wheel={target['center_bore']}"
                ),
                "vehicle_constraints": constraints,
            }

    exact_matches = []
    uncertain_matches = []
    near_matches = []

    for rec in allowed:
        size_reasons = []

        if not almost_equal(target["diameter"], rec["rim_diameter"], tol=0.1):
            size_reasons.append(
                f"diameter mismatch ({target['diameter']} vs {rec['rim_diameter']})"
            )

        if not almost_equal(target["width"], rec["rim_width"], tol=0.1):
            size_reasons.append(
                f"width mismatch ({target['width']} vs {rec['rim_width']})"
            )

        if size_reasons:
            score = (
                abs(target["diameter"] - rec["rim_diameter"]) * 10
                + abs(target["width"] - rec["rim_width"])
            )
            near_matches.append(
                {
                    "axle": rec["axle"],
                    "rim_diameter": rec["rim_diameter"],
                    "rim_width": rec["rim_width"],
                    "offset": rec["offset"],
                    "reasons": size_reasons,
                    "score": score,
                }
            )
            continue

        if target["offset"] is not None and rec["offset"] is not None:
            if almost_equal(target["offset"], rec["offset"], tol=2.0):
                exact_matches.append(
                    {
                        "axle": rec["axle"],
                        "rim_diameter": rec["rim_diameter"],
                        "rim_width": rec["rim_width"],
                        "offset": rec["offset"],
                    }
                )
            else:
                near_matches.append(
                    {
                        "axle": rec["axle"],
                        "rim_diameter": rec["rim_diameter"],
                        "rim_width": rec["rim_width"],
                        "offset": rec["offset"],
                        "reasons": [f"offset mismatch ({target['offset']} vs {rec['offset']})"],
                        "score": 0.01 + abs(target["offset"] - rec["offset"]),
                    }
                )
        else:
            uncertain_matches.append(
                {
                    "axle": rec["axle"],
                    "rim_diameter": rec["rim_diameter"],
                    "rim_width": rec["rim_width"],
                    "offset": rec["offset"],
                    "note": "Size matched, but offset could not be fully verified.",
                }
            )

    near_matches.sort(key=lambda x: x["score"])

    if exact_matches:
        return {
            "fits": True,
            "status": "exact_fit",
            "reason": "Wheel matches an approved wheel configuration from the API.",
            "vehicle_constraints": constraints,
            "matches": exact_matches,
            "closest_allowed": near_matches[:5],
        }

    if uncertain_matches:
        return {
            "fits": True,
            "status": "uncertain_due_to_missing_offset",
            "reason": "Wheel size matches approved fitment, but offset could not be fully verified.",
            "vehicle_constraints": constraints,
            "matches": uncertain_matches,
            "closest_allowed": near_matches[:5],
        }

    return {
        "fits": False,
        "status": "mounting_ok_but_size_not_approved",
        "reason": "Mounting geometry is acceptable, but no approved wheel size matched.",
        "vehicle_constraints": constraints,
        "closest_allowed": near_matches[:5],
    }


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
        "requested_at": datetime.utcnow().isoformat() + "Z",
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


def extract_vehicle_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = payload.get("data", [])
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first
    return None


def get_wheels_from_settings(settings: Dict[str, Any]) -> list[Dict[str, Any]]:
    if "wheels" in settings:
        wheels = settings["wheels"]
        if not isinstance(wheels, list) or not wheels:
            raise RuntimeError("'wheels' must be a non-empty list")
        return wheels

    if "wheel" in settings:
        wheel = settings["wheel"]
        if not isinstance(wheel, dict):
            raise RuntimeError("'wheel' must be a dict")
        return [wheel]

    raise RuntimeError("search_settings.json must contain either 'wheel' or 'wheels'")


def main() -> None:
    if not CREDS_PATH.exists():
        raise FileNotFoundError(f"Missing {CREDS_PATH}")

    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Missing {SETTINGS_PATH}")

    creds = load_json(CREDS_PATH)
    settings = load_json(SETTINGS_PATH)

    api_key = creds.get("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY is missing in wheel_size_creds.json")

    if "car" not in settings:
        raise RuntimeError("search_settings.json must contain 'car' section")

    car = settings["car"]
    wheels = get_wheels_from_settings(settings)

    required_car_fields = ("make", "model", "year", "region")
    missing = [k for k in required_car_fields if k not in car]
    if missing:
        raise RuntimeError(f"Missing car fields in search_settings.json: {missing}")

    payload, vehicle_path, source = load_or_query_vehicle(api_key, car)
    vehicle = extract_vehicle_from_payload(payload)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_items = []

    for idx, wheel in enumerate(wheels):
        if vehicle is None:
            result = {
                "car": car,
                "wheel": wheel,
                "fits": False,
                "status": "vehicle_not_found",
                "reason": "Vehicle was not found or API returned no usable data.",
                "vehicle_payload_source": source,
                "vehicle_payload_path": str(vehicle_path),
                "vehicle_search_meta": payload.get("_debug", {}),
                "raw_response_excerpt": {
                    "code": payload.get("code"),
                    "message": payload.get("message"),
                    "meta": payload.get("meta"),
                    "data_count": len(payload.get("data", [])) if isinstance(payload.get("data"), list) else None,
                },
            }
        else:
            fitment = validate_wheel_only_v2(vehicle, wheel)
            result = {
                "car": car,
                "wheel": wheel,
                "vehicle_payload_source": source,
                "vehicle_payload_path": str(vehicle_path),
                "vehicle_search_meta": payload.get("_debug", {}),
                **fitment,
            }

        result_path = result_file_for_fitment(car, wheel, idx)
        save_json(result_path, result)

        summary_items.append(
            {
                "label": wheel.get("label", f"wheel{idx + 1}"),
                "result_file": str(result_path),
                "status": result["status"],
                "fits": result["fits"],
                "reason": result["reason"],
            }
        )

    summary = {
        "car": car,
        "vehicle_payload_source": source,
        "vehicle_payload_path": str(vehicle_path),
        "items": summary_items,
    }
    summary_path = summary_file_for_car(car)
    save_json(summary_path, summary)

    print(f"Vehicle payload source: {source}")
    print(f"Vehicle payload file:   {vehicle_path}")
    print(f"Summary result file:    {summary_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
