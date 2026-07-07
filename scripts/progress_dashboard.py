"""绘本生产进度看板：大纲书目 × 钉钉进度表优先，本地输出扫描兜底。"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import OUTPUTS_DIR
from progress_milestones import (
    KEY_MILESTONES,
    MILESTONE_KEYS,
    MILESTONE_NAMES,
    milestone_done_count,
    milestone_next_pending,
    resolve_book_milestones,
)
from seedream_client import scan_placeholder_pages
from syllabus import SyllabusEntry, get_by_number, load_syllabus

_REPO = Path(__file__).resolve().parents[1]
_DINGTALK_SYNC_STATE = _REPO / "references" / "syllabus" / "_dingtalk_cache" / "sync_state.json"
_DINGTALK_REQ_MD = _REPO / "references" / "dingtalk" / "requirements.md"
_DINGTALK_PROGRESS_CACHE = _REPO / "references" / "syllabus" / "progress_status.json"

_BOOK_DIR_RE = re.compile(r"^Level\s+(\d+)_Book(\d+)_(.+)$", re.I)


def _can_run_dingtalk_sync() -> bool:
    """Only show live DingTalk sync where the local dws CLI is available."""
    return shutil.which("dws") is not None

# 流水线步骤 → 磁盘产物映射（story 来自大纲 SSOT，其余扫输出目录）
PIPELINE_STEPS: list[tuple[str, str, str]] = [
    ("story", "故事/大纲", "syllabus"),
    ("images", "分页出图", "images/"),
    ("ppt", "绘本 PPT", "_Reader.pptx"),
    ("ws", "练习册 WS", "_Worksheet.pptx"),
    ("rr", "阅读报告 RR", "_Reading_Report.docx"),
    ("tg", "教师指南 TG", "_Teachers_Guide.docx"),
    ("zip", "ZIP 打包", ".zip"),
]

_STATUS_LABEL = {
    "done": "✅ 完成",
    "partial": "🟡 进行中",
    "pending": "⬜ 未开始",
}

_GROUP_LABELS = {
    "picture_ppt": "绘本/PPT",
    "worksheet": "Worksheet",
    "reading_report": "Reading Report",
    "review_check": "审核/反馈",
    "final_publish": "终检/发布",
    "other": "其他",
}

_TIMELINE_CELL_LABEL = {
    "done": "✅ Done",
    "pending": "⬜",
    "warn": "🟡",
    "blocked": "🔴",
}


@dataclass
class BookArtifacts:
    level: str
    book_number: str
    title: str
    output_dir: Path | None = None
    steps: dict[str, bool] = field(default_factory=dict)
    status: str = "pending"  # done | partial | pending
    progress_pct: int = 0
    genre: str = ""
    manual_todos: list[str] = field(default_factory=list)
    placeholder_pages: list[int] = field(default_factory=list)
    current_step: str = ""
    owner: str = ""
    progress_updated_at: str = ""
    progress_source: str = "local"  # dingtalk | local
    progress_source_label: str = "本地输出扫描（降级）"
    raw_status: str = ""
    timeline_steps: list[dict[str, Any]] = field(default_factory=list)
    raw_fields: dict[str, Any] = field(default_factory=dict)
    timeline_done_count: int = 0
    timeline_total_count: int = 0
    timeline_done_pct: int = 0
    completed_steps: list[str] = field(default_factory=list)
    next_pending_step: str = ""
    pending_steps: list[str] = field(default_factory=list)
    blocked_steps: list[str] = field(default_factory=list)
    # 钉钉关键里程碑（6 项）：{milestone_key: {done, state, column, label, ...}}
    milestones: dict[str, dict[str, Any]] = field(default_factory=dict)
    milestone_done_count: int = 0
    milestone_next: str = ""

    @property
    def level_book(self) -> str:
        bn = self.book_number or "—"
        return f"L{self.level} · Book {bn}"


def _norm_book_num(n: str) -> str:
    s = str(n or "").strip()
    try:
        return str(int(float(s)))
    except Exception:
        return s


def _scan_book_dir(book_dir: Path) -> dict[str, bool]:
    """检测单本书目录内各步骤产物是否存在。"""
    name = book_dir.name
    steps: dict[str, bool] = {"story": True}  # 命中输出目录时大纲视为已有

    # 分页出图：images/ 下至少 7 张页图或封面+页
    img_dir = book_dir / "images"
    if img_dir.is_dir():
        imgs = [
            p for p in img_dir.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
            and not p.name.startswith("_")
        ]
        page_like = [p for p in imgs if re.search(r"p\d{2}|page|cover", p.name, re.I)]
        steps["images"] = len(page_like) >= 7 or len(imgs) >= 8
    else:
        steps["images"] = False

    for key, _label, suffix in PIPELINE_STEPS[2:]:
        if suffix == ".zip":
            steps["zip"] = any(
                p.suffix.lower() == ".zip" and name in p.stem
                for p in book_dir.iterdir()
                if p.is_file()
            )
        else:
            steps[key] = any(
                p.name.endswith(suffix) for p in book_dir.iterdir() if p.is_file()
            )
    return steps


def _status_from_steps(steps: dict[str, bool]) -> tuple[str, int]:
    keys = [s[0] for s in PIPELINE_STEPS]
    done_n = sum(1 for k in keys if steps.get(k))
    total = len(keys)
    pct = int(done_n / total * 100) if total else 0
    # 四件套 + 出图 + ZIP 才算完成
    kit_keys = ("images", "ppt", "ws", "rr", "tg", "zip")
    if all(steps.get(k) for k in kit_keys):
        return "done", pct
    if done_n > 1 or steps.get("images") or steps.get("ppt"):
        return "partial", pct
    if steps.get("story"):
        return "pending", pct
    return "pending", pct


def _book_cache_key(level: str, book_number: str) -> str:
    return f"L{_norm_book_num(level)}-B{_norm_book_num(book_number)}"


def _title_cache_key(level: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", str(title or "").lower())
    return f"L{_norm_book_num(level)}-T{slug}"


@lru_cache(maxsize=2)
def load_progress_cache() -> dict[str, Any]:
    """读取钉钉生产进度缓存。

    缓存由 scripts/sync_progress_from_dingtalk.py 生成。存在有效记录时，
    看板的 done/partial/pending 全部以它为准；磁盘扫描只保留为产物明细。
    """
    if not _DINGTALK_PROGRESS_CACHE.is_file():
        return {
            "available": False,
            "meta": {
                "reason": "未找到 progress_status.json",
                "cache_path": str(_DINGTALK_PROGRESS_CACHE),
            },
            "books": {},
        }
    try:
        payload = json.loads(_DINGTALK_PROGRESS_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {
            "available": False,
            "meta": {
                "reason": f"进度缓存不可读: {e}",
                "cache_path": str(_DINGTALK_PROGRESS_CACHE),
            },
            "books": {},
        }
    books = payload.get("books") if isinstance(payload, dict) else {}
    meta = payload.get("_meta") if isinstance(payload, dict) else {}
    if not isinstance(books, dict) or not books:
        return {
            "available": False,
            "meta": {
                **(meta if isinstance(meta, dict) else {}),
                "reason": "进度缓存没有逐本记录",
                "cache_path": str(_DINGTALK_PROGRESS_CACHE),
            },
            "books": {},
        }
    return {
        "available": True,
        "meta": meta if isinstance(meta, dict) else {},
        "books": books,
    }


def progress_source_status() -> dict[str, Any]:
    cache = load_progress_cache()
    meta = cache.get("meta") or {}
    if cache.get("available"):
        return {
            "mode": "dingtalk",
            "label": "钉钉进度表",
            "last_synced": str(meta.get("synced_at", ""))[:19].replace("T", " ") or "—",
            "source_url": str(meta.get("source_url", "")),
            "record_count": int(meta.get("record_count") or len(cache.get("books") or {})),
            "cache_path": str(_DINGTALK_PROGRESS_CACHE),
            "warnings": meta.get("warnings") or [],
            "done_definition": str(meta.get("done_definition", "")),
        }
    return {
        "mode": "local",
        "label": "本地输出扫描（降级）",
        "last_synced": "—",
        "source_url": "",
        "record_count": 0,
        "cache_path": str(_DINGTALK_PROGRESS_CACHE),
        "warnings": [str(meta.get("reason") or "缺少钉钉进度缓存")],
        "done_definition": "本地降级：仅按输出目录产物估算，不代表真实团队进度。",
    }


def _steps_from_progress_record(record: dict[str, Any]) -> dict[str, bool]:
    steps = record.get("steps")
    if isinstance(steps, dict):
        return {k: bool(steps.get(k)) for k, _label, _artifact in PIPELINE_STEPS}
    status = str(record.get("status") or "pending")
    return {k: (status == "done" or k == "story") for k, _label, _artifact in PIPELINE_STEPS}


def _timeline_from_progress_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    steps = record.get("timeline_steps")
    if isinstance(steps, list):
        return [s for s in steps if isinstance(s, dict) and s.get("label")]
    raw = record.get("raw_fields")
    if not isinstance(raw, dict):
        return []
    meta_keys = {"level_raw", "sequence_order", "title", "production_core_team", "sheet"}
    timeline: list[dict[str, Any]] = []
    for idx, (raw_key, entry) in enumerate(raw.items()):
        if raw_key in meta_keys:
            continue
        if isinstance(entry, dict):
            label = str(entry.get("label") or raw_key)
            text = str(entry.get("value") or "").strip()
            key = str(entry.get("key") or raw_key)
            column = str(entry.get("column") or "")
            group_label = str(entry.get("group_label") or "")
            sub_label = str(entry.get("sub_label") or "")
        else:
            label = str(raw_key)
            text = str(entry or "").strip()
            key = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", label.lower()).strip("_")[:80] or f"col{idx}"
            column = ""
            group_label = ""
            sub_label = ""
        low = text.lower()
        done = bool(text) and "未完成" not in text and ("done" in low or "完成" in text)
        if done:
            state = "done"
        elif any(x in low for x in ("issue", "blocked", "问题", "不通过", "失败", "错误")):
            state = "blocked"
        elif any(x in low for x in ("fix", "修改", "待改", "need", "check", "review", "反馈")):
            state = "warn"
        elif text:
            state = "warn"
        else:
            state = "pending"
        timeline.append({
            "key": key,
            "label": label,
            "column": column,
            "group_label": group_label,
            "sub_label": sub_label,
            "value": text,
            "state": state,
            "done": done,
            "group": "other",
        })
    return timeline


def _timeline_counts(steps: list[dict[str, Any]]) -> tuple[int, int, int]:
    total = len(steps)
    done = sum(1 for s in steps if s.get("done") or s.get("state") == "done")
    pct = int(done / total * 100) if total else 0
    return done, total, pct


def _timeline_cell(step: dict[str, Any] | None) -> str:
    if not step:
        return "—"
    state = str(step.get("state") or "pending")
    text = _TIMELINE_CELL_LABEL.get(state, "⬜")
    value = str(step.get("value") or "").strip()
    if state == "done":
        return text
    if value:
        return f"{text} {value}"
    return text


def _timeline_rollup(steps: list[dict[str, Any]]) -> tuple[list[str], str, list[str], list[str]]:
    def step_label(step: dict[str, Any]) -> str:
        return str(step.get("label") or step.get("key") or "").strip()

    completed = [step_label(s) for s in steps if s.get("done") or s.get("state") == "done"]
    pending = [step_label(s) for s in steps if s.get("state") == "pending"]
    blocked = [step_label(s) for s in steps if s.get("state") in {"blocked", "warn"}]
    next_pending = ""
    for step in steps:
        if not (step.get("done") or step.get("state") == "done"):
            next_pending = step_label(step)
            break
    return completed, next_pending, pending, blocked


def _pipeline_step_stats(by_level: dict[str, list[BookArtifacts]]) -> list[dict[str, Any]]:
    order: list[str] = []
    stats: dict[str, dict[str, Any]] = {}
    for books in by_level.values():
        for b in books:
            seen_in_book: set[str] = set()
            for step in b.timeline_steps:
                step_key = str(step.get("key") or step.get("label") or "").strip()
                label = str(step.get("label") or "").strip()
                if not step_key or step_key in seen_in_book:
                    continue
                seen_in_book.add(step_key)
                if step_key not in stats:
                    order.append(step_key)
                    col = str(step.get("column") or "").strip()
                    stats[step_key] = {
                        "列": col or "—",
                        "列Key": step_key,
                        "环节": label,
                        "分组": _GROUP_LABELS.get(str(step.get("group") or "other"), "其他"),
                        "Done": 0,
                        "问题/警告": 0,
                        "总数": 0,
                    }
                stats[step_key]["总数"] += 1
                if step.get("done") or step.get("state") == "done":
                    stats[step_key]["Done"] += 1
                elif step.get("state") in ("blocked", "warn"):
                    stats[step_key]["问题/警告"] += 1
    rows = [stats[key] for key in order]
    for row in rows:
        total = int(row.get("总数") or 0)
        done = int(row.get("Done") or 0)
        row["完成率"] = f"{int(done / total * 100) if total else 0}%"
    return rows


def _timeline_columns_from_stats(progress_cache: dict[str, Any], by_level: dict[str, list[BookArtifacts]]) -> list[dict[str, Any]]:
    meta = progress_cache.get("meta") if isinstance(progress_cache, dict) else {}
    raw_cols = meta.get("timeline_columns") if isinstance(meta, dict) else None
    columns: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw_cols, list):
        for col in raw_cols:
            if not isinstance(col, dict):
                continue
            key = str(col.get("key") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            columns.append(col)
    if columns:
        return columns
    for books in by_level.values():
        for b in books:
            for step in b.timeline_steps:
                key = str(step.get("key") or "").strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                columns.append({
                    "key": key,
                    "excel_col": step.get("excel_col") or step.get("column") or "",
                    "display_label": step.get("display_label") or step.get("label") or key,
                    "label": step.get("label") or key,
                    "group_header": step.get("group_header") or step.get("group_label") or "",
                    "sub_header": step.get("sub_header") or step.get("sub_label") or "",
                })
    return columns


@lru_cache(maxsize=4)
def scan_output_index(outputs_root: str) -> dict[tuple[str, str], tuple[Path, dict[str, bool]]]:
    """递归扫描输出根目录，按 (level, book_number) 索引最佳匹配目录。"""
    root = Path(outputs_root)
    if not root.is_dir():
        return {}

    index: dict[tuple[str, str], tuple[Path, dict[str, bool], float]] = {}
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        m = _BOOK_DIR_RE.match(d.name)
        if not m:
            continue
        lvl, bn, _title = m.group(1), _norm_book_num(m.group(2)), m.group(3)
        steps = _scan_book_dir(d)
        score = sum(1 for v in steps.values() if v)
        try:
            mtime = d.stat().st_mtime
        except OSError:
            mtime = 0.0
        key = (lvl, bn)
        prev = index.get(key)
        if prev is None or (score, mtime) > (prev[2], prev[3] if len(prev) > 3 else 0):
            index[key] = (d, steps, score, mtime)

    return {k: (v[0], v[1]) for k, v in index.items()}


def _load_batch_review_flag(out_dir: Path | None, level: str, book_number: str) -> bool:
    """扫描输出目录及父级 batch_log，该书是否标记 needs_human_review。"""
    if not out_dir:
        return False
    want_lvl = _norm_book_num(level)
    want_bn = _norm_book_num(book_number)
    candidates: list[Path] = []
    for p in [out_dir, *out_dir.parents[:4]]:
        candidates.extend(sorted(p.glob("batch_log.json"), reverse=True))
        candidates.extend(sorted(p.glob("*summary.json"), reverse=True))
    seen: set[str] = set()
    for log_path in candidates:
        key = str(log_path.resolve())
        if key in seen or not log_path.is_file():
            continue
        seen.add(key)
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        books = data.get("books")
        if isinstance(books, list):
            for b in books:
                if not isinstance(b, dict) or not b.get("needs_human_review"):
                    continue
                bn = _norm_book_num(str(b.get("book_number", "")))
                lvl = _norm_book_num(str(b.get("level", "")))
                if bn == want_bn and lvl == want_lvl:
                    return True
    return False


def compute_manual_todos(art: BookArtifacts) -> tuple[list[str], list[int]]:
    """待您手动列：占位页 / RR 审阅 / 大纲待确认。"""
    todos: list[str] = []
    ph_pages: list[int] = []
    steps = art.steps or {}

    if not art.output_dir:
        todos.append("大纲待确认")
        return todos, ph_pages

    img_dir = art.output_dir / "images"
    ph_pages = scan_placeholder_pages(img_dir) if img_dir.is_dir() else []
    if ph_pages:
        todos.append(f"占位页×{len(ph_pages)}")

    if steps.get("images") and not steps.get("rr"):
        todos.append("RR待出/审")
    elif steps.get("rr") and art.status != "done":
        todos.append("RR待审")

    if _load_batch_review_flag(art.output_dir, art.level, art.book_number):
        if "RR待审" not in todos:
            todos.append("RR待审")

    if art.status == "partial" and steps.get("images") and not steps.get("zip"):
        if not ph_pages:
            todos.append("组装待完成")

    return todos, ph_pages


def load_dingtalk_sync_status(meta: dict | None = None) -> dict[str, Any]:
    """钉钉 S&S + Timeline 需求表同步元信息（供看板顶栏）。"""
    meta = meta or {}
    state: dict[str, str] = {}
    if _DINGTALK_SYNC_STATE.is_file():
        try:
            raw = json.loads(_DINGTALK_SYNC_STATE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                state = {str(k): str(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError):
            pass

    req_synced = "—"
    if _DINGTALK_REQ_MD.is_file():
        try:
            head = _DINGTALK_REQ_MD.read_text(encoding="utf-8")[:800]
            m = re.search(r"同步时间:\s*([^\n]+)", head)
            if m:
                req_synced = m.group(1).strip()[:19].replace("T", " ")
        except OSError:
            pass

    synced_at = str(meta.get("synced_at", ""))[:19].replace("T", " ") or "—"

    return {
        "syllabus_synced_at": synced_at,
        "syllabus_via": str(meta.get("sync_via", "—")),
        "source_l02": str(meta.get("source_l02", "—")),
        "source_l36": str(meta.get("source_l36", "—")),
        "timeline_req_synced": req_synced,
        "hash_l02": bool(state.get("L0-L2")),
        "hash_l36": bool(state.get("L3-L6")),
        "hash_requirements": bool(state.get("requirements")),
        "book_count": int(meta.get("book_count") or 0),
    }


def build_level_stats(outputs_root: Path | None = None) -> dict[str, Any]:
    """汇总各级别书目统计 + 逐本进度。"""
    data = load_syllabus()
    meta = data.get("_meta") or {}
    books_raw: dict = data.get("books") or {}
    out_root = outputs_root or OUTPUTS_DIR
    out_index = scan_output_index(str(out_root.resolve()))
    progress_cache = load_progress_cache()
    progress_books: dict[str, Any] = progress_cache.get("books") or {}
    progress_by_title: dict[str, Any] = {}
    for rec in progress_books.values():
        if not isinstance(rec, dict):
            continue
        rk = _title_cache_key(str(rec.get("level", "")), str(rec.get("title", "")))
        if rk.endswith("-T"):
            continue
        progress_by_title.setdefault(rk, rec)
    progress_source = progress_source_status()
    use_dingtalk_progress = progress_source.get("mode") == "dingtalk"

    by_level: dict[str, list[BookArtifacts]] = {}
    for _key, raw in books_raw.items():
        lvl = _norm_book_num(str(raw.get("level", "")).strip())
        if not lvl:
            continue
        bn = _norm_book_num(str(raw.get("book_number", "")).strip())
        title = str(raw.get("title", "")).strip()
        genre = str(raw.get("genre", "")).strip()

        hit = out_index.get((lvl, bn))
        if hit:
            out_dir, local_steps = hit
        else:
            out_dir = None
            local_steps = {s[0]: (s[0] == "story") for s in PIPELINE_STEPS}

        progress_record = None
        if use_dingtalk_progress:
            if bn:
                progress_record = progress_books.get(_book_cache_key(lvl, bn))
            if not isinstance(progress_record, dict):
                progress_record = progress_by_title.get(_title_cache_key(lvl, title))
        if isinstance(progress_record, dict):
            steps = _steps_from_progress_record(progress_record)
            timeline_steps = _timeline_from_progress_record(progress_record)
            tl_done, tl_total, tl_pct = _timeline_counts(timeline_steps)
            completed_steps, next_pending_step, pending_steps, blocked_steps = _timeline_rollup(timeline_steps)
            status = str(progress_record.get("status") or "pending")
            pct = int(progress_record.get("progress_pct") or 0)
            current_step = str(
                progress_record.get("current_step")
                or (f"待处理：{next_pending_step}" if next_pending_step else "")
                or progress_record.get("status_text")
                or ""
            )
            owner = str(progress_record.get("owner") or "")
            updated_at = str(progress_record.get("updated_at") or "")
            raw_status = str(progress_record.get("status_text") or "")
            raw_fields = progress_record.get("raw_fields") if isinstance(progress_record.get("raw_fields"), dict) else {}
            source = "dingtalk"
            source_label = "钉钉进度表"
        elif use_dingtalk_progress:
            steps = {s[0]: (s[0] == "story") for s in PIPELINE_STEPS}
            timeline_steps = []
            tl_done, tl_total, tl_pct = 0, 0, 0
            completed_steps, next_pending_step, pending_steps, blocked_steps = [], "", [], []
            status, pct = "pending", 0
            current_step = "钉钉进度表暂无状态"
            owner = ""
            updated_at = ""
            raw_status = ""
            raw_fields = {}
            source = "dingtalk"
            source_label = "钉钉进度表"
        else:
            steps = local_steps
            timeline_steps = []
            tl_done, tl_total, tl_pct = 0, 0, 0
            completed_steps, next_pending_step, pending_steps, blocked_steps = [], "", [], []
            status, pct = _status_from_steps(steps) if hit else ("pending", int(100 / len(PIPELINE_STEPS)))
            current_step = "本地产物扫描"
            owner = ""
            updated_at = ""
            raw_status = ""
            raw_fields = {}
            source = "local"
            source_label = "本地输出扫描（降级）"

        art = BookArtifacts(
            level=lvl,
            book_number=bn,
            title=title,
            output_dir=out_dir,
            steps=steps,
            status=status,
            progress_pct=pct,
            genre=genre,
            current_step=current_step,
            owner=owner,
            progress_updated_at=updated_at,
            progress_source=source,
            progress_source_label=source_label,
            raw_status=raw_status,
            timeline_steps=timeline_steps,
            raw_fields=raw_fields,
            timeline_done_count=tl_done,
            timeline_total_count=tl_total,
            timeline_done_pct=tl_pct,
            completed_steps=completed_steps,
            next_pending_step=next_pending_step,
            pending_steps=pending_steps,
            blocked_steps=blocked_steps,
        )
        # 钉钉关键里程碑（6 项）只在有钉钉逐列时计算，完全以真实列单元格为准。
        if source == "dingtalk" and timeline_steps:
            art.milestones = resolve_book_milestones(timeline_steps)
            art.milestone_done_count = milestone_done_count(art.milestones)
            art.milestone_next = milestone_next_pending(art.milestones)
        todos, ph_pages = compute_manual_todos(art)
        art.manual_todos = todos
        art.placeholder_pages = ph_pages
        by_level.setdefault(lvl, []).append(art)

    for lvl in by_level:
        by_level[lvl].sort(key=lambda b: (int(b.book_number) if b.book_number.isdigit() else 9999, b.title))

    level_rows: list[dict] = []
    totals = {"total": 0, "done": 0, "partial": 0, "pending": 0}
    for lvl in sorted(by_level.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        items = by_level[lvl]
        done = sum(1 for b in items if b.status == "done")
        partial = sum(1 for b in items if b.status == "partial")
        pending = sum(1 for b in items if b.status == "pending")
        total = len(items)
        step_done = sum(b.timeline_done_count for b in items)
        step_total = sum(b.timeline_total_count for b in items)
        level_rows.append({
            "级别": f"Level {lvl}",
            "大纲总数": total,
            "✅ 完成": done,
            "🟡 进行中": partial,
            "⬜ 未开始": pending,
            "终局完成率": f"{int(done / total * 100) if total else 0}%",
            "环节完成率": f"{int(step_done / step_total * 100) if step_total else 0}%",
        })
        totals["total"] += total
        totals["done"] += done
        totals["partial"] += partial
        totals["pending"] += pending

    manual_count = sum(
        1 for items in by_level.values() for b in items if b.manual_todos
    )
    step_done_total = sum(b.timeline_done_count for items in by_level.values() for b in items)
    step_total = sum(b.timeline_total_count for items in by_level.values() for b in items)
    timeline_columns = _timeline_columns_from_stats(progress_cache, by_level)
    milestone_matrix = _milestone_level_matrix(by_level)

    return {
        "meta": meta,
        "dingtalk": load_dingtalk_sync_status(meta),
        "progress_source": progress_source,
        "outputs_root": out_root,
        "level_rows": level_rows,
        "by_level": by_level,
        "totals": totals,
        "timeline_totals": {
            "done": step_done_total,
            "total": step_total,
            "pct": int(step_done_total / step_total * 100) if step_total else 0,
        },
        "timeline_columns": timeline_columns,
        "milestone_matrix": milestone_matrix,
        "pipeline_step_rows": _pipeline_step_stats(by_level),
        "manual_count": manual_count,
    }


def _milestone_level_matrix(by_level: dict[str, list[BookArtifacts]]) -> dict[str, Any]:
    """按 Level 0-6 汇总 6 个关键里程碑的 done/present/total。

    返回 {"rows": [...每 Level 一行...], "milestone_keys": [...], "milestone_names": {...}}。
    rows 元素含每个里程碑的 done/present 计数，便于 UI 渲染矩阵。
    """
    rows: list[dict[str, Any]] = []
    for lvl in sorted(by_level.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        items = by_level[lvl]
        total = len(items)
        row: dict[str, Any] = {"level": lvl, "level_label": f"Level {lvl}", "total": total}
        per: dict[str, dict[str, int]] = {}
        for key in MILESTONE_KEYS:
            done = 0
            present = 0
            for b in items:
                m = (b.milestones or {}).get(key) or {}
                if m.get("found"):
                    present += 1
                if m.get("done"):
                    done += 1
            per[key] = {"done": done, "present": present, "total": total}
        row["per"] = per
        rows.append(row)
    return {
        "rows": rows,
        "milestone_keys": list(MILESTONE_KEYS),
        "milestone_names": dict(MILESTONE_NAMES),
        "milestone_specs": [
            {"key": m["key"], "name": m["name"], "group": m["group"]}
            for m in KEY_MILESTONES
        ],
    }


def _step_icon(ok: bool) -> str:
    return "✅" if ok else "⬜"


def milestone_cell_icon(m: dict[str, Any] | None) -> str:
    """单本里程碑 → ✅ / ⬜ / 🟡 / 🔴 / —（无此列）。"""
    if not m:
        return "—"
    state = str(m.get("state") or "")
    if state == "absent" or not m.get("found"):
        return "—"
    if m.get("done"):
        return "✅"
    if state == "blocked":
        return "🔴"
    if state == "warn":
        return "🟡"
    return "⬜"


def _render_milestone_matrix(matrix: dict[str, Any]) -> None:
    import streamlit as st

    rows = matrix.get("rows") or []
    specs = matrix.get("milestone_specs") or []
    if not rows or not specs:
        st.caption("暂无钉钉关键里程碑数据（需先同步钉钉进度缓存）。")
        return

    table: list[dict[str, Any]] = []
    for row in rows:
        per = row.get("per") or {}
        out: dict[str, Any] = {"级别": row.get("level_label", ""), "本数": row.get("total", 0)}
        for spec in specs:
            key = spec["key"]
            cell = per.get(key) or {}
            total = int(cell.get("total") or 0)
            present = int(cell.get("present") or 0)
            done = int(cell.get("done") or 0)
            if total and present == 0:
                out[spec["name"]] = "无此列"
            else:
                out[spec["name"]] = f"{done}/{total}"
        table.append(out)

    col_order = ["级别", "本数"] + [spec["name"] for spec in specs]
    st.dataframe(
        table,
        column_order=col_order,
        width="stretch",
        hide_index=True,
        height=min(360, 80 + len(table) * 36),
    )


def render_progress_dashboard(
    *,
    on_start_book: Any | None = None,
    on_open_book: Any | None = None,
    on_refresh: Any | None = None,
) -> None:
    """Streamlit 进度看板主渲染（由 web_app 主导航调用）。"""
    import streamlit as st

    st.markdown(
        """
        <div class="dash-hero">
          <div class="dash-kicker">Picturebook Pipeline · DingTalk Dashboard</div>
          <h2>进度看板：大纲书目 × 钉钉生产进度</h2>
          <p>左侧看各级团队进度，右侧逐本核对当前步骤、负责人和产物明细。
          点选书目行 → <b>去制作</b> 自动预填 Level / Book# / 书名。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_scan, col_sync, col_go = st.columns([2, 2, 1])
    with col_scan:
        if st.button("🔄 刷新扫描", key="dash_refresh", help="重新扫描输出目录与本地缓存"):
            scan_output_index.cache_clear()
            load_progress_cache.cache_clear()
            if on_refresh:
                on_refresh()
            st.rerun()
    with col_sync:
        if not _can_run_dingtalk_sync():
            st.info("线上环境不能直接连接钉钉。请在本地同步后发布。")
        elif st.button("☁️ 从钉钉刷新进度", key="dash_sync_dingtalk", help="运行 sync_progress_from_dingtalk.py 更新逐列缓存"):
            script = _REPO / "scripts" / "sync_progress_from_dingtalk.py"
            with st.spinner("正在读取钉钉 Timeline 表并重建进度缓存…"):
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script)],
                        cwd=str(_REPO),
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        timeout=900,
                    )
                except Exception as e:
                    st.error(f"钉钉刷新失败：{e}")
                else:
                    if proc.returncode == 0:
                        scan_output_index.cache_clear()
                        load_progress_cache.cache_clear()
                        st.success("钉钉进度缓存已刷新。")
                        st.code((proc.stdout or "").strip()[-2000:] or "sync ok", language="text")
                        st.rerun()
                    else:
                        st.error("钉钉刷新失败；可在终端手动运行 `py scripts/sync_progress_from_dingtalk.py`。")
                        st.code(((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-3000:], language="text")
    with col_go:
        if on_start_book and st.button("✨ 去制作", key="dash_go_work", type="primary"):
            on_start_book()

    with st.spinner("读取大纲、钉钉进度缓存与输出目录…"):
        stats = build_level_stats()

    totals = stats["totals"]
    timeline_totals = stats.get("timeline_totals") or {}
    meta = stats["meta"]
    dt = stats.get("dingtalk") or {}
    ps = stats.get("progress_source") or {}
    out_root = stats["outputs_root"]
    done_pct = int(totals["done"] / totals["total"] * 100) if totals["total"] else 0
    manual_count = int(stats.get("manual_count") or 0)

    # —— 钉钉 Timeline / S&S 同步状态条 ——
    hash_bits = []
    if dt.get("hash_l02"):
        hash_bits.append("L0-L2 ✓")
    if dt.get("hash_l36"):
        hash_bits.append("L3-L6 ✓")
    if dt.get("hash_requirements"):
        hash_bits.append("Timeline需求 ✓")
    hash_line = " · ".join(hash_bits) if hash_bits else "未检测到本地 hash 快照"
    st.info(
        f"**钉钉同步** · S&S 大纲 `{dt.get('syllabus_synced_at', '—')}` "
        f"via `{dt.get('syllabus_via', '—')}` · "
        f"Timeline 需求表 `{dt.get('timeline_req_synced', '—')}` · {hash_line}"
    )
    if ps.get("mode") == "dingtalk":
        st.success(
            f"**进度数据源：{ps.get('label')}** · 最后同步 `{ps.get('last_synced', '—')}` · "
            f"缓存记录 {ps.get('record_count', 0)} 条"
        )
    else:
        st.warning(
            "**进度数据源：本地输出扫描（降级）** · 当前没有可用钉钉进度缓存，"
            "完成量只代表本机输出目录产物，不代表真实团队进度。"
        )
        st.caption(
            "配置/同步：设置 `DINGTALK_PROGRESS_NODE_ID`（或复用 `DINGTALK_REQUIREMENTS_NODE_ID`）后运行 "
            "`py scripts/sync_progress_from_dingtalk.py`。"
        )
    for w in ps.get("warnings") or []:
        st.caption(f"进度缓存提示：{w}")
    st.caption(
        f"Excel 快照：L0-L2 `{dt.get('source_l02', '—')}` · "
        f"L3-L6 `{dt.get('source_l36', '—')}` · "
        f"共 {dt.get('book_count', 0)} 本 · "
        f"同步脚本 `py scripts/sync_syllabus_from_dingtalk.py`"
    )

    st.markdown(
        f"<div class='dash-track'><div class='dash-fill' style='width:{done_pct}%'></div></div>",
        unsafe_allow_html=True,
    )
    done_help = ps.get("done_definition") or "完成=钉钉状态达到终稿/完成/交付/发布。"
    step_pct = int(timeline_totals.get("pct") or 0)
    st.caption(
        f"全库终局完成率 **{done_pct}%**（{totals['done']}/{totals['total']} 本） · "
        f"钉钉环节完成率 **{step_pct}%**（{timeline_totals.get('done', 0)}/{timeline_totals.get('total', 0)} 列） · "
        f"{done_help}"
    )

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("大纲书目", totals["total"], help="syllabus.json 官方 S&S")
    m2.metric("✅ 终局完成", totals["done"], help="由钉钉终检/发布/打印/版本等终局列判断")
    m3.metric("🟡 进行中", totals["partial"])
    m4.metric("⬜ 未开始", totals["pending"])
    m5.metric("钉钉环节完成", f"{step_pct}%", help="所有真实 Timeline 列的 Done 数 / 总列数")
    synced = str(meta.get("synced_at", ""))[:19].replace("T", " ") or "—"
    m6.metric("大纲同步", synced, help=str(meta.get("sync_via", "")))

    st.caption(f"进度缓存：`{ps.get('cache_path', '—')}` · 输出根目录：`{out_root}`")

    st.markdown("---")
    st.subheader("🎯 关键里程碑 × Level（钉钉真实列）")
    st.caption(
        "用户最关心的最终交付阶段：绘本终审/印刷/App、WS+RR 合并/终审、TG 完成/App。"
        "每格 = 该 Level 下完成本数/总本数（判定完全以钉钉对应列单元格 Done 为准）。"
    )
    _render_milestone_matrix(stats.get("milestone_matrix") or {})

    st.markdown("---")
    st.subheader("各级别概览")
    st.dataframe(stats["level_rows"], width="stretch", hide_index=True)

    with st.expander("钉钉全部列统计（193 列明细，非主视图）", expanded=False):
        step_rows = stats.get("pipeline_step_rows") or []
        if step_rows:
            st.dataframe(step_rows, width="stretch", hide_index=True, height=min(420, 80 + len(step_rows) * 32))
        else:
            st.caption("暂无钉钉逐列统计。")

    st.subheader("书目明细（钉钉真实列）")
    level_options = ["全部"] + [f"Level {lv}" for lv in sorted(stats["by_level"].keys(), key=lambda x: int(x))]
    f1, f2, f3 = st.columns([1, 1, 2])
    with f1:
        lv_filter = st.selectbox("级别筛选", level_options, key="dash_lv_filter")
    with f2:
        status_filter = st.selectbox(
            "状态筛选",
            ["全部", "✅ 完成", "🟡 进行中", "⬜ 未开始"],
            key="dash_status_filter",
        )
    with f3:
        q = st.text_input("搜索书名 / Book#", key="dash_search", placeholder="例如：Mystery Dish 或 15")

    rows: list[dict] = []
    row_keys: list[tuple[str, str, str]] = []  # (level, book_number, title)
    levels = stats["by_level"]
    if lv_filter != "全部":
        lv_key = lv_filter.replace("Level ", "").strip()
        levels = {lv_key: levels.get(lv_key, [])}

    status_map = {
        "✅ 完成": "done",
        "🟡 进行中": "partial",
        "⬜ 未开始": "pending",
    }

    visible_books: list[BookArtifacts] = []
    for _lv, books in sorted(levels.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 99):
        for b in books:
            if status_filter != "全部" and b.status != status_map.get(status_filter, ""):
                continue
            if q:
                ql = q.lower().strip()
                if ql not in b.title.lower() and ql not in b.book_number and ql not in b.level:
                    continue
            visible_books.append(b)

    timeline_display_cols: list[tuple[str, str]] = []
    seen_timeline_cols: set[str] = set()
    for b in visible_books:
        for step in b.timeline_steps:
            key = str(step.get("key") or "").strip()
            if not key or key in seen_timeline_cols:
                continue
            seen_timeline_cols.add(key)
            excel_col = str(step.get("excel_col") or step.get("column") or "").strip()
            label = str(step.get("display_label") or step.get("label") or key).strip()
            display = f"{excel_col} {label}".strip()
            timeline_display_cols.append((key, display))

    # 6 个关键里程碑短列名（默认主视图，突出最终交付阶段）
    milestone_headers = [(spec["key"], f"★{spec['name']}") for spec in KEY_MILESTONES]

    for b in visible_books:
            row = {
                "级别": f"L{b.level}",
                "Book#": b.book_number,
                "书名": b.title,
                "体裁": b.genre or "—",
                "状态": _STATUS_LABEL.get(b.status, b.status),
                "关键里程碑": f"{b.milestone_done_count}/{len(KEY_MILESTONES)}",
                "下一关键步": b.milestone_next or "—",
                "环节完成": f"{b.timeline_done_count}/{b.timeline_total_count}" if b.timeline_total_count else "—",
                "当前卡点": b.next_pending_step or "—",
                "问题": " · ".join(b.blocked_steps[:2]) if b.blocked_steps else "—",
                "负责人": b.owner or "—",
                "更新时间": b.progress_updated_at or "—",
                "数据源": b.progress_source_label,
            }
            for mkey, mhead in milestone_headers:
                row[mhead] = milestone_cell_icon((b.milestones or {}).get(mkey))
            step_by_key = {str(s.get("key") or ""): s for s in b.timeline_steps}
            for key, display in timeline_display_cols:
                row[display] = _timeline_cell(step_by_key.get(key))
            rows.append(row)
            row_keys.append((b.level, b.book_number, b.title))

    if not rows:
        st.warning("无匹配书目")
        return

    # 行选择 → 跳转制作（Streamlit ≥1.35 on_select；旧版用下方 selectbox）
    # 主视图：基础信息 + 6 个关键里程碑 ✅/⬜；全部 193 钉钉列追加在右侧可横滚查看。
    display_cols = [
        "级别", "Book#", "书名", "体裁", "状态", "关键里程碑", "下一关键步",
        *[mhead for _mkey, mhead in milestone_headers],
        "环节完成", "当前卡点", "问题", "负责人", "更新时间", "数据源",
        *[display for _key, display in timeline_display_cols],
    ]
    try:
        st.dataframe(
            rows,
            column_order=display_cols,
            width="stretch",
            hide_index=True,
            height=min(520, 80 + len(rows) * 36),
            on_select="rerun",
            selection_mode="single-row",
            key="dash_book_table",
        )
        sel = (st.session_state.get("dash_book_table") or {}).get("selection") or {}
        sel_rows = sel.get("rows") or []
    except TypeError:
        st.dataframe(rows, width="stretch", hide_index=True, height=min(520, 80 + len(rows) * 36))
        sel_rows = []

    pick_options = [
        f"L{lv} · Book {bn} · {title}" for lv, bn, title in row_keys
    ]
    pick_idx = 0
    if sel_rows and 0 <= sel_rows[0] < len(row_keys):
        pick_idx = sel_rows[0]

    act1, act2 = st.columns([3, 1])
    with act1:
        picked = st.selectbox(
            "选中书目（点表格行或下拉）",
            range(len(pick_options)),
            format_func=lambda i: pick_options[i],
            index=pick_idx,
            key="dash_pick_book",
            label_visibility="collapsed",
        )
    with act2:
        if on_open_book and st.button("✨ 去制作此书", key="dash_open_book", type="primary"):
            lv, bn, title = row_keys[picked]
            on_open_book(level=lv, book_number=bn, title=title)

    with st.expander("本地 SOP / 磁盘产物辅助（非主表）", expanded=False):
        aux_rows = []
        for lv, bn, title in row_keys:
            b = next((item for item in stats["by_level"].get(lv, []) if item.book_number == bn and item.title == title), None)
            if not b:
                continue
            aux = {"级别": f"L{lv}", "Book#": bn, "书名": title, "待您手动": " · ".join(b.manual_todos) if b.manual_todos else "—"}
            for key, label, _art in PIPELINE_STEPS:
                aux[label] = _step_icon(b.steps.get(key, False))
            aux["输出目录"] = str(b.output_dir) if b.output_dir else "—"
            aux_rows.append(aux)
        st.caption("这里只是本地输出目录/SOP 辅助判断，不参与主表列名和钉钉 Done 对齐。")
        st.dataframe(aux_rows, width="stretch", hide_index=True, height=min(360, 80 + len(aux_rows) * 32))

    st.caption(
        f"共 {len(rows)} 条 · 主表列名/顺序来自钉钉 Timeline 当前表头；"
        f"每格状态来自对应钉钉单元格，未映射成本地 SOP 列。"
    )


def syllabus_entry_for(level: str, book_number: str) -> SyllabusEntry | None:
    return get_by_number(level, book_number)
