"""批量生产：N 个绘本大纲 → N×4 件套（绘本 PPT / 练习册 / 阅读报告 / 教师指南）。

设计要点（用户 2026-06-03 拍板）：
- 数据隔离：每本独立 BookOutline 实例，互不串混。
- N 进 N×4 出：单本失败不影响其他本，记录到日志，支持单独重跑。
- 资源管理：并发可配（ThreadPool）、单本超时 ≤30min。
- 绘本图全自动出图（不逐页停），每本标记『待人工抽查』，可事后回单本模式逐页重生。
- 输出两模式：每本子文件夹 / 平铺 + 规范命名；可选打包 ZIP。
"""
from __future__ import annotations

import json
import re
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ai_extractor import apply_extracted_to_outline, extract_all
from cn_prompt_builder import build_cn_page_prompt
from config import OUTPUTS_DIR, resolve_ip_age
from parser import BookOutline, PageSpec
from ppt_builder import build_picturebook_pptx, safe_filename
from reading_report_builder import attach_rr_questions, build_reading_report
from seedream_client import generate_image
from teacher_guide_builder import build_teacher_guide
from worksheet_builder import attach_worksheet_questions, build_worksheet

try:
    from auto_fill import auto_summary
except Exception:  # pragma: no cover
    auto_summary = None  # type: ignore

PER_BOOK_TIMEOUT_S = 30 * 60  # 单本超时 30 分钟


@dataclass
class BatchItem:
    title: str
    level: str
    book_number: str
    story: str
    cefr: str = ""
    theme: str = ""

    @property
    def name_prefix(self) -> str:
        # safe_filename 会补 .pptx 后缀，这里去掉，只要干净标题
        t = re.sub(r"\.pptx$", "", safe_filename(self.title))
        return f"Level {self.level}_Book{self.book_number}_{t}"


@dataclass
class BatchResult:
    item: BatchItem
    status: str = "pending"          # pending | ok | failed
    outputs: list[str] = field(default_factory=list)
    zip_path: str = ""
    error: str = ""
    elapsed_s: float = 0.0
    needs_human_review: bool = True  # 绘本图全自动出，标记待人工抽查


# ============================================================
#  解析批量输入
# ============================================================
def parse_batch_outlines(raw: str) -> list[BatchItem]:
    """解析多本大纲文本。每本用 `===` 分隔；每本第一行 = `Title | Level | Book#`，其后为故事。"""
    items: list[BatchItem] = []
    blocks = [b.strip() for b in re.split(r"^\s*={3,}\s*$", raw or "", flags=re.MULTILINE)]
    for blk in blocks:
        if not blk.strip():
            continue
        lines = [ln for ln in blk.splitlines() if ln.strip()]
        if not lines:
            continue
        head = lines[0]
        parts = [p.strip() for p in head.split("|")]
        title = parts[0] if parts else "Untitled"
        level = (parts[1] if len(parts) > 1 else "5").lstrip("Ll").strip() or "5"
        book_no = (parts[2] if len(parts) > 2 else "01").strip()
        # 规范 book# 两位
        if book_no.isdigit():
            book_no = f"{int(book_no):02d}"
        story = "\n".join(lines[1:]).strip()
        items.append(BatchItem(title=title, level=level, book_number=book_no, story=story))
    return items


# ============================================================
#  单本流水线（隔离）
# ============================================================
def _story_lines(story: str) -> list[str]:
    out = []
    for ln in story.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        # 去掉 "Page 1:" 前缀
        m = re.match(r"^[Pp]age\s*\d+\s*[:：]\s*(.+)$", ln)
        out.append(m.group(1).strip() if m else ln)
    return out[:7]


