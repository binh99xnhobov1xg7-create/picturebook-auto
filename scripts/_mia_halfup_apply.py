"""临时脚本：把通过自检的 half-up 候选图替换两处正式 Mia 定妆图，替换前自动备份。

- 候选：D:\\picturebook_outputs\\_mia_ref_new\\mia_{age}_cand{K}.png
- 目标(两处)：assets/ip_library/mia_{age}.png 与 assets/characters/mia_age{age}.png
- 备份：原文件 -> 同名 *.bak.png（若 .bak.png 已存在则不覆盖备份）
- 尺寸/比例：候选等比缩放后白底居中贴入【与原图完全相同的 W×H 画布】（不拉伸变形），
  保存时沿用原图色彩模式（RGB/RGBA）。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(r"C:\Users\Jered\picturebook-auto")
CAND_DIR = Path(r"D:\picturebook_outputs\_mia_ref_new")

# age -> (选用候选编号, [两处目标正式文件])
PLAN = {
    8:  (1, [ROOT / "assets/ip_library/mia_8.png",  ROOT / "assets/characters/mia_age8.png"]),
    10: (1, [ROOT / "assets/ip_library/mia_10.png", ROOT / "assets/characters/mia_age10.png"]),
    12: (1, [ROOT / "assets/ip_library/mia_12.png", ROOT / "assets/characters/mia_age12.png"]),
}


def conform(src: Path, w: int, h: int, mode: str) -> Image.Image:
    """候选等比缩放 + 白底居中贴入 w×h 画布（不变形、不裁切）。"""
    im = Image.open(src).convert("RGB")
    sw, sh = im.size
    scale = min(w / sw, h / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    canvas.paste(im2, ((w - nw) // 2, (h - nh) // 2))
    return canvas.convert("RGBA") if mode == "RGBA" else canvas


def main() -> None:
    for age, (cand_k, targets) in PLAN.items():
        src = CAND_DIR / f"mia_{age}_cand{cand_k}.png"
        if not src.exists():
            print(f"[age{age}] 候选缺失，跳过：{src}")
            continue
        for tgt in targets:
            with Image.open(tgt) as orig:
                w, h = orig.size
                mode = orig.mode
            bak = tgt.with_suffix(".bak.png")
            if bak.exists():
                print(f"[age{age}] 备份已存在(不覆盖)：{bak.name}")
            else:
                shutil.copy2(tgt, bak)
                print(f"[age{age}] 备份：{tgt.name} -> {bak.name}")
            out = conform(src, w, h, mode)
            out.save(tgt)
            print(f"[age{age}] 替换：{tgt}  ({w}x{h}, {mode})  <- cand{cand_k}")
    print("DONE")


if __name__ == "__main__":
    main()
