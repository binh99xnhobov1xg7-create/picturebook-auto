# -*- coding: utf-8 -*-
"""从 dino_logo.png 设定图里抠出单个 Dino 姿势（白底转透明 + 自动裁剪）。"""
from pathlib import Path
from PIL import Image

SRC = Path(r"C:\Users\Jered\picturebook-auto\assets\brand\dino_logo.png")
OUT = Path(r"C:\Users\Jered\picturebook-auto\outputs\_ppt_assets")

im = Image.open(SRC).convert("RGBA")
W, H = im.size
print("source", W, H)

# 按观察的设定图布局给出大致区域（相对比例，稳健）
regions = {
    "dino_front":  (0.02, 0.33, 0.18, 0.74),   # 左1 正面大图
    "dino_side":   (0.18, 0.33, 0.34, 0.74),   # 左3 侧面
    "dino_wave":   (0.64, 0.05, 0.80, 0.34),    # 右上 招手
    "dino_think":  (0.80, 0.05, 0.98, 0.34),    # 右上 托腮
    "dino_point":  (0.62, 0.38, 0.80, 0.68),    # 右中 指
    "dino_hi":     (0.80, 0.38, 0.99, 0.70),    # 右中 双手
    "dino_cheer":  (0.80, 0.70, 0.99, 0.99),    # 右下 欢呼
    "dino_shy":    (0.62, 0.70, 0.80, 0.99),    # 右下 害羞
}


def white_to_transparent(crop, thresh=238):
    crop = crop.convert("RGBA")
    px = crop.load()
    w, h = crop.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= thresh and g >= thresh and b >= thresh:
                px[x, y] = (r, g, b, 0)
    return crop


def autocrop(img):
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


for name, (l, t, r, b) in regions.items():
    box = (int(l * W), int(t * H), int(r * W), int(b * H))
    crop = im.crop(box)
    crop = white_to_transparent(crop)
    crop = autocrop(crop)
    dest = OUT / f"{name}.png"
    crop.save(dest)
    print(f"[ok] {dest.name} {crop.size}")

print("DONE")
