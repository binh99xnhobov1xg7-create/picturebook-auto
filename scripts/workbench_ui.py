"""单页工作台 Workbench — 三栏布局；顶栏步骤与 web_app.BOOK_STEPS 一致（仅展示，不改 SOP）。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import streamlit as st

from progress_dashboard import (
    PIPELINE_STEPS,
    BookArtifacts,
    _STATUS_LABEL,
    build_level_stats,
    load_progress_cache,
    milestone_cell_icon,
    scan_output_index,
)
from progress_milestones import GROUP_LABELS as MILESTONE_GROUP_LABELS
from progress_milestones import KEY_MILESTONES

_STATUS_DOT = {"done": "🟢", "partial": "🟡", "pending": "⚪"}
_TIMELINE_STATE_LABEL = {
    "done": "✅ Done",
    "pending": "⬜ 待做",
    "warn": "🟡 待确认/修改",
    "blocked": "🔴 问题",
}

# 当前书内部 SOP 展示步：只展示，不改底层历史步骤号/解锁逻辑。
SOP_PIPELINE: list[tuple[str, str, str]] = [
    ("extract", "录入&拉大纲", "填书名、选 Level、填 Book#。点『从大纲拉取正文』自动带出 7 页故事；没匹配上点『AI 生成故事草稿』。"),
    ("ip", "IP+画风锁", "不用手动画。系统已按级别锁好 Mia/Tommy 形象和画风，核对年龄/紫马尾/蓝衣后点确认。"),
    ("images", "逐页出图", "点『一键出 8 页』。逐页看：满意锁定，不对重生或 AI 修。8 张都锁定再下一步。"),
    ("refine", "图片精修(可选)", "出图草稿后可做清晰化/终稿编辑，自动备份原图，可上传 PDF/PPTX/散图处理。"),
    ("assemble", "组装4件套", "用终稿图生成 Reader PPT、练习册、阅读报告、教师指南。右栏逐件打勾。"),
    ("deliver", "终稿质检&合并", "老师上传/确认 WS 与 RR 后，自检并合并为教研版 PDF。"),
]

# 旧工作台 focus key → SOP key（兼容 session）
_PIPELINE_FOCUS_ALIASES: dict[str, str] = {
    "info": "extract",
    "story": "extract",
    "download": "assemble",
}

WORKBENCH_PIPELINE = SOP_PIPELINE  # 兼容旧引用

# 生产平台五大教师入口：单本标准生产是默认核心；RR/WS 是终稿质检区。
CENTER_FUNCTIONS: list[tuple[str, str, str, str]] = [
    ("single", "单本绘本标准生产（核心）", "基础信息/拉大纲 → 出图草稿 → 图片精修/终稿编辑 → Reader PPT + WS/RR/TG → 终稿质检。", "核心默认"),
    ("refine_pub", "绘本图片精修 / 终稿编辑", "适用于草稿、终稿和已发布绘本：上传 PDF/PPTX/8 图，清晰化并重出 Reader PPT。", "终稿编辑"),
    ("upload", "已有绘本生成三件套", "导入 PDF/PPTX/散图，自动匹配大纲并生成 Worksheet、Reading Report、TG。", "导入绘本"),
    ("rr_ws", "RR+Worksheet 终稿质检/PDF合并", "老师上传 WS/RR 后，对照绘本/大纲自检，签字后 WPS 转 PDF 并合并。", "质检交付"),
    ("batch", "批量生产（高级）", "最多 5 本并行，适合稳定批次；不抢单本主流程。", "≤5 本"),
]

_INPUT_SUB_STEPS = ("① Level", "② Book #", "③ 自动匹配书名", "④ 故事正文")
_DEFAULT_LEVEL_OPTIONS = ["Smart", "1", "2", "3", "4", "5", "6"]

# 问题清单动作 → 按钮文案（对标 Dino 问题回流）
_ISSUE_ACTION_LABELS: dict[str, str] = {
    "extract": "去填写",
    "info": "去填写",
    "story": "去填写",
    "ip": "去定妆",
    "images": "去出图",
    "refine": "去精修",
    "assemble": "去组装",
    "rr_ws": "去校验",
    "work": "进入经典制作",
}

_STATUS_PILL_CLASS: dict[str, tuple[str, str]] = {
    "done": ("wb-status-pill published", "✅ 完成"),
    "partial": ("wb-status-pill editing", "🟡 进行中"),
    "pending": ("wb-status-pill warning", "⬜ 未开始"),
}

_STEP_GUIDE: dict[str, tuple[str, str]] = {
    "extract": ("Step 1 · 输入+AI抽取", "下方表单填书名/Level/Book#/故事 → 进入经典制作做 AI 抽取。"),
    "ip": ("Step 2 · IP+画风", "经典制作：确认 Mia/Tommy 按级别定妆与画风锁定。"),
    "images": ("Step 3 · 生图工作台", "一键 8 页 → 逐页审图、重生、锁定。"),
    "refine": (
        "Step 3b · 图片精修",
        "8 页锁定后可做清晰化/终稿编辑；也可上传 PDF/PPTX/散图进入精修模式，默认使用固定清晰化 prompt。",
    ),
    "assemble": ("Step 4 · 组装", "生成 PPT / WS / RR / TG 并打包 ZIP。"),
}


def _norm_sel(art: BookArtifacts) -> tuple[str, str, str]:
    return art.level, art.book_number, art.title


def _list_page_images(out_dir: Path | None) -> list[tuple[int, Path]]:
    """扫描输出目录 images/ 下的分页图（跳过 _anchors 等）。"""
    if not out_dir:
        return []
    img_dir = out_dir / "images"
    if not img_dir.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for p in img_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        if p.name.startswith("_"):
            continue
        m = re.search(r"(?:page[_-]?|p)(\d{1,2})", p.name, re.I)
        if not m:
            if "cover" in p.name.lower():
                found.append((0, p))
            continue
        found.append((int(m.group(1)), p))
    # 同页多版本取最新 mtime
    by_idx: dict[int, Path] = {}
    for idx, p in found:
        prev = by_idx.get(idx)
        if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
            by_idx[idx] = p
    return sorted(by_idx.items(), key=lambda x: x[0])


def _title_slug(title: str) -> str:
    s = re.sub(r"[^\w]+", "_", (title or "book").strip().lower())
    return (s[:40] or "book").strip("_")


def _book_widget_id(b: BookArtifacts, *, idx: int | None = None) -> str:
    """Streamlit widget key 片段。

    S&S 里不仅 L0 会缺 Book#，部分级别还可能出现重复 Book#。
    在循环渲染按钮时始终带 idx，避免 StreamlitDuplicateElementKey。
    """
    bn = str(b.book_number or "").strip()
    slug = _title_slug(b.title)
    if idx is not None:
        base = bn or "no_book"
        return f"{b.level}_{idx}_{base}_{slug}"
    if bn:
        return f"{b.level}_{bn}"
    return f"{b.level}_{slug}"


def _find_book(
    by_level: dict[str, list[BookArtifacts]],
    level: str,
    bn: str,
    title: str | None = None,
) -> BookArtifacts | None:
    matches = [b for b in by_level.get(level, []) if b.book_number == bn]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    if title:
        for b in matches:
            if b.title == title:
                return b
    return matches[0]


def _session_matches_book(level: str, bn: str) -> bool:
    outline = st.session_state.get("outline")
    if not outline:
        return False
    ol = str(getattr(outline, "level", "") or "").strip().lstrip("L")
    if ol == "Smart":
        ol = "0"
    obn = str(getattr(outline, "book_number", "") or "").strip()
    try:
        return ol == str(int(level)) and obn == str(int(bn))
    except ValueError:
        return ol == level and obn == bn


def _refine_done_on_disk(out_dir: Path | None) -> bool:
    """Step 2b 精修是否已跑过（有备份目录即视为做过画质精修）。"""
    if not out_dir:
        return False
    pre = out_dir / "images" / "_pre_refine"
    return pre.is_dir() and any(pre.glob("page_*.png"))


def _final_rr_ws_pdf_done(out_dir: Path | None) -> bool:
    return bool(out_dir and any(out_dir.glob("*_Worksheet+RR_Final.pdf")))


def _level_to_age(level: str) -> int:
    try:
        d = int(str(level).strip().lstrip("L") or "4")
    except ValueError:
        return 8
    if d <= 2:
        return 8
    if d <= 4:
        return 10
    return 12


def _ip_reference_paths(level: str) -> list[tuple[str, Path]]:
    age = _level_to_age(level)
    repo = Path(__file__).resolve().parents[1]
    ip_dir = repo / "assets" / "ip_library"
    return [
        (f"Mia {age} 岁", ip_dir / f"mia_{age}.png"),
        (f"Tommy {age} 岁", ip_dir / f"tommy_{age}.png"),
    ]


def _pipeline_step_done(
    key: str,
    art: BookArtifacts | None,
    *,
    session_active: bool,
) -> bool:
    """判断 SOP 展示步是否已完成（只读状态，不改变制作逻辑）。"""
    key = _PIPELINE_FOCUS_ALIASES.get(key, key)
    story = (st.session_state.get("raw_story_input") or "").strip()
    unlocked = int(st.session_state.get("book_unlocked_step", 1) or 1)
    image_results = st.session_state.get("image_results") or {}
    extracted = st.session_state.get("extracted") is not None

    if key == "extract":
        if session_active and extracted:
            return True
        if session_active and unlocked > 1:
            return True
        return bool(story) or bool(art and art.steps.get("story"))
    if key == "ip":
        return session_active and unlocked >= 3
    if key == "images":
        if session_active and len(image_results) >= 7:
            return True
        return bool(art and art.steps.get("images"))
    if key == "refine":
        if session_active:
            locked = sum(
                1 for e in image_results.values()
                if isinstance(e, dict) and e.get("locked")
            )
            if locked >= 7:
                return True
        if art and art.output_dir:
            if _refine_done_on_disk(art.output_dir):
                return True
            if art.steps.get("images") and not art.placeholder_pages:
                return True
        return False
    if key == "assemble":
        if art:
            return all(art.steps.get(k) for k in ("ppt", "ws", "rr", "tg"))
        return session_active and unlocked >= 5
    if key == "deliver":
        return bool(art and (art.steps.get("zip") or _final_rr_ws_pdf_done(art.output_dir)))
    return False


def _normalize_pipeline_focus(key: str | None) -> str | None:
    if not key:
        return None
    k = _PIPELINE_FOCUS_ALIASES.get(str(key), str(key))
    if k in {x[0] for x in SOP_PIPELINE}:
        return k
    return None


def _active_pipeline_key(
    art: BookArtifacts | None,
    *,
    session_active: bool,
) -> str:
    forced = _normalize_pipeline_focus(st.session_state.get("wb_pipeline_focus"))
    if forced:
        return forced
    for key, _, _ in SOP_PIPELINE:
        if not _pipeline_step_done(key, art, session_active=session_active):
            return key
    return SOP_PIPELINE[-1][0]


def _render_sop_flow_bar(
    art: BookArtifacts | None,
    *,
    session_active: bool,
) -> str:
    """VIPKID SOP 横向进度条（只展示，与经典制作 4+1 步一致）。"""
    active = _active_pipeline_key(art, session_active=session_active)
    parts: list[str] = []
    for i, (key, label, hint) in enumerate(SOP_PIPELINE):
        done = _pipeline_step_done(key, art, session_active=session_active)
        if key == active:
            state = "active"
        elif done:
            state = "done"
        else:
            state = "pending"
        parts.append(
            f"<div class='wb-flow-step {state}'>"
            f"<span class='n'>{i + 1}</span>"
            f"<b>{label}</b><span>{hint}</span></div>"
        )
    st.markdown(
        f"<div class='wb-sop-flow'>{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )
    st.caption("标准生产顺序：出图草稿 → 图片精修/终稿编辑 → Reader PPT → RR/Worksheet 终稿质检")
    return active


_render_mvp_flow_bar = _render_sop_flow_bar  # 兼容


def _handle_issue_action(
    action: str,
    art: BookArtifacts,
    *,
    on_enter_work: Callable[[str, str, str], None] | None,
) -> None:
    """问题清单按钮：基础信息留在本页，其余进经典制作（SOP 不变）。"""
    action = _PIPELINE_FOCUS_ALIASES.get(action, action)
    if action in _ISSUE_ACTION_LABELS and action not in ("work",):
        st.session_state["wb_pipeline_focus"] = action
    if action in ("extract", "info", "story"):
        return
    if action == "rr_ws":
        st.session_state["wb_pipeline_focus"] = "deliver"
        return
    if action == "work" or action in ("ip", "images", "refine", "assemble"):
        if on_enter_work:
            on_enter_work(art.level, art.book_number, art.title)


def _render_pipeline_focus_section(
    key: str,
    art: BookArtifacts,
    *,
    session_active: bool,
    on_enter_work: Callable[[str, str, str], None] | None,
) -> None:
    """当前 SOP 步简要说明（Step 1 已由下方表单覆盖）。"""
    key = _PIPELINE_FOCUS_ALIASES.get(key, key)
    if key == "extract":
        return
    guide = _STEP_GUIDE.get(key)
    if not guide:
        return
    title, desc = guide
    st.markdown(f"#### 📍 {title}")
    st.caption(desc)
    if key == "images" and art.placeholder_pages:
        st.warning(
            f"占位页待处理：{', '.join(f'P{p:02d}' for p in art.placeholder_pages)}"
        )
    if key == "refine" and art.output_dir and _refine_done_on_disk(art.output_dir):
        st.success("✅ 已检测到图片精修备份（`images/_pre_refine/`）")
    elif key == "refine" and session_active:
        locked = sum(
            1 for e in (st.session_state.get("image_results") or {}).values()
            if isinstance(e, dict) and e.get("locked")
        )
        st.info(f"分页图锁定 {locked}/7 后，可在经典制作生图区点「全书精修」，或上传 PDF/PPTX/散图进入终稿编辑。")
    if key == "ip":
        _render_ip_lock_visual(art)
    if key == "deliver" and art.output_dir:
        if _final_rr_ws_pdf_done(art.output_dir):
            st.success("✅ 已检测到教研版终稿 PDF（Worksheet + RR Final）")
        else:
            st.info("终稿质检会检查 RR/WS 与绘本/大纲一致性，并合并为教研版 PDF。")
    if on_enter_work:
        if st.button(
            f"→ 经典制作 · {title}",
            key=f"wb_sec_go_{key}",
            type="primary",
            use_container_width=True,
        ):
            on_enter_work(art.level, art.book_number, art.title)


def _render_ip_lock_visual(art: BookArtifacts) -> None:
    """Step ②：按当前 Level 展示参考图，只核对，不配置。"""
    st.markdown("##### Step ② IP 锁可视化（核对而非配置）")
    st.caption("系统按 Level 自动锁 Mia/Tommy 年龄与形象；老师只需核对年龄、Mia 紫色高马尾、Tommy 蓝衣。")
    cols = st.columns(2)
    for i, (col, (label, p)) in enumerate(zip(cols, _ip_reference_paths(art.level))):
        with col:
            _render_thumb_with_lightbox(p, label, key=f"ip_{art.level}_{i}")


def _substep_pills(art: BookArtifacts | None) -> None:
    """基础信息/故事 内的 4 个子步骤 pill。"""
    title = (st.session_state.get("input_title") or "").strip()
    level = st.session_state.get("input_level", "")
    bn = (st.session_state.get("input_book_number") or "").strip()
    story = (st.session_state.get("raw_story_input") or "").strip()
    done_flags = [bool(level), bool(bn), bool(title), bool(story or (art and art.steps.get("story")))]
    pills = []
    for label, ok in zip(_INPUT_SUB_STEPS, done_flags):
        cls = "wb-pill done" if ok else "wb-pill"
        pills.append(f"<span class='{cls}'>{label}</span>")
    st.markdown(f"<div class='wb-pill-row'>{''.join(pills)}</div>", unsafe_allow_html=True)


def _collect_issues(
    art: BookArtifacts | None,
    *,
    session_active: bool,
) -> list[tuple[str, str, str]]:
    """问题清单：(分类, 描述, 动作 key)。"""
    issues: list[tuple[str, str, str]] = []
    title = (st.session_state.get("input_title") or "").strip()
    bn = (st.session_state.get("input_book_number") or "").strip()
    story = (st.session_state.get("raw_story_input") or "").strip()

    if not bn:
        issues.append(("Step1", "建议填写 Book#，系统才能自动匹配大纲", "extract"))
    if not title:
        issues.append(("Step1", "未命中/未确认书名", "extract"))
    if not story and not (art and art.steps.get("story")):
        issues.append(("Step1", "故事正文为空", "extract"))
    if art:
        if art.placeholder_pages:
            issues.append(
                ("精修", f"占位页 {', '.join(f'P{p:02d}' for p in art.placeholder_pages)}", "refine"),
            )
        if not art.steps.get("images"):
            issues.append(("出图", "尚未生成分页图", "images"))
        elif not art.steps.get("ppt"):
            issues.append(("组装", "缺绘本 PPT", "assemble"))
        if not art.steps.get("zip"):
            issues.append(("Step4", "四件套 ZIP 未打包", "assemble"))
        if not _pipeline_step_done("ip", art, session_active=session_active):
            issues.append(("Step2", "IP+画风未确认", "ip"))
        if art.steps.get("images") and not _pipeline_step_done("refine", art, session_active=session_active):
            issues.append(("Step3b", "图片精修未完成（可选）", "refine"))
        if all(art.steps.get(k) for k in ("ws", "rr")) and not _final_rr_ws_pdf_done(art.output_dir):
            issues.append(("终稿", "尚未生成 Worksheet+RR 教研版 PDF", "rr_ws"))
    elif not session_active:
        issues.append(("流程", "尚未进入经典制作向导", "work"))
    return issues


def _hard_gate_rows(art: BookArtifacts | None, *, session_active: bool) -> list[tuple[str, bool, str]]:
    """右栏硬门禁：映射 SOP 自检门，展示为状态行。"""
    image_results = st.session_state.get("image_results") or {}
    prompts = st.session_state.get("page_prompts") or {}
    prompt_ok = True
    if isinstance(prompts, dict) and prompts:
        prompt_ok = all(len(str(v)) < 3800 for v in prompts.values())
    has_images = bool(art and art.steps.get("images")) or bool(image_results)
    rows = [
        ("防分身/超员", has_images and not bool(art and art.placeholder_pages), "每页女孩≤1、男孩≤1；配角≤2且占比≤15%"),
        ("无 Dino 入画", has_images, "Dino 只能作为品牌 logo，不能进故事画面"),
        ("主角在场·年龄对", _pipeline_step_done("ip", art, session_active=session_active), "按 Level 锁 Mia/Tommy 年龄与形象"),
        ("截断防护", prompt_ok, "每页 prompt < 3800 字符"),
        ("④ 精修（可选）", bool(art and _refine_done_on_disk(art.output_dir)), "可跳过；做过会有 images/_pre_refine 备份"),
        ("⑤ 4 件套齐", bool(art and all(art.steps.get(k) for k in ("ppt", "ws", "rr", "tg"))), "Reader PPT / WS / RR / TG"),
        ("⑥ 教辅签字门禁", bool(st.session_state.get("s7_rr_signed") and st.session_state.get("s7_ws_signed")) or bool(art and _final_rr_ws_pdf_done(art.output_dir)), "RR/WS 人工审阅后再放行终稿"),
    ]
    return rows


def _render_production_inline(
    art: BookArtifacts,
    *,
    level_options: list[str],
    on_syllabus_change: Callable[[], None] | None,
    on_pull_syllabus: Callable[[], None] | None,
    on_generate_story_draft: Callable[[], None] | None = None,
    on_enter_work: Callable[[str, str, str], None] | None,
) -> None:
    """内联基础信息 + 故事表单（对标经典制作页 Section A）。"""
    pending = st.session_state.pop("_pending_story_draft", None)
    if pending is not None:
        st.session_state.raw_story_input = pending

    story_err = st.session_state.pop("_wb_story_err", None)
    if story_err:
        st.error(story_err)

    for key, default in (
        ("raw_story_input", ""),
        ("input_level", level_options[0]),
        ("input_book_number", ""),
        ("input_title", art.title or ""),
    ):
        if key not in st.session_state:
            st.session_state[key] = default

    st.markdown('<div id="wb-sec-info" class="wb-sec-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='wb-prod-hint'>"
        "🎯 <b>老师默认只填</b>：① Level ② Book#<br/>"
        "系统会从官方 S&S / 本地 syllabus 自动带出书名、7 页故事、核心词、句型和 phonics；"
        "只在未命中大纲时，才手填书名或点「AI 生成故事草稿」。"
        "</div>",
        unsafe_allow_html=True,
    )
    _substep_pills(art)

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        st.selectbox(
            "🎚️ Level *",
            level_options,
            key="input_level",
            on_change=on_syllabus_change,
        )
    with c2:
        st.text_input(
            "📖 Book # *",
            placeholder="如 45",
            key="input_book_number",
            on_change=on_syllabus_change,
        )
    with c3:
        st.text_input(
            "📕 Book Title（自动匹配，可微调）",
            placeholder="Level + Book# 命中后自动填入",
            key="input_title",
            on_change=on_syllabus_change,
        )

    pull_msg = st.session_state.pop("_syllabus_pull_msg", None)
    if pull_msg == "miss":
        st.warning("⚠️ 未在大纲中找到匹配书目，请核对 Level / Book# / 书名")

    if st.session_state.get("_syllabus_auto_hit"):
        meta = st.session_state.get("_syllabus_auto_meta") or {}
        bc, rc = st.columns([5, 1])
        with bc:
            st.info(
                "📥 **已从大纲自动填入（可编辑）** — "
                f"Level {meta.get('level', '?')} · Book {meta.get('book_number', '—')} · "
                f"{meta.get('title', '')}"
            )
        with rc:
            if on_pull_syllabus and st.button("重新拉取", key="wb_refetch_syllabus"):
                on_pull_syllabus()
    elif on_pull_syllabus:
        if st.button(
            "📥 从大纲拉取正文",
            key="wb_pull_syllabus",
            help="按当前 Level + Book#（优先）或 Level + 书名 从官方大纲拉取 7 页故事",
        ):
            on_pull_syllabus()

    st.markdown(
        "<div class='wb-story-head'>📝 <b>故事正文</b> — 大纲自动填入后可微调，"
        "完成后点「进入制作流程」做 AI 抽取与出图；未命中时再手填</div>",
        unsafe_allow_html=True,
    )
    st.markdown('<div id="wb-sec-story" class="wb-sec-anchor"></div>', unsafe_allow_html=True)
    st.text_area(
        "Raw story",
        label_visibility="collapsed",
        height=180,
        placeholder="选择 Level + 填写 Book# 后自动填入官方故事；或点「从大纲拉取正文」/「AI 生成故事草稿」…",
        key="raw_story_input",
    )
    g1, g2 = st.columns(2)
    with g1:
        if on_generate_story_draft and st.button(
            "✨ AI 生成故事草稿",
            key="wb_gen_story_draft",
            help="未命中大纲时，按书名+Level 生成 7 页故事草稿（可编辑）",
        ):
            on_generate_story_draft()
    with g2:
        st.caption("生成后请在上方微调，再进入制作流程做 AI 抽取")

    a1, a2 = st.columns([2, 1])
    with a1:
        if on_enter_work and st.button(
            "🚀 进入制作流程（AI 抽取 → 出图）",
            type="primary",
            key="wb_enter_work_inline",
            use_container_width=True,
        ):
            on_enter_work(art.level, art.book_number, art.title)
    with a2:
        if on_enter_work and st.button(
            "↗ 展开完整向导",
            key="wb_expand_wizard",
            use_container_width=True,
            help="跳转到经典制作页（批量 / 教辅 / 完整 7 步解锁）",
        ):
            on_enter_work(art.level, art.book_number, art.title)


@st.dialog("图片预览", width="large", dismissible=True)
def _image_preview_dialog(
    *,
    path_str: str,
    page_label: str,
    page_idx: int,
    session_active: bool,
    on_lock: Callable[[int, bool], None] | None,
    on_regen: Callable[[int], None] | None,
    on_refine: Callable[[int], None] | None,
) -> None:
    """shadcn Dialog 风格：大图预览 + 锁定 / 重生 / 精修。"""
    path = Path(path_str)
    if path.exists():
        st.image(str(path), use_container_width=True)
    else:
        st.warning("图片文件不存在")
    st.markdown(f"**{page_label}** · 页 {page_idx}")

    locked = False
    if session_active:
        entry = (st.session_state.get("image_results") or {}).get(page_idx) or {}
        locked = bool(entry.get("locked"))

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        if session_active and on_regen:
            if st.button("🔁 重生", key=f"dlg_regen_{page_idx}", use_container_width=True):
                on_regen(page_idx)
                st.rerun()
        else:
            st.caption("重生需在制作流程中生图后可用")
    with c2:
        if session_active and on_lock:
            new_lock = st.checkbox("✅ 锁定", value=locked, key=f"dlg_lock_{page_idx}")
            if new_lock != locked:
                on_lock(page_idx, new_lock)
                st.rerun()
        else:
            st.caption("锁定需在制作流程中生图后可用")
    with c3:
        if session_active and on_refine:
            if st.button("🪄 GPT 审图修复", key=f"dlg_refine_{page_idx}", use_container_width=True):
                on_refine(page_idx)
                st.rerun()
        else:
            st.caption("审图修复需在制作流程中可用")

    if not session_active:
        st.info("💡 点中栏「进入制作流程」生图后，可在此对话框内直接重生 / 锁定 / 审图。")


def _render_left_tree(
    by_level: dict[str, list[BookArtifacts]],
    *,
    selected: tuple[str, str, str] | None,
    on_select: Callable[[str, str, str], None],
    source_label: str = "",
) -> None:
    st.markdown("##### 📚 课程书目")
    if source_label:
        st.caption(f"进度源：{source_label}")
    search = st.text_input(
        "搜索",
        key="wb_tree_search",
        placeholder="书名 / Book#",
        label_visibility="collapsed",
    )
    ql = (search or "").lower().strip()

    for lvl in sorted(by_level.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        books = by_level[lvl]
        done = sum(1 for b in books if b.status == "done")
        suffix = "钉钉" if any(b.progress_source == "dingtalk" for b in books) else "本地"
        with st.expander(f"Level {lvl} · {done}/{len(books)} · {suffix}", expanded=(lvl == (selected[0] if selected else ""))):
            for i, b in enumerate(books):
                if ql and ql not in b.title.lower() and ql not in b.book_number and ql not in f"l{b.level}":
                    continue
                dot = _STATUS_DOT.get(b.status, "⚪")
                is_sel = selected and _norm_sel(b) == selected
                short = b.title[:26] + ("…" if len(b.title) > 26 else "")
                bn_disp = str(b.book_number or "").strip()
                prefix = f"B{bn_disp}" if bn_disp else f"L{lvl}"
                # 兼容里程碑代理的数据：节点上显示关键里程碑进度
                if b.milestones:
                    ms = f" · 🎯{b.milestone_done_count}/{len(KEY_MILESTONES)}"
                else:
                    ms = f" · {b.current_step[:10]}" if b.current_step else ""
                label = f"{dot} {prefix} · {short}{ms}"
                if st.button(
                    label,
                    key=f"wb_pick_{_book_widget_id(b, idx=i)}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                ):
                    on_select(b.level, b.book_number, b.title)
                    st.rerun()


def _render_milestone_strip(art: BookArtifacts | None) -> None:
    """钉钉 6 个关键里程碑主视图：绘本终审/印刷、合并完成/合并终审、TG终审/App上线。"""
    if art is None or not art.milestones:
        return
    st.markdown(
        f"**🎯 关键里程碑（钉钉真实列）· {art.milestone_done_count}/{len(KEY_MILESTONES)}**"
    )
    # 按归属组分行展示：Book / WS+RR / TG
    by_group: dict[str, list[tuple[str, dict]]] = {}
    for spec in KEY_MILESTONES:
        m = art.milestones.get(spec["key"]) or {}
        by_group.setdefault(spec["group"], []).append((spec["name"], m))
    for group, items in by_group.items():
        glabel = MILESTONE_GROUP_LABELS.get(group, group)
        chips = []
        for name, m in items:
            icon = milestone_cell_icon(m)
            col = m.get("column") or ""
            col_hint = f" <code>{col}</code>" if col else ""
            chips.append(f"{icon} {name}{col_hint}")
        st.markdown(
            f"<div class='wb-checklist-row'><b>{glabel}</b><br/>"
            + " &nbsp;·&nbsp; ".join(chips)
            + "</div>",
            unsafe_allow_html=True,
        )
    nxt = art.milestone_next or "全部关键里程碑已完成"
    st.caption(f"下一关键步：{nxt}  （✅完成 ⬜未完成 🟡待确认 🔴问题 —无此列）")


def _render_center_pipeline(
    art: BookArtifacts | None,
    *,
    on_enter_work: Callable[[str, str, str], None] | None,
    session_active: bool,
    on_regen: Callable[[int], None] | None,
    on_lock: Callable[[int, bool], None] | None,
    on_refine: Callable[[int], None] | None,
    level_options: list[str] | None = None,
    on_syllabus_change: Callable[[], None] | None = None,
    on_pull_syllabus: Callable[[], None] | None = None,
    on_generate_story_draft: Callable[[], None] | None = None,
) -> None:
    st.markdown("##### ⚙️ 制作流水线")

    if art is None:
        st.markdown(
            "<div class='wb-empty'>← 请从左侧选择一本书</div>",
            unsafe_allow_html=True,
        )
        return

    pill_cls, status_lbl = _STATUS_PILL_CLASS.get(
        art.status, ("wb-status-pill warning", _STATUS_LABEL.get(art.status, art.status))
    )
    st.markdown(
        f"<div class='wb-book-head'>"
        f"<span class='{pill_cls}'>{status_lbl}</span>"
        f"<h3>L{art.level} · Book {art.book_number}</h3>"
        f"<p>{art.title}</p></div>",
        unsafe_allow_html=True,
    )

    active_key = _render_sop_flow_bar(art, session_active=session_active)

    done_n = art.timeline_done_count or sum(1 for k, _, _ in PIPELINE_STEPS if art.steps.get(k))
    total_n = art.timeline_total_count or len(PIPELINE_STEPS)
    pct = art.timeline_done_pct if art.timeline_total_count else art.progress_pct
    st.markdown(
        f"<div class='wb-track'><div class='wb-fill' style='width:{pct}%'></div></div>",
        unsafe_allow_html=True,
    )
    source_name = "钉钉环节" if art.timeline_total_count else "磁盘产物"
    st.caption(f"{source_name} {pct}%（{done_n}/{total_n} 项）")
    if art.timeline_total_count:
        next_step = art.next_pending_step or "全部关键环节已完成"
        issue_line = "；".join(art.blocked_steps[:2]) if art.blocked_steps else "无"
        st.info(
            f"钉钉同步：已完成 {art.timeline_done_count}/{art.timeline_total_count} 环节 · "
            f"下一步：{next_step} · 问题：{issue_line}"
        )

    _render_milestone_strip(art)

    lv_opts = level_options or _DEFAULT_LEVEL_OPTIONS
    _render_production_inline(
        art,
        level_options=lv_opts,
        on_syllabus_change=on_syllabus_change,
        on_pull_syllabus=on_pull_syllabus,
        on_generate_story_draft=on_generate_story_draft,
        on_enter_work=on_enter_work,
    )
    _render_pipeline_focus_section(
        active_key,
        art,
        session_active=session_active,
        on_enter_work=on_enter_work,
    )

    if session_active:
        unlocked = st.session_state.get("book_unlocked_step", 1)
        st.success(f"✨ 当前会话正在编辑此书 · 向导 Step {unlocked}")
        if st.button("📖 继续当前会话（经典页）", key="wb_continue_session"):
            if on_enter_work:
                on_enter_work(art.level, art.book_number, art.title)

    st.markdown("---")
    st.markdown("##### 🖼️ 分页图")

    images: list[tuple[int, Path]] = []
    if session_active and st.session_state.get("image_results"):
        for idx, entry in sorted(st.session_state.get("image_results", {}).items()):
            p = entry.get("path")
            if p and Path(p).exists():
                images.append((int(idx), Path(p)))
    elif art.output_dir:
        images = _list_page_images(art.output_dir)

    if not images:
        st.caption("暂无分页图 · 进入制作流程后出图")
    else:
        ncols = 4
        cols = st.columns(ncols)
        for i, (pidx, img_path) in enumerate(images):
            with cols[i % ncols]:
                if img_path.exists():
                    st.image(str(img_path), use_container_width=True)
                label = "封面" if pidx == 0 else f"P{pidx:02d}"
                lock_mark = ""
                if session_active:
                    ent = (st.session_state.get("image_results") or {}).get(pidx) or {}
                    if ent.get("locked"):
                        lock_mark = " 🔒"
                if st.button(
                    f"🔍 预览{label}{lock_mark}",
                    key=f"wb_img_{_book_widget_id(art)}_{pidx}",
                    use_container_width=True,
                ):
                    _image_preview_dialog(
                        path_str=str(img_path),
                        page_label=label,
                        page_idx=pidx,
                        session_active=session_active,
                        on_lock=on_lock,
                        on_regen=on_regen,
                        on_refine=on_refine,
                    )


def _render_right_checklist(
    art: BookArtifacts | None,
    stats: dict[str, Any],
    *,
    session_active: bool = False,
    on_enter_work: Callable[[str, str, str], None] | None = None,
) -> None:
    st.markdown("##### ✅ 本书检查清单")

    dt = stats.get("dingtalk") or {}
    ps = stats.get("progress_source") or {}
    hash_bits = []
    if dt.get("hash_l02"):
        hash_bits.append("L0-L2")
    if dt.get("hash_l36"):
        hash_bits.append("L3-L6")
    if dt.get("hash_requirements"):
        hash_bits.append("Timeline")
    hash_line = " · ".join(hash_bits) if hash_bits else "未检测到 hash"

    st.markdown(
        f"<div class='wb-dingtalk-strip'>"
        f"<span class='k'>钉钉同步</span>"
        f"S&S <b>{dt.get('syllabus_synced_at', '—')}</b> · "
        f"Timeline <b>{dt.get('timeline_req_synced', '—')}</b><br/>"
        f"进度源 <b>{ps.get('label', '本地输出扫描（降级）')}</b> · "
        f"同步 <b>{ps.get('last_synced', '—')}</b><br/>"
        f"<span class='sub'>{hash_line}</span></div>",
        unsafe_allow_html=True,
    )

    totals = stats.get("totals") or {}
    st.markdown(
        f"<div class='wb-light-status'>团队进度：完成 <b>{totals.get('done', 0)}/{totals.get('total', 0)}</b> · "
        f"待人工 <b>{stats.get('manual_count', 0)}</b><br/>完整明细请到「数据看板」。</div>",
        unsafe_allow_html=True,
    )

    if art is None:
        st.caption("选中书目后显示本书待办")
        return

    st.markdown("---")
    st.markdown(f"**本书 · L{art.level} B{art.book_number}**")
    st.caption(
        f"进度源：{art.progress_source_label}"
        + (f" · 当前步骤：{art.current_step}" if art.current_step else "")
        + (f" · 下一步：{art.next_pending_step}" if art.next_pending_step else "")
        + (f" · 负责人：{art.owner}" if art.owner else "")
    )
    if art.timeline_total_count:
        issue_line = "；".join(art.blocked_steps[:3]) if art.blocked_steps else "无"
        st.markdown(
            f"<div class='wb-light-status'>钉钉环节：已完成 "
            f"<b>{art.timeline_done_count}/{art.timeline_total_count}</b> · "
            f"下一步 <b>{art.next_pending_step or '全部关键环节已完成'}</b><br/>"
            f"问题/待确认：{issue_line}</div>",
            unsafe_allow_html=True,
        )

    # 关键里程碑主视图（默认展开）
    _render_milestone_strip(art)

    timeline_steps = art.timeline_steps or []
    with st.expander(
        f"钉钉全部列明细（真实列顺序 · Done {art.timeline_done_count}/{art.timeline_total_count}）",
        expanded=False,
    ):
        if timeline_steps:
            for step in timeline_steps:
                state = str(step.get("state") or "pending")
                label = str(step.get("display_label") or step.get("label") or "")
                col = str(step.get("excel_col") or step.get("column") or "").strip()
                prefix = f"`{col}` · " if col else ""
                value = str(step.get("value") or "").strip()
                value_hint = f" · `{value}`" if value else ""
                st.markdown(
                    f"<div class='wb-checklist-row'>"
                    f"{_TIMELINE_STATE_LABEL.get(state, '⬜ 待做')} {prefix}<b>{label}</b>{value_hint}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("暂无钉钉逐列缓存；可在数据看板点击“从钉钉刷新进度”。")

    st.markdown("---")
    with st.expander("本地 SOP / 磁盘产物辅助（非钉钉主表）", expanded=False):
        st.markdown("**硬门禁自检**")
        for label, ok, hint in _hard_gate_rows(art, session_active=session_active):
            icon = "✅" if ok else "⬜"
            st.markdown(
                f"<div class='wb-checklist-row'>{icon} <b>{label}</b><br/><span>{hint}</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown("**当前书 SOP 6 步**")
        for key, label, _hint in SOP_PIPELINE:
            ok = _pipeline_step_done(key, art, session_active=session_active)
            icon = "✅" if ok else "⬜"
            focus = " ←" if st.session_state.get("wb_pipeline_focus") == key else ""
            opt = " <span class='wb-opt'>可跳过</span>" if key == "refine" else ""
            st.markdown(f"<div class='wb-checklist-row'>{icon} {label}{opt}{focus}</div>", unsafe_allow_html=True)

        st.markdown("**待您手动**")
        todos = art.manual_todos or []
        if todos:
            for j, t in enumerate(todos):
                st.markdown(
                    f"<div class='wb-issue-card manual'>"
                    f"<span class='cat'>手动</span>🖐 {t}</div>",
                    unsafe_allow_html=True,
                )
                if st.button("去处理", key=f"wb_todo_{_book_widget_id(art)}_{j}", use_container_width=True):
                    _handle_issue_action("work", art, on_enter_work=on_enter_work)
                    st.rerun()
        else:
            st.markdown("<div class='wb-todo-ok'>✅ 无待办项</div>", unsafe_allow_html=True)

        if art.placeholder_pages:
            st.warning(f"占位页：{', '.join(f'P{p:02d}' for p in art.placeholder_pages)}")

        st.markdown("**磁盘产物**")
        for key, label, _art in PIPELINE_STEPS:
            ok = art.steps.get(key, False)
            icon = "✅" if ok else "⬜"
            st.markdown(f"{icon} {label}")

        if art.output_dir:
            st.caption(f"`{art.output_dir}`")

    st.markdown("---")
    st.markdown("##### ⚠️ 本地辅助问题清单")
    issues = _collect_issues(art, session_active=session_active)
    if not issues:
        st.markdown("<div class='wb-issue-ok'>✅ 暂无阻塞项</div>", unsafe_allow_html=True)
    else:
        for i, (cat, msg, action) in enumerate(issues):
            btn_lbl = _ISSUE_ACTION_LABELS.get(action, "去处理")
            st.markdown(
                f"<div class='wb-issue-card'>"
                f"<span class='cat'>{cat}</span>{msg}</div>",
                unsafe_allow_html=True,
            )
            if st.button(btn_lbl, key=f"wb_issue_{i}_{action}", use_container_width=True):
                _handle_issue_action(action, art, on_enter_work=on_enter_work)
                st.rerun()

    st.markdown("---")
    st.markdown("##### ⚡ 快捷动作")
    q1, q2 = st.columns(2)
    with q1:
        if st.button("🔎 定位缺失页", key="wb_quick_missing", use_container_width=True):
            st.session_state["wb_pipeline_focus"] = "images"
            st.rerun()
        if st.button("🧪 全书体检", key="wb_quick_check", use_container_width=True):
            st.session_state["wb_pipeline_focus"] = "deliver"
            st.rerun()
    with q2:
        if st.button("⚡ 一键生成资源", key="wb_quick_assemble", use_container_width=True):
            _handle_issue_action("assemble", art, on_enter_work=on_enter_work)
            st.rerun()
        if st.button("📤 提交审核", key="wb_quick_submit", use_container_width=True):
            st.session_state["wb_pipeline_focus"] = "deliver"
            st.info("已定位到校验&打包；请完成 RR/WS 签字门禁后提交。")


def _function_done(
    key: str,
    art: BookArtifacts | None,
    *,
    session_active: bool,
) -> bool:
    """五大用户入口的轻量状态，不改变底层生产逻辑。"""
    if key == "single":
        return bool(art and art.steps.get("zip"))
    if key == "upload":
        return False
    if key == "refine_pub":
        return bool(art and _refine_done_on_disk(art.output_dir))
    if key == "rr_ws":
        return bool(art and _final_rr_ws_pdf_done(art.output_dir))
    if key == "batch":
        return False
    return _pipeline_step_done(key, art, session_active=session_active)


def _active_function_key(art: BookArtifacts | None, *, session_active: bool) -> str:
    """当前应聚焦的功能（第一个未完成项）。"""
    forced = str(st.session_state.get("wb_function_focus") or "")
    if forced in {x[0] for x in CENTER_FUNCTIONS}:
        return forced
    if art is None:
        return "single"
    for key, *_ in CENTER_FUNCTIONS:
        if not _function_done(key, art, session_active=session_active):
            return key
    return CENTER_FUNCTIONS[-1][0]


def _render_center_functions(
    art: BookArtifacts | None,
    *,
    session_active: bool,
) -> None:
    """生产平台五大入口卡片；单本标准生产始终为最大核心。"""
    active = _active_function_key(art, session_active=session_active)
    cards: list[str] = []
    for i, (key, label, hint, badge) in enumerate(CENTER_FUNCTIONS):
        done = _function_done(key, art, session_active=session_active) if art else False
        if key == "single":
            state = "core done" if done else "core active"
        elif art and key == active and not done:
            state = "active"
        elif done:
            state = "done"
        else:
            state = "pending"
        cards.append(
            f"<div class='wb-func-card {state}'>"
            f"<span class='n'>{i + 1}</span>"
            f"<em>{badge}</em><b>{label}</b><span class='d'>{hint}</span></div>"
        )
    st.markdown(
        f"<div class='wb-func-grid'>{''.join(cards)}</div>",
        unsafe_allow_html=True,
    )


def _render_global_kpis(stats: dict[str, Any]) -> None:
    """生产页只保留小状态徽章；完整分析在独立数据看板页。"""
    totals = stats.get("totals") or {}
    total = int(totals.get("total", 0) or 0)
    done = int(totals.get("done", 0) or 0)
    partial = int(totals.get("partial", 0) or 0)
    pct = int(done / total * 100) if total else 0
    ps = stats.get("progress_source") or {}
    st.markdown(
        f"<div class='wb-mini-status'>生产状态：已完成 <b>{done}/{total}</b> · "
        f"进行中 <b>{partial}</b> · 完成率 <b>{pct}%</b> "
        f"<span>数据源：{ps.get('label', '本地输出扫描（降级）')} · 完整明细请到「数据看板」页查看</span></div>",
        unsafe_allow_html=True,
    )


def _render_left_rail(
    by_level: dict[str, list[BookArtifacts]],
    stats: dict[str, Any],
    *,
    selected: tuple[str, str, str] | None,
    on_select: Callable[[str, str, str], None],
    on_open_nav: Callable[[str], None] | None,
    on_enter_work: Callable[[str, str, str], None] | None,
) -> None:
    """左侧导航：生产平台内只保留选书与入口，不承载数据看板。"""
    st.markdown(
        "<div class='wb-rail-intro'>"
        "<div class='wb-rail-kicker'>DINO ONLINE CLUB</div>"
        "<b>绘本生产工作台</b>"
        "<p>生产平台默认聚焦 <b>单本绘本标准生产</b>。数据统计在独立「数据看板」页；"
        "本页只保留必要状态、选书与交付核对。</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if on_open_nav and st.button("📊 打开数据看板", key="wb_rail_dashboard", use_container_width=True):
        on_open_nav("dashboard")

    ps = stats.get("progress_source") or {}
    st.markdown("---")
    _render_left_tree(
        by_level,
        selected=selected,
        on_select=on_select,
        source_label=str(ps.get("label", "本地输出扫描（降级）")),
    )

    st.markdown("---")
    with st.expander("🗄️ 数据模型 / 数据源", expanded=False):
        st.caption(
            "· 官方 S&S 大纲（在场名单 / 逐页场景的权威源）\n\n"
            "· IP 形象库 `assets/ip_library`（按级别年龄定妆）\n\n"
            "· 钉钉进度表缓存 `references/syllabus/progress_status.json`（团队生产进度优先源）\n\n"
            "· 输出目录（仅在钉钉进度不可用时降级估算）"
        )
        dt = stats.get("dingtalk") or {}
        st.caption(
            f"钉钉同步：S&S {dt.get('syllabus_synced_at', '—')} · "
            f"Timeline {dt.get('timeline_req_synced', '—')} · "
            f"进度源 {ps.get('label', '本地输出扫描（降级）')} {ps.get('last_synced', '—')}"
        )

    with st.expander("⚙️ 配置", expanded=False):
        _cfg = (
            ("settings", "🔑 设置 / 密钥"),
            ("overview", "🏠 概览"),
            ("onboarding", "📖 新手引导"),
            ("metrics", "📈 指标"),
        )
        for nav_key, lbl in _cfg:
            if on_open_nav and st.button(lbl, key=f"wb_rail_cfg_{nav_key}", use_container_width=True):
                on_open_nav(nav_key)
        if on_open_nav and st.button("🧰 经典制作（完整 7 步向导）", key="wb_rail_classic", use_container_width=True):
            on_open_nav("work")


def _render_right_panel(
    art: BookArtifacts | None,
    stats: dict[str, Any],
    *,
    session_active: bool,
    on_enter_work: Callable[[str, str, str], None] | None,
) -> None:
    """右侧：本书「全部功能」状态总览 + 检查清单（详情 / 待办 / 问题）。"""
    if art is not None:
        st.markdown("##### 🧭 本书全部功能")
        for i, (key, label, _hint, _badge) in enumerate(CENTER_FUNCTIONS):
            ok = _function_done(key, art, session_active=session_active)
            icon = "✅" if ok else "⬜"
            st.markdown(
                f"<div class='wb-checklist-row'>{icon} <b>{i + 1}.</b> {label}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("---")
    _render_right_checklist(
        art,
        stats,
        session_active=session_active,
        on_enter_work=on_enter_work,
    )


# =========================================================================
# IDE 化增强（仅 UI / 同步入口；绝不改动底层 SOP 生产逻辑/提示词）
# =========================================================================
_WB_REPO = Path(__file__).resolve().parents[1]
_WB_SCRIPTS_DIR = Path(__file__).resolve().parent
_NOTES_JSON = _WB_REPO / "references" / "workbench_notes.json"

# 顶部统一「从钉钉刷新」覆盖的脚本（手动触发；无后台轮询/定时线程）。
_SYNC_SCRIPTS = ("sync_syllabus_from_dingtalk.py", "sync_progress_from_dingtalk.py")


def _can_run_dingtalk_sync() -> bool:
    """Only show live DingTalk sync where the local dws CLI is available."""
    return shutil.which("dws") is not None

# 布局调宽预设：Streamlit 折中——切换 st.columns 比例，不能像浏览器自由拖拽分隔条。
# "专注中栏" 用 (0,1,0) 标记为「只渲染中栏全宽」。
_LAYOUT_PRESETS: dict[str, tuple[float, float, float]] = {
    "偏左": (1.65, 1.85, 0.95),
    "均衡": (1.05, 2.15, 0.95),
    "偏右": (0.95, 1.85, 1.45),
    "专注中栏": (0.0, 1.0, 0.0),
}
_LAYOUT_ORDER = ["偏左", "均衡", "偏右", "专注中栏"]

_AI_SYSTEM = (
    "你是 VIPKID Dino 绘本生产平台的只读助手。"
    "只能依据【已知数据】回答关于 OKR / SOP / 生产进度 / 某本书状态的问题，"
    "用简体中文、简洁作答。数据没覆盖时明确说『当前数据未覆盖』，绝不编造数字或状态。"
    "你没有任何写入或修改数据的能力，只做问答。"
)


# ---------------- 本地备注存储（按节点 id 区分，存本地 json） ----------------
def _load_notes() -> dict[str, str]:
    if not _NOTES_JSON.is_file():
        return {}
    try:
        data = json.loads(_NOTES_JSON.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_note(node_id: str, text: str) -> None:
    notes = _load_notes()
    if (text or "").strip():
        notes[node_id] = text
    else:
        notes.pop(node_id, None)
    try:
        _NOTES_JSON.parent.mkdir(parents=True, exist_ok=True)
        _NOTES_JSON.write_text(
            json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        st.warning(f"备注保存失败：{e}")


def _node_id(art: BookArtifacts) -> str:
    base = str(art.book_number or "").strip() or _title_slug(art.title)
    return f"L{art.level}-B{base}"


# ---------------- 布局调宽控件 ----------------
def _render_layout_control() -> tuple[str, tuple[float, float, float]]:
    """顶部布局调宽控件：切换三栏比例并记忆到 session_state（Streamlit 折中方案）。"""
    cur = st.session_state.get("wb_layout_mode")
    if cur not in _LAYOUT_PRESETS:
        cur = "均衡"
    picker = getattr(st, "segmented_control", None)
    if callable(picker):
        choice = picker(
            "栏宽布局",
            _LAYOUT_ORDER,
            default=cur,
            key="wb_layout_seg",
            help="切换三栏宽度比例（偏左/均衡/偏右/专注中栏）。Streamlit 下为比例切换，非自由拖拽。",
        )
    else:
        choice = st.radio(
            "栏宽布局",
            _LAYOUT_ORDER,
            index=_LAYOUT_ORDER.index(cur),
            horizontal=True,
            key="wb_layout_seg",
        )
    choice = choice if choice in _LAYOUT_PRESETS else cur
    st.session_state["wb_layout_mode"] = choice
    return choice, _LAYOUT_PRESETS[choice]


# ---------------- 顶部钉钉统一刷新条（手动 + 上次同步时间） ----------------
def _run_sync_scripts(scripts: tuple[str, ...]) -> list[tuple[str, bool, str]]:
    """顺序运行 sync 脚本（复用现有脚本，不新增轮询/线程）。返回 (名称, 成功, 日志尾)。"""
    results: list[tuple[str, bool, str]] = []
    for name in scripts:
        script = _WB_SCRIPTS_DIR / name
        if not script.is_file():
            results.append((name, False, "脚本不存在"))
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(_WB_REPO),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=1800,
            )
            ok = proc.returncode == 0
            tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-1800:]
            results.append((name, ok, tail or ("同步完成" if ok else "无输出")))
        except Exception as e:  # noqa: BLE001 - 同步失败要回显，不抛断 UI
            results.append((name, False, str(e)))
    return results


def _render_dingtalk_sync_bar(stats: dict[str, Any]) -> None:
    """统一「从钉钉刷新」入口：覆盖 4 个文档，各自显示上次同步时间与状态。"""
    dt = stats.get("dingtalk") or {}
    ps = stats.get("progress_source") or {}
    docs = [
        ("📚 大纲总文档", f"同步 {dt.get('syllabus_synced_at', '—')}",
         f"{dt.get('book_count', 0)} 本 · syllabus.json", bool(dt.get("book_count"))),
        ("🟢 Level 0-2 大纲", "已同步" if dt.get("hash_l02") else "未同步",
         str(dt.get("source_l02", "—")), bool(dt.get("hash_l02"))),
        ("🔵 Level 3-6 大纲", "已同步" if dt.get("hash_l36") else "未同步",
         str(dt.get("source_l36", "—")), bool(dt.get("hash_l36"))),
        ("🗓️ 进度表 Timeline", f"同步 {ps.get('last_synced', '—')}",
         f"{ps.get('record_count', 0)} 条 · {ps.get('label', '—')}", ps.get("mode") == "dingtalk"),
    ]
    chips = "".join(
        f"<div class='wb-sync-card {'ok' if ok else 'warn'}'>"
        f"<b>{title}</b><span>{when}</span><em>{extra}</em></div>"
        for title, when, extra, ok in docs
    )
    st.markdown(f"<div class='wb-sync-bar'>{chips}</div>", unsafe_allow_html=True)

    can_sync = _can_run_dingtalk_sync()
    c1, c2 = st.columns([1, 4])
    with c1:
        if can_sync:
            do_sync = st.button(
                "☁️ 从钉钉刷新",
                key="wb_sync_all",
                use_container_width=True,
                help="手动运行 sync_syllabus + sync_progress，一次覆盖 4 个文档（无后台轮询/定时线程）。",
            )
        else:
            do_sync = False
            st.info("线上环境不能直接连接钉钉。请在本地同步后发布。")
    with c2:
        if can_sync:
            st.caption(
                "统一手动刷新：大纲总文档 / L0-2 / L3-6 / 进度表 Timeline。"
                "各自上次同步时间见上方卡片；钉钉为只读取数，不回写。"
            )
        else:
            st.caption(
                "钉钉同步依赖本机 dws 登录状态，Streamlit Cloud 无法扫码登录。"
                "更新大纲后，请在本地执行同步脚本并 git push，线上会随 GitHub 自动重部署。"
            )
    if do_sync:
        with st.spinner("正在从钉钉刷新 4 个文档（大纲 + 进度表）…"):
            results = _run_sync_scripts(_SYNC_SCRIPTS)
        scan_output_index.cache_clear()
        load_progress_cache.cache_clear()
        all_ok = all(ok for _n, ok, _t in results)
        for name, ok, tail in results:
            (st.success if ok else st.error)(
                f"{name} {'✓ 已刷新' if ok else '失败 · 可在终端运行 `py scripts/' + name + '`'}"
            )
            with st.expander(f"日志 · {name}", expanded=not ok):
                st.code(tail or "无输出", language="text")
        if all_ok:
            st.rerun()


# ---------------- 可复用图片放大 lightbox ----------------
@st.dialog("图片预览", width="large", dismissible=True)
def _simple_image_dialog(*, path_str: str, caption: str = "") -> None:
    p = Path(path_str)
    if p.exists():
        st.image(str(p), use_container_width=True)
        if caption:
            st.caption(caption)
    else:
        st.warning(f"图片不存在：{p.name}")


def _render_thumb_with_lightbox(path: Path, caption: str, key: str) -> None:
    """缩略图 + 点击放大（lightbox）。可复用到任意已展示图片处。"""
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=True)
        if st.button("🔍 放大", key=f"wb_lb_{key}", use_container_width=True):
            _simple_image_dialog(path_str=str(path), caption=caption)
    else:
        st.info(f"{caption}：未找到 `{path.name}`")


# ---------------- 中栏：可编辑备注（按节点 id 存本地 json） ----------------
def _render_book_notes(art: BookArtifacts) -> None:
    nid = _node_id(art)
    notes = _load_notes()
    widget_key = f"wb_note_{nid}"
    st.markdown("##### 📝 本书备注（本地保存）")
    st.text_area(
        "备注",
        value=notes.get(nid, ""),
        key=widget_key,
        height=110,
        label_visibility="collapsed",
        placeholder="记录本书的人工抽查 / 待确认事项 / 沟通备忘…（仅存本地 references/workbench_notes.json）",
    )
    bc1, bc2 = st.columns([1, 3])
    with bc1:
        if st.button("💾 保存备注", key=f"wb_note_save_{nid}", use_container_width=True):
            _save_note(nid, st.session_state.get(widget_key, ""))
            st.toast("备注已保存")
    with bc2:
        st.caption(f"节点 id：`{nid}` · 切换书目自动载入对应备注")


# ---------------- 右侧只读 AI 对话 dock ----------------
def _ai_build_context(
    art: BookArtifacts | None,
    stats: dict[str, Any],
    by_level: dict[str, list[BookArtifacts]],
) -> str:
    """从本地数据(syllabus/progress)汇总只读上下文，喂给 LLM 或规则式回退。"""
    lines: list[str] = []
    totals = stats.get("totals") or {}
    ps = stats.get("progress_source") or {}
    dt = stats.get("dingtalk") or {}
    lines.append(
        f"团队进度：完成 {totals.get('done', 0)}/{totals.get('total', 0)}，"
        f"进行中 {totals.get('partial', 0)}，待人工 {stats.get('manual_count', 0)}。"
    )
    lines.append(
        f"进度数据源：{ps.get('label', '—')}，最后同步 {ps.get('last_synced', '—')}，"
        f"缓存记录 {ps.get('record_count', 0)} 条。"
    )
    lines.append(
        f"钉钉大纲同步：{dt.get('syllabus_synced_at', '—')}，共 {dt.get('book_count', 0)} 本；"
        f"Timeline 需求表 {dt.get('timeline_req_synced', '—')}。"
    )
    for lvl in sorted(by_level.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        books = by_level[lvl]
        done = sum(1 for b in books if b.status == "done")
        partial = sum(1 for b in books if b.status == "partial")
        lines.append(f"Level {lvl}：共 {len(books)} 本，完成 {done}，进行中 {partial}。")
    if art is not None:
        lines.append("")
        lines.append(f"【当前选中】L{art.level} Book {art.book_number or '—'} · {art.title}")
        lines.append(
            f"状态：{_STATUS_LABEL.get(art.status, art.status)}；"
            f"当前步骤：{art.current_step or '—'}；下一步：{art.next_pending_step or '—'}；"
            f"负责人：{art.owner or '—'}；进度源：{art.progress_source_label}。"
        )
        if art.milestones:
            ms = []
            for spec in KEY_MILESTONES:
                m = art.milestones.get(spec["key"]) or {}
                ms.append(f"{spec['name']}={milestone_cell_icon(m)}")
            lines.append(
                f"关键里程碑（{art.milestone_done_count}/{len(KEY_MILESTONES)}）："
                + " ".join(ms)
            )
        if art.timeline_steps:
            done_steps = [str(s.get("label")) for s in art.timeline_steps if s.get("state") == "done"]
            pend_steps = [str(s.get("label")) for s in art.timeline_steps if s.get("state") == "pending"]
            if done_steps:
                lines.append("已完成环节：" + "、".join(done_steps[:20]))
            if pend_steps:
                lines.append("待办环节：" + "、".join(pend_steps[:20]))
        if art.blocked_steps:
            lines.append("问题/待确认：" + "、".join(art.blocked_steps[:10]))
        nid = _node_id(art)
        note = _load_notes().get(nid)
        if note:
            lines.append(f"本书备注：{note[:300]}")
    return "\n".join(lines)


def _ai_rule_based(question: str, context: str) -> str:
    """无 LLM 时的规则式占位问答：基于本地数据上下文做关键词召回。"""
    ctx_lines = [ln for ln in context.splitlines() if ln.strip()]
    kws = [w for w in re.split(r"[\s，。、?？!！:：;；()（）]+", question) if len(w) >= 2]
    picked = [ln for ln in ctx_lines if any(k in ln for k in kws)] if kws else []
    body = "\n".join(picked or ctx_lines[:8])
    return (
        "（规则式占位回答 · 未配置 LLM API Key，仅基于本地 syllabus.json / "
        "progress_status.json 数据召回相关行）\n\n"
        + body
        + "\n\nTODO：配置 `DEEPSEEK_API_KEY` 后将自动启用自然语言问答。"
    )


def _ai_answer(question: str, context: str) -> str:
    try:
        from deepseek_client import deepseek_chat, is_deepseek_available

        if is_deepseek_available():
            return deepseek_chat(
                system=_AI_SYSTEM,
                user=f"已知数据：\n{context}\n\n问题：{question}",
                temperature=0.2,
                max_tokens=700,
            )
    except Exception as e:  # noqa: BLE001 - LLM 不可用时降级到规则式
        return _ai_rule_based(question, context) + f"\n\n（注：LLM 暂不可用：{e}）"
    return _ai_rule_based(question, context)


def _render_ai_dock(
    art: BookArtifacts | None,
    stats: dict[str, Any],
    by_level: dict[str, list[BookArtifacts]],
) -> None:
    st.markdown("##### 🤖 AI 助手 · 只读问答")
    try:
        from deepseek_client import is_deepseek_available

        avail = is_deepseek_available()
    except Exception:
        avail = False
    if avail:
        st.caption("基于本地大纲/进度数据回答 OKR / SOP / 进度 / 某本书状态。只读，不写数据。")
    else:
        st.caption(
            "⚠️ 未配置 LLM Key：当前为规则式占位问答（基于本地 JSON）。"
            "配置 `DEEPSEEK_API_KEY` 后自动启用自然语言问答。"
        )

    history: list[dict[str, str]] = st.session_state.setdefault("wb_ai_chat", [])
    if not history:
        scope = f"已选《{art.title}》" if art else "未选书（团队总览）"
        st.info(
            f"问答范围：{scope}。例如：本书还差哪些环节？/ L4 完成多少本？/ 这本谁负责？"
        )
    for msg in history[-12:]:
        with st.chat_message(msg.get("role", "assistant")):
            st.markdown(msg.get("content", ""))
    if history and st.button("🧹 清空对话", key="wb_ai_clear", use_container_width=True):
        st.session_state["wb_ai_chat"] = []
        st.rerun()
    prompt = st.chat_input("问关于进度 / SOP / 某本书的问题…", key="wb_ai_input")
    if prompt:
        history.append({"role": "user", "content": prompt})
        ctx = _ai_build_context(art, stats, by_level)
        with st.spinner("思考中…"):
            answer = _ai_answer(prompt, ctx)
        history.append({"role": "assistant", "content": answer})
        st.session_state["wb_ai_chat"] = history
        st.rerun()


def render_workbench(
    *,
    on_enter_work: Callable[[str, str, str], None] | None = None,
    on_select_book: Callable[[str, str, str, BookArtifacts | None], None] | None = None,
    on_open_nav: Callable[[str], None] | None = None,
    on_lock_image: Callable[[int, bool], None] | None = None,
    on_regen_image: Callable[[int], None] | None = None,
    on_refine_image: Callable[[int], None] | None = None,
    on_syllabus_change: Callable[[], None] | None = None,
    on_pull_syllabus: Callable[[], None] | None = None,
    on_generate_story_draft: Callable[[], None] | None = None,
    level_options: list[str] | None = None,
) -> None:
    """三栏单页工作台主入口（IDE 化：目录树 / 详情文档 / AI dock）。"""
    st.markdown(
        """
        <div class="wb-hero">
          <div class="wb-kicker">VIPKID 绘本 SOP · 生产平台</div>
          <h2>生产平台：单本标准生产为核心</h2>
          <p>默认单本标准生产；后续可做图片精修/Reader 终稿编辑，再做已有绘本三件套、RR/Worksheet 教研版和批量高级入口。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hdr_l, hdr_r = st.columns([5, 1])
    with hdr_r:
        if st.button("🔄 全量刷新", key="wb_global_refresh", use_container_width=True):
            scan_output_index.cache_clear()
            load_progress_cache.cache_clear()
            st.rerun()

    with st.spinner("扫描大纲与输出目录…"):
        stats = build_level_stats()

    by_level: dict[str, list[BookArtifacts]] = stats.get("by_level") or {}

    # 顶部钉钉统一刷新条（4 文档 + 各自上次同步时间）
    _render_dingtalk_sync_bar(stats)

    # 选中态
    sel = st.session_state.get("wb_selected")
    if isinstance(sel, (list, tuple)) and len(sel) == 3:
        selected: tuple[str, str, str] | None = (str(sel[0]), str(sel[1]), str(sel[2]))
    else:
        selected = None

    def _on_select(level: str, bn: str, title: str) -> None:
        art_sel = _find_book(by_level, level, bn, title)
        if on_select_book:
            on_select_book(level, bn, title, art_sel)
        else:
            st.session_state["wb_selected"] = (level, bn, title)

    art: BookArtifacts | None = None
    if selected:
        art = _find_book(by_level, selected[0], selected[1], selected[2] if len(selected) > 2 else None)

    session_active = bool(selected and _session_matches_book(selected[0], selected[1]))

    # 布局调宽控件（IDE 化折中：切换三栏比例）
    layout_mode, ratios = _render_layout_control()
    focus_center = layout_mode == "专注中栏"

    def _render_center() -> None:
        st.markdown("##### 🗂️ 生产平台")
        _render_global_kpis(stats)
        st.markdown("**📌 生产入口 · 单本优先，终稿后置**")
        _render_center_functions(art, session_active=session_active)
        st.markdown("---")
        _render_center_pipeline(
            art,
            on_enter_work=on_enter_work,
            session_active=session_active,
            on_regen=on_regen_image,
            on_lock=on_lock_image,
            on_refine=on_refine_image,
            level_options=level_options,
            on_syllabus_change=on_syllabus_change,
            on_pull_syllabus=on_pull_syllabus,
            on_generate_story_draft=on_generate_story_draft,
        )
        if art is not None:
            st.markdown("---")
            _render_book_notes(art)

    if focus_center:
        # 专注中栏：仅渲染中栏全宽，左树 / AI dock 收进折叠（Streamlit 折中“最大化中栏”）
        st.caption("专注中栏：左目录树 / 右 AI dock 暂折叠，切回其他布局即恢复三栏。")
        with st.container(border=True):
            _render_center()
        with st.expander("📚 目录树（专注模式下临时折叠）", expanded=False):
            _render_left_rail(
                by_level,
                stats,
                selected=selected,
                on_select=_on_select,
                on_open_nav=on_open_nav,
                on_enter_work=on_enter_work,
            )
        with st.expander("🤖 AI 助手（专注模式下临时折叠）", expanded=False):
            _render_ai_dock(art, stats, by_level)
    else:
        col_l, col_c, col_r = st.columns(ratios, gap="medium")
        with col_l:
            with st.container(border=True, height=760):
                _render_left_rail(
                    by_level,
                    stats,
                    selected=selected,
                    on_select=_on_select,
                    on_open_nav=on_open_nav,
                    on_enter_work=on_enter_work,
                )
        with col_c:
            with st.container(border=True):
                _render_center()
        with col_r:
            with st.container(border=True, height=760):
                _render_ai_dock(art, stats, by_level)
                st.markdown("---")
                with st.expander("✅ 本书检查清单 / 待办 / 问题", expanded=False):
                    _render_right_panel(
                        art,
                        stats,
                        session_active=session_active,
                        on_enter_work=on_enter_work,
                    )

    # 折叠：旧版分页入口
    with st.expander("🧰 更多页面", expanded=False):
        st.caption("进度看板、概览、设置等仍在独立页；完整 AI 抽取与批量生产在「经典制作」。")
        leg1, leg2, leg3, leg4 = st.columns(4)
        _legacy = (
            ("dashboard", "📊 进度看板"),
            ("overview", "🏠 概览"),
            ("onboarding", "📖 新手引导"),
            ("settings", "⚙️ 设置"),
        )
        for col, (nav_key, lbl) in zip((leg1, leg2, leg3, leg4), _legacy):
            with col:
                if on_open_nav and st.button(lbl, key=f"wb_legacy_{nav_key}", use_container_width=True):
                    on_open_nav(nav_key)
        show_legacy = os.getenv("WEB_FULL_NAV", "").lower() in ("1", "true", "yes")
        st.checkbox(
            "顶栏显示完整导航",
            value=bool(st.session_state.get("web_full_nav", show_legacy)),
            key="web_full_nav",
            help="勾选后顶栏出现全部 Tab（进度看板 / 概览 / 设置等）",
        )


