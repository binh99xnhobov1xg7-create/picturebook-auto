"""即梦 4.6 (火山方舟 Seedream) 图片生成客户端 + 占位图。

API: POST {base_url}/images/generations
Auth: Bearer {ARK_API_KEY}
Body: { model, prompt, size, response_format, watermark, image?(ref) }
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageDraw, ImageFont

from config import (
    IMAGE_SIZE,
    IMAGE_WATERMARK,
    JIMENG_API_KEY,
    JIMENG_BASE_URL,
    JIMENG_MODEL,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
)


def generate_image(
    *,
    prompt: str,
    dest: Path,
    references: Iterable[Path] = (),
    mock: bool = False,
    label: str = "",
) -> Path:
    """生成单张图，写入 dest。失败抛异常。"""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if mock or not JIMENG_API_KEY:
        _save_mock_image(dest, prompt, label)
        return dest

    url = f"{JIMENG_BASE_URL.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {JIMENG_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": JIMENG_MODEL,
        "prompt": prompt[:800],
        "size": IMAGE_SIZE,
        "response_format": "url",
        "watermark": IMAGE_WATERMARK,
        "sequential_image_generation": "disabled",
    }

    refs = [p for p in references if Path(p).exists()]
    if refs:
        encoded = [_encode_image(p) for p in refs]
        payload["image"] = encoded[0] if len(encoded) == 1 else encoded

    last_err: Exception | None = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:600]}")
            data = resp.json()

            # response_format=url
            img_url = _extract_url(data)
            if img_url:
                img_bytes = requests.get(img_url, timeout=REQUEST_TIMEOUT).content
                dest.write_bytes(img_bytes)
                return dest

            # response_format=b64_json fallback
            b64 = _extract_b64(data)
            if b64:
                dest.write_bytes(base64.b64decode(b64))
                return dest

            raise RuntimeError(f"响应中没有 url 或 b64_json: {json.dumps(data)[:500]}")

        except Exception as e:
            last_err = e
            if attempt < REQUEST_RETRIES:
                time.sleep(3 * (attempt + 1))
            else:
                break

    raise RuntimeError(f"即梦生图失败（已重试）: {last_err}")


def _encode_image(path: Path) -> str:
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    ext = Path(path).suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    return f"data:image/{mime};base64,{b64}"


def _extract_url(data: dict) -> str | None:
    if "data" in data and isinstance(data["data"], list) and data["data"]:
        item = data["data"][0]
        if isinstance(item, dict) and item.get("url"):
            return item["url"]
    return data.get("url")


def _extract_b64(data: dict) -> str | None:
    if "data" in data and isinstance(data["data"], list) and data["data"]:
        item = data["data"][0]
        if isinstance(item, dict) and item.get("b64_json"):
            return item["b64_json"]
    return None


# ---------- 占位图（无 API 时使用，便于调试 PPT 版式） ----------
def _save_mock_image(dest: Path, prompt: str, label: str) -> None:
    w, h = 2048, 1536
    img = Image.new("RGB", (w, h), (244, 240, 232))
    draw = ImageDraw.Draw(img)

    # 渐变色块 = 视觉占位
    for y in range(h):
        v = int(232 + (y / h) * 16)
        draw.line([(0, y), (w, y)], fill=(v, v - 4, v - 12))

    # 大字标签
    draw.text((80, 80), f"[MOCK] {label}", fill=(80, 70, 60))

    # 显示 prompt 头
    pre = prompt[:280]
    y = 220
    for line in _wrap(pre, 60)[:7]:
        draw.text((80, y), line, fill=(40, 40, 40))
        y += 56

    draw.text(
        (80, h - 120),
        "Configure JIMENG_API_KEY / ARK_API_KEY in .env to render real images.",
        fill=(120, 110, 100),
    )

    img.save(dest, "PNG")


def _wrap(s: str, width: int) -> list[str]:
    words, lines, cur = s.split(), [], []
    for w_ in words:
        if len(" ".join(cur + [w_])) > width and cur:
            lines.append(" ".join(cur))
            cur = [w_]
        else:
            cur.append(w_)
    if cur:
        lines.append(" ".join(cur))
    return lines or [s[:width]]
