"""Step 2b · 全书分页画质精修（8 页确认后 · 即梦/Seedream img2img）。

与 love_art_composite（8 页拼网格）不同：本模块逐页图生图，只做降噪/平滑/清晰度提升，
保留每页构图、剧情与文字留白区。用户 prompt 待定时可用 config.GPT_STYLE_POSITIVE 等默认值。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from config import GPT_STYLE_NEGATIVE, GPT_STYLE_POSITIVE
from seedream_client import generate_image_jimeng, is_placeholder_image, postprocess_4k


DEFAULT_REFINE_POSITIVE = GPT_STYLE_POSITIVE
DEFAULT_REFINE_NEGATIVE = GPT_STYLE_NEGATIVE

# 用户拍板的固定精修口径（2026-06）：8 图一键去噪 / 平滑 / 统一画风。
USER_REFINE_POSITIVE = (
    "clean illustration, smooth shading, soft lighting, controlled details, "
    "minimal texture, high clarity, refined edges, smooth gradients"
)
USER_REFINE_NEGATIVE = (
    "noise, grain, artifacts, high frequency detail, dirty texture, "
    "oversharpen, blotchy, chaotic details"
)


def _refine_prompt(user_positive: str, user_negative: str = "") -> str:
    """低改动 img2img 指令：强调保留内容，只优化画质。"""
    pos = (user_positive or DEFAULT_REFINE_POSITIVE).strip()
    neg = (user_negative or DEFAULT_REFINE_NEGATIVE).strip()
    body = (
        "【图生图·画质精修·不改内容】所附参考图是本页【已定稿画面】：人物数量、身份、站位、"
        "构图、道具、场景叙事、文字留白区域——全部 1:1 保留，绝不增删改剧情、绝不改布局。\n"
        "你只做画质与画风平滑优化：\n"
        f"{pos}\n"
        "硬约束：不改变画面内容与镜头；不新增可辨认文字/水印/logo；"
        "Mia 紫色上衣 + 后脑中高马尾、Tommy 浅蓝上衣 + 棕色短发等 IP 配色发型不变；"
        "同一角色只出现一次。"
    )
    if neg:
        body += f"\n避免：{neg}"
    return body


def _collect_locked_pages(img_dir: Path) -> list[Path]:
    """按页序收集 page_XX.png（跳过 _anchors、版本后缀与占位图）。"""
    if not img_dir.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for fp in sorted(img_dir.glob("page_*.png")):
        if fp.parent.name.startswith("_") or "_v" in fp.stem or "_draft" in fp.stem:
            continue
        if is_placeholder_image(fp):
            continue
        try:
            idx = int(fp.stem.split("_")[-1])
        except ValueError:
            continue
        found.append((idx, fp))
    return [p for _, p in sorted(found, key=lambda x: x[0])]


def refine_page_images(
    book_dir: Path | str,
    prompt: str = "",
    *,
    negative: str = "",
    mock: bool = False,
    deliver_print: bool = True,
    backup: bool = True,
) -> list[Path]:
    """对 book_dir/images/ 下各页执行即梦 img2img 精修，原地覆盖并可选备份。

    Args:
        book_dir: 单本书输出目录（含 images/ 子目录）。
        prompt: 用户正向精修词（空则用 config.GPT_STYLE_POSITIVE）。
        negative: 可选负向词（空则用 config.GPT_STYLE_NEGATIVE）。
        mock: True 时跳过 API（由 generate_image_jimeng mock 处理）。
        deliver_print: 精修后是否走 4:3 裁切 + 放大后处理。
        backup: 覆盖前是否备份到 images/_pre_refine/。

    Returns:
        精修后的页图路径列表。
    """
    book_dir = Path(book_dir)
    img_dir = book_dir / "images"
    pages = _collect_locked_pages(img_dir)
    if len(pages) < 7:
        raise ValueError(f"分页图不足（{len(pages)}/8），请先完成出图并确认")

    refine_prompt = _refine_prompt(prompt, negative)
    backup_dir = img_dir / "_pre_refine"
    if backup:
        backup_dir.mkdir(parents=True, exist_ok=True)

    out_paths: list[Path] = []
    for src in pages:
        if backup:
            shutil.copy2(src, backup_dir / src.name)
        tmp = src.with_name(src.stem + "_refining.png")
        generate_image_jimeng(
            prompt=refine_prompt,
            dest=tmp,
            references=[src],
            mock=mock,
            label=f"精修 {src.name}",
            deliver_print=False,
        )
        if deliver_print:
            postprocess_4k(tmp)
        tmp.replace(src)
        out_paths.append(src)
    return out_paths