def workbench_css_block() -> str:
    """shadcn 风格工作台 CSS 片段（由 web_app._inject_css 注入）。"""
    return """
        /* ---------- Workbench 三栏（shadcn 映射） ---------- */
        .wb-hero{
          background:linear-gradient(135deg,hsl(0 0% 100%),hsl(210 40% 98%));
          border:1px solid hsl(214 32% 91%);
          border-radius:12px;
          padding:16px 18px;
          margin-bottom:12px;
          box-shadow:0 1px 2px rgba(0,0,0,.04);
        }
        .wb-kicker{
          font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
          color:hsl(215 16% 47%);margin-bottom:4px;
        }
        .wb-hero h2{ margin:0 0 6px;font-size:20px;font-weight:700;color:hsl(222 47% 11%); }
        .wb-hero p{ margin:0;font-size:13px;color:hsl(215 16% 47%);line-height:1.55;max-width:760px; }

        /* ---------- 左侧公告栏：简介 ---------- */
        .wb-rail-intro{
          padding:10px 12px;margin-bottom:10px;border-radius:10px;
          background:hsl(210 40% 98%);
          border:1px solid hsl(214 32% 91%);
        }
        .wb-rail-kicker{
          font-size:9.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
          color:hsl(215 16% 47%);margin-bottom:3px;
        }
        .wb-rail-intro b{ font-size:14px;color:hsl(222 47% 11%); }
        .wb-rail-intro p{ margin:5px 0 0;font-size:11.5px;line-height:1.5;color:hsl(215 16% 47%); }

        /* ---------- 中栏五大功能编号卡片 ---------- */
        .wb-mini-status{
          font-size:12px;line-height:1.5;
          padding:8px 10px;margin:4px 0 10px;border-radius:10px;
          background:hsl(210 40% 98%);border:1px solid hsl(214 32% 91%);
          color:hsl(222 47% 11%);
        }
        .wb-mini-status span{ color:hsl(215 16% 47%);margin-left:8px; }
        .wb-light-status{
          font-size:12px;line-height:1.45;
          padding:8px 10px;margin:6px 0 10px;border-radius:10px;
          color:hsl(222 47% 11%);
          background:hsl(33 100% 96%);
          border:1px solid hsl(24 95% 45% / .35);
        }

        .wb-func-grid{
          display:grid;grid-template-columns:1.35fr 1fr 1fr;gap:8px;margin:6px 0 4px;
        }
        @media (max-width:1280px){ .wb-func-grid{ grid-template-columns:repeat(2,1fr); } }
        .wb-func-card{
          position:relative;padding:10px 10px 9px;border-radius:10px;
          background:hsl(0 0% 100%);border:1px solid hsl(214 32% 91%);
          border-left:3px solid hsl(214 32% 88%);
        }
        .wb-func-card.done{
          background:hsl(138 76% 97%);border-left-color:hsl(142 71% 45%);
        }
        .wb-func-card.active{
          background:hsl(210 40% 98%);border-left-color:hsl(222 47% 11%);
          box-shadow:0 2px 8px rgba(0,0,0,.08);
        }
        .wb-func-card.core{
          grid-row:span 2;
          padding:14px 14px 12px;
          background:hsl(0 0% 100%);
          border-left-color:hsl(222 47% 11%);
          box-shadow:0 4px 14px rgba(0,0,0,.08);
        }
        .wb-func-card .n{
          display:inline-grid;place-items:center;width:18px;height:18px;border-radius:6px;
          font-size:10px;font-weight:800;color:#fff;background:hsl(215 16% 55%);margin-bottom:5px;
        }
        .wb-func-card.done .n{ background:hsl(142 71% 45%); }
        .wb-func-card.active .n{ background:hsl(222 47% 11%); }
        .wb-func-card.core .n{ width:24px;height:24px;background:hsl(222 47% 11%); }
        .wb-func-card em{
          position:absolute;right:10px;top:10px;font-style:normal;
          font-size:9.5px;font-weight:700;padding:2px 6px;border-radius:999px;
          color:hsl(215 16% 47%);background:hsl(210 40% 96%);
          border:1px solid hsl(214 32% 91%);
        }
        .wb-func-card b{ display:block;font-size:12px;font-weight:700;color:hsl(222 47% 11%);margin-bottom:2px; }
        .wb-func-card.core b{ font-size:14px;margin-top:6px; }
        .wb-func-card .d{ display:block;font-size:9.5px;line-height:1.3;color:hsl(215 25% 32%); }
        .wb-func-card.core .d{ font-size:11px;line-height:1.45; }

        .wb-panel{
          background:hsl(0 0% 100%);
          border:1px solid hsl(214 32% 91%);
          border-radius:12px;
          padding:12px 14px;
          min-height:420px;
          box-shadow:0 1px 3px rgba(0,0,0,.05);
        }
        .wb-panel-left{ max-height:72vh; overflow-y:auto; }
        .wb-panel-center{ min-height:480px; }
        .wb-panel-right{ position:sticky; top:12px; align-self:flex-start; }

        .wb-book-head h3{ margin:6px 0 2px;font-size:17px;font-weight:700; }
        .wb-book-head p{ margin:0 0 8px;color:hsl(215 16% 47%);font-size:13px; }
        .wb-badge{
          display:inline-block;font-size:11px;font-weight:600;
          padding:2px 8px;border-radius:999px;
          background:hsl(210 40% 96%);border:1px solid hsl(214 32% 91%);
          color:hsl(222 47% 11%);
        }
        /* Dino status pills: editing / published / warning */
        .wb-status-pill{
          display:inline-block;font-size:11px;font-weight:600;
          padding:3px 10px;border-radius:999px;
          border:1px solid transparent;margin-bottom:4px;
        }
        .wb-status-pill.editing{
          background:hsl(48 100% 96%);border-color:hsl(38 92% 50% / .4);
          color:hsl(32 95% 35%);
        }
        .wb-status-pill.published{
          background:hsl(138 76% 97%);border-color:hsl(142 71% 45% / .35);
          color:hsl(142 40% 28%);
        }
        .wb-status-pill.warning{
          background:hsl(210 40% 96%);border-color:hsl(214 32% 91%);
          color:hsl(215 16% 47%);
        }
        .wb-btn-primary{
          display:inline-flex;align-items:center;justify-content:center;
          padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600;
          background:hsl(222 47% 11%);color:#fff;border:1px solid hsl(222 47% 11%);
        }
        .wb-btn-outline{
          display:inline-flex;align-items:center;justify-content:center;
          padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600;
          background:hsl(0 0% 100%);color:hsl(222 47% 11%);
          border:1px solid hsl(214 32% 91%);
        }
        .wb-flow-nav [data-testid="column"] button{
          font-size:10.5px !important;min-height:34px !important;
          padding:4px 6px !important;border-radius:8px !important;
        }
        .wb-sec-anchor{ scroll-margin-top:80px; }
        .wb-checklist-row{
          font-size:12.5px;padding:4px 0;color:hsl(222 47% 11%);
        }
        .wb-checklist-row span{ color:hsl(215 25% 32%);font-size:10.5px;line-height:1.25; }
        .wb-checklist-row .wb-opt{
          display:inline-block;margin-left:4px;padding:1px 5px;border-radius:999px;
          background:hsl(210 40% 96%);border:1px solid hsl(214 32% 91%);
          font-size:9px;color:hsl(215 16% 47%);
        }
        .wb-track{
          height:6px;border-radius:6px;background:hsl(210 40% 96%);
          overflow:hidden;margin:8px 0 4px;
        }
        .wb-fill{
          height:100%;border-radius:6px;
          background:hsl(222 47% 11%);
          transition:width .35s ease;
        }
        .wb-step{
          background:hsl(0 0% 100%);border:1px solid hsl(214 32% 91%);
          border-radius:8px;padding:8px;min-height:64px;font-size:11px;
        }
        .wb-step.done{ border-color:hsl(142 71% 45%);background:hsl(138 76% 97%); }
        .wb-step .n{
          width:18px;height:18px;border-radius:5px;
          background:hsl(222 47% 11%);color:#fff;
          display:grid;place-items:center;font-size:10px;font-weight:700;margin-bottom:4px;
        }
        .wb-step.done .n{ background:hsl(142 71% 45%); }
        .wb-step b{ display:block;font-size:11px;margin-bottom:2px; }
        .wb-step span{ color:hsl(215 16% 47%);font-size:9.5px;line-height:1.3;display:block; }

        /* SOP 横向 5 步（与经典制作一致 + 画质精修） */
        .wb-sop-flow,.wb-mvp-flow{
          display:flex;align-items:stretch;gap:0;
          margin:10px 0 8px;overflow-x:auto;padding-bottom:2px;
        }
        .wb-flow-step{
          flex:1 1 0;min-width:72px;text-align:center;
          padding:10px 6px 8px;
          background:hsl(0 0% 100%);
          border:1px solid hsl(214 32% 91%);
          border-radius:10px 10px 0 0;
          border-bottom:3px solid hsl(214 32% 91%);
          position:relative;
        }
        .wb-flow-step.done{
          border-bottom-color:hsl(142 71% 45%);
          background:hsl(138 76% 97%);
        }
        .wb-flow-step.active{
          border-bottom-color:hsl(222 47% 11%);
          background:hsl(210 40% 98%);
          box-shadow:0 2px 8px rgba(0,0,0,.08);
        }
        .wb-flow-step .n{
          width:20px;height:20px;border-radius:6px;margin:0 auto 5px;
          background:hsl(215 16% 47%);color:#fff;
          display:grid;place-items:center;font-size:10px;font-weight:800;
        }
        .wb-flow-step.done .n{ background:hsl(142 71% 45%); }
        .wb-flow-step.active .n{ background:hsl(222 47% 11%); }
        .wb-flow-step b{ display:block;font-size:11px;font-weight:700;margin-bottom:2px; }
        .wb-flow-step span{
          display:block;font-size:9px;color:hsl(215 25% 32%);
          line-height:1.25;
        }
        .wb-flow-conn{
          display:none;
        }

        /* 经典制作页风格：绿色提示 + 橙色故事区 */
        .wb-prod-hint{
          font-size:12.5px;line-height:1.55;
          padding:10px 12px;margin:8px 0 6px;
          border-radius:10px;
          background:hsl(138 76% 97%);
          border:1px solid hsl(142 71% 45% / .35);
          color:hsl(142 45% 18%);
        }
        .wb-pill-row{
          display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px;
        }
        .wb-pill{
          display:inline-flex;align-items:center;
          padding:4px 10px;border-radius:999px;
          font-size:11.5px;font-weight:600;
          color:hsl(215 16% 47%);
          background:hsl(210 40% 96%);
          border:1px solid hsl(214 32% 91%);
        }
        .wb-pill.done{
          color:hsl(142 40% 28%);
          background:hsl(138 76% 97%);
          border-color:hsl(142 71% 45% / .35);
        }
        .wb-prod-form{
          border:1px solid hsl(214 32% 91%);
          border-radius:12px;
          padding:10px 12px 12px;
          background:hsl(0 0% 100%);
          margin-bottom:8px;
        }
        .wb-story-head{
          font-size:12.5px;margin:10px 0 6px;
          padding:8px 10px;border-radius:8px;
          background:hsl(210 40% 98%);
          border:1px solid hsl(214 32% 91%);
          color:hsl(222 47% 11%);
        }
        .wb-prod-form [data-testid="stTextArea"] textarea,
        [data-testid="stTextArea"] textarea{
          border-color:hsl(214 32% 91%) !important;
          background:hsl(0 0% 100%) !important;
          color:hsl(222 47% 11%) !important;
        }
        .wb-prod-form [data-testid="stTextArea"] textarea:focus{
          border-color:hsl(222 47% 11%) !important;
          box-shadow:0 0 0 2px rgba(17,24,39,.12) !important;
        }

        .wb-issue-card{
          padding:10px 12px;margin:6px 0 4px;
          border-radius:10px;border:1px solid hsl(214 32% 91%);
          background:hsl(0 0% 100%);font-size:12px;line-height:1.45;
          box-shadow:0 1px 2px rgba(0,0,0,.04);
        }
        .wb-issue-card.manual{
          border-color:hsl(38 92% 50% / .35);
          background:hsl(48 100% 96%);
        }
        .wb-issue-card .cat{
          display:inline-block;font-size:10px;font-weight:700;
          padding:1px 6px;border-radius:4px;margin-right:6px;
          background:hsl(210 40% 96%);color:hsl(215 16% 47%);
          border:1px solid hsl(214 32% 91%);
        }
        .wb-issue-card.manual .cat{
          background:hsl(38 92% 50% / .12);color:hsl(32 95% 35%);
          border-color:hsl(38 92% 50% / .25);
        }
        .wb-issue-item{
          padding:8px 10px;margin:4px 0 2px;
          border-radius:8px;border:1px solid hsl(0 84% 60% / .25);
          background:hsl(0 86% 97%);font-size:12px;line-height:1.45;
        }
        .wb-issue-item .cat{
          display:inline-block;font-size:10px;font-weight:700;
          padding:1px 6px;border-radius:4px;margin-right:6px;
          background:hsl(0 84% 60% / .12);color:hsl(0 70% 40%);
        }
        .wb-issue-ok{
          padding:8px 10px;border-radius:8px;
          background:hsl(138 76% 97%);border:1px solid hsl(142 71% 45% / .3);
          font-size:12.5px;color:hsl(142 71% 30%);
        }

        .wb-img-card{
          border:1px solid hsl(214 32% 91%);
          border-radius:10px;
          padding:6px;
          margin-bottom:8px;
          background:hsl(0 0% 100%);
          transition:box-shadow .15s ease,border-color .15s ease;
        }
        .wb-img-card:hover{
          border-color:hsl(214 32% 82%);
          box-shadow:0 4px 12px rgba(0,0,0,.08);
        }
        .wb-empty{
          padding:48px 16px;text-align:center;color:hsl(215 16% 47%);
          border:1px dashed hsl(214 32% 91%);border-radius:10px;
        }

        .wb-dingtalk-strip{
          font-size:12px;line-height:1.5;
          padding:10px 12px;border-radius:8px;
          background:hsl(210 40% 98%);
          border:1px solid hsl(214 32% 91%);
          margin-bottom:10px;
        }
        .wb-dingtalk-strip .k{
          display:block;font-size:10px;font-weight:700;
          letter-spacing:.08em;text-transform:uppercase;
          color:hsl(215 16% 47%);margin-bottom:4px;
        }
        .wb-dingtalk-strip .sub{ color:hsl(215 16% 47%);font-size:11px; }

        .wb-todo-item{
          padding:8px 10px;margin:4px 0;
          border-radius:8px;border:1px solid hsl(38 92% 50% / .35);
          background:hsl(48 100% 96%);font-size:12.5px;
        }
        .wb-todo-ok{
          padding:8px 10px;border-radius:8px;
          background:hsl(138 76% 97%);border:1px solid hsl(142 71% 45% / .3);
          font-size:12.5px;color:hsl(142 71% 30%);
        }

        /* st.dialog overlay — shadcn Dialog */
        [data-testid="stDialog"] > div{
          border-radius:12px !important;
          border:1px solid hsl(214 32% 91%) !important;
          box-shadow:0 25px 50px -12px rgba(0,0,0,.25) !important;
        }
        [data-testid="stDialog"] h2{
          font-size:16px !important;font-weight:600 !important;
        }

        /* 提升生产平台控件可读性 */
        [data-testid="stButton"] button{
          color:hsl(222 47% 11%) !important;
          border-color:hsl(215 24% 72%) !important;
          font-weight:700 !important;
        }
        [data-testid="stBaseButton-primary"]{
          background:hsl(222 47% 11%) !important;
          border-color:hsl(222 47% 11%) !important;
          color:#fff !important;
        }
        [data-testid="stFileUploader"] section{
          border-color:hsl(214 32% 91%) !important;
          background:hsl(210 40% 98%) !important;
        }
        [data-testid="stFileUploader"] button{
          color:hsl(222 47% 11%) !important;
          border-color:hsl(215 24% 62%) !important;
          font-weight:700 !important;
        }

        /* ---------- 顶部钉钉统一同步条（4 文档卡片） ---------- */
        .wb-sync-bar{
          display:grid;grid-template-columns:repeat(4,1fr);gap:8px;
          margin:4px 0 8px;
        }
        @media (max-width:1100px){ .wb-sync-bar{ grid-template-columns:repeat(2,1fr); } }
        .wb-sync-card{
          padding:8px 10px;border-radius:10px;
          background:hsl(0 0% 100%);border:1px solid hsl(214 32% 91%);
          border-left:3px solid hsl(214 32% 88%);
        }
        .wb-sync-card.ok{ border-left-color:hsl(142 71% 45%);background:hsl(138 76% 98%); }
        .wb-sync-card.warn{ border-left-color:hsl(38 92% 50%);background:hsl(48 100% 97%); }
        .wb-sync-card b{ display:block;font-size:11.5px;font-weight:700;color:hsl(222 47% 11%);margin-bottom:2px; }
        .wb-sync-card span{ display:block;font-size:10.5px;color:hsl(215 25% 32%); }
        .wb-sync-card em{ display:block;font-style:normal;font-size:9.5px;color:hsl(215 16% 47%);margin-top:1px; }

        /* ---------- 右侧 AI dock ---------- */
        .wb-ai-empty{
          font-size:12px;color:hsl(215 16% 47%);
          padding:8px 10px;border-radius:8px;
          background:hsl(210 40% 98%);border:1px solid hsl(214 32% 91%);
        }

        @media (max-width: 1100px){
          .wb-panel-left{ max-height:none; }
          .wb-panel-right{ position:static; }
        }
    """
