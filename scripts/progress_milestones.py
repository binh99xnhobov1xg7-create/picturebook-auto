"""钉钉关键里程碑映射（SSOT = 钉钉进度表真实列）。

用户只关心每类交付物真正关键的少数"是否 Done"里程碑，而不是 193 列全平铺。
本模块把这些里程碑映射到 `progress_status.json` 里的钉钉真实列（按 group_header
+ 中段列名 + 关键 token 做健壮匹配，兼容各 Level sheet 列名细微差异）。

判定完全以钉钉真实列单元格的 state 为准：
  state == "done"  → 里程碑完成
  空/pending       → 未完成
  warn/blocked     → 未完成（保留 state 以便标 warn/blocked）
绝不使用本地磁盘文件 / 本地 SOP 推断这些关键里程碑。
"""
from __future__ import annotations

from typing import Any

GROUP_BOOK = "Book"
GROUP_WSRR = "WS+RR"
GROUP_TG = "TG"

GROUP_LABELS = {
    GROUP_BOOK: "绘本 Book",
    GROUP_WSRR: "Worksheet+RR 合并",
    GROUP_TG: "Lesson Guide / TG",
}

# 每个里程碑匹配规则：
#   group_any : group_header（或整列 label）需包含其中之一
#   mid_any   : 列中段（label 去掉首段 group 后）需包含其中之一
#   mid_exact : 列中段第一节（真正的列标题）需精确等于其中之一
#   mid_not   : 列中段不得包含其中之一（排除同名近似列）
# 用户拍板（2026-06-12）：6 个关键里程碑。
#   - 去掉「绘本·App图片导出」，App 统一只看整表最后的 `APP upload / Ready to Launch`。
#   - merge_final 改判为「合并列自带的 审核(Check)」= 与 merge_done 同一列（L3-L6 也有值），
#     不再用只在 L0-L2 存在且全空的「TG及Worksheet+RR交叉审核」列。
KEY_MILESTONES: list[dict[str, Any]] = [
    {
        "key": "book_final", "name": "绘本·终审", "group": GROUP_BOOK,
        "group_any": ["Books"], "mid_any": ["终审"],
    },
    {
        "key": "book_print", "name": "绘本·印刷版(给US)", "group": GROUP_BOOK,
        "group_any": ["Books"], "mid_any": ["Ready to print", "印刷"],
    },
    {
        "key": "merge_done", "name": "WS+RR·合并完成(Ready to Print)", "group": GROUP_WSRR,
        "group_any": ["Printables+Reading Report PDF合并", "PDF合并"],
    },
    {
        "key": "merge_final", "name": "WS+RR·合并终审(Check)", "group": GROUP_WSRR,
        # 合并列自带 审核(Check)/Selena：与 merge_done 同一列，单元格 Done 即审核通过。
        "group_any": ["Printables+Reading Report PDF合并", "PDF合并"],
    },
    {
        "key": "tg_done", "name": "TG·终审完成(Final Check)", "group": GROUP_TG,
        "group_any": ["Lesson Guide"], "mid_any": ["Final Check"], "mid_not": ["Ready to print"],
    },
    {
        "key": "tg_app", "name": "App·上线(Ready to Launch)", "group": GROUP_TG,
        "group_any": ["APP upload"], "mid_exact": ["Ready to Launch"],
    },
]

MILESTONE_KEYS: list[str] = [m["key"] for m in KEY_MILESTONES]
MILESTONE_TOTAL: int = len(KEY_MILESTONES)
MILESTONE_NAMES: dict[str, str] = {m["key"]: m["name"] for m in KEY_MILESTONES}
MILESTONE_GROUP: dict[str, str] = {m["key"]: m["group"] for m in KEY_MILESTONES}


def _label_parts(step: dict[str, Any]) -> list[str]:
    return [p.strip() for p in str(step.get("label") or "").split("/")]


def _label_mid(step: dict[str, Any]) -> str:
    """列中段：去掉首段 group_header 之后的部分（含真正列标题 + sub）。"""
    parts = _label_parts(step)
    if len(parts) >= 2:
        return " / ".join(parts[1:])
    return str(step.get("label") or "")


def _mid_head(step: dict[str, Any]) -> str:
    """列中段的第一节，即钉钉里真正的列标题（不含 group / sub）。"""
    parts = _label_parts(step)
    if len(parts) >= 2:
        return parts[1]
    return str(step.get("label") or "")


