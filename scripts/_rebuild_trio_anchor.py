# -*- coding: utf-8 -*-
"""零成本重建 references/official_style/trio_style_anchor.png 为【新 IP 定妆】。

用现有干净单人锚图 mia_10.png + tommy_10.png 横向并排合成（白底、无文字），
作为"代词页/无角色页"的画风兜底，保证 Tommy=浅天蓝、Mia=后脑中高位马尾+紫色发圈。
原图先备份 .bak。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

LIB = Path("assets/ip_library")
DEST = Path("references/official_style/trio_style_anchor.png")
SRC = [LIB / "tommy_10.png", LIB / "mia_10.png"]  # 左 Tommy、右 Mia（与配色轮左→右一致）


def trim_white(im: Image.Image, thresh: int = 238, min_dark: int = 3) -> Image.Image:
    rgb = im.convert("RGB")
    g = rgb.convert("L")
    w, h = g.size
    px = g.load()
    cols = [0] * w
    rows = [0] * h
    for y in range(h):
        for x in range(w):
            if px[x, y] < thresh:
                cols[x] += 1
                rows[y] += 1
    xs = [x for x in range(w) if cols[x] >= min_dark]
    ys = [y for y in range(h) if rows[y] >= min_dark]
    if not xs or not ys:
        return rgb
    return rgb.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))


def main() -> None:
    if DEST.exists():
        bak = DEST.with_suffix(".bak.png")
        if not bak.exists():
            DEST.replace(bak)
            # replace 会移动文件；重新从 bak 读不到原图也无妨，下面只用 ip_library 合成
            print(f"备份原图 -> {bak}")
        else:
            print(f"备份已存在 -> {bak}")

    canvas_w, canvas_h = 1536, 1024
    pad = 60
    gap = 80
    bg = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    figs = [trim_white(Image.open(p).convert("RGB")) for p in SRC]
    n = len(figs)
    slot_w = (canvas_w - 2 * pad - (n - 1) * gap) // n
    avail_h = canvas_h - 2 * pad
    x = pad
    for fig in figs:
        fw, fh = fig.size
        scale = min(slot_w / fw, avail_h / fh)
        new = fig.resize((max(1, int(fw * scale)), max(1, int(fh * scale))), Image.LANCZOS)
        ox = x + (slot_w - new.size[0]) // 2
        oy = pad + (avail_h - new.size[1])  # 底对齐（脚踩同一水平线）
        bg.paste(new, (ox, oy))
        x += slot_w + gap
    DEST.parent.mkdir(parents=True, exist_ok=True)
    bg.save(DEST)
    print(f"已重建 -> {DEST}  size={bg.size}  from={[p.name for p in SRC]}")


if __name__ == "__main__":
    main()
