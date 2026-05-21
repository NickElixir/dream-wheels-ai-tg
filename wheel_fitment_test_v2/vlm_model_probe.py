# vlm_model_probe.py
# pip install openai
#
# Expected files next to this script:
#
# 1) vlm_cred.json
# {
#   "API_KEY": "your_openai_api_key_here",
#   "MODEL": "gpt-4.1-mini"   // optional
# }
#
# 2) search_model.png
#    Image of the car to identify
#
# What it does:
# - reads API key from vlm_cred.json
# - reads search_model.png
# - sends the image to OpenAI Responses API
# - asks for strict JSON describing make / model / year candidate
# - saves parsed result to vlm_results/model_guess.json

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI


CREDS_PATH = Path("vlm_cred.json")
IMAGE_PATH = Path("search_model.jpg")
OUT_DIR = Path("vlm_results")
OUT_PATH = OUT_DIR / "model_guess.json"


def load_json(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{path} is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{path} is not valid JSON: {e}")


def image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def extract_text(response) -> str:
    # Most convenient path when available
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()

    # Fallback: walk output items
    pieces = []
    for item in getattr(response, "output", []) or []:
        content = getattr(item, "content", None) or []
        for c in content:
            txt = getattr(c, "text", None)
            if txt:
                pieces.append(txt)
    return "\n".join(pieces).strip()


def main() -> None:
    if not CREDS_PATH.exists():
        raise FileNotFoundError(f"Missing {CREDS_PATH}")
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"Missing {IMAGE_PATH}")

    creds = load_json(CREDS_PATH)
    api_key = creds.get("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY is missing in vlm_cred.json")

    # Reasonable default for vision + low cost
    model = creds.get("MODEL", "gpt-4.1-mini")

    client = OpenAI(api_key=api_key)

    schema = {
        "type": "object",
        "properties": {
            "make": {"type": "string"},
            "model": {"type": "string"},
            "year_from": {"type": ["integer", "null"]},
            "year_to": {"type": ["integer", "null"]},
            "body_type": {"type": ["string", "null"]},
            "market_guess": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
            "notes": {"type": ["string", "null"]},
        },
        "required": [
            "make",
            "model",
            "year_from",
            "year_to",
            "body_type",
            "market_guess",
            "confidence",
            "notes",
        ],
        "additionalProperties": False,
    }

    prompt = (
        "Identify the car in the image as conservatively as possible. "
        "Return only the JSON object matching the schema. "
        "Rules: "
        "1) If exact year is uncertain, provide a small year range via year_from/year_to. "
        "2) If you are unsure of the model, return the most likely model and explain uncertainty in notes. "
        "3) confidence must be between 0 and 1. "
        "4) market_guess should be a short value like russia, chdm, eudm, usdm, or null if unknown. "
        "5) Do not mention wheel fitment. Only identify the car."
    )

    data_url = image_to_data_url(IMAGE_PATH)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "car_identification",
                "schema": schema,
                "strict": True,
            }
        },
    )

    raw_text = extract_text(response)
    parsed = json.loads(raw_text)

    result = {
        "model_used": model,
        "image_path": str(IMAGE_PATH),
        "parsed": parsed,
        "search_candidates": [
            {
                "make": parsed["make"],
                "model": parsed["model"],
                "year": year,
                "region": parsed["market_guess"] or "russia",
            }
            for year in range(
                parsed["year_from"] if parsed["year_from"] is not None else 2023,
                (parsed["year_to"] if parsed["year_to"] is not None else parsed["year_from"] or 2023) + 1,
            )
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
