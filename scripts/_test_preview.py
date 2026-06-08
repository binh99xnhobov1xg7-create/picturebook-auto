import sys, time
sys.path.insert(0, "scripts")
from doc_preview import render_to_images, has_visual_preview

base = r"C:\Users\Jered\picturebook-auto\outputs\L4_BodiesOfWater_20260605_145933\Level 4_Book02_Bodies_of_Water"
files = [
    base + r"\Level 4_Book02_Bodies_of_Water_Reading_Report.docx",
    base + r"\Level 4_Book02_Bodies_of_Water_Teachers_Guide.docx",
    base + r"\Level 4_Book02_Bodies_of_Water_Worksheet.pptx",
]
print("has_visual_preview:", has_visual_preview())
for f in files:
    t = time.time()
    imgs = render_to_images(f, dpi=100, max_pages=8)
    print(f"{time.time()-t:5.1f}s  pages={len(imgs)}  {f.split(chr(92))[-1]}")
    for im in imgs[:2]:
        print("    ", im)
