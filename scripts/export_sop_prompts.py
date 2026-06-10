# -*- coding: utf-8 -*-
"""SOP 第8条 · 对外交付「4部分纯文本 Prompt 导出层」。

用户拍板（2026-06-10）：实现 SOP 第8条规定的对外交付固定 4 部分、顺序不可颠倒：
  ①【关键贯穿物件/人物统一描述】（若无贯穿关键物件则注明“无关键贯穿物件”）
  ②【故事情节描述】（100 字以内）
  ③【封面 Prompt】
  ④【分页 Prompt】（按页顺序，每页一条纯 Prompt 文本，全程复用①的统一描述）

设计要点（不破坏现有流程，纯新增）：
- **复用已构建好的分页 prompt，不重算**：本模块只接收 batch_runner.run_one 在
  阶段 1 已经构建好的 `BuiltPromptCN`（含 .prompt / .scene_cn / .used_characters），
  按 SOP 4 部分固定顺序组装成纯文本文档。绝不再调 build_cn_page_prompt、绝不调图片 API。
- **④ 复用 ①**：每页 prompt 内已含【3·主体角色】角色外观锁 + 【15·配饰/道具】贯穿
  关键道具锁，与①的统一描述同源，因此④天然逐页复用①（文末注明）。
- **② 100 字以内**：从 outline 已有信息（safety_line / scene_cn / theme）确定性归纳，
  不调 LLM、不触发出图。

入口：
- `build_sop_document(outline, built_pages, name_prefix)`：纯组装函数，供 run_one 调用。
- CLI：`py scripts/export_sop_prompts.py 66 72`（dry-run，prompts_only，不出图）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

_SEP = "=" * 60
_SUB = "-" * 60


# ============================================================
#  ① 关键贯穿物件 / 人物统一描述
# ============================================================
def _aggregate_characters(outline, built_pages) -> list[tuple[str, str]]:
    """聚合全书贯穿人物 → [(显示名, 统一形象描述)]，按首次出现顺序去重。

    来源：① 各页 BuiltPromptCN.used_characters（系列 IP / 主角，含 description_cn）；
          ② outline.book_cast（反复出场的一次性/非 IP 角色，含 desc_en）。
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    for _page, built in built_pages:
        for c in (getattr(built, "used_characters", None) or []):
            key = str(c.get("key") or c.get("name") or "").strip().lower()
            name = str(c.get("name") or "").strip()
            desc = str(c.get("description_cn") or "").strip()
            if not name or key in seen:
                continue
            # 一次性角色（oneoff:*）在下面 book_cast 段用更完整的 desc_en 补全，这里跳过空描述项
            if not desc and key.startswith("oneoff:"):
                continue
            seen.add(key)
            out.append((name, desc or "（沿用系列定妆参考图，全书一致）"))

    book_cast = getattr(outline, "book_cast", None)
    if book_cast:
        for r in book_cast.values():
            disp = (getattr(r, "display", "") or "").strip()
            key = f"oneoff:{getattr(r, 'rid', disp)}".lower()
            if not disp or key in seen:
                continue
            seen.add(key)
            desc = (getattr(r, "desc_en", "") or "").strip()
            out.append((disp, desc or "（书内角色册锁定，全书形象一致）"))

    return out


def _aggregate_key_props(outline) -> list[str]:
    """聚合全书贯穿关键道具（与 build_cn_page_prompt 中 _detect_key_props 同源、同输入口径）。

    复用 cn_prompt_builder._detect_key_props，对每个故事页用其相同的 cast_text
    （page.text + page.scene）检测，跨页去重。封面不计（与 build 一致）。
    """
    try:
        from cn_prompt_builder import _detect_key_props
    except Exception:
        return []
    props: list[str] = []
    seen: set[str] = set()
    for p in getattr(outline, "pages", []):
        if getattr(p, "page_type", "") == "cover":
            continue
        cast_text = (getattr(p, "text", "") or "") + " " + (getattr(p, "scene", "") or "")
        for d in _detect_key_props(cast_text):
            if d not in seen:
                seen.add(d)
                props.append(d)
    return props


def _part1(outline, built_pages) -> str:
    chars = _aggregate_characters(outline, built_pages)
    props = _aggregate_key_props(outline)

    lines: list[str] = []
    lines.append("【贯穿人物 · 全书形象统一描述（每页逐页复用，造型/配色/比例全程一致）】")
    if chars:
        for name, desc in chars:
            lines.append(f"- {name}：{desc}")
    else:
        lines.append("- （本书无可登记的贯穿人物）")
    lines.append("")
    lines.append("【关键贯穿物件 · 统一描述（造型/颜色/大小/材质全书逐页一致）】")
    if props:
        for d in props:
            lines.append(f"- {d}")
    else:
        # SOP 第8/13 条：无则明确注明
        lines.append("- 无关键贯穿物件")
    return "\n".join(lines)


# ============================================================
#  ② 故事情节描述（100 字以内，确定性归纳，不调 LLM/不出图）
# ============================================================
def _strip_tags(s: str) -> str:
    """去掉 scene_cn/safety_line 里的【…】技术性包裹与画风/留白措辞，留干净剧情句。"""
    s = re.sub(r"【[^】]*】", "", s or "")
    s = re.sub(r"\s+", "", s)
    return s.strip()


def _first_clause(s: str) -> str:
    s = _strip_tags(s)
    return re.split(r"[。！？!?；;\n]", s)[0].strip()


