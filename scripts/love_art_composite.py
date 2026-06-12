"""Love Art / 即梦 8 页合成增强（出图流水线最后一步 · P2 占位 hook）。

设计：
  1. 收集本书 8 张分页图（cover + p01–p07 或 page_00–page_07）
  2. 本地拼成参考网格（2×4 或 4×2）
  3. 调用即梦/Seedream 图生图（generate_image_jimeng）+ 用户 prompt（待提供）
  4. 可选：按页裁切回 8 张或整页交付一张「生动版」汇总

Web App 集成点：生图工作台 Step 4 全部页完成后，显示「Love Art 增强」按钮。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

# 用户 prompt TBD — 占位常量，P2 改为 secrets / 每书 config 绑定
LOVE_ART_DEFAULT_PROMPT = (
    "【占位】将参考网格中的儿童绘本分页统一增强为更生动、更有故事感的插画风格，"
    "保持每格人物身份/构图/叙事不变，仅提升光影、表情与氛围。"
)


def collect_page_images(img_dir: Path) -> list[Path]:
    """按页序收集最多 8 张分页图（跳过 _anchors 等内部目录）。"""
    if not img_dir.is_dir():
        return []
    patterns = (
        "cover*.png", "cover*.jpg",
        "page_0*.png", "page_*.png",
        "p0*.png", "p*.png",
    )
    found: list[Path] = []
    seen: set[str] = set()
    for pat in patterns:
        for fp in sorted(img_dir.glob(pat)):
            if fp.parent.name.startswith("_"):
                continue
            key = fp.name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(fp)
    return found[:8]


def stitch_grid(image_paths: list[Path], *, cols: int = 4) -> Image.Image:
    """将 N 张 4:3 图拼成网格（默认 2 行 × 4 列）。"""
    if not image_paths:
        raise ValueError("无分页图可合成")
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    w = max(im.width for im in imgs)
    h = max(im.height for im in imgs)
    rows = -(-len(imgs) // cols)
    canvas = Image.new("RGB", (w * cols, h * rows), (244, 240, 232))
    for i, im in enumerate(imgs):
        im_r = im.resize((w, h), Image.Resampling.LANCZOS)
        r, c = divmod(i, cols)
        canvas.paste(im_r, (c * w, r * h))
    return canvas


def compose_book_pages(
    img_dir: Path,
    dest: Path,
    *,
    prompt: str = "",
    mock: bool = False,
) -> Path:
    """P2 MVP hook：拼网格 → （TODO）即梦 img2img → 写 dest。

    当前仅落盘本地网格参考图，不调 API（prompt TBD）。
    """
    pages = collect_page_images(img_dir)
    if len(pages) < 7:
        raise ValueError(f"分页图不足（{len(pages)}/8），请先完成出图")
    grid = stitch_grid(pages)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    grid.save(dest)
    if not mock:
        # P2: from seedream_client import generate_image_jimeng
        # generate_image_jimeng(prompt=prompt or LOVE_ART_DEFAULT_PROMPT, dest=dest,
        #                       references=[dest], mock=False, label="LoveArt")
        pass
    return dest
