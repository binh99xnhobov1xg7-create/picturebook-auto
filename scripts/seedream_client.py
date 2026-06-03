"""gpt-image-2（imarouter 托管）图片生成客户端 + 占位图。

2026-06-02 迁移：从火山 Seedream（同步）换到 imarouter gpt-image-2（异步任务制）。

生成链路：
  1. POST {base}/images/generations  →  返回 task_id
  2. 轮询 GET {base}/images/generations/{task_id}  →  data.status == "succeeded"
  3. 下载 data.url（阿里云 OSS 临时直链）写入 dest

参考图（锁 IP 形象 / 图生图）：
  - gpt-image-2 只接受 **单个 image URL**（base64 / 多图都不支持）
  - 本地参考图需先托管成公网 URL（临时图床即可，生成时只拉取一次）
  - 已是 URL 的参考（如上一轮输出 OSS url，做链式图生图）直接用
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageDraw

from config import (
    IMAGE_DELIVER_PRINT,
    IMAGE_HOST_PROVIDER,
    IMAGE_POLL_INTERVAL,
    IMAGE_POLL_MAX_TRIES,
    IMAGE_SIZE,
    IMAGE_TARGET_PRINT,
    IMAGE_TARGET_RATIO,
    IMAGE_UPSCALE_METHOD,
    JIMENG_API_KEY,
    JIMENG_BASE_URL,
    JIMENG_MODEL,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
)

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) picturebook-auto/1.0"}


# ============================================================
#  后处理：3:2 直出 → 居中裁 4:3 → 放大到精细印刷 2000×1500（方案A）
# ============================================================
def crop_to_ratio(img: "Image.Image", ratio: tuple[int, int] = IMAGE_TARGET_RATIO) -> "Image.Image":
    """居中裁切到目标宽高比（默认 4:3）。3:2(1536x1024) → 4:3(1365x1024)。"""
    rw, rh = ratio
    w, h = img.size
    target_ar = rw / rh
    cur_ar = w / h
    if abs(cur_ar - target_ar) < 1e-3:
        return img
    if cur_ar > target_ar:
        # 太宽 → 裁左右
        new_w = int(round(h * target_ar))
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    # 太高 → 裁上下
    new_h = int(round(w / target_ar))
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def _upscale_esrgan(img: "Image.Image", target: tuple[int, int]) -> "Image.Image | None":
    """尝试用 Real-ESRGAN 超分；未安装则返回 None 让调用方回退 Lanczos。"""
    try:
        from realesrgan_ncnn_py import Realesrgan  # type: ignore
        import numpy as np  # type: ignore

        engine = Realesrgan(gpuid=0)
        out = engine.process_pil(img.convert("RGB"))
        return out.resize(target, Image.LANCZOS) if out.size != target else out
    except Exception:
        return None


def postprocess_4k(path: Path) -> Path:
    """对已落地的图做 方案A 后处理：居中裁 4:3 → 放大到精细印刷尺寸。原地覆盖 path。"""
    if not IMAGE_DELIVER_PRINT:
        return path
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im = crop_to_ratio(im, IMAGE_TARGET_RATIO)
            out = None
            if IMAGE_UPSCALE_METHOD.lower() == "esrgan":
                out = _upscale_esrgan(im, IMAGE_TARGET_PRINT)
            if out is None:
                out = im.resize(IMAGE_TARGET_PRINT, Image.LANCZOS)
            out.save(path)
    except Exception as e:
        # 后处理失败不影响主流程：保留原图
        print(f"[postprocess_4k] 跳过放大（保留原图）: {e}")
    return path


# ============================================================
#  图片托管：本地图 → 公网 URL（gpt-image-2 参考图只收 URL）
# ============================================================
def host_image_to_url(path: Path) -> str | None:
    """把本地图片上传到临时图床，返回公网直链。失败返回 None。

    参考图只需在生成的几秒内可访问，临时图床（tmpfiles 24h）足够。
    """
    path = Path(path)
    if not path.exists():
        return None

    provider = IMAGE_HOST_PROVIDER.lower()

    if provider in ("tmpfiles", "auto"):
        try:
            with path.open("rb") as f:
                r = requests.post(
                    "https://tmpfiles.org/api/v1/upload",
                    headers=_UA, files={"file": (path.name, f)}, timeout=120,
                )
            if r.status_code == 200:
                u = r.json().get("data", {}).get("url", "")
                if u:
                    # 直链：tmpfiles.org/xxx → tmpfiles.org/dl/xxx
                    return u.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        except Exception:
            pass

    # 兜底：litterbox（catbox 临时版，72h）
    try:
        with path.open("rb") as f:
            r = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": (path.name, f)},
                headers=_UA, timeout=120,
            )
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except Exception:
        pass

    return None


def _resolve_reference_url(references: Iterable[Path | str]) -> str | None:
    """从参考列表里取第一个可用的 URL。

    - 元素是 http(s) URL → 直接用（链式图生图：上一轮输出）
    - 元素是本地 Path → 托管成 URL
    gpt-image-2 只能用一张参考图。
    """
    for ref in references:
        if not ref:
            continue
        s = str(ref)
        if s.startswith("http://") or s.startswith("https://"):
            return s
        p = Path(s)
        if p.exists():
            url = host_image_to_url(p)
            if url:
                return url
    return None


# ============================================================
#  合成「定妆参考图」（解决 gpt-image-2 单参考图 → 多角色页崩形）
# ============================================================
#  gpt-image-2 只能吃 1 张参考图，多角色页若只发主角那张，其余角色会被模型瞎编。
#  这里把本页所有角色的固定定妆图横向拼成 1 张「定妆合集」白底图，作为唯一参考发出去，
#  一张图里同时锁住每个人的长相/发型/服装，配合 prompt 里的姓名即可稳定还原。
def build_reference_sheet(
    refs: list[Path | str],
    dest: Path,
    labels: list[str] | None = None,
    *,
    panel_h: int = 768,
    gap: int = 32,
    pad: int = 40,
    label_h: int = 64,
) -> Path | None:
    """把多张角色定妆图横向拼成一张白底「定妆合集」图。

    Args:
        refs: 角色定妆图路径列表（本地文件；URL 会被跳过——拼图需要本地像素）。
        dest: 输出路径。
        labels: 与 refs 对应的名字标签（英文名渲染良好；缺失/失败则不画标签）。
    Returns:
        拼好的图路径；可用本地图不足 2 张时返回 None（调用方应回退到原单图逻辑）。
    """
    imgs: list[Image.Image] = []
    used_labels: list[str] = []
    for i, r in enumerate(refs):
        if not r:
            continue
        s = str(r)
        if s.startswith("http://") or s.startswith("https://"):
            continue  # 拼图需要本地像素
        p = Path(s)
        if not p.exists():
            continue
        try:
            im = Image.open(p).convert("RGBA")
        except Exception:
            continue
        # 贴到白底，去透明
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im).convert("RGB")
        # 统一高度
        w, h = im.size
        new_w = max(1, int(w * panel_h / h))
        im = im.resize((new_w, panel_h), Image.LANCZOS)
        imgs.append(im)
        used_labels.append((labels[i] if labels and i < len(labels) else "") or "")

    if len(imgs) < 2:
        return None  # 不足两张本地图，没必要拼，回退原逻辑

    total_w = pad * 2 + sum(im.width for im in imgs) + gap * (len(imgs) - 1)
    has_labels = any(used_labels)
    total_h = pad * 2 + panel_h + (label_h if has_labels else 0)
    sheet = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    font = None
    if has_labels:
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 36)
        except Exception:
            try:
                from PIL import ImageFont
                font = ImageFont.load_default()
            except Exception:
                font = None

    x = pad
    for im, lab in zip(imgs, used_labels):
        sheet.paste(im, (x, pad))
        if has_labels and lab and font is not None:
            try:
                tb = draw.textbbox((0, 0), lab, font=font)
                tw = tb[2] - tb[0]
            except Exception:
                tw = len(lab) * 18
            tx = x + max(0, (im.width - tw) // 2)
            ty = pad + panel_h + (label_h - 40) // 2
            draw.text((tx, ty), lab, fill=(40, 40, 40), font=font)
        x += im.width + gap

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "PNG")
    return dest


# ============================================================
#  发送前敏感词清洗（避免 Azure 图像安全审核误判 safety_violations）
# ============================================================
#  说明：最终 prompt = 正向 + 负向 拼成一整段文本。Azure 的内容安全审核只看“词本身”，
#  不区分“禁止出现 XX”这种否定语境，因此即使我们是在负向里禁止它，也会被判定违规拦截。
#  这里在真正发送前，把这些高危词整体抹掉/替换为中性表达，保证安全意图不靠“写出敏感词”实现。
_MODERATION_BLOCKLIST: tuple[str, ...] = (
    "裸露", "性感", "暴露着装", "紧身暴露", "暴露",
    "血腥", "暴力", "惊悚", "恐怖", "怪兽",
    "持刀", "利器", "玩火", "成人隐喻", "成人化妆", "成人内容",
    "宗教符号", "政治",
    "nude", "naked", "nsfw", "sexy", "sexual", "violence", "blood", "gore",
)


def _sanitize_prompt_for_moderation(text: str) -> str:
    """剔除发送给 gpt-image-2 的高危敏感词（不区分大小写）。

    这些词通常出现在“请勿出现 XX”的负向里，但 Azure 审核只看词本身会误判。
    抹掉后留下的孤立分隔符（、；,）会被收敛，避免产生空洞标点。
    """
    if not text:
        return text
    out = text
    for w in _MODERATION_BLOCKLIST:
        if not w:
            continue
        # 大小写不敏感替换
        low = out.lower()
        token = w.lower()
        if token in low:
            start = 0
            pieces = []
            while True:
                i = low.find(token, start)
                if i < 0:
                    pieces.append(out[start:])
                    break
                pieces.append(out[start:i])
                start = i + len(token)
            out = "".join(pieces)
            low = out.lower()
    # 收敛被掏空后残留的标点/空白
    for sep in ("、、", "；；", "，，", ";;", ",,", "//", "  "):
        while sep in out:
            out = out.replace(sep, sep[0])
    out = out.replace("、；", "；").replace("，；", "；").replace("；、", "；")
    return out.strip(" 、，；,;\n")


# ============================================================
#  gpt-image-2 异步生图
# ============================================================
def generate_image(
    *,
    prompt: str,
    dest: Path,
    references: Iterable[Path | str] = (),
    mock: bool = False,
    label: str = "",
    seed: int | None = None,  # gpt-image-2 不支持 seed，签名保留兼容
    size: str | None = None,
    reference_url: str | None = None,
) -> Path:
    """生成单张图写入 dest。失败抛异常。

    Args:
        references: 参考图列表（本地 Path 或 URL），仅用第一个（gpt-image-2 单图）。
        reference_url: 直接指定参考 URL（优先于 references），链式图生图用。
        size: 覆盖默认 IMAGE_SIZE（如封面想用别的比例）。
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if mock or not JIMENG_API_KEY:
        _save_mock_image(dest, prompt, label)
        return dest

    img_size = size or IMAGE_SIZE
    ref_url = reference_url or _resolve_reference_url(references)

    url = f"{JIMENG_BASE_URL.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {JIMENG_API_KEY}",
        "Content-Type": "application/json",
    }
    safe_prompt = _sanitize_prompt_for_moderation(prompt)
    payload: dict = {
        "model": JIMENG_MODEL,
        "prompt": safe_prompt[:4000],
        "size": img_size,
        "n": 1,
    }
    if ref_url:
        payload["image"] = ref_url

    last_err: Exception | None = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            task_id = _submit_task(url, headers, payload)
            img_url = _poll_task(task_id, headers)
            img_bytes = requests.get(img_url, timeout=REQUEST_TIMEOUT).content
            dest.write_bytes(img_bytes)
            postprocess_4k(dest)   # 方案A：居中裁 4:3 → 升 4K
            return dest
        except Exception as e:
            last_err = e
            if attempt < REQUEST_RETRIES:
                time.sleep(3 * (attempt + 1))
            else:
                break

    raise RuntimeError(f"gpt-image-2 生图失败（已重试）: {last_err}")


