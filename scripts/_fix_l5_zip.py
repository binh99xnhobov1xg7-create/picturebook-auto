# -*- coding: utf-8 -*-
import glob, os, zipfile

d = r"D:\picturebook_outputs\L5_Friends_v4"
zips = glob.glob(os.path.join(d, "*.zip"))
zp = zips[0] if zips else os.path.join(d, "L5_set.zip")

bad = True
if zips:
    try:
        with zipfile.ZipFile(zp) as z:
            bad = z.testzip() is not None
            print("existing zip entries:", len(z.namelist()), "corrupt:", bad)
    except Exception as e:
        print("zip open failed:", e)
        bad = True

if bad:
    docs = [f for ext in ("*.docx", "*.pptx") for f in glob.glob(os.path.join(d, ext))
            if not os.path.basename(f).startswith("~$")]
    imgs = sorted(glob.glob(os.path.join(d, "images", "*.png")))
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in docs:
            z.write(f, arcname=os.path.basename(f))
        for f in imgs:
            z.write(f, arcname="images/" + os.path.basename(f))
    print("REBUILT zip:", zp, "docs:", len(docs), "imgs:", len(imgs),
          "size_MB:", round(os.path.getsize(zp) / 1048576, 1))
else:
    print("zip OK, no rebuild needed")