def run_one(item: BatchItem, out_root: Path, *, mock: bool = False,
            flat: bool = False) -> BatchResult:
    """跑一本：抽取 → outline → 生图 → 4 件套 → zip。失败抛异常由上层捕获。"""
    t0 = time.time()
    res = BatchResult(item=item)
    ip_age = resolve_ip_age(item.level)

    cefr, theme = item.cefr, item.theme
    if auto_summary and (not cefr or not theme):
        try:
            auto = auto_summary(item.level, item.story, item.title)
            cefr = cefr or auto.get("cefr", "")
            theme = theme or auto.get("theme", "")
        except Exception:
            pass

    ec = extract_all(item.story, item.title, item.level, cefr=cefr, theme=theme, mock=mock)

    pages = [PageSpec(index=0, page_type="cover", text="")]
    for i, line in enumerate(_story_lines(item.story), start=1):
        pages.append(PageSpec(index=i, page_type="story", text=line))
    # 不足 7 页补空，保证 8 页结构
    while len(pages) < 8:
        pages.append(PageSpec(index=len(pages), page_type="story", text=""))

    outline = BookOutline(
        title=item.title, pages=pages, level=item.level, book_number=item.book_number,
        cefr=cefr, ip_age=ip_age, theme=theme,
    )
    apply_extracted_to_outline(outline, ec)
    attach_rr_questions(outline, ec.rr_questions)
    attach_worksheet_questions(outline, ec.worksheet_questions, reading_q_count=4)

    # 输出目录：子文件夹 or 平铺
    book_dir = out_root if flat else (out_root / item.name_prefix)
    img_dir = book_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # 绘本全自动出图（不逐页停）
    image_paths: list[Path] = []
    for page in outline.pages:
        built = build_cn_page_prompt(page, outline, ip_age)
        dest = img_dir / f"page_{page.index:02d}.png"
        try:
            generate_image(prompt=built.prompt, dest=dest,
                           references=list(built.references)[:3],
                           label=f"{item.name_prefix} P{page.index}", mock=mock)
        except Exception as e:  # noqa: BLE001
            # 单页失败不致命：用占位让组装继续，标记待人工抽查
            generate_image(prompt=built.prompt, dest=dest, mock=True,
                           label=f"P{page.index} FALLBACK")
            res.error += f"[P{page.index} img: {e}] "
        image_paths.append(dest)

    pre = item.name_prefix
    pb = book_dir / f"{pre}_绘本.pptx"
    build_picturebook_pptx(outline, image_paths, pb)
    ws = book_dir / f"{pre}_练习册.pptx"
    build_worksheet(outline, ws, image_paths=image_paths)
    rr = book_dir / f"{pre}_阅读报告.docx"
    build_reading_report(outline, rr)
    tg = book_dir / f"{pre}_教师指南.docx"
    build_teacher_guide(outline, tg)

    res.outputs = [str(pb), str(ws), str(rr), str(tg)]

    # 单本 ZIP
    zp = book_dir / f"{pre}_全套.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in [pb, ws, rr, tg]:
            z.write(f, arcname=f.name)
        for img in image_paths:
            if img.exists():
                z.write(img, arcname=f"images/{img.name}")
    res.zip_path = str(zp)
    res.status = "ok"
    res.elapsed_s = time.time() - t0
    return res


