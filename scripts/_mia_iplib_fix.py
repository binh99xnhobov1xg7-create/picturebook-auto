"""一次性修复：把 ip_library/mia_{8,10,12}.png(旧高马尾) 替换为 characters/mia_age{N}.png(half-up)。
- 替换前把当前马尾版备份为 mia_{N}.ponytail.bak.png(已存在则跳过, 不覆盖)。
- 写入时保持与原 ip_library 文件一致的尺寸/色彩模式, 避免下游引用破裂。
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IPLIB = ROOT / "assets" / "ip_library"
CHARS = ROOT / "assets" / "characters"

PAIRS = {
    8:  (IPLIB / "mia_8.png",  CHARS / "mia_age8.png"),
    10: (IPLIB / "mia_10.png", CHARS / "mia_age10.png"),
    12: (IPLIB / "mia_12.png", CHARS / "mia_age12.png"),
}

for age, (dst, src) in PAIRS.items():
    cur = Image.open(dst)
    tgt_size, tgt_mode = cur.size, cur.mode
    cur.close()

    bak = dst.with_name(f"mia_{age}.ponytail.bak.png")
    if bak.exists():
        print(f"[age{age}] 备份已存在, 跳过: {bak.name}")
    else:
        Image.open(dst).save(bak)
        print(f"[age{age}] 已备份当前马尾版 -> {bak.name}")

    img = Image.open(src)
    if img.size != tgt_size:
        img = img.resize(tgt_size, Image.LANCZOS)
    if img.mode != tgt_mode:
        if tgt_mode == "RGB" and img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        else:
            img = img.convert(tgt_mode)
    img.save(dst)
    out = Image.open(dst)
    print(f"[age{age}] 已写入 half-up -> {dst.name}  size={out.size} mode={out.mode}")
    out.close()

print("DONE")
