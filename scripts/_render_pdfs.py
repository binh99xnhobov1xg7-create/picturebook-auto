"""一次性：把 _ppt_assets 下的 4 件套 PDF 渲染成逐页 PNG（给分享 PPT 用）。"""
from pathlib import Path
import fitz  # PyMuPDF

OUT = Path(r"C:\Users\Jered\picturebook-auto\outputs\_ppt_assets")
ZOOM = 2.0  # 2x ~ 144dpi，截图清晰

mapping = {
    "Level 5_Book01_What Makes a Good Friend_Reader.pdf": "reader",
    "Level 5_Book01_What Makes a Good Friend_Worksheet.pdf": "worksheet",
    "Level 5_Book01_What Makes a Good Friend_Reading_Report.pdf": "rr",
    "Level 5_Book01_What Makes a Good Friend_Teachers_Guide.pdf": "tg",
}

for pdf_name, tag in mapping.items():
    pdf = OUT / pdf_name
    if not pdf.exists():
        print(f"[skip] missing {pdf_name}")
        continue
    doc = fitz.open(pdf)
    mat = fitz.Matrix(ZOOM, ZOOM)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        dest = OUT / f"{tag}_p{i:02d}.png"
        pix.save(dest)
        print(f"[ok] {dest.name}  {pix.width}x{pix.height}")
    doc.close()

print("DONE")