# ============================================================
#  批量编排（并发 + 隔离 + 重试 + 日志）
# ============================================================
def run_batch(
    items: list[BatchItem],
    *,
    out_root: Optional[Path] = None,
    concurrency: int = 2,
    flat: bool = False,
    make_master_zip: bool = True,
    mock: bool = False,
    retries: int = 1,
    progress_cb: Optional[Callable[[int, int, BatchResult], None]] = None,
) -> dict:
    """跑一批。返回 summary dict（含每本结果 + 日志路径）。"""
    out_root = out_root or (OUTPUTS_DIR / f"batch_{time.strftime('%Y%m%d_%H%M%S')}")
    out_root.mkdir(parents=True, exist_ok=True)
    results: list[BatchResult] = []
    total = len(items)
    done = 0

    def _task(it: BatchItem) -> BatchResult:
        last_err = ""
        for attempt in range(retries + 1):
            try:
                return run_one(it, out_root, mock=mock, flat=flat)
            except Exception as e:  # noqa: BLE001
                last_err = f"{e}\n{traceback.format_exc()[:800]}"
                time.sleep(2)
        r = BatchResult(item=it, status="failed", error=last_err)
        return r

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futures = {ex.submit(_task, it): it for it in items}
        for fut in as_completed(futures):
            it = futures[fut]
            try:
                r = fut.result(timeout=PER_BOOK_TIMEOUT_S)
            except Exception as e:  # noqa: BLE001 (含超时)
                r = BatchResult(item=it, status="failed", error=f"timeout/exec: {e}")
            results.append(r)
            done += 1
            if progress_cb:
                progress_cb(done, total, r)

    # 主 ZIP（把每本的全套 zip 再合并）
    master_zip = ""
    if make_master_zip:
        master_zip = str(out_root / "ALL_BOOKS.zip")
        with zipfile.ZipFile(master_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for r in results:
                if r.zip_path and Path(r.zip_path).exists():
                    z.write(r.zip_path, arcname=Path(r.zip_path).name)

    # 处理日志
    log = {
        "out_root": str(out_root),
        "total": total,
        "ok": sum(1 for r in results if r.status == "ok"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "master_zip": master_zip,
        "books": [
            {
                "title": r.item.title, "level": r.item.level, "book": r.item.book_number,
                "status": r.status, "elapsed_s": round(r.elapsed_s, 1),
                "outputs": r.outputs, "zip": r.zip_path,
                "needs_human_review": r.needs_human_review, "error": r.error[:500],
            }
            for r in results
        ],
    }
    log_path = out_root / "batch_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    log["log_path"] = str(log_path)
    return log


# ============================================================
#  Streamlit 入口
# ============================================================
def run_batch_from_ui() -> None:
    """从 web_app 的 session_state 读取配置并跑批量，带进度展示。"""
    import streamlit as st

    raw = st.session_state.get("batch_outlines_raw", "")
    items = parse_batch_outlines(raw)
    if not items:
        st.warning("没解析到任何大纲。请检查格式：每本第一行 `Title | Level | Book#`，多本用 `===` 分隔。")
        return

    concurrency = int(st.session_state.get("batch_concurrency", 2))
    flat = st.session_state.get("batch_output_mode") == "平铺 + 规范命名"
    make_zip = bool(st.session_state.get("batch_zip", True))
    mock = bool(st.session_state.get("batch_mock", False))

    st.info(f"共 {len(items)} 本，将产出 {len(items) * 4} 件交付物。并发 {concurrency}。")
    bar = st.progress(0.0, "批量生产中...")
    status_box = st.empty()

    def _cb(done: int, total: int, r: BatchResult) -> None:
        bar.progress(done / total, f"已完成 {done}/{total} 本")
        icon = "✅" if r.status == "ok" else "❌"
        status_box.write(f"{icon} {r.item.name_prefix} · {r.status} · {r.elapsed_s:.0f}s {r.error[:120]}")

    summary = run_batch(
        items, concurrency=concurrency, flat=flat,
        make_master_zip=make_zip, mock=mock, progress_cb=_cb,
    )
    bar.progress(1.0, "完成")
    st.success(f"完成：成功 {summary['ok']} / 失败 {summary['failed']}，输出目录 `{summary['out_root']}`")
    st.caption("⚠️ 绘本图为全自动生成，建议回单本模式抽查关键页；失败本可单独重跑。")
    if summary.get("master_zip"):
        mz = summary["master_zip"]
        if Path(mz).exists():
            with open(mz, "rb") as f:
                st.download_button("⬇️ 下载全部（ALL_BOOKS.zip）", data=f.read(),
                                   file_name="ALL_BOOKS.zip", mime="application/zip")
    st.json(summary)
