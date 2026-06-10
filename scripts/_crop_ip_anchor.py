# -*- coding: utf-8 -*-
"""从角色定妆表里裁出【干净单人正视全身图】做 ip_library 锚图。

流程：按给定区域裁 FRONT 视图 → 自动去白边(near-white) → 居中贴到白底画布 → 保存。
先输出候选到 D:\\picturebook_outputs\\_ipcrop\\ 供评审，确认后再替换 assets/ip_library。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(r"C:\Users\Jered\.cursor\projects\c-Users-Jered-picturebook-auto\assets")
TOMMY = ASSETS / "c__Users_Jered_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_ChatGPT_Image_Jun_10__2026__02_06_50_AM-de785cbd-b554-497e-a583-2509ad30fb06.png"
MIA = ASSETS / "c__Users_Jered_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_ChatGPT_Image_Jun_10__2026__02_03_27_AM-5e5d5fde-80f0-4e6e-8afd-4ad755147f71.png"
OUT = Path(r"D:\picturebook_outputs\_ipcrop")


def trim_white(im: Image.Image, thresh: int = 238, min_dark: int = 3) -> Image.Image:
    """去掉四周近白边，返回内容包围盒。

    按【行/列暗像素计数】判定内容边界：一行/列至少有 min_dark 个暗像素才算内容，
    忽略零散杂点/淡线（修裁图轻微偏移、底部淡线）。
    """
    rgb = im.convert("RGB")
    gray = rgb.convert("L")
    w, h = gray.size
    px = gray.load()
    col_dark = [0] * w
    row_dark = [0] * h
    for y in range(h):
        for x in range(w):
            if px[x, y] < thresh:
                col_dark[x] += 1
                row_dark[y] += 1
    xs = [x for x in range(w) if col_dark[x] >= min_dark]
    ys = [y for y in range(h) if row_dark[y] >= min_dark]
    if not xs or not ys:
        return rgb
    return rgb.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))


def make_anchor(src: Path, box: tuple[int, int, int, int], dest: Path,
                canvas=(820, 1024), pad_frac: float = 0.06) -> None:
    im = Image.open(src).convert("RGB")
    region = im.crop(box)
    fig = trim_white(region)
    cw, ch = canvas
    pad = int(min(cw, ch) * pad_frac)
    avail_w, avail_h = cw - 2 * pad, ch - 2 * pad
    fw, fh = fig.size
    scale = min(avail_w / fw, avail_h / fh)
    new = fig.resize((max(1, int(fw * scale)), max(1, int(fh * scale))), Image.LANCZOS)
    bg = Image.new("RGB", canvas, (255, 255, 255))
    ox = (cw - new.size[0]) // 2
    oy = (ch - new.size[1]) // 2
    bg.paste(new, (ox, oy))
    dest.parent.mkdir(parents=True, exist_ok=True)
    bg.save(dest)
    print(f"  {src.name} {box} -> {dest}  (fig {fig.size} -> {new.size})", flush=True)


# 裁剪区域（FRONT 视图；可按评审结果调整）。
BOXES = {
    "tommy": (TOMMY, (196, 82, 294, 414)),
    "mia": (MIA, (106, 92, 234, 421)),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (src, box) in BOXES.items():
        make_anchor(src, box, OUT / f"{name}_10_crop.png")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