def _match_step(step: dict[str, Any], spec: dict[str, Any]) -> bool:
    group = str(step.get("group_header") or step.get("group_label") or "")
    label = str(step.get("label") or "")
    mid = _label_mid(step)
    mid_head = _mid_head(step)

    group_any = spec.get("group_any")
    if group_any and not any(g in group or g in label for g in group_any):
        return False
    mid_any = spec.get("mid_any")
    if mid_any and not any(t in mid or t in label for t in mid_any):
        return False
    mid_exact = spec.get("mid_exact")
    if mid_exact and mid_head not in mid_exact:
        return False
    mid_not = spec.get("mid_not")
    if mid_not and any(t in mid for t in mid_not):
        return False
    return True


def resolve_book_milestones(timeline_steps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """对一本书的钉钉真实列求 6 个关键里程碑布尔结果。

    返回 {milestone_key: {found, done, state, value, column, label, name, group}}。
    """
    steps = timeline_steps or []
    result: dict[str, dict[str, Any]] = {}
    for spec in KEY_MILESTONES:
        matched: dict[str, Any] | None = None
        for step in steps:
            if _match_step(step, spec):
                matched = step
                break
        if matched is None:
            result[spec["key"]] = {
                "key": spec["key"], "name": spec["name"], "group": spec["group"],
                "found": False, "done": False, "state": "absent",
                "value": "", "column": "", "label": "",
            }
        else:
            state = str(matched.get("state") or "pending")
            result[spec["key"]] = {
                "key": spec["key"], "name": spec["name"], "group": spec["group"],
                "found": True, "done": state == "done", "state": state,
                "value": str(matched.get("value") or ""),
                "column": str(matched.get("excel_col") or matched.get("column") or ""),
                "label": str(matched.get("label") or ""),
            }
    return result


def milestone_done_count(ms: dict[str, dict[str, Any]]) -> int:
    return sum(1 for m in ms.values() if m.get("done"))


def milestone_next_pending(ms: dict[str, dict[str, Any]]) -> str:
    """关键里程碑里第一个未完成项的显示名（按 KEY_MILESTONES 顺序）。"""
    for key in MILESTONE_KEYS:
        m = ms.get(key) or {}
        if not m.get("done"):
            suffix = "（无此列）" if m.get("state") == "absent" else ""
            return f"{MILESTONE_NAMES.get(key, key)}{suffix}"
    return ""


def _debug_print(sample_books: int = 5) -> None:
    """调试：打印抽样书的 6 里程碑布尔 + Level 0-6 里程碑汇总。

    用法： py scripts/progress_milestones.py [N]
    """
    import json
    from pathlib import Path

    cache = Path(__file__).resolve().parents[1] / "references" / "syllabus" / "progress_status.json"
    data = json.loads(cache.read_text(encoding="utf-8"))
    books = data.get("books") or {}

    print(f"== 抽样前 {sample_books} 本书的 {MILESTONE_TOTAL} 关键里程碑 ==")
    for key, rec in list(books.items())[:sample_books]:
        if not isinstance(rec, dict):
            continue
        ms = resolve_book_milestones(rec.get("timeline_steps") or [])
        flags = " ".join(
            f"{k}={'DONE' if ms[k]['done'] else ('N/A' if ms[k]['state']=='absent' else '--')}"
            for k in MILESTONE_KEYS
        )
        print(f"  {key} ({rec.get('title')}): {milestone_done_count(ms)}/{MILESTONE_TOTAL} | {flags}")

    print("\n== Level 0-6 关键里程碑汇总 (done/total, present) ==")
    levels: dict[str, dict[str, Any]] = {}
    for rec in books.values():
        if not isinstance(rec, dict):
            continue
        lvl = str(rec.get("level"))
        ms = resolve_book_milestones(rec.get("timeline_steps") or [])
        agg = levels.setdefault(lvl, {"total": 0, **{k: {"done": 0, "present": 0} for k in MILESTONE_KEYS}})
        agg["total"] += 1
        for k in MILESTONE_KEYS:
            if ms[k]["found"]:
                agg[k]["present"] += 1
            if ms[k]["done"]:
                agg[k]["done"] += 1
    for lvl in sorted(levels.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        agg = levels[lvl]
        parts = [f"{MILESTONE_NAMES[k]}={agg[k]['done']}/{agg['total']}(p{agg[k]['present']})" for k in MILESTONE_KEYS]
        print(f"  L{lvl} total={agg['total']}: " + " | ".join(parts))


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    _debug_print(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
