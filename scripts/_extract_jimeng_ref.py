"""提取即梦样书 pptx 内嵌图片，供逐图反推画风。"""
import os
import zipfile

PPTX = r"C:\Users\Jered\下载\2D L2 B60 Things That Go together-Fixed\2D L2 B60 Things That Go together-Fixed.pptx"
OUT = r"C:\Users\Jered\picturebook-auto\references\official_style\_jimeng_ref"

os.makedirs(OUT, exist_ok=True)
z = zipfile.ZipFile(PPTX)
n = 0
for name in z.namelist():
    if name.startswith("ppt/media/") and name.lower().endswith((".png", ".jpg", ".jpeg")):
        data = z.read(name)
        base = os.path.basename(name)
        dst = os.path.join(OUT, base)
        with open(dst, "wb") as f:
            f.write(data)
        print("EXTRACT:", base, len(data) // 1024, "KB")
        n += 1
print("TOTAL:", n, "->", OUT)