def _part2(outline, max_chars: int = 100) -> str:
    story = [p for p in getattr(outline, "pages", [])
             if getattr(p, "page_type", "") == "story"
             and ((getattr(p, "safety_line", "") or getattr(p, "scene_cn", "")
                   or getattr(p, "text", "")).strip())]
    parts: list[str] = []
    for p in story:
        cand = (getattr(p, "safety_line", "") or getattr(p, "scene_cn", "")).strip()
        c = _first_clause(cand)
        if c:
            parts.append(c)

    if not parts:
        gist = (getattr(outline, "theme", "") or getattr(outline, "title", "") or "").strip()
        return gist[:max_chars] or "（暂无可归纳的情节信息）"

    if len(parts) == 1:
        summary = parts[0]
    else:
        summary = parts[0] + "；" + parts[-1]

    if len(summary) > max_chars:
        summary = summary[:max_chars - 1].rstrip("，、；;") + "…"
    return summary


# ============================================================
#  ③ 封面 Prompt / ④ 分页 Prompt（直接复用已构建 BuiltPromptCN.prompt）
# ============================================================
def _clean_prompt(built) -> str:
    """取纯 Prompt 文本（已构建好的 BuiltPromptCN.prompt），剔除多余空行。"""
    return (getattr(built, "prompt", "") or "").strip()


def _part3(built_pages) -> str:
    for page, built in built_pages:
        if getattr(page, "page_type", "") == "cover" or getattr(page, "index", -1) == 0:
            return _clean_prompt(built)
    # 没有显式封面页时回退第一页
    if built_pages:
        return _clean_prompt(built_pages[0][1])
    return "（无封面 Prompt）"


def _part4(built_pages) -> str:
    story = [(pg, b) for pg, b in built_pages
             if not (getattr(pg, "page_type", "") == "cover" or getattr(pg, "index", -1) == 0)]
    story.sort(key=lambda t: getattr(t[0], "index", 0))
    blocks: list[str] = []
    for pg, built in story:
        body = _clean_prompt(built)
        if not body:
            continue
        blocks.append(f"—— P{getattr(pg, 'index', '?')} ——\n{body}")
    return ("\n" + _SUB + "\n").join(blocks) if blocks else "（无分页 Prompt）"


# ============================================================
#  对外交付文档组装（固定 4 部分、顺序不可颠倒）
# ============================================================
def build_sop_document(outline, built_pages: Iterable, name_prefix: str) -> str:
    """按 SOP 第8条把已构建好的分页 prompt 组装成对外交付 4 部分纯文本文档。

    built_pages：[(PageSpec, BuiltPromptCN), ...]，由 batch_runner.run_one 阶段 1
                 已构建好直接传入（不在此重算）。
    """
    bp = list(built_pages)
    doc: list[str] = []
    doc.append(f"# {name_prefix} · 对外交付 Prompt（SOP 第8条 · 固定4部分 · 顺序不可颠倒）")
    doc.append("")
    doc.append(_SEP)
    doc.append("① 关键贯穿物件 / 人物统一描述")
    doc.append(_SEP)
    doc.append(_part1(outline, bp))
    doc.append("")
    doc.append(_SEP)
    doc.append("② 故事情节描述（100 字以内）")
    doc.append(_SEP)
    doc.append(_part2(outline))
    doc.append("")
    doc.append(_SEP)
    doc.append("③ 封面 Prompt")
    doc.append(_SEP)
    doc.append(_part3(bp))
    doc.append("")
    doc.append(_SEP)
    doc.append("④ 分页 Prompt（按页顺序 · 每页纯 Prompt · 全程复用①的贯穿物件/人物统一描述）")
    doc.append(_SEP)
    doc.append(_part4(bp))
    doc.append("")
    return "\n".join(doc)


def write_sop_document(outline, built_pages: Iterable, book_dir: Path, name_prefix: str) -> Path:
    """把 SOP 4 部分文档落盘为 {name_prefix}_SOP_Prompts.txt，返回路径。"""
    book_dir = Path(book_dir)
    book_dir.mkdir(parents=True, exist_ok=True)
    out = book_dir / f"{name_prefix}_SOP_Prompts.txt"
    out.write_text(build_sop_document(outline, built_pages, name_prefix), encoding="utf-8")
    return out


# ============================================================
#  CLI（dry-run）：复用 _dryrun_prompts 的 Excel 加载 + run_one(prompts_only)
# ============================================================
def main() -> None:
    import sys
    import tempfile

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if len(sys.argv) < 2:
        raise SystemExit("用法: py scripts/export_sop_prompts.py <book_number> [more...]")

    from _dryrun_prompts import _load_item
    from batch_runner import run_one

    bns = [int(x) for x in sys.argv[1:]]
    tmp_root = Path(tempfile.mkdtemp(prefix="pb_sop_"))
    print(f"[SOP_OUT] {tmp_root}", flush=True)
    for bn in bns:
        item = _load_item(bn)
        print(f"\n########## SOP EXPORT {bn} {item.title} ##########", flush=True)
        run_one(item, tmp_root, resume=False, prompts_only=True)
        sop = tmp_root / item.name_prefix / f"{item.name_prefix}_SOP_Prompts.txt"
        print(f"[SOP_FILE] {bn} -> {sop}", flush=True)
        if sop.exists():
            print(sop.read_text(encoding="utf-8"), flush=True)
        print(f"########## END {bn} ##########", flush=True)


if __name__ == "__main__":
    main()