def _submit_task(url: str, headers: dict, payload: dict) -> str:
    resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 400:
        raise RuntimeError(f"提交任务 HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    task_id = data.get("task_id") or data.get("id")
    if not task_id:
        raise RuntimeError(f"提交任务无 task_id: {json.dumps(data)[:400]}")
    return task_id


def _poll_task(task_id: str, headers: dict) -> str:
    """轮询任务直到 succeeded，返回图片 URL。"""
    poll_url = f"{JIMENG_BASE_URL.rstrip('/')}/images/generations/{task_id}"
    running = {"queued", "running", "processing", "pending", "in_progress", ""}
    for _ in range(IMAGE_POLL_MAX_TRIES):
        r = requests.get(poll_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            raise RuntimeError(f"轮询 HTTP {r.status_code}: {r.text[:300]}")
        data = r.json().get("data", {})
        status = data.get("status")
        if status == "succeeded":
            img_url = data.get("url")
            if img_url:
                return img_url
            raise RuntimeError(f"任务成功但无 url: {json.dumps(data)[:300]}")
        if status and status not in running:
            raise RuntimeError(f"任务失败 status={status} err={data.get('error')}")
        time.sleep(IMAGE_POLL_INTERVAL)
    raise RuntimeError(f"任务轮询超时（{IMAGE_POLL_MAX_TRIES}×{IMAGE_POLL_INTERVAL}s）")


def generate_image_candidates(
    *,
    prompt: str,
    dest_dir: Path,
    base_name: str,
    n: int = 3,
    references: Iterable[Path | str] = (),
    mock: bool = False,
    label: str = "",
    seeds: list[int] | None = None,
    reference_url: str | None = None,
    size: str | None = None,
) -> list[Path]:
    """单页 N 候选生图（串行调用 generate_image）。

    gpt-image-2 无 seed，多样性来自模型自身随机性。失败容错：至少返回 1 张。
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = max(1, min(n, 5))

    # 参考图只需托管一次，复用给所有候选
    ref_url = reference_url or _resolve_reference_url(references)

    results: list[Path] = []
    errors: list[str] = []
    for i in range(1, n + 1):
        dest = dest_dir / f"{base_name}_cand{i}.png"
        try:
            generate_image(
                prompt=prompt, dest=dest, mock=mock,
                label=f"{label} cand{i}", reference_url=ref_url, size=size,
            )
            results.append(dest)
        except Exception as e:
            errors.append(f"cand{i}: {e}")

    if not results:
        raise RuntimeError(f"全部 {n} 张候选图都失败：{' | '.join(errors)}")
    return results


# ---------- 占位图（无 API / mock 时） ----------
def _save_mock_image(dest: Path, prompt: str, label: str) -> None:
    w, h = 1536, 1024
    img = Image.new("RGB", (w, h), (244, 240, 232))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        v = int(232 + (y / h) * 16)
        draw.line([(0, y), (w, y)], fill=(v, v - 4, v - 12))
    draw.text((80, 80), f"[MOCK] {label}", fill=(80, 70, 60))
    y = 200
    for line in _wrap(prompt[:280], 60)[:7]:
        draw.text((80, y), line, fill=(40, 40, 40))
        y += 56
    draw.text((80, h - 100),
              "Set IMAROUTER_API_KEY in .env to render real images.",
              fill=(120, 110, 100))
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
