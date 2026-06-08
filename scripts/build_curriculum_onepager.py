# -*- coding: utf-8 -*-
"""生成「0-6 课程地图」可打印一页纸（对外版：带品牌 logo + 精美版式）。

- 自包含 HTML（内嵌 logo base64），双击用浏览器打开即可看；
- 打印 CSS 已调好（A4 横向），浏览器 Ctrl/Cmd + P → 另存为 PDF 即得对外宣传页；
- 数据与 课程对标总表_L0-L6.xlsx 完全同源（import 自 build_curriculum_xlsx）；
- 级别配色 = 练习册同款（按级别一色）。
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_curriculum_xlsx import (
    DATA, HEADER_AGE, HEADER_GRADE, LEVEL_HEX, LEVELS, SUGGEST,
    level_tint_hex,
)

try:
    from config import OUTPUTS_DIR
except Exception:  # pragma: no cover
    OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "brand" / "dino_reading_logo.png"
OUT = OUTPUTS_DIR / "_framework" / "课程地图_L0-L6.html"
OUT_PDF = OUTPUTS_DIR / "_framework" / "课程地图_L0-L6.pdf"


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
            f"<th class='lv' style='--bd:{bd};background:{bd}'>"
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
            f"<span><span class='dot' style='background:{LEVEL_HEX[i]}'></span>{lv}"
            f"<small> {HEADER_AGE[i]}</small></span>"
        )
    return "".join(out)


HTML = """<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>VIPKID Dino · 0–6 课程地图</title>
<style>
  :root{{ --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --brand:#F47332; --brand-2:#ff9a4d; }}
  *{{ box-sizing:border-box; }}
  html,body{{ margin:0; padding:0; background:#f3f4f6;
    font-family:"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif; color:var(--ink); }}
  .sheet{{ width:1123px; min-height:794px; margin:18px auto; padding:26px 30px 22px;
    background:#fff; border-radius:14px; box-shadow:0 10px 40px rgba(0,0,0,.10); }}
  .top{{ display:flex; align-items:center; gap:18px; padding-bottom:14px; border-bottom:3px solid var(--brand); }}
  .top img{{ height:46px; }}
  .top .ttl{{ flex:1; }}
  .top .ttl h1{{ margin:0; font-size:23px; letter-spacing:.5px; }}
  .top .ttl p{{ margin:3px 0 0; font-size:12.5px; color:var(--muted); }}
  .top .badge{{ font-size:12px; font-weight:800; color:#fff;
    background:linear-gradient(135deg,var(--brand),var(--brand-2)); padding:7px 14px; border-radius:999px; white-space:nowrap; }}
  .legend{{ display:flex; flex-wrap:wrap; gap:13px; margin:12px 0 10px; font-size:11.5px; color:var(--ink); align-items:center; }}
  .legend small{{ color:var(--muted); }}
  .legend .dot{{ display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:5px; vertical-align:-1px; }}
  table{{ width:100%; border-collapse:collapse; table-layout:fixed; }}
  col.c-dim{{ width:120px; }}
  th,td{{ border:1px solid var(--line); padding:5px 7px; font-size:11px; line-height:1.32;
    vertical-align:top; text-align:left; word-break:break-word; }}
  th.corner{{ background:#374151; color:#fff; font-size:12px; border-color:#374151; }}
  th.lv{{ text-align:center; color:#fff; }}
  th.lv .lv-name{{ font-size:17px; font-weight:900; text-shadow:0 1px 2px rgba(0,0,0,.2); }}
  th.lv .lv-sub{{ font-size:10px; font-weight:700; opacity:.95; }}
  tr.sec .sec-cell{{ background:#374151; color:#fff; font-weight:800; font-size:12.5px; padding:6px 10px; letter-spacing:.4px; }}
  th.dim{{ background:#f3f4f6; font-weight:800; color:var(--ink); }}
  th.dim .ref{{ display:inline-block; font-size:8.5px; font-weight:700; color:#9aa1ab;
    border:1px solid #d8dce2; border-radius:4px; padding:0 3px; margin-left:4px; vertical-align:1px; }}
  .foot{{ margin-top:12px; font-size:10.5px; color:var(--muted); line-height:1.55; }}
  .foot b{{ color:var(--ink); }}
  @page{{ size:A4 landscape; margin:8mm; }}
  @media print{{
    html,body{{ background:#fff; }}
    .sheet{{ width:auto; min-height:auto; margin:0; padding:0; box-shadow:none; border-radius:0; }}
    .no-print{{ display:none !important; }}
    .top{{ padding-bottom:8px; }} .top img{{ height:38px; }} .top .ttl h1{{ font-size:19px; }}
    .legend{{ margin:7px 0 6px; }}
    th,td{{ font-size:8.4px; padding:2px 4px; line-height:1.2; }}
    th.lv .lv-name{{ font-size:13px; }} th.lv .lv-sub{{ font-size:8px; }}
    tr.sec .sec-cell{{ font-size:9.5px; padding:3px 8px; }}
    .foot{{ margin-top:7px; font-size:8px; line-height:1.4; }}
    tr{{ page-break-inside:avoid; }} tr.sec{{ page-break-after:avoid; }}
  }}
  .tipbar{{ max-width:1123px; margin:0 auto 4px; text-align:center; font-size:12px; color:var(--muted); }}
  .tipbar button{{ font:inherit; font-weight:700; color:#fff; background:var(--brand);
    border:0; border-radius:8px; padding:7px 16px; cursor:pointer; margin-left:8px; }}
</style></head>
<body>
  <div class="tipbar no-print">这是对外可打印版 · 按
    <button onclick="window.print()">打印 / 另存为 PDF（A4 横向）</button>
  </div>
  <div class="sheet">
    <div class="top">
      {logo}
      <div class="ttl">
        <h1>Levels 0–6 课程地图</h1>
        <p>一页看懂每级别：年龄学龄 · 欧标/剑桥/AR/蓝思对标 · 学习重点与考察 · 题型能力 · 学完产出</p>
      </div>
      <div class="badge">分级阅读教学体系</div>
    </div>

    <div class="legend"><span style="font-weight:800">级别配色（练习册同款）：</span>{legend}</div>

    <table>
      <colgroup><col class="c-dim"/>{cols}</colgroup>
      <thead><tr><th class="corner">维度 \\ 级别</th>{head}</tr></thead>
      <tbody>{body}</tbody>
    </table>

    <div class="foot">
      <b>权威值</b>（CEFR / 蓝思 / 解码句法 / 核心词·本 / 词汇主题 / 阅读文体 / 阅读策略·技能 / 学完产出）来自官方 S&amp;S 大纲 + TG_SOP，与系统 level_profiles 同源；
      标「参考」的维度（阅读阶段·语言发展·素质培养 / 学生年龄 / 国内·美国年级 / 剑桥 YLE·KET·PET / TOEFL / RAZ / AR 值 / 累计词汇量·阅读字数 / 核心目标 / 考察方向）依 CEFR 推导，供校准。
      &nbsp;·&nbsp; VIPKID Dino 阅读馆 · 教研与对外说明通用。
    </div>
  </div>
</body></html>
"""


def build() -> Path:
    b64 = _logo_b64()
    logo_html = (f"<img src='data:image/png;base64,{b64}' alt='VIPKID Dino 阅读馆'/>"
                 if b64 else "<span style='font-size:30px'>🦖</span>")
    cols = "".join(f"<col style='width:{(995 // len(LEVELS))}px'/>" for _ in LEVELS)
    html = HTML.format(
        logo=logo_html, cols=cols, head=_header_cells(), body=_body_rows(), legend=_legend(),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print("WROTE", OUT)
    _export_pdf()
    return OUT


def _export_pdf() -> None:
    """用 Playwright 把同源 HTML 打印为 A4 横向 PDF（失败不致命，HTML 仍可手动打印）。"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("SKIP PDF（未装 playwright，用 HTML 的打印按钮另存即可）")
        return
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(OUT.as_uri(), wait_until="networkidle", timeout=40000)
            page.pdf(path=str(OUT_PDF), landscape=True, format="A4",
                     print_background=True,
                     margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"})
            browser.close()
        print("WROTE", OUT_PDF)
    except Exception as e:  # pragma: no cover
        print("SKIP PDF（生成失败，可用 HTML 打印按钮另存）:", e)


if __name__ == "__main__":
    build()
