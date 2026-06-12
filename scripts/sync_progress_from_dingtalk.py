"""同步钉钉生产进度表为结构化缓存，供进度看板使用。

默认只读：从 DINGTALK_PROGRESS_NODE_ID（未配置时回退 DINGTALK_REQUIREMENTS_NODE_ID）
导出/下载 xlsx 后解析。若本地已有导出的 xlsx，也可用 --input 直接解析。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
CACHE_JSON = REPO / "references" / "syllabus" / "progress_status.json"
DOWNLOAD_DIR = REPO / "references" / "syllabus" / "_dingtalk_cache"
DEFAULT_LOCAL_XLSX = REPO / "references" / "dingtalk" / "requirements.xlsx"
SYLLABUS_JSON = REPO / "references" / "syllabus" / "syllabus.json"

DEFAULT_PROGRESS_SOURCE_URL = (
    "https://alidocs.dingtalk.com/i/nodes/"
    "7NkDwLng8ZMaj15pHaqGnz5jJKMEvZBY?utm_scene=person_space"
)
DEFAULT_PROGRESS_URL = os.getenv(
    "DINGTALK_PROGRESS_SOURCE_URL",
    DEFAULT_PROGRESS_SOURCE_URL,
)
DEFAULT_PROGRESS_NODE = os.getenv(
    "DINGTALK_PROGRESS_NODE_ID",
    os.getenv("DINGTALK_REQUIREMENTS_NODE_ID", DEFAULT_PROGRESS_URL),
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "level": ("level", "级别", "等级"),
    "book_number": ("book", "book#", "book no", "book number", "编号", "册次", "书号", "课次"),
    "title": ("title", "name", "书名", "绘本名称", "课程名称", "标题"),
    "status": ("status", "状态", "进度", "当前状态", "生产状态", "完成情况", "阶段"),
    "current_step": ("current step", "current_step", "步骤", "当前步骤", "环节", "节点", "阶段", "进度"),
    "owner": ("owner", "负责人", "责任人", "制作人", "跟进人", "美工"),
    "updated_at": ("updated", "updated_at", "update time", "更新时间", "更新日期", "最后更新", "修改时间", "日期"),
}

DONE_WORDS = (
    "终稿", "完成", "已完成", "已交付", "交付完成", "已发布", "发布完成", "done",
    "final", "complete", "completed", "delivered", "published", "ready",
)
DONE_NEGATIONS = ("未完成", "未交付", "未发布", "待完成", "待交付", "待发布", "不完成", "not complete")
PENDING_WORDS = ("未开始", "待开始", "未排期", "待排期", "pending", "todo", "backlog", "未启动")
BLOCKED_WORDS = ("问题", "issue", "blocked", "block", "阻塞", "卡住", "不通过", "失败", "错误")
WARN_WORDS = ("修改", "待改", "需要改", "需改", "check", "检查", "review", "反馈", "待审核", "审核中")
PARTIAL_WORDS = (
    "出书", "出图", "生图", "检查", "自检", "审核", "审阅", "交美工", "美工",
    "排版", "制作", "进行", "处理中", "已生成", "待检查", "rr", "worksheet",
    "reading report", "ws", "rrws", "rr+worksheet", "练习册", "阅读报告", "ppt",
)
META_FIELD_KEYS = {"level_raw", "sequence_order", "title", "production_core_team", "sheet"}


def _dws_bin() -> str:
    found = shutil.which("dws")
    if found:
        return found
    for candidate in (
        Path.home() / ".local" / "bin" / "dws.exe",
        Path.home() / ".local" / "bin" / "dws",
    ):
        if candidate.exists():
            return str(candidate)
    return "dws"


def _run_json(cmd: list[str], *, timeout: int = 600) -> dict[str, Any]:
    if cmd and cmd[0] == "dws":
        cmd = [_dws_bin(), *cmd[1:]]
    if "--format" not in cmd and "-f" not in cmd:
        cmd.extend(["--format", "json"])
    print("+", " ".join(cmd))
    out = subprocess.check_output(cmd, timeout=timeout, text=True, encoding="utf-8", errors="replace")
    out = out.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw_output": out}


def _download_from_dingtalk(node: str, dst: Path) -> Path:
    """按节点类型导出/下载 xlsx。所有 dws 命令均使用 --format json。"""
    if not node:
        raise RuntimeError("缺少 DINGTALK_PROGRESS_NODE_ID 或 DINGTALK_REQUIREMENTS_NODE_ID")
    if _dws_bin() == "dws" and not shutil.which("dws"):
        raise RuntimeError("dws 未安装或不在 PATH；可先用本地 --input xlsx 生成缓存")

    dst.parent.mkdir(parents=True, exist_ok=True)
    info = _run_json(["dws", "doc", "info", "--node", node])
    blob = info.get("result") if isinstance(info.get("result"), dict) else info
    ext = str(blob.get("extension") or "").lower()
    ctype = str(blob.get("contentType") or "").upper()

    if ctype == "ALIDOC" and ext == "axls":
        _run_json(["dws", "sheet", "export", "--node", node, "--output", str(dst)])
    elif ext in ("xlsx", "xls", "xlsm", "csv") or ctype == "DOCUMENT":
        _run_json(["dws", "doc", "download", "--node", node, "--output", str(dst)])
    else:
        raise RuntimeError(f"进度节点不是可解析表格：contentType={ctype!r}, extension={ext!r}")

    if not dst.exists() or dst.stat().st_size < 1024:
        raise RuntimeError(f"导出/下载未生成有效 xlsx: {dst}")
    return dst


def _doc_info(node: str) -> dict[str, Any]:
    info = _run_json(["dws", "doc", "info", "--node", node])
    return info.get("result") if isinstance(info.get("result"), dict) else info


def _sheet_list(node: str) -> list[dict[str, Any]]:
    payload = _run_json(["dws", "sheet", "list", "--node", node])
    sheets = payload.get("sheets") or payload.get("result") or []
    return sheets if isinstance(sheets, list) else []


def _sheet_range_values_single(node: str, sheet_id: str, cell_range: str) -> list[list[Any]]:
    payload = _run_json([
        "dws", "sheet", "range", "read",
        "--node", node,
        "--sheet-id", sheet_id,
        "--range", cell_range,
    ])
    values = payload.get("displayValues") or payload.get("values") or []
    return values if isinstance(values, list) else []


def _merge_row_blocks(blocks: list[list[list[Any]]]) -> list[list[Any]]:
    max_rows = max((len(b) for b in blocks), default=0)
    merged: list[list[Any]] = []
    for r in range(max_rows):
        row: list[Any] = []
        for block in blocks:
            row.extend(block[r] if r < len(block) else [])
        merged.append(row)
    return merged


def _sheet_range_values(node: str, sheet_id: str) -> list[list[Any]]:
    """分段读取宽 Timeline 表。

    直接读宽表偶发 DWS 网关超时；按 26 列分段读取，覆盖 A:CZ，避免右侧
    Lesson Guide / Final Check / APP upload 等当前版本列被截掉。
    """
    blocks: list[list[list[Any]]] = []
    for start in range(0, 104, 26):
        cell_range = f"{_excel_col_name(start)}1:{_excel_col_name(start + 25)}180"
        try:
            block = _sheet_range_values_single(node, sheet_id, cell_range)
        except Exception as e:
            print(f"WARN: {sheet_id} {cell_range} range read failed: {e}", file=sys.stderr)
            if start == 0:
                raise
            continue
        blocks.append(block)
    return _merge_row_blocks(blocks)


def _cell_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    return str(v).strip()


def _is_done_cell(v: Any) -> bool:
    s = _cell_text(v).lower()
    if not s:
        return False
    if any(n.lower() in s for n in DONE_NEGATIONS):
        return False
    return any(w.lower() in s for w in DONE_WORDS)


def _state_from_cell(v: Any) -> str:
    s = _cell_text(v).lower()
    if not s:
        return "pending"
    if any(n.lower() in s for n in DONE_NEGATIONS):
        return "pending"
    if any(w.lower() in s for w in BLOCKED_WORDS):
        return "blocked"
    if any(w.lower() in s for w in DONE_WORDS):
        return "done"
    if any(w.lower() in s for w in WARN_WORDS):
        return "warn"
    if any(w.lower() in s for w in PENDING_WORDS):
        return "pending"
    # 非空但语义不明的单元格要保留，避免把批注/日期误判成完成。
    return "warn"


def _excel_col_name(index: int) -> str:
    """Return Excel-style column name for a zero-based column index."""
    n = index + 1
    parts: list[str] = []
    while n:
        n, rem = divmod(n - 1, 26)
        parts.append(chr(ord("A") + rem))
    return "".join(reversed(parts))


def _step_key(label: str, *, index: int) -> str:
    text = _norm_header(label)
    if not text:
        text = f"col{index + 1}"
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text, flags=re.I).strip("_")[:80] or f"col{index + 1}"
    return f"{_excel_col_name(index)}__{slug}"


def _step_group(label: str) -> str:
    low = label.lower()
    if any(t in low for t in ("worksheet", "printables", "练习册")):
        return "worksheet"
    if any(t in low for t in ("reading report", "阅读报告", "rr")):
        return "reading_report"
    if any(t in low for t in ("final", "终审", "ready to print", "print", "印刷", "app上传", "ppt version", "版本")):
        return "final_publish"
    if any(t in low for t in ("picture", "ppt", "art", "4k", "图片", "学生用书", "美化")):
        return "picture_ppt"
    if any(t in low for t in ("ic", "反馈", "审核", "check", "issue", "确认")):
        return "review_check"
    return "other"


def _is_terminal_step(label: str) -> bool:
    low = label.lower()
    terminal_tokens = (
        "ready to print", "final check", "final", "终审", "印刷文件导出", "app上传图片导出",
        "ppt version", "final version", "printing", "ready教材", "ready 教材",
    )
    return any(t in low for t in terminal_tokens)


def _timeline_steps_from_fields(raw_fields: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for idx, (raw_key, entry) in enumerate(raw_fields.items()):
        if raw_key in META_FIELD_KEYS:
            continue
        if isinstance(entry, dict):
            value = _cell_text(entry.get("value"))
            label = _cell_text(entry.get("label")) or raw_key
            column = _cell_text(entry.get("column")) or _excel_col_name(idx)
            group_label = _cell_text(entry.get("group_label"))
            sub_label = _cell_text(entry.get("sub_label"))
            step_key = raw_key
        else:
            value = _cell_text(entry)
            label = raw_key
            column = _excel_col_name(idx)
            group_label = ""
            sub_label = ""
            step_key = _step_key(label, index=idx)
        state = _state_from_cell(value)
        steps.append({
            "key": step_key,
            "label": label,
            "display_label": label,
            "column": column,
            "excel_col": column,
            "group_label": group_label,
            "group_header": group_label,
            "sub_label": sub_label,
            "sub_header": sub_label,
            "value": value,
            "state": state,
            "done": state == "done",
            "group": _step_group(label),
        })
    return steps


def _timeline_summary(steps: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(steps)
    done = sum(1 for s in steps if s.get("done"))
    blocked = sum(1 for s in steps if s.get("state") == "blocked")
    warn = sum(1 for s in steps if s.get("state") == "warn")
    return {
        "total": total,
        "done": done,
        "blocked": blocked,
        "warn": warn,
        "pending": max(0, total - done - blocked - warn),
        "done_pct": int(done / total * 100) if total else 0,
    }


def _timeline_rollup(steps: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [str(s.get("label") or s.get("key") or "") for s in steps if s.get("done") or s.get("state") == "done"]
    pending = [str(s.get("label") or s.get("key") or "") for s in steps if s.get("state") == "pending"]
    blocked = [
        str(s.get("label") or s.get("key") or "")
        for s in steps
        if s.get("state") in {"blocked", "warn"}
    ]
    next_step = ""
    for step in steps:
        if not (step.get("done") or step.get("state") == "done"):
            next_step = str(step.get("label") or step.get("key") or "")
            break
    return {
        "completed_steps": completed,
        "next_pending_step": next_step,
        "pending_steps": pending,
        "blocked_steps": blocked,
    }


def _merge_header(col_values: list[Any]) -> str:
    parts = [_cell_text(v).replace("\r\n", " ").replace("\n", " ") for v in col_values]
    return " / ".join(p for p in parts if p)


def _fill_header_row(row: list[Any], width: int) -> list[str]:
    """Fill merged-header blanks to the right so group labels survive export."""
    filled: list[str] = []
    last = ""
    for i in range(width):
        text = _cell_text(row[i] if i < len(row) else "")
        if text:
            last = text
        filled.append(last)
    return filled


def _header_parts(rows: list[list[Any]], col: int, *, width: int) -> tuple[str, str, str, str, bool]:
    raw = [
        _cell_text(rows[r][col] if r < len(rows) and col < len(rows[r]) else "")
        for r in range(3)
    ]
    filled = [
        _fill_header_row(rows[r] if r < len(rows) else [], width)[col]
        for r in range(3)
    ]
    group_label, label, sub_label = filled
    merged = _merge_header([group_label, label, sub_label])
    return group_label, label, sub_label, merged, any(raw)


def _raw_step_entry(
    *,
    key: str,
    label: str,
    group_label: str,
    sub_label: str,
    column_index: int,
    value: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "display_label": label,
        "group_label": group_label,
        "group_header": group_label,
        "sub_label": sub_label,
        "sub_header": sub_label,
        "column": _excel_col_name(column_index),
        "excel_col": _excel_col_name(column_index),
        "column_index": column_index,
        "value": value,
    }


def _timeline_columns_from_rows(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if len(rows) < 3:
        return []
    max_cols = max((len(r) for r in rows[:4]), default=0)
    header_info = [_header_parts(rows, i, width=max_cols) for i in range(max_cols)]
    headers = [info[3] for info in header_info]
    is_l36_layout = (
        "book no" in _cell_text(rows[0][0] if rows and rows[0] else "").lower()
        and ("题目" in _cell_text(rows[0][1] if rows and len(rows[0]) > 1 else "")
             or "title" in _cell_text(rows[0][1] if rows and len(rows[0]) > 1 else "").lower())
    )
    status_start_col = 3 if is_l36_layout else 5
    columns: list[dict[str, Any]] = []
    for i, label in enumerate(headers):
        if i < status_start_col or not label or not header_info[i][4]:
            continue
        group_label, _label_part, sub_label, display_label, _has_own_header = header_info[i]
        key = _step_key(display_label, index=i)
        columns.append({
            "excel_col": _excel_col_name(i),
            "column_index": i,
            "group_header": group_label,
            "sub_header": sub_label,
            "label": label,
            "display_label": display_label,
            "key": key,
        })
    return columns


def _norm_header(s: str) -> str:
    s = _cell_text(s).lower()
    s = re.sub(r"[\s_\-:：/（）()\[\]【】]+", "", s)
    return s


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _cell_text(title).lower())


def _syllabus_title_index() -> dict[str, tuple[str, str]]:
    if not SYLLABUS_JSON.is_file():
        return {}
    try:
        payload = json.loads(SYLLABUS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    books = payload.get("books") if isinstance(payload, dict) else {}
    if not isinstance(books, dict):
        return {}
    index: dict[str, tuple[str, str]] = {}
    for raw in books.values():
        if not isinstance(raw, dict):
            continue
        key = _title_key(str(raw.get("title") or ""))
        level = _norm_level(str(raw.get("level") or ""))
        book_number = _norm_book_num(str(raw.get("book_number") or ""))
        if key and level:
            index.setdefault(key, (level, book_number))
    return index


def _level_from_syllabus_title(title: str) -> str:
    hit = _syllabus_title_index().get(_title_key(title))
    return hit[0] if hit else ""


def _pick_field(headers: list[str], field: str) -> str | None:
    aliases = {_norm_header(a) for a in FIELD_ALIASES[field]}
    for h in headers:
        hn = _norm_header(h)
        if hn in aliases:
            return h
    for h in headers:
        hn = _norm_header(h)
        if any(a and a in hn for a in aliases):
            return h
    return None


def _find_header_row(rows: list[list[Any]]) -> tuple[int, list[str]] | None:
    best: tuple[int, list[str], int] | None = None
    for i, row in enumerate(rows[:30]):
        headers = [_cell_text(v) for v in row]
        if sum(1 for h in headers if h) < 3:
            continue
        score = 0
        for field in FIELD_ALIASES:
            if _pick_field(headers, field):
                score += 1
        if best is None or score > best[2]:
            best = (i, headers, score)
    if best and best[2] >= 2:
        return best[0], best[1]
    return None


def _norm_book_num(v: Any) -> str:
    s = _cell_text(v)
    m = re.search(r"\d+", s)
    if m:
        return str(int(m.group(0)))
    return s


def _norm_level(v: Any, *, fallback_text: str = "") -> str:
    s = _cell_text(v)
    if "smart" in s.lower():
        return "0"
    m = re.search(r"(?:level|l)?\s*([0-6])\b", s, re.I)
    if m:
        return str(int(m.group(1)))
    m = re.search(r"(?:level|l)\s*([0-6])\b", fallback_text, re.I)
    if m:
        return str(int(m.group(1)))
    return s


def classify_status(status_text: str, step_text: str = "") -> tuple[str, int]:
    text = f"{status_text} {step_text}".strip()
    low = text.lower()
    if not text:
        return "pending", 0
    if any(w.lower() in low for w in PENDING_WORDS):
        return "pending", 0
    if any(w.lower() in low for w in DONE_NEGATIONS):
        if any(w.lower() in low for w in PARTIAL_WORDS):
            return "partial", _progress_pct_from_text(low)
        return "pending", 0
    if any(w.lower() in low for w in DONE_WORDS):
        return "done", 100
    if any(w.lower() in low for w in PARTIAL_WORDS):
        return "partial", _progress_pct_from_text(low)
    return "pending", 0


def _progress_pct_from_text(low: str) -> int:
    if any(w in low for w in ("交美工", "美工", "排版")):
        return 85
    if any(w in low for w in ("rr", "worksheet", "reading report", "练习册", "阅读报告", "rrws")):
        return 70
    if any(w in low for w in ("ppt", "出书", "绘本")):
        return 55
    if any(w in low for w in ("检查", "审核", "审阅", "自检")):
        return 45
    if any(w in low for w in ("出图", "生图", "图片")):
        return 35
    return 20


def _steps_from_progress(status: str, text: str) -> dict[str, bool]:
    low = text.lower()
    done = status == "done"
    return {
        "story": True,
        "images": done or any(w in low for w in ("出图", "生图", "图片", "检查", "美工", "终稿", "完成")),
        "ppt": done or any(w in low for w in ("ppt", "出书", "绘本", "交美工", "终稿", "完成")),
        "ws": done or any(w in low for w in ("worksheet", "ws", "rrws", "练习册", "教辅", "终稿", "完成")),
        "rr": done or any(w in low for w in ("reading report", "rr", "rrws", "阅读报告", "教辅", "终稿", "完成")),
        "tg": done or any(w in low for w in ("teacher", "tg", "教师指南", "教辅", "终稿", "完成")),
        "zip": done,
    }


def _record_key(level: str, book_number: str, title: str) -> str:
    if level and book_number:
        return f"L{level}-B{book_number}"
    slug = re.sub(r"\W+", "_", title.lower()).strip("_")[:80] or "untitled"
    return f"L{level or 'unknown'}-{slug}"


def _parse_progress_sheet_rows(
    rows: list[list[Any]],
    *,
    sheet_name: str,
    source_url: str,
) -> dict[str, Any]:
    """解析 Timeline Level sheet 的多行表头。

    实际表结构通常为：
    row 1-3: 分组表头；row 4+: Lx / Sequence Order / Title / Reader / Owner / 多列状态。
    """
    records: dict[str, Any] = {}
    if len(rows) < 4:
        return records
    fallback_level = _norm_level(sheet_name)
    max_cols = max((len(r) for r in rows[:4]), default=0)
    header_info = [_header_parts(rows, i, width=max_cols) for i in range(max_cols)]
    headers = [info[3] for info in header_info]
    is_l36_layout = "book no" in _cell_text(rows[0][0]).lower() and ("题目" in _cell_text(rows[0][1]) or "title" in _cell_text(rows[0][1]).lower())
    bn_col = 0 if is_l36_layout else 1
    title_col = 1 if is_l36_layout else 2
    owner_col = 2 if is_l36_layout else 4
    status_start_col = 3 if is_l36_layout else 5
    status_cols = [
        i for i, h in enumerate(headers)
        if i >= status_start_col and h and header_info[i][4]
    ]

    for row in rows[3:]:
        if len(row) <= title_col:
            continue
        bn = _norm_book_num(row[bn_col] if len(row) > bn_col else "")
        title = _cell_text(row[title_col] if len(row) > title_col else "")
        if not bn or not title:
            continue
        if bn.lower() == "done" or title.lower() == "done":
            continue
        raw_level = _cell_text(row[0] if row else "")
        if is_l36_layout:
            # Level 3-6 production sheet uses column A as Book No., not level.
            level = _level_from_syllabus_title(title) or fallback_level
            raw_level = sheet_name
        else:
            level = _norm_level(raw_level) if re.search(r"\bL?\s*[0-6]\b|smart", raw_level, re.I) else fallback_level
        if not level:
            continue
        owner = _cell_text(row[owner_col] if len(row) > owner_col else "")

        done_cols: list[str] = []
        missing_cols: list[str] = []
        raw_fields: dict[str, Any] = {
            "level_raw": raw_level,
            "sequence_order": bn,
            "title": title,
            "production_core_team": owner,
            "sheet": sheet_name,
        }
        for i in status_cols:
            group_label, label_part, sub_label, label, _has_own_header = header_info[i]
            label = headers[i]
            key = _step_key(label, index=i)
            value = _cell_text(row[i] if i < len(row) else "")
            raw_fields[key] = _raw_step_entry(
                key=key,
                label=label,
                group_label=group_label,
                sub_label=sub_label,
                column_index=i,
                value=value,
            )
            if _is_done_cell(value):
                done_cols.append(label)
            else:
                # 空白列常是分隔/确认列；只有有具体表头的关键列才算缺口。
                low_label = label.lower()
                if any(token in low_label for token in ("pictures", "ppt", "ready", "审核", "终审", "worksheet", "reading report", "print")):
                    missing_cols.append(label)

        timeline_steps = _timeline_steps_from_fields(raw_fields)
        timeline = _timeline_summary(timeline_steps)
        rollup = _timeline_rollup(timeline_steps)

        # 终局列来自真实表头：终检/发布/打印/版本等列；中间列 Done 不等于整本完成。
        terminal_cols = [(i, h) for i, h in enumerate(headers) if i in status_cols and _is_terminal_step(h)]
        terminal_done = [
            (i, h) for i, h in terminal_cols
            if _is_done_cell(row[i] if i < len(row) else "")
        ]
        all_terminal_done = bool(terminal_cols) and len(terminal_done) >= max(1, len(terminal_cols) - 1)

        if all_terminal_done:
            status, pct = "done", 100
            current_step = "终稿/打印/Worksheet/RR 已完成"
        elif done_cols:
            status = "partial"
            pct = min(95, max(20, int(len(done_cols) / max(len(status_cols), 1) * 100)))
            current_step = (
                f"待处理：{rollup['next_pending_step']}"
                if rollup.get("next_pending_step")
                else f"已完成 {len(done_cols)}/{len(status_cols)} 项"
            )
        else:
            status, pct = "pending", 0
            current_step = "未开始/未填写进度"

        records[_record_key(level, bn, title)] = {
            "level": level,
            "book_number": bn,
            "title": title.replace("\r\n", " ").replace("\n", " ").strip(),
            "status": status,
            "status_text": current_step,
            "current_step": current_step,
            "owner": owner,
            "updated_at": "",
            "progress_pct": pct,
            "steps": _steps_from_progress_record_like(status, raw_fields),
            "timeline_steps": timeline_steps,
            "timeline": timeline,
            **rollup,
            "source_url": source_url,
            "sheet": sheet_name,
            "raw_fields": raw_fields,
        }
    return records


def _steps_from_progress_record_like(status: str, raw_fields: dict[str, Any]) -> dict[str, bool]:
    blob = json.dumps(raw_fields, ensure_ascii=False).lower()
    done = status == "done"
    return {
        "story": True,
        "images": done or any(w in blob for w in ("pictures", "图片", "4k", "ppt", "美化", "art format")),
        "ppt": done or any(w in blob for w in ("ppt", "pictures", "学生用书", "ready to print")),
        "ws": done or any(w in blob for w in ("worksheet", "练习册")),
        "rr": done or any(w in blob for w in ("reading report", "阅读报告")),
        "tg": done,
        "zip": done,
    }


def parse_progress_sheet_online(node: str, *, source_url: str) -> dict[str, Any]:
    sheets = _sheet_list(node)
    records: dict[str, Any] = {}
    warnings: list[str] = []
    used_sheets: list[str] = []
    timeline_columns_by_sheet: dict[str, list[dict[str, Any]]] = {}
    timeline_columns: list[dict[str, Any]] = []
    seen_column_keys: set[str] = set()
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        name = str(sheet.get("name") or "")
        sheet_id = str(sheet.get("sheetId") or "")
        if not sheet_id:
            continue
        if not (re.fullmatch(r"Level\s+[0-6]", name, re.I) or "样书制作进度" in name):
            continue
        try:
            rows = _sheet_range_values(node, sheet_id)
            sheet_columns = _timeline_columns_from_rows(rows)
            if sheet_columns:
                timeline_columns_by_sheet[name] = sheet_columns
                for col in sheet_columns:
                    dedupe_key = f"{name}::{col.get('key')}"
                    if dedupe_key in seen_column_keys:
                        continue
                    seen_column_keys.add(dedupe_key)
                    timeline_columns.append({**col, "sheet": name})
            parsed = _parse_progress_sheet_rows(rows, sheet_name=name, source_url=source_url)
            if parsed:
                used_sheets.append(name)
                records.update(parsed)
            else:
                warnings.append(f"{name}: 未解析到逐本记录")
        except Exception as e:
            warnings.append(f"{name}: range read 失败: {e}")

    return {
        "_meta": {
            "source": "dingtalk-progress-table",
            "source_url": source_url,
            "source_node": node,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "detected_fields": {
                "level": "Level sheet / col A",
                "book_number": "Sequence Order",
                "title": "Title",
                "owner": "Production Core Team",
                "status": "多列生产状态汇总",
            },
            "sheets": used_sheets,
            "columns_order": [str(c.get("key") or "") for c in timeline_columns],
            "timeline_columns": timeline_columns,
            "timeline_columns_by_sheet": timeline_columns_by_sheet,
            "warnings": warnings,
            "done_definition": "Timeline 表每列独立同步为环节；整本完成量只看终检/发布/打印/版本等终局列，中间列 Done 只计入环节完成率。",
        },
        "books": records,
    }


def parse_progress_xlsx(path: Path, *, source_url: str = "") -> dict[str, Any]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    records: dict[str, Any] = {}
    warnings: list[str] = []
    detected_fields: dict[str, str] = {}
    timeline_columns: list[dict[str, Any]] = []
    timeline_columns_by_sheet: dict[str, list[dict[str, Any]]] = {}

    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        found = _find_header_row(rows)
        if not found:
            warnings.append(f"{ws.title}: 未识别表头，已跳过")
            continue
        header_idx, headers = found
        sheet_columns: list[dict[str, Any]] = []
        for i, h in enumerate(headers):
            if not h:
                continue
            key = _step_key(h, index=i)
            sheet_columns.append({
                "excel_col": _excel_col_name(i),
                "column_index": i,
                "group_header": "",
                "sub_header": "",
                "label": h,
                "display_label": h,
                "key": key,
                "sheet": ws.title,
            })
        timeline_columns_by_sheet[ws.title] = sheet_columns
        timeline_columns.extend(sheet_columns)
        field_to_header = {f: _pick_field(headers, f) for f in FIELD_ALIASES}
        for f, h in field_to_header.items():
            if h and f not in detected_fields:
                detected_fields[f] = h

        for row in rows[header_idx + 1:]:
            raw: dict[str, Any] = {}
            for i, h in enumerate(headers):
                if not h:
                    continue
                key = _step_key(h, index=i)
                raw[key] = _raw_step_entry(
                    key=key,
                    label=h,
                    group_label="",
                    sub_label="",
                    column_index=i,
                    value=_cell_text(row[i] if i < len(row) else ""),
                )
            if not any(raw.values()):
                continue

            def val(field: str) -> str:
                h = field_to_header.get(field)
                if not h:
                    return ""
                for item in raw.values():
                    if isinstance(item, dict) and item.get("label") == h:
                        return _cell_text(item.get("value"))
                return ""

            title = val("title")
            status_text = val("status")
            step_text = val("current_step") or status_text
            level = _norm_level(val("level"), fallback_text=" ".join(raw.values()))
            book_number = _norm_book_num(val("book_number"))
            owner = val("owner")
            updated_at = val("updated_at")

            if not (level or book_number or title or status_text or step_text):
                continue
            status, progress_pct = classify_status(status_text, step_text)
            text = f"{status_text} {step_text}"
            key = _record_key(level, book_number, title)
            meta_headers = {h for h in field_to_header.values() if h}
            step_raw = {
                k: v for k, v in raw.items()
                if not (isinstance(v, dict) and v.get("label") in meta_headers)
            }
            timeline_steps = _timeline_steps_from_fields(step_raw)
            timeline = _timeline_summary(timeline_steps)
            rollup = _timeline_rollup(timeline_steps)
            records[key] = {
                "level": level,
                "book_number": book_number,
                "title": title,
                "status": status,
                "status_text": status_text,
                "current_step": step_text,
                "owner": owner,
                "updated_at": updated_at,
                "progress_pct": progress_pct,
                "steps": _steps_from_progress(status, text),
                "timeline_steps": timeline_steps,
                "timeline": timeline,
                **rollup,
                "source_url": source_url,
                "sheet": ws.title,
                "raw_fields": raw,
            }

    return {
        "_meta": {
            "source": "dingtalk-progress-table",
            "source_url": source_url,
            "source_file": str(path),
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "detected_fields": detected_fields,
            "columns_order": [str(c.get("key") or "") for c in timeline_columns],
            "timeline_columns": timeline_columns,
            "timeline_columns_by_sheet": timeline_columns_by_sheet,
            "warnings": warnings,
            "done_definition": "Timeline 表每列独立同步为环节；本地 xlsx 通用解析时保留真实列名，整本完成量沿用状态/终稿字段判断。",
        },
        "books": records,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, help="直接解析本地 xlsx，不访问钉钉")
    ap.add_argument("--node", default=DEFAULT_PROGRESS_NODE, help="钉钉进度表节点 ID/URL")
    ap.add_argument("--output", type=Path, default=CACHE_JSON, help="输出缓存 JSON")
    ap.add_argument("--dry-run", action="store_true", help="只解析并打印摘要，不写缓存")
    ap.add_argument("--inspect-book", help="打印某本书逐列状态，例如 L0-B1 / 0-1 / B1")
    ap.add_argument("--inspect-first", type=int, default=0, help="打印前 N 本书的 timeline 列和值")
    args = ap.parse_args()

    try:
        if args.input:
            src = args.input
            payload = parse_progress_xlsx(src, source_url=DEFAULT_PROGRESS_URL)
        elif DEFAULT_LOCAL_XLSX.exists():
            src = DEFAULT_LOCAL_XLSX
            payload = parse_progress_xlsx(src, source_url=DEFAULT_PROGRESS_URL)
        else:
            info = _doc_info(args.node)
            ext = str(info.get("extension") or "").lower()
            ctype = str(info.get("contentType") or "").upper()
            if ctype == "ALIDOC" and ext == "axls":
                payload = parse_progress_sheet_online(args.node, source_url=DEFAULT_PROGRESS_URL)
            else:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                src = _download_from_dingtalk(args.node, DOWNLOAD_DIR / f"progress_{ts}.xlsx")
                payload = parse_progress_xlsx(src, source_url=DEFAULT_PROGRESS_URL)
        meta = payload["_meta"]
        print(json.dumps({
            "source_file": meta.get("source_file") or meta.get("source_node"),
            "record_count": meta["record_count"],
            "detected_fields": meta["detected_fields"],
            "sheets": meta.get("sheets", []),
            "warnings": meta["warnings"],
        }, ensure_ascii=False, indent=2))
        if args.inspect_book:
            want = args.inspect_book.strip().lower()
            books = payload.get("books") or {}
            matched = None
            for key, rec in books.items():
                if not isinstance(rec, dict):
                    continue
                aliases = {
                    str(key).lower(),
                    f"l{rec.get('level')}-b{rec.get('book_number')}".lower(),
                    f"{rec.get('level')}-{rec.get('book_number')}".lower(),
                    f"b{rec.get('book_number')}".lower(),
                    str(rec.get("title") or "").lower(),
                }
                if want in aliases or want in str(rec.get("title") or "").lower():
                    matched = (key, rec)
                    break
            if matched:
                key, rec = matched
                print(json.dumps({
                    "book_key": key,
                    "title": rec.get("title"),
                    "timeline": rec.get("timeline"),
                    "completed_steps": rec.get("completed_steps"),
                    "next_pending_step": rec.get("next_pending_step"),
                    "pending_steps": rec.get("pending_steps"),
                    "blocked_steps": rec.get("blocked_steps"),
                    "timeline_steps": [
                        {
                            "column": s.get("column"),
                            "key": s.get("key"),
                            "label": s.get("label"),
                            "value": s.get("value"),
                            "state": s.get("state"),
                        }
                        for s in rec.get("timeline_steps", [])
                    ],
                }, ensure_ascii=False, indent=2))
            else:
                print(f"INSPECT: 未找到 {args.inspect_book!r}", file=sys.stderr)
        if args.inspect_first:
            sample = []
            for key, rec in list((payload.get("books") or {}).items())[: max(0, args.inspect_first)]:
                if not isinstance(rec, dict):
                    continue
                sample.append({
                    "book_key": key,
                    "title": rec.get("title"),
                    "timeline": rec.get("timeline"),
                    "steps": [
                        {
                            "excel_col": s.get("excel_col") or s.get("column"),
                            "key": s.get("key"),
                            "display_label": s.get("display_label") or s.get("label"),
                            "value": s.get("value"),
                            "state": s.get("state"),
                        }
                        for s in rec.get("timeline_steps", [])
                    ],
                })
            print(json.dumps({"inspect_first": sample}, ensure_ascii=False, indent=2))
        if args.dry_run:
            return 0
        if meta["record_count"] < 10 and args.output.exists():
            try:
                old = json.loads(args.output.read_text(encoding="utf-8"))
                old_count = int((old.get("_meta") or {}).get("record_count") or len(old.get("books") or {}))
            except Exception:
                old_count = 0
            if old_count > meta["record_count"]:
                raise RuntimeError(
                    f"解析结果只有 {meta['record_count']} 条，少于现有缓存 {old_count} 条；"
                    "已阻止覆盖，请检查 DWS range read 或表头解析。"
                )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("WROTE", args.output)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
