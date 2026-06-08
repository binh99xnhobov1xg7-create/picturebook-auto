# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
import openpyxl
from image_prompts import match

XLSX = r"C:\Users\Jered\下载\VIPKID\大纲\Level 3-6  S&S.xlsx"
wb = openpyxl.load_workbook(XLSX, data_only=True)
ws = wb["Level 3"]
rows = [list(r) for r in ws.iter_rows(values_only=True)]
for r in rows[1:]:
    no = r[0]
    if no is None:
        continue
    try:
        n = int(no)
    except Exception:
        continue
    if 62 <= n <= 72:
        title = r[3]
        genre = r[1]
        pure = str(r[10] or "")
        t7 = str(r[9] or "")
        vocab = str(r[8] or "")
        oip = match("3", title)
        oip_tag = "YES" if oip else "no"
        print("=" * 70)
        print("#%s | %s | genre=%s | OIP=%s" % (n, title, genre, oip_tag))
        print("  pure_text len=%d  text7 len=%d" % (len(pure), len(t7)))
        print("  pure_text head:", repr(pure[:240]))
        print("  vocab:", repr(vocab[:160]))
