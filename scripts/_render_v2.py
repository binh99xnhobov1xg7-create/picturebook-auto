# -*- coding: utf-8 -*-
from pathlib import Path
import fitz

OUT = Path(r"C:\Users\Jered\picturebook-auto\outputs\_ppt_assets")
pdf = next(OUT.glob("*_v2.pdf"))
doc = fitz.open(pdf)
mat = fitz.Matrix(1.5, 1.5)
for i, page in enumerate(doc):
    page.get_pixmap(matrix=mat).save(OUT / f"v2_{i:02d}.png")
print("rendered", len(doc), "slides from", pdf.name)
