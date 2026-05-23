"""Public share pages for completed Dream Wheels jobs."""

import html
import logging
import re
from io import BytesIO

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from src import db, storage
from src.config import PUBLIC_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/s", tags=["share"])

SHORT_ID_RE = re.compile(r"^[0-9a-fA-F]{8,36}$")


def share_url_for_job(job_id: str) -> str:
    return f"{PUBLIC_BASE_URL}/s/{job_id[:8]}"


def _content_type_for_path(path: str | None) -> str:
    ext = (path or "").rsplit(".", 1)[-1].lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")


def _normalize_short_id(short_id: str) -> str:
    value = short_id.strip()
    if not SHORT_ID_RE.match(value):
        raise HTTPException(status_code=404, detail="Share not found")
    return value.lower()


async def _find_completed_job(short_id: str):
    prefix = _normalize_short_id(short_id)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, car_image_url, output_image_url, completed_at
            FROM jobs
            WHERE id::text LIKE $1
              AND status = 'completed'
              AND output_image_url IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 2
            """,
            f"{prefix}%",
        )
    if not rows:
        raise HTTPException(status_code=404, detail="Share not found")
    if len(rows) > 1:
        raise HTTPException(status_code=409, detail="Share id is ambiguous")
    return rows[0]


async def _fetch_result_bytes(result_url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(result_url)
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="Result image fetch failed")
    return resp.content


async def _fetch_original_bytes(car_image_url: str | None) -> bytes | None:
    if not car_image_url:
        return None
    if car_image_url.startswith("http://") or car_image_url.startswith("https://"):
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(car_image_url)
        if resp.status_code >= 400:
            return None
        return resp.content
    try:
        return await storage.download_bytes(bucket=storage.RAW_BUCKET, path=car_image_url)
    except storage.StorageError:
        return None


def _draw_contained_image(canvas, source, box):
    from PIL import ImageOps

    x, y, width, height = box
    fitted = ImageOps.contain(ImageOps.exif_transpose(source).convert("RGB"), (width, height))
    offset_x = x + (width - fitted.width) // 2
    offset_y = y + (height - fitted.height) // 2
    canvas.paste(fitted, (offset_x, offset_y))


def _load_preview_font(size: int):
    from PIL import ImageFont

    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _make_comparison_preview(original_bytes: bytes | None, result_bytes: bytes) -> bytes:
    from PIL import Image, ImageDraw

    result = Image.open(BytesIO(result_bytes))
    original = Image.open(BytesIO(original_bytes)) if original_bytes else result

    canvas_width = 1200
    canvas_height = 630
    padding = 34
    header_height = 82
    gap = 22
    label_height = 42
    panel_width = (canvas_width - padding * 2 - gap) // 2
    image_height = canvas_height - padding * 2 - header_height - label_height

    canvas = Image.new("RGB", (canvas_width, canvas_height), "#0a0a0b")
    draw = ImageDraw.Draw(canvas)
    title_font = _load_preview_font(42)
    label_font = _load_preview_font(28)
    brand_font = _load_preview_font(24)

    draw.text((padding, 24), "DREAMWHEELS AI", fill="#e8ff00", font=brand_font)
    draw.text((padding, 54), "Before / After", fill="#f4f4f5", font=title_font)

    panels = (
        ("BEFORE", original, padding),
        ("AFTER", result, padding + panel_width + gap),
    )
    for label, image, x in panels:
        y = padding + header_height
        draw.rectangle(
            [x, y, x + panel_width, y + label_height + image_height],
            fill="#15161a",
            outline="#34363c",
            width=2,
        )
        draw.text((x + 18, y + 8), label, fill="#a3a3a3", font=label_font)
        image_y = y + label_height
        draw.rectangle(
            [x + 2, image_y, x + panel_width - 2, image_y + image_height - 2],
            fill="#050506",
        )
        _draw_contained_image(
            canvas,
            image,
            (x + 2, image_y, panel_width - 4, image_height - 4),
        )

    out = BytesIO()
    canvas.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


@router.get("/{short_id}", response_class=HTMLResponse)
async def share_page(short_id: str):
    row = await _find_completed_job(short_id)
    job_id = row["id"]
    result_url = row["output_image_url"]
    page_url = share_url_for_job(job_id)
    original_url = f"{page_url}/original" if row["car_image_url"] else None
    preview_url = f"{page_url}/preview.jpg"

    title = "Dream Wheels AI render"
    description = "Before and after AI wheel visualization."
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)
    escaped_page_url = html.escape(page_url, quote=True)
    escaped_result_url = html.escape(result_url, quote=True)
    escaped_original_url = html.escape(original_url, quote=True) if original_url else ""
    escaped_preview_url = html.escape(preview_url, quote=True)

    before_markup = ""
    if escaped_original_url:
        before_markup = f"""
          <section class="panel">
            <div class="label">Before</div>
            <img src="{escaped_original_url}" alt="Original car photo" loading="lazy">
          </section>
        """

    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <meta name="description" content="{escaped_description}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escaped_title}">
  <meta property="og:description" content="{escaped_description}">
  <meta property="og:url" content="{escaped_page_url}">
  <meta property="og:image" content="{escaped_preview_url}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escaped_title}">
  <meta name="twitter:description" content="{escaped_description}">
  <meta name="twitter:image" content="{escaped_preview_url}">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0a0a0b;
      --surface: #15161a;
      --border: rgba(255,255,255,.12);
      --text: #f4f4f5;
      --muted: rgba(255,255,255,.58);
      --accent: #e8ff00;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    main {{
      width: min(760px, 100%);
      margin: 0 auto;
      padding: 24px 16px 40px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--border);
    }}
    .brand {{
      color: var(--accent);
      font-weight: 700;
      letter-spacing: .1em;
      font-size: 13px;
    }}
    h1 {{
      margin: 8px 0 0;
      font-size: clamp(26px, 5vw, 44px);
      line-height: 1.05;
      letter-spacing: -.02em;
    }}
    .job {{
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      white-space: nowrap;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .panel {{
      min-width: 0;
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    .label {{
      padding: 12px 14px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .12em;
      border-bottom: 1px solid var(--border);
    }}
    img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: contain;
      background: #050506;
    }}
    .cta {{
      display: inline-flex;
      margin-top: 18px;
      color: #050506;
      background: var(--accent);
      padding: 12px 16px;
      text-decoration: none;
      font-weight: 700;
    }}
    @media (max-width: 720px) {{
      header {{ display: block; }}
      .job {{ margin-top: 8px; white-space: normal; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <div class="brand">DREAMWHEELS AI</div>
        <h1>Before / After</h1>
      </div>
      <div class="job">{html.escape(job_id)}</div>
    </header>
    <div class="grid">
      {before_markup}
      <section class="panel">
        <div class="label">After</div>
        <img src="{escaped_result_url}" alt="AI render" loading="eager">
      </section>
    </div>
    <a class="cta" href="{escaped_result_url}" target="_blank" rel="noreferrer">Open image</a>
  </main>
</body>
</html>""",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/{short_id}/original")
async def share_original(short_id: str):
    row = await _find_completed_job(short_id)
    car_image_url = row["car_image_url"]
    if not car_image_url:
        raise HTTPException(status_code=404, detail="Original image not found")

    if car_image_url.startswith("http://") or car_image_url.startswith("https://"):
        return RedirectResponse(car_image_url, status_code=302)

    try:
        content = await storage.download_bytes(bucket=storage.RAW_BUCKET, path=car_image_url)
    except storage.StorageError as exc:
        logger.exception(f"❌ Original fetch failed for share {short_id}: {exc}")
        raise HTTPException(status_code=404, detail="Original image not found") from exc

    return Response(
        content=content,
        media_type=_content_type_for_path(car_image_url),
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/{short_id}/preview.jpg")
async def share_preview(short_id: str):
    row = await _find_completed_job(short_id)
    original_bytes = await _fetch_original_bytes(row["car_image_url"])
    result_bytes = await _fetch_result_bytes(row["output_image_url"])

    try:
        image_bytes = _make_comparison_preview(original_bytes, result_bytes)
    except Exception as exc:
        logger.exception(f"❌ Preview render failed for share {short_id}: {exc}")
        raise HTTPException(status_code=502, detail="Preview render failed") from exc

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{short_id}/result")
async def share_result(short_id: str):
    row = await _find_completed_job(short_id)
    result_url = row["output_image_url"]
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.head(result_url)
    except httpx.HTTPError:
        resp = None
    if resp is not None and resp.status_code >= 400:
        raise HTTPException(status_code=404, detail="Result image not found")
    return RedirectResponse(result_url, status_code=302)
