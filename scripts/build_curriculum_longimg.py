# -*- coding: utf-8 -*-
"""生成「0-6 课程级别介绍」竖版长图 PNG（对外分享 / 朋友圈·微信首选）。

形态参考 VIPKID 主修课 / 北美外教阅读课对标长图：级别为列、维度为行的整张
对比表，按级别配色（练习册同款），不压缩成一页，整体偏竖长（长图）。

实现：与 课程对标总表_L0-L6.xlsx / 课程地图_L0-L6.html 完全同源（import 自
build_curriculum_xlsx 的 DATA / 表头 / 配色），渲染竖版 HTML 后用 Playwright
截全页导出 PNG，保证清晰、可直接发图。
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_curriculum_xlsx import (  # noqa: E402
    DATA, HEADER_AGE, HEADER_GRADE, LEVEL_HEX, LEVELS, SUGGEST,
    level_tint_hex,
)

try:
    from config import OUTPUTS_DIR
except Exception:  # pragma: no cover
    OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "brand" / "dino_reading_logo.png"
OUT_HTML = OUTPUTS_DIR / "_framework" / "_longimg_source.html"
OUT_PNG = OUTPUTS_DIR / "_framework" / "课程级别长图_L0-L6.png"

# 竖版长图整体宽度（微信/朋友圈友好）：维度列 + 7 个级别列
WIDTH = 1242


def _logo_b64() -> str:
    try:
        return base64.b64encode(LOGO.read_bytes()).decode("ascii")
    except Exception:
        return ""


def _header_cells() -> str:
    out = []
    for i, lv in enumerate(LEVELS):
        bd = LEVEL_HEX[i]
        out.append(
            f"<th class='lv' style='background:{bd}'>"
            f"<div class='lv-name'>{lv}</div>"
            f"<div class='lv-sub'>{HEADER_AGE[i]}</div>"
            f"<div class='lv-sub'>{HEADER_GRADE[i]}</div></th>"
        )
    return "".join(out)


def _body_rows() -> str:
    rows = []
    for section, dims in DATA.items():
        rows.append(
            f"<tr class='sec'><td class='sec-cell' colspan='{1 + len(LEVELS)}'>{section}</td></tr>"
        )
        for dim, vals in dims.items():
            ref = "<span class='ref'>参考</span>" if dim in SUGGEST else ""
            tds = [f"<th class='dim' scope='row'>{dim}{ref}</th>"]
            for i, v in enumerate(vals):
                tds.append(f"<td style='background:#{level_tint_hex(i)}'>{v}</td>")
            rows.append("<tr>" + "".join(tds) + "</tr>")
    return "\n".join(rows)


def _legend() -> str:
    out = []
    for i, lv in enumerate(LEVELS):
        out.append(
            f"<span class='lg'><span class='dot' style='background:{LEVEL_HEX[i]}'></span>"
            f"{lv}<small> {HEADER_AGE[i]}</small></span>"
        )
    return "".join(out)


HTML = """<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<style>
  :root{{ --ink:#1f2937; --muted:#6b7280; --line:#e7eaef; --brand:#F47332; --brand-2:#ff9a4d; }}
  *{{ box-sizing:border-box; margin:0; padding:0; }}
  html,body{{ background:#fff; font-family:"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif; color:var(--ink); }}
  .page{{ width:{width}px; padding:34px 30px 26px; background:
      radial-gradient(1200px 300px at 50% -120px, #fff3ea 0%, #ffffff 60%); }}
  .top{{ display:flex; align-items:center; gap:18px; padding-bottom:18px;
      border-bottom:4px solid var(--brand); }}
  .top img{{ height:56px; }}
  .top .ttl{{ flex:1; }}
  .top .ttl h1{{ font-size:30px; letter-spacing:.5px; }}
  .top .ttl p{{ margin-top:6px; font-size:14px; color:var(--muted); }}
  .top .badge{{ font-size:14px; font-weight:800; color:#fff;
      background:linear-gradient(135deg,var(--brand),var(--brand-2));
      padding:10px 18px; border-radius:999px; white-space:nowrap; }}
  .legend{{ display:flex; flex-wrap:wrap; gap:16px; margin:16px 0 14px; align-items:center; }}
  .legend .lg{{ font-size:13px; font-weight:700; }}
  .legend small{{ color:var(--muted); font-weight:400; }}
  .legend .dot{{ display:inline-block; width:14px; height:14px; border-radius:4px;
      margin-right:6px; vertical-align:-2px; }}
  table{{ width:100%; border-collapse:separate; border-spacing:0; table-layout:fixed;
      border-radius:14px; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,.08); }}
  col.c-dim{{ width:150px; }}
  th,td{{ border-bottom:1px solid var(--line); border-right:1px solid var(--line);
      padding:11px 12px; font-size:13.5px; line-height:1.5; vertical-align:middle;
      text-align:left; word-break:break-word; }}
  th.corner{{ background:#2f3742; color:#fff; font-size:15px; border-color:#2f3742;
      text-align:center; }}
  th.lv{{ text-align:center; color:#fff; vertical-align:middle; }}
  th.lv .lv-name{{ font-size:22px; font-weight:900; text-shadow:0 1px 3px rgba(0,0,0,.25); }}
  th.lv .lv-sub{{ font-size:11.5px; font-weight:700; opacity:.96; }}
  tr.sec .sec-cell{{ background:#2f3742; color:#fff; font-weight:800; font-size:15px;
      padding:10px 14px; letter-spacing:.6px; }}
  th.dim{{ background:#f5f7fa; font-weight:800; color:var(--ink); font-size:13.5px; }}
  th.dim .ref{{ display:inline-block; font-size:10px; font-weight:700; color:#9aa1ab;
      border:1px solid #d8dce2; border-radius:5px; padding:0 5px; margin-left:6px;
      vertical-align:1px; }}
  tbody tr:hover td{{ filter:brightness(.985); }}
  .foot{{ margin-top:18px; font-size:12.5px; color:var(--muted); line-height:1.7; }}
  .foot b{{ color:var(--ink); }}
</style></head>
<body>
  <div class="page">
    <div class="top">
      {logo}
      <div class="ttl">
        <h1>Levels 0–6 课程级别介绍</h1>
        <p>一图看懂每个级别：阶段与培养目标 · 欧标/剑桥/TOEFL/RAZ/AR/蓝思对标 · 语言知识 · 阅读策略与技能 · 题型能力 · 学完产出</p>
      </div>
      <div class="badge">分级阅读教学体系</div>
    </div>

    <div class="legend"><span style="font-weight:800;font-size:13px">级别配色（练习册同款）：</span>{legend}</div>

    <table>
      <colgroup><col class="c-dim"/>{cols}</colgroup>
      <thead><tr><th class="corner">维度 \\ 级别</th>{head}</tr></thead>
      <tbody>{body}</tbody>
    </table>

    <div class="foot">
      <b>权威值</b>（CEFR / 蓝思 / 解码句法 / 核心词·本 / 词汇主题 / 阅读文体 / 阅读策略·技能 / 学完产出）来自官方 S&amp;S 大纲 + TG_SOP，与系统 level_profiles 同源；
      标「参考」的维度（阶段·语言发展·素质培养 / 学生年龄 / 国内·美国年级 / 剑桥 YLE·KET·PET / TOEFL / RAZ / AR 值 / 累计词汇量·阅读字数 / 核心目标 / 考察方向）依 CEFR 推导，供校准。
      &nbsp;·&nbsp; VIPKID Dino 阅读馆 · 教研与对外说明通用。
    </div>
  </div>
</body></html>
"""


def _build_html() -> str:
    b64 = _logo_b64()
    logo_html = (f"<img src='data:image/png;base64,{b64}' alt='VIPKID Dino 阅读馆'/>"
                 if b64 else "<span style='font-size:40px'>🦖</span>")
    col_w = (WIDTH - 60 - 150) // len(LEVELS)
    cols = "".join(f"<col style='width:{col_w}px'/>" for _ in LEVELS)
    return HTML.format(
        width=WIDTH, logo=logo_html, cols=cols,
        head=_header_cells(), body=_body_rows(), legend=_legend(),
    )


def build() -> Path:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(_build_html(), encoding="utf-8")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP PNG（未装 playwright；Streamlit Cloud 使用 assets/curriculum 内置长图）")
        return OUT_HTML

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": 1600}, device_scale_factor=2,
        )
        page = context.new_page()
        page.goto(OUT_HTML.as_uri(), wait_until="networkidle", timeout=40000)
        page.wait_for_timeout(400)
        page.locator(".page").screenshot(path=str(OUT_PNG))
        browser.close()
    print("WROTE", OUT_PNG)
    return OUT_PNG


if __name__ == "__main__":
    build()
