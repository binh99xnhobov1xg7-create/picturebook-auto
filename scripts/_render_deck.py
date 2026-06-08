"""把分享 PPT 的 PDF 渲染成逐页 PNG 自检。"""
from pathlib import Path
import fitz

OUT = Path(r"C:\Users\Jered\picturebook-auto\outputs\_ppt_assets")
pdf = OUT / "VIPKID_Dino_绘本自动化_分享.pdf"
doc = fitz.open(pdf)
mat = fitz.Matrix(1.6, 1.6)
for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=mat)
    pix.save(OUT / f"deck_{i:02d}.png")
print("rendered", len(doc), "slides")
