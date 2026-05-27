"""清洗 character_bible_l4-6.png：自动识别水印文字行并涂白。

策略：
  逐行扫描，找"窄黑像素带"（非主体的零散文字行）。
  人物绘画行的非白像素分布是大片连续的（衣服、肤色），
  而文字行是稀疏小点+大量白底，且像素带高度 < 25。
  把这些行整行涂白。

另外：硬覆盖顶部 50px 区域（Dino 绘本标题永远在这里）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw


def main(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGB")
    W, H = img.size
    px = img.load()

    # 逐行统计非白像素数（灰度 < 230 视为非白）
    dark_per_row: list[int] = [0] * H
    for y in range(H):
        cnt = 0
        for x in range(W):
            r, g, b = px[x, y]
            if (r + g + b) < 230 * 3:
                cnt += 1
        dark_per_row[y] = cnt

    # 人物绘画行非白像素通常 > W * 0.15；文字行非白像素 < W * 0.10 但 > 5
    text_row_mask = [(d > 5) and (d < int(W * 0.10)) for d in dark_per_row]

    # 把孤立的高密度行视为人物（保留），把窄文字行整行涂白
    # 找连续的 text_row 区段
    runs: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for y in range(H):
        if text_row_mask[y]:  # type: ignore[index]
            if not in_run:
                start = y
                in_run = True
        else:
            if in_run:
                runs.append((start, y - 1))
                in_run = False
    if in_run:
        runs.append((start, H - 1))

    # 只处理高度 <= 25 像素的文字带（避免误伤人物）
    short_text_runs = [(a, b) for a, b in runs if (b - a + 1) <= 30]

    # 顶部 50 px 永远涂白（标题区）
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 50], fill="white")
    for a, b in short_text_runs:
        # 适度扩边 ±2 避免残笔画
        y0 = max(0, a - 2)
        y1 = min(H - 1, b + 2)
        draw.rectangle([0, y0, W, y1], fill="white")

    img.save(dst)
    print(f"saved cleaned bible: {dst} ({len(short_text_runs)+1} bands wiped)")


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/characters/character_bible_l4-6.png")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "assets/characters/character_bible_l4-6_clean.png")
    main(src, dst)
