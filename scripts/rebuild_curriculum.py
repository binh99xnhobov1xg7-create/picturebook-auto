# -*- coding: utf-8 -*-
"""一键重建「课程级别介绍」全部对外物料（数据/长图改完后跑这一个就够）。

依次重建（全部同源自 build_curriculum_xlsx.DATA）：
  1. 课程对标总表_L0-L6.xlsx   （教研/销售）
  2. 课程地图_L0-L6.html + .pdf （对外一页纸，A4 横向）
  3. 课程级别长图_L0-L6.png     （竖版长图，微信/朋友圈分享）

网页 (web_app.py) 的下载按钮在每次交互时实时读取这些文件，并且 Streamlit 以
runOnSave 运行——所以跑完本脚本，同事网址下次刷新即是最新，无需重启服务。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    import build_curriculum_xlsx
    import build_curriculum_onepager
    import build_curriculum_longimg

    print(">> 1/3 Excel 对标总表 ...")
    build_curriculum_xlsx.build()
    print(">> 2/3 一页纸 HTML + PDF ...")
    build_curriculum_onepager.build()
    print(">> 3/3 竖版长图 PNG ...")
    build_curriculum_longimg.build()
    _sync_bundle_to_repo()
    print("\n全部重建完成。同事网址 / Streamlit Cloud 下次刷新即为最新。")


def _sync_bundle_to_repo() -> None:
    """把生成物同步进 assets/curriculum，供 Streamlit Cloud 免 Playwright 部署。"""
    import shutil

    from config import OUTPUTS_DIR

    bundled = Path(__file__).resolve().parent.parent / "assets" / "curriculum"
    bundled.mkdir(parents=True, exist_ok=True)
    fw = OUTPUTS_DIR / "_framework"
    for name in (
        "课程对标总表_L0-L6.xlsx",
        "课程地图_L0-L6.html",
        "课程地图_L0-L6.pdf",
        "课程级别长图_L0-L6.png",
    ):
        src = fw / name
        if src.exists():
            shutil.copy2(src, bundled / name)
            print("  bundled", name)


if __name__ == "__main__":
    main()
