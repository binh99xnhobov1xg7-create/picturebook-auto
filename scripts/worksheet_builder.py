"""Worksheet PPTX 生成器 v2.0（6 页固定模板，对齐真实 L5-1 样本）。

页面结构（强制 6 页）：
    Page 1  Vocabulary  - Match the words to their definitions   (5 对连线)
    Page 2  Vocabulary  - Use the words / phrase to fill blanks  (5 题填空 + 词库条)
    Page 3  Sentence    - Choose the correct sentence            (4 题二选一 + 绘本图)
    Page 4  Reading     - Choose the correct answer              (全文 + 8 道 3 选)
    Page 5  Writing     - Write about [theme]                    (5 步骨架 + 写作区)
    Page 6  Reading     - Filling the mind map                   (3 列表 5 行)

字体/字号（v1.6 真实样本）：
    大标题 Poppins Bold 20pt #333333  / 副标题 Poppins Regular 12pt #666666
    题号  Poppins Bold 16pt 圆形粉底白字
    题干  Poppins Regular 16pt 黑色  /  Reading 长文 12pt 黑色

品牌外框（统一 6 页）：
    粉色外背景 (BRAND_COLORS[level]) + 内白圆角
    左上 VIPKID Dino Reading Club logo（Dino 头像 + 白色文字）
    右上 Name 五角形角标 (粉底白字)
    右下 footer "Level X - <Title>" 白字
"""
from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Iterable, Optional

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches as _RawInches, Pt, Emu

from config import BRAND_DIR, brand_color_rgb
from parser import BookOutline
from text_format import (
    _to_us_spelling,
    capitalize_names,
    format_word_answer,
    format_sentence_answer,
    smart_format_answer,
    is_sentence_like,
)


# ---------- 几何尺寸 ----------
# v2.2：直接以官方模板画布为准 = PowerPoint「A4 纸张」横向 = 27.517 x 19.05 cm
#        = 10.833 x 7.5 in。不再二次放大（_WS_SCALE=1.0），坐标即原生英寸。
DESIGN_W = 10.833
DESIGN_H = 7.5
_WS_SCALE = 1.0

SLIDE_W = DESIGN_W
SLIDE_H = DESIGN_H


def Inches(value):
    """worksheet 坐标 = 原生英寸（官方 A4 横向画布 10.833x7.5）。"""
    return _RawInches(value * _WS_SCALE)

# 内容白底（对齐官方模板的内白圆角区 x=0.46 y=0.73 w=9.9 h=6.43）
CONTENT_X = 0.46
CONTENT_Y = 0.73
CONTENT_W = 9.90
CONTENT_H = 6.43
CONTENT_ROUND = 0.06  # 圆角调整比例（python-pptx adjustments[0]）

# 顶部 logo 区（露在粉色背景上）
LOGO_X = 0.40
LOGO_Y = 0.10
LOGO_ICON_W = 0.55
LOGO_ICON_H = 0.55

# Name 角标（v1.9：放成矩形标签，避免旋转 PENTAGON 跑位）
NAME_X = 8.85
NAME_Y = 0.18
NAME_W = 1.50
NAME_H = 0.42

# Footer（v1.9：往上挪到内容白底底边附近，避免被裁切）
FOOTER_X = 0.30
FOOTER_Y = 6.85
FOOTER_W = 10.23
FOOTER_H = 0.30


# ---------- 字号/颜色 ----------
FONT = "Poppins"
FONT_BOLD = "Poppins"
# underscore 字符在 Poppins 下被压扁，改用 Arial 才显示得清晰粗实
FONT_BLANK = "Arial"

# 验收口径：大标题 40pt 黑、副标题 20pt 浅灰（完整句指令）
TITLE_PT = 40
SUBTITLE_PT = 20
BODY_PT = 18
READING_PT = 13
QNUM_PT = 18
HEADER_PT = 20  # mind map 表头
LOGO_TEXT_PT = 20
NAME_PT = 16
FOOTER_PT = 14.5

TITLE_RGB = RGBColor(0x33, 0x33, 0x33)  # 深炭灰
SUB_RGB = RGBColor(0x66, 0x66, 0x66)
BLACK = RGBColor(0x00, 0x00, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
NAME_FILL = RGBColor(0xF8, 0xC8, 0xDC)
LIGHT_GRAY = RGBColor(0xCC, 0xCC, 0xCC)

# Mind Map 三列表头颜色（v1.6 紫粉 / 黄 / 绿）
MM_PURPLE = RGBColor(0xE6, 0xD8, 0xF2)
MM_YELLOW = RGBColor(0xFA, 0xEB, 0xC6)
MM_GREEN = RGBColor(0xCE, 0xE7, 0xCD)
MM_PURPLE_DARK = RGBColor(0xC9, 0xB3, 0xE2)
MM_YELLOW_DARK = RGBColor(0xF5, 0xDC, 0x95)
MM_GREEN_DARK = RGBColor(0xA8, 0xD3, 0xA6)

# Reading 红框
READ_BORDER = RGBColor(0xE9, 0x52, 0x83)


# ============================================================
#  对外入口
# ============================================================

def _level_num(level: str) -> int:
    """取 level 数字（smart→0），用于分级页面逻辑。"""
    s = str(level or "").lower()
    if "smart" in s:
        return 0
    digits = "".join(ch for ch in s if ch.isdigit())
    try:
        return int(digits) if digits else 5
    except ValueError:
        return 5


# ============================================================
#  句型考点引擎：故事时态（一般过去时）—— 学什么考什么
# ============================================================
# 过去式 → 原形（不规则 + 常见 magic-e / -ied 规则动词，避免启发式还原出错）
_PAST_TO_BASE: dict[str, str] = {
    # be / 高频不规则
    "was": "be", "were": "be", "felt": "feel", "saw": "see", "shook": "shake",
    "ran": "run", "said": "say", "took": "take", "gave": "give", "told": "tell",
    "went": "go", "had": "have", "made": "make", "came": "come", "brought": "bring",
    "thought": "think", "found": "find", "got": "get", "knew": "know", "drew": "draw",
    "ate": "eat", "sat": "sit", "stood": "stand", "heard": "hear", "held": "hold",
    "kept": "keep", "left": "leave", "met": "meet", "won": "win", "wrote": "write",
    "began": "begin", "drank": "drink", "swam": "swim", "sang": "sing", "flew": "fly",
    "grew": "grow", "threw": "throw", "blew": "blow", "broke": "break", "spoke": "speak",
    "woke": "wake", "chose": "choose", "rode": "ride", "drove": "drive", "rose": "rise",
    "fell": "fall", "bought": "buy", "caught": "catch", "taught": "teach", "fought": "fight",
    "slept": "sleep", "spent": "spend", "sent": "send", "built": "build", "paid": "pay",
    "burst": "burst", "read": "read", "put": "put", "cut": "cut", "hit": "hit",
    "let": "let", "set": "set", "shut": "shut", "hurt": "hurt", "cost": "cost",
    # magic-e 规则动词（启发式会还原错，单列）
    "shared": "share", "liked": "like", "baked": "bake", "smiled": "smile",
    "hoped": "hope", "moved": "move", "lived": "live", "used": "use", "closed": "close",
    "danced": "dance", "loved": "love", "saved": "save", "named": "name", "placed": "place",
    "arrived": "arrive", "decided": "decide", "invited": "invite", "noticed": "notice",
    "promised": "promise", "surprised": "surprise", "cared": "care", "waved": "wave",
    "smiled ": "smile", "raced": "race",
    # -ied
    "hurried": "hurry", "carried": "carry", "tried": "try", "cried": "cry",
    "studied": "study", "replied": "reply", "worried": "worry",
}


def _regular_base(past: str) -> Optional[str]:
    """规则动词过去式 → 原形（启发式，用于 _PAST_TO_BASE 未覆盖的 -ed 词）。"""
    if not past.endswith("ed") or len(past) < 4:
        return None
    if past.endswith("ied"):
        return past[:-3] + "y"          # tried→try
    stem = past[:-2]
    # 双写辅音：grabbed→grab, stopped→stop, hugged→hug
    if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
        return stem[:-1]
    return stem                          # listened→listen, helped→help, looked→look


def _past_to_base(word: str) -> Optional[str]:
    low = word.lower()
    if low in _PAST_TO_BASE:
        return _PAST_TO_BASE[low]
    return _regular_base(low)


def _present_3rd(base: str) -> str:
    """原形 → 一般现在时第三人称单数（用于造『现在时』错误项）。"""
    if base == "be":
        return "is"
    if base == "have":
        return "has"
    if base.endswith(("s", "x", "z", "ch", "sh", "o")):
        return base + "es"
    if base.endswith("y") and len(base) >= 2 and base[-2] not in "aeiou":
        return base[:-1] + "ies"
    return base + "s"


# 不是动词的常见 -ed/过去式同形词（避免误判）
_NOT_VERB = {"red", "bed", "bird", "good", "food", "wood", "need", "feed", "seed", "ahead"}


def _find_past_verb(sentence: str) -> Optional[tuple[str, str]]:
    """在句子里找第一个『过去式动词』token，返回 (原 token, 原形 base)。"""
    for tok in sentence.split():
        clean = "".join(ch for ch in tok if ch.isalpha())
        if not clean or clean.lower() in _NOT_VERB:
            continue
        base = _past_to_base(clean)
        if base and base != clean.lower():  # 必须确实是过去式（与原形不同）
            return tok, base
        # was/were/read/put 等过去=原形同形的，靠白名单确认
        if clean.lower() in ("was", "were"):
            return tok, "be"
    return None


def _story_sentences_for_grammar(outline: BookOutline) -> list[str]:
    out: list[str] = []
    for p in outline.pages:
        if p.page_type == "story" and (p.text or "").strip():
            for s in re.split(r"(?<=[.!?])\s+", p.text.strip()):
                s = s.strip()
                if s and len(s.split()) >= 4:
                    out.append(capitalize_names(s))
    return out


def _tense_fill_items(outline: BookOutline, max_n: int = 4) -> tuple[list[dict], list[str]]:
    """第 2 句型页（考点=故事时态）：给出原形提示，挖空让学生写出正确过去式。

    例：『Anna ________ (feel) nervous on her first day.』 答案 felt。
    返回 (fills, word_bank=正确过去式列表)。
    """
    fills: list[dict] = []
    bank: list[str] = []
    for sent in _story_sentences_for_grammar(outline):
        if len(fills) >= max_n:
            break
        found = _find_past_verb(sent)
        if not found:
            continue
        tok, base = found
        past_word = "".join(ch for ch in tok if ch.isalpha())
        # 用『________ (base)』替换该动词，保留句中其余部分
        blanked = sent.replace(tok, f"________ ({base})", 1)
        fills.append({"sentence": blanked, "answer": past_word})
        bank.append(past_word)
    return fills, bank


_PLURAL_SUBJECTS = {"they", "we", "you", "i", "children", "kids", "friends", "students"}


def _present_form(base: str, plural: bool) -> str:
    """原形 → 一般现在时（按主语单复数）。"""
    if plural:
        return "are" if base == "be" else base
    return _present_3rd(base)


def _sentence_to_present(sent: str) -> Optional[str]:
    """把整句里所有过去式动词换成一般现在时，得到（错误的）现在时句子；无可换则 None。"""
    first = "".join(ch for ch in sent.split()[0] if ch.isalpha()).lower() if sent.split() else ""
    plural = first in _PLURAL_SUBJECTS
    tokens = sent.split()
    changed = False
    for i, tok in enumerate(tokens):
        clean = "".join(ch for ch in tok if ch.isalpha())
        if not clean or clean.lower() in _NOT_VERB:
            continue
        base = _past_to_base(clean)
        if not base or base == clean.lower():
            continue  # 非过去式 / 过去=原形同形（put/read），跳过不制造对比
        present = _present_form(base, plural)
        if clean[:1].isupper():
            present = present[:1].upper() + present[1:]
        tokens[i] = tok.replace(clean, present, 1)
        changed = True
    return " ".join(tokens) if changed else None


def _tense_mc_items(outline: BookOutline, max_n: int = 4) -> list[dict]:
    """第 1 句型页（考点=故事时态）：两句二选一，选『正确过去式』那句。

    正确项 = 故事原句（过去式）；干扰项 = 整句动词换成一般现在时（错误）。
    """
    mcs: list[dict] = []
    for sent in _story_sentences_for_grammar(outline):
        if len(mcs) >= max_n:
            break
        wrong = _sentence_to_present(sent)
        if not wrong or wrong == sent:
            continue
        mcs.append({"options": [sent, wrong], "correct": 0})
    return mcs


# 兼容旧调用名
def _sentence_fill_items(outline: BookOutline, max_n: int = 4) -> tuple[list[dict], list[str]]:
    return _tense_fill_items(outline, max_n=max_n)


# ---------- 官方 A4 模板（底版/母版）----------
# 7 个 slide：index = 级别数字（Smart=0, L1=1 … L6=6），各带原生 Logo 图 / Name 角标 / 配色 / 页脚。
_WS_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "templates" / "Worksheet_A4_L0-L6.pptx"


def _template_slide_index(level: str) -> int:
    return max(0, min(6, _level_num(level)))


def _clone_template_slide(prs: Presentation, src_slide):
    """把模板某个级别的 slide 整体克隆成新 slide（保留原生 Logo/Name 角标/配色/页脚）。
    深拷贝形状 XML 并重映射图片关系 rId，确保图片正常显示。"""
    import copy
    from pptx.oxml.ns import qn

    new_slide = prs.slides.add_slide(src_slide.slide_layout)
    # 清掉版式带进来的占位形状
    for shp in list(new_slide.shapes):
        shp._element.getparent().remove(shp._element)
    # 重建图片关系 rId 映射（老 rId → 新 rId）
    rid_map: dict[str, str] = {}
    for rid, rel in src_slide.part.rels.items():
        if "image" in rel.reltype:
            rid_map[rid] = new_slide.part.relate_to(rel._target, rel.reltype)
    # 拷贝形状并改写 embed/link 引用
    for shp in src_slide.shapes:
        el = copy.deepcopy(shp._element)
        for node in el.iter():
            for attr in ("embed", "link"):
                a = qn("r:" + attr)
                old = node.get(a)
                if old in rid_map:
                    node.set(a, rid_map[old])
        new_slide.shapes._spTree.append(el)
    return new_slide


def _set_footer(slide, footer_text: str) -> None:
    """把克隆 slide 右下页脚文本框的内容改成本书的 'Level X - Title'。
    找不到就在官方页脚位置新建一个。"""
    target = None
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        left_in = sh.left / 914400 if sh.left is not None else 0
        top_in = sh.top / 914400 if sh.top is not None else 0
        if top_in > 6.8 and left_in > 6.0:  # 右下角区域
            target = sh
            break
    if target is None:
        target = slide.shapes.add_textbox(
            Inches(7.46), Inches(7.16), Inches(2.94), Inches(0.35))
    tf = target.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = footer_text
    r.font.name = FONT
    r.font.size = Pt(FOOTER_PT)
    r.font.color.rgb = WHITE


def _retell_writing_scaffold(outline: BookOutline) -> dict:
    """生成【基于本文故事】的引导式复述写作脚手架（v2.2）。

    用户拍板：写作题必须扣住本篇文章——让孩子复述/分析这个故事，而不是写空泛抽象题
    （如 "Write about friendship"，孩子无从下手）。这里把 5 步换成针对本故事的引导问题，
    读完原文就能照着一步步写出来。step_labels 是引导问句（孩子照着回答即可成文）。
    """
    title = (outline.title or "the story").strip()
    return {
        "theme": outline.theme or title,
        "title": f"Retell the story: {title}",
        "subtitle": "Read the story again, then retell it in your own words.",
        "steps": ["", "", "", "", ""],
        # 引导问句（通用于任何叙事文，且明确指向"本文"）：
        "step_labels": [
            "Who is the story about, and how did they feel at the start?",
            "What happened first?",
            "What happened next?",
            "What was the best, funniest or most surprising part?",
            "How did the story end? How did they feel?",
        ],
        "min_words": 50, "max_words": 80,
    }


def _resolve_second_reading_mode(mode: str, lvl_n: int) -> str:
    """解析第 2 张 Reading 页内容模式。

    auto：L0-2 用思维导图(SWBST 复述)，L3-6 用写作脚手架。
    其余取值原样返回：reading / mindmap / writing / pbl。
    """
    m = (mode or "auto").strip().lower()
    if m in ("reading", "mindmap", "writing", "pbl"):
        return m
    return "mindmap" if lvl_n <= 2 else "writing"


def build_worksheet(
    outline: BookOutline,
    out_path: Path,
    *,
    image_paths: Optional[Iterable[Path]] = None,
    sentence_image_mode: str = "reuse",  # reuse=复用绘本图 / none=不配图
    second_reading_mode: str = "auto",   # auto/reading/mindmap/writing/pbl
) -> Path:
    """生成 worksheet（所有级别统一 6 页）：

    2 词汇(Vocabulary) + 2 句型(Sentence) + 2 阅读(Reading)。
      阅读① = 原文 + 理解题（垂直列表）。
      阅读② 内容由 second_reading_mode 决定（标题统一 Reading）：
        auto    → L0-2 思维导图(SWBST 复述) / L3-6 写作脚手架
        reading → 阅读理解延伸（题目分两页）
        mindmap → 思维导图(SWBST)
        writing → 写作脚手架
        pbl     → 读后 PBL 迷你项目

    阅读理解题优先取 outline._reading_questions（AI 专门抽的 mc/tf/short），
    无则兜底旧 reading_mcs。Sentence 页复用 image_paths[2..5]（故事 P2..P5）。
    """
    data = _resolve_worksheet_data(outline)
    brand_rgb = brand_color_rgb(outline.level)
    level_label = _level_label(outline.level)
    footer_text = f"{level_label} - {outline.title}"
    # v2.1: 用专门的 Dino 头 icon（不是设定卡 dino_logo.png）
    logo_icon = BRAND_DIR / "dino_head_icon.png"
    if not logo_icon.exists():
        logo_icon = BRAND_DIR / "dino_logo.png"  # 兜底
    images = list(image_paths or [])
    lvl_n = _level_num(outline.level)

    # v2.2：优先以官方 A4 模板为底版（按级别克隆 slide → 100% 还原边框/Logo/Name/配色/页脚）；
    # 模板缺失时退回旧的自绘外框。
    use_template = _WS_TEMPLATE.exists()
    if use_template:
        prs = Presentation(str(_WS_TEMPLATE))
        n_template = len(prs.slides._sldIdLst)
        tpl_src = prs.slides[_template_slide_index(outline.level)]
        blank = None
    else:
        prs = Presentation()
        prs.slide_width = _RawInches(SLIDE_W)
        prs.slide_height = _RawInches(SLIDE_H)
        n_template = 0
        tpl_src = None
        blank = prs.slide_layouts[6]

    def new_page():
        if use_template:
            s = _clone_template_slide(prs, tpl_src)
            _set_footer(s, footer_text)
        else:
            s = prs.slides.add_slide(blank)
            _draw_brand_frame(s, brand_rgb, footer_text, logo_icon)
        return s

    # ===== 2 词汇页 =====
    _build_p1_match(new_page(), brand_rgb, data["match_pairs"], images)
    _build_p2_fill(new_page(), brand_rgb, data["fill_blanks"], data["word_bank"], images)

    # ===== 2 句型页（考点 = 故事时态，一般过去时；学什么考什么）=====
    # 句型页① 二选一：选出用正确过去式的句子；AI 数据不贴合考点时用时态引擎兜底
    tense_mcs = _tense_mc_items(outline)
    sent_mcs = tense_mcs if tense_mcs else data["sentence_mcs"]
    _build_p3_sentence(new_page(), brand_rgb, sent_mcs, images,
                       show_images=(sentence_image_mode != "none"))
    # 句型页② 填空：写出动词的正确过去式（给原形提示）
    sent_fills, sent_bank = _tense_fill_items(outline)
    if not sent_fills:
        sent_fills, sent_bank = _sentence_fill_items(outline)
    _build_p2_fill(
        new_page(), brand_rgb, sent_fills, [], images,
        title="Sentence",
        subtitle="Write the correct past tense of each verb in brackets.",
    )

    # ===== 阅读 / 思维导图 / 写作 =====
    # 阅读理解题优先用专用 _reading_questions（mc/tf/short），否则兜底旧 reading_mcs。
    reading_text = capitalize_names(data["reading_text"])
    rq = list(getattr(outline, "_reading_questions", []) or [])
    if not rq:
        rq = [
            {"kind": "mc", "q": m.get("q", ""), "options": m.get("options", []),
             "correct": m.get("correct", 0)}
            for m in (data.get("reading_mcs") or []) if m.get("q")
        ]

    # 所有级别统一 6 页：2 词汇 + 2 句型 + 2 阅读（两页标题都叫 Reading）。
    # 第 2 张 Reading 页内容按 second_reading_mode（auto=按级别）：
    #   reading 阅读延伸 / mindmap 思维导图(SWBST) / writing 写作脚手架 / pbl 迷你项目
    mode = _resolve_second_reading_mode(second_reading_mode, lvl_n)
    if mode == "reading":
        mc_first = [q for q in rq if q.get("kind") == "mc"]
        rest = [q for q in rq if q.get("kind") != "mc"]
        ordered = mc_first + rest
        half = max(4, (len(ordered) + 1) // 2)
        page1_q, page2_q = ordered[:half], ordered[half:]
        _build_reading_page(new_page(), brand_rgb, reading_text, page1_q,
                            subtitle="Choose the correct answer for each question.", start_no=1)
        _build_reading_page(new_page(), brand_rgb, reading_text, page2_q,
                            subtitle="Read the passage and answer the questions.",
                            start_no=len(page1_q) + 1)
    else:
        _build_reading_page(new_page(), brand_rgb, reading_text, rq[:6],
                            subtitle="Read and answer the questions.", start_no=1)
        if mode == "writing":
            _build_p5_writing(new_page(), brand_rgb, data["writing"], title="Reading")
        elif mode == "pbl":
            _build_pbl_page(new_page(), brand_rgb, data, outline, title="Reading")
        else:  # mindmap
            _build_p6_mindmap(new_page(), data["mind_map"])

    # 删除模板自带的 7 个级别原始 slide，只留我们克隆出来的内容页
    if use_template and n_template:
        sld_lst = prs.slides._sldIdLst
        for sld in list(sld_lst)[:n_template]:
            sld_lst.remove(sld)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path


def attach_worksheet_questions(
    outline: BookOutline, data, *, reading_q_count: int = 4
) -> None:
    """挂载 AI 抽取的 worksheet 内容到 outline。

    v1.9：兼容两种输入格式：
      - dict：直接用（match_pairs/word_bank/fill_blanks/sentence_mcs/reading_text/reading_mcs/writing/mind_map）
      - list[dict]（AI 抽出来的 6 道题 list，每条 {type, items, ...}）→ 自动跑 adapter

    v2.0: 加 reading_q_count 参数（4/6/8），控制 Reading MC 页题量。
    """
    if isinstance(data, list):
        # 原始 6 题（含 title/instruction/answer_key）也存一份，供 Teacher Guide 同源取 Answer Key
        setattr(outline, "_worksheet_questions", data)
        data = _questions_list_to_template_data(data, outline)
    if isinstance(data, dict):
        data = dict(data)
        data["_reading_q_count"] = reading_q_count
    setattr(outline, "_worksheet_data", data)


def _questions_list_to_template_data(qlist: list[dict], outline: BookOutline) -> dict:
    """把 AI 抽取的"按 level 池子的 6 道题"映射到 worksheet PPTX 模板的 7 个固定字段。

    Worksheet 模板有 6 页固定结构：
      P1 Match (word ↔ definition)
      P2 Fill blanks (word_bank + 5 句 fill_blanks)
      P3 Sentence MC (4 题 2 选 1，可配图)
      P4 Reading MC (4 题，每题 3 options)
      P5 Writing (scaffold + 写作区)
      P6 Mind Map (character / problem / solution)

    AI 抽取的题型五花八门（match_definition / fill_blank / true_false / inference / unscramble / …）
    本函数把它们分发到对应模板字段，并用 outline 数据兜底空字段。
    """
    out: dict = {
        "match_pairs": [],
        "word_bank": [],
        "fill_blanks": [],
        "sentence_mcs": [],
        "reading_text": "",
        "reading_mcs": [],
        "writing": {},
        "mind_map": [],
    }

    for q in qlist or []:
        if not isinstance(q, dict):
            continue
        qtype = (q.get("type") or "").lower()
        # AI 抽取偶尔把 items 给成字符串列表（而非 dict 列表），统一规整成 dict，
        # 字符串元素塞进 _str，供 match/fill 等分支兜底使用，避免 .get 崩溃。
        items = [
            it if isinstance(it, dict) else {"_str": str(it)}
            for it in (q.get("items") or [])
            if it is not None
        ]
        extra = q.get("extra") or ""

        if qtype == "match_definition":
            out["match_pairs"] = [
                {"word": it.get("word") or it.get("_str", ""),
                 "def": it.get("def") or it.get("definition", "")}
                for it in items if (it.get("word") or it.get("_str"))
            ][:5]
            if not out["word_bank"]:
                out["word_bank"] = [
                    it.get("word") or it.get("_str", "") for it in items
                ][:5]

        elif qtype in ("fill_blank", "fill_blank_simple", "fill_blank_advanced", "emotion_fill"):
            out["fill_blanks"] = [
                {"sentence": it.get("sentence") or it.get("_str", ""),
                 "answer": it.get("answer", "")}
                for it in items if (it.get("sentence") or it.get("_str"))
            ][:5]
            if not out["word_bank"]:
                if extra:
                    bank = [w.strip() for w in extra.split(",") if w.strip()]
                else:
                    bank = [it.get("answer", "") for it in items]
                out["word_bank"] = bank[:5]

        elif qtype in ("true_false", "true_false_simple"):
            for it in items[:4]:
                stmt = it.get("statement", "")
                if not stmt:
                    continue
                # AI 给的 T/F 转成 sentence MC：正确句 vs 语法可读的反义句
                ans = (it.get("answer") or "T").upper()
                opt_true = stmt
                core = stmt.rstrip(".!?")
                opt_false = f"It is not true that {core}." if core else ""
                out["sentence_mcs"].append({
                    "options": [opt_true, opt_false],
                    "correct": 0 if ans == "T" else 1,
                })

        elif qtype in ("inference", "reading_mc"):
            for it in items[:4]:
                stem = it.get("q") or it.get("question", "")
                if not stem:
                    continue
                opts = it.get("options") or []
                if len(opts) < 2:
                    continue
                out["reading_mcs"].append({
                    "q": stem,
                    "options": list(opts)[:3],
                    "correct": int(it.get("correct", 0)),
                })

        elif qtype in ("plot_chart", "plot_chart_pbl"):
            # AI 给 {label: Setting/Problem/Solution/..., answer: 内容}
            buf: dict[str, str] = {}
            for it in items:
                buf[(it.get("label") or "").lower()] = it.get("answer", "")
            character = buf.get("characters") or buf.get("character") or "Main character"
            problem = buf.get("problem") or buf.get("conflict") or ""
            solution = buf.get("solution") or buf.get("resolution") or buf.get("ending") or ""
            out["mind_map"].append({
                "character": character,
                "problem": problem,
                "solution": solution,
            })

        elif qtype == "compare_contrast":
            for it in items[:3]:
                out["mind_map"].append({
                    "character": it.get("topic", "Comparison"),
                    "problem": it.get("side_a", ""),
                    "solution": it.get("side_b", ""),
                })

        elif qtype in ("essay_short", "personal_write", "personal_simple",
                       "draw_favorite", "open_ended_pbl", "research_pbl"):
            # v2.2：统一改成【基于本文】的引导式复述脚手架（不再用空泛 "Write about X" 题）
            out["writing"] = _retell_writing_scaffold(outline)

        elif qtype == "unscramble":
            # 转化为 fill_blanks（"Unscramble: o c k l → ____" 的形式）
            if not out["fill_blanks"]:
                for it in items[:5]:
                    scr = it.get("scrambled", "")
                    ans = it.get("answer", "")
                    if scr and ans:
                        out["fill_blanks"].append({
                            "sentence": f"Unscramble: {scr} → ____",
                            "answer": ans,
                        })

        elif qtype in ("word_order", "word_order_simple", "story_sequence"):
            # 当 sentence_mcs（按 order 排）— 不太贴合，跳过
            pass

        elif qtype in ("rewrite_tense", "rewrite_voice"):
            if not out["fill_blanks"]:
                for it in items[:5]:
                    prm = it.get("prompt", "")
                    ans = it.get("answer", "")
                    if prm and ans:
                        out["fill_blanks"].append({
                            "sentence": f"Rewrite: {prm} → ____",
                            "answer": ans,
                        })

        elif qtype in ("color_match", "circle_match", "word_to_pic"):
            # 简单 vocab cue，用作 word_bank 兜底
            if not out["word_bank"]:
                out["word_bank"] = [
                    it.get("word", "") for it in items if it.get("word")
                ][:5]

    # ----- 兜底字段：用 outline 数据补全 -----
    pages = outline.pages or []
    story_text = capitalize_names(" ".join(
        (p.text or "").strip() for p in pages if (p.text or "").strip()
    ).strip())

    if not out["reading_text"]:
        out["reading_text"] = story_text or "Story text goes here."

    # Match 兜底：用 vocab
    if not out["match_pairs"]:
        words = (outline.vocabulary_mastery or outline.vocabulary_simple or [])[:5]
        out["match_pairs"] = [
            {"word": w, "def": f"meaning of {w}"} for w in words
        ]
        if not out["word_bank"]:
            out["word_bank"] = words[:]

    # word_bank 兜底
    if not out["word_bank"]:
        out["word_bank"] = (outline.vocabulary_mastery or outline.vocabulary_simple or [])[:5]

    # Fill 兜底
    if not out["fill_blanks"] and out["word_bank"]:
        out["fill_blanks"] = [
            {"sentence": f"I feel ____ when I see this.", "answer": w}
            for w in out["word_bank"][:5]
        ]

    story_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", story_text) if s.strip()]

    # Sentence MC 兜底：用故事原文 + 语法可读的反义句
    if not out["sentence_mcs"]:
        for s in story_sentences[:4]:
            core = s.rstrip(".!?")
            out["sentence_mcs"].append({
                "options": [s, f"It is not true that {core}." if core else ""],
                "correct": 0,
            })

    # Reading MC 兜底：从故事生成简单 5W（按上限取，不固定 4）
    if not out["reading_mcs"] and story_sentences:
        for i, s in enumerate(story_sentences[:8]):
            out["reading_mcs"].append({
                "q": f"What does the passage say in sentence {i + 1}?",
                "options": [
                    s[:60] + ("..." if len(s) > 60 else ""),
                    "Something opposite happens.",
                    "The story does not mention it.",
                ],
                "correct": 0,
            })

    # Writing 兜底（v2.2：基于本文的引导式复述）
    if not out["writing"]:
        out["writing"] = _retell_writing_scaffold(outline)

    # Mind Map 兜底
    if not out["mind_map"]:
        out["mind_map"] = [{
            "character": "Main character",
            "problem": "What is the problem in the story?",
            "solution": "How is it solved?",
        }]

    return out


# ============================================================
#  品牌外框
# ============================================================

def _draw_brand_frame(slide, brand_rgb: tuple, footer_text: str, logo_icon: Path) -> None:
    """所有 6 页统一的外框：粉背景 + 圆角白底 + 左上 logo + 右上 Name + 右下 footer。"""
    # 1. 外背景
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, Inches(SLIDE_W), Inches(SLIDE_H),
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(*brand_rgb)
    bg.line.fill.background()
    bg.shadow.inherit = False

    # 2. 内白底圆角
    content = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X), Inches(CONTENT_Y),
        Inches(CONTENT_W), Inches(CONTENT_H),
    )
    content.adjustments[0] = CONTENT_ROUND
    content.fill.solid()
    content.fill.fore_color.rgb = WHITE
    content.line.fill.background()
    content.shadow.inherit = False

    # 3. 左上 logo (icon + 文字)
    if logo_icon and logo_icon.exists():
        try:
            slide.shapes.add_picture(
                str(logo_icon),
                Inches(LOGO_X), Inches(LOGO_Y),
                width=Inches(LOGO_ICON_W), height=Inches(LOGO_ICON_H),
            )
        except Exception:
            pass
    text_x = LOGO_X + LOGO_ICON_W + 0.10
    tb = slide.shapes.add_textbox(
        Inches(text_x), Inches(LOGO_Y), Inches(4.5), Inches(LOGO_ICON_H),
    )
    tb.text_frame.margin_left = tb.text_frame.margin_right = 0
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    tb.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    r = p.add_run()
    r.text = "VIPKID Dino Reading Club"
    r.font.name = FONT
    r.font.size = Pt(LOGO_TEXT_PT)
    r.font.bold = True
    r.font.color.rgb = WHITE

    # 4. 右上 Name 角标（v2.0 改回盾形：上方矩形 + 下方三角尖角，对齐官方模板）
    # Name 颜色用 brand_rgb 加深 30%（更接近模板的酒红/暗粉效果）
    name_dark = RGBColor(
        max(0, brand_rgb[0] - 50),
        max(0, brand_rgb[1] - 30),
        max(0, brand_rgb[2] - 30),
    )

    # 矩形部分（上半部）
    name_rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(NAME_X), Inches(NAME_Y),
        Inches(NAME_W), Inches(NAME_H),
    )
    name_rect.fill.solid()
    name_rect.fill.fore_color.rgb = name_dark
    name_rect.line.fill.background()
    name_rect.shadow.inherit = False
    tf = name_rect.text_frame
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "Name"
    r.font.name = FONT
    r.font.size = Pt(NAME_PT)
    r.font.color.rgb = WHITE
    r.font.bold = True

    # 三角形尖角部分（朝下，宽度比矩形窄，居中下方）
    tri_w = NAME_W * 0.55
    tri_h = 0.22
    tri_x = NAME_X + (NAME_W - tri_w) / 2
    tri_y = NAME_Y + NAME_H
    tri = slide.shapes.add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE,
        Inches(tri_x), Inches(tri_y),
        Inches(tri_w), Inches(tri_h),
    )
    tri.rotation = 180  # 翻转让尖朝下
    tri.fill.solid()
    tri.fill.fore_color.rgb = name_dark
    tri.line.fill.background()
    tri.shadow.inherit = False

    # 5. 底部 footer（v1.9：全宽 + 右对齐，往上挪到白底里面避免被裁切）
    fo = slide.shapes.add_textbox(
        Inches(FOOTER_X), Inches(FOOTER_Y),
        Inches(FOOTER_W), Inches(FOOTER_H),
    )
    fo.text_frame.margin_left = fo.text_frame.margin_right = Inches(0.10)
    p = fo.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = footer_text
    r.font.name = FONT
    r.font.size = Pt(FOOTER_PT)
    r.font.color.rgb = RGBColor(*brand_rgb)
    r.font.bold = True


def _get_subtitle(qtype_id: str, fallback: str) -> str:
    """v2.0 从题型库取标准英文 instruction；找不到就用兜底文本。"""
    try:
        from worksheet_question_types import get_type
        t = get_type(qtype_id)
        if t and t.en_instr:
            return t.en_instr
    except Exception:
        pass
    return fallback


def _add_title(slide, title: str, subtitle: str) -> None:
    """大标题 + 副标题（居中，位于内容白底顶部）。"""
    # Title
    tb = slide.shapes.add_textbox(
        Inches(CONTENT_X), Inches(CONTENT_Y + 0.20),
        Inches(CONTENT_W), Inches(0.55),
    )
    tb.text_frame.margin_left = tb.text_frame.margin_right = 0
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = title
    r.font.name = FONT
    r.font.bold = True
    r.font.size = Pt(TITLE_PT)
    r.font.color.rgb = TITLE_RGB

    # Subtitle
    sb = slide.shapes.add_textbox(
        Inches(CONTENT_X), Inches(CONTENT_Y + 0.78),
        Inches(CONTENT_W), Inches(0.30),
    )
    sb.text_frame.margin_left = sb.text_frame.margin_right = 0
    p2 = sb.text_frame.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    r2.text = subtitle
    r2.font.name = FONT
    r2.font.size = Pt(SUBTITLE_PT)
    r2.font.color.rgb = SUB_RGB


# ============================================================
#  Page 1 — Vocabulary 连线
# ============================================================

def _derange_order(n: int) -> list[int]:
    """返回 0..n-1 的一个错位排列（保证每个位置 i 的取值 != i）。

    用于连线题：右列定义要打乱顺序，且不能有任何一条定义恰好落在它对应单词的同一行
    （否则等于把正确答案直接画成水平对齐）。n<=1 时无法错位，原样返回。
    """
    if n <= 1:
        return list(range(n))
    idx = list(range(n))
    for _ in range(50):
        random.shuffle(idx)
        if all(idx[i] != i for i in range(n)):
            return idx
    # 兜底：整体循环移位（天然错位）
    return [(i + 1) % n for i in range(n)]


def _build_p1_match(slide, brand_rgb: tuple, pairs: list[dict], images: list[Path]) -> None:
    """5 对连线：左列小图（绘本图） + 中列粉色实心词卡 ↔ 右列白底粉边定义卡。

    v1.8 新增：每个 vocab 配一张绘本小图（用 page_02..page_06.png 循环）当 visual cue。
    v2.2 修复：右列定义【打乱顺序】渲染（错位排列），让连线题真正需要学生自己连线，
              而不是行对行直接把正确答案对齐给出。
    """
    _add_title(slide, "Vocabulary", _get_subtitle("vocab_match_definition", "Match the words to their definitions."))

    n = min(len(pairs), 5)
    if n == 0:
        return

    # 右列定义的错位渲染顺序：def_render_order[row] = 该行要显示 pairs 里第几个的定义
    def_render_order = _derange_order(n)

    # 区域
    area_top = CONTENT_Y + 1.30
    area_bottom = CONTENT_Y + CONTENT_H - 0.30
    area_h = area_bottom - area_top

    # 三列布局：放大绘本配图 + 缩小文字（用户反馈：图太小、字太大）
    img_x = CONTENT_X + 0.40
    img_w = 1.55
    word_x = img_x + img_w + 0.28
    word_w = 1.85
    def_x = word_x + word_w + 0.30
    def_w = CONTENT_W - (def_x - CONTENT_X) - 0.40
    row_gap = 0.20
    row_h = (area_h - row_gap * (n - 1)) / n
    word_pt = 15
    def_pt = 13

    for i, pair in enumerate(pairs[:n]):
        y = area_top + i * (row_h + row_gap)

        # 小图（左，绘本插画，正方形等比缩放）
        img_idx = (i % max(1, len(images) - 2)) + 2  # 从 page_02 起
        img_path = images[img_idx] if (img_idx < len(images) and images[img_idx]) else None
        if img_path and img_path.exists():
            try:
                from PIL import Image as _PILImg
                with _PILImg.open(str(img_path)) as _pim:
                    iw, ih = _pim.size
                aspect = iw / ih if ih else 1.0
                fit_w = img_w
                fit_h = fit_w / aspect
                if fit_h > row_h:
                    fit_h = row_h
                    fit_w = fit_h * aspect
                off_x = img_x + (img_w - fit_w) / 2
                off_y = y + (row_h - fit_h) / 2
                slide.shapes.add_picture(
                    str(img_path),
                    Inches(off_x), Inches(off_y),
                    width=Inches(fit_w), height=Inches(fit_h),
                )
            except Exception:
                _draw_image_placeholder(slide, img_x, y, img_w, row_h)
        else:
            _draw_image_placeholder(slide, img_x, y, img_w, row_h)

        # 词卡（中，粉色实心，白字）
        wc = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(word_x), Inches(y), Inches(word_w), Inches(row_h),
        )
        wc.adjustments[0] = 0.28
        wc.fill.solid()
        wc.fill.fore_color.rgb = RGBColor(*brand_rgb)
        wc.line.fill.background()
        wc.shadow.inherit = False
        tf = wc.text_frame
        tf.margin_left = tf.margin_right = Inches(0.1)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(pair.get("word", "")).strip()
        r.font.name = FONT
        r.font.size = Pt(word_pt)
        r.font.color.rgb = WHITE
        r.font.bold = False

        # 定义卡（右，白底粉边，黑字）
        dc = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(def_x), Inches(y), Inches(def_w), Inches(row_h),
        )
        dc.adjustments[0] = 0.28
        dc.fill.solid()
        dc.fill.fore_color.rgb = WHITE
        dc.line.color.rgb = RGBColor(*brand_rgb)
        dc.line.width = Pt(1.8)
        dc.shadow.inherit = False
        tf = dc.text_frame
        tf.margin_left = tf.margin_right = Inches(0.15)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT  # v1.8: 定义文本左对齐更易读
        r = p.add_run()
        # v2.2: 定义按错位顺序取，避免和左侧单词行对行（即直接给出正确答案）
        def_pair = pairs[def_render_order[i]] if def_render_order[i] < len(pairs) else pair
        r.text = str(def_pair.get("def", "")).strip()
        r.font.name = FONT
        r.font.size = Pt(def_pt)
        r.font.color.rgb = BLACK


# ============================================================
#  Page 2 — Vocabulary 填空
# ============================================================

def _build_p2_fill(slide, brand_rgb: tuple, fills: list[dict], word_bank: list[str],
                   images: Optional[list[Path]] = None,
                   title: str = "Vocabulary", subtitle: str | None = None) -> None:  # noqa: ARG001
    """顶部粉色词库条 + 5 道填空题（用 ____ 表示空）。images 参数留作未来扩展。

    title/subtitle 可覆盖（第 2 句型页复用本渲染器时传 title='Sentence'）。
    """
    _add_title(slide, title,
               subtitle or _get_subtitle("vocab_fill_blank", "Use the words to fill each blank."))

    has_bank = bool(word_bank)

    # 词库条（粉色实心圆角，水平排列词）—— 仅在有词库时绘制
    bank_top = CONTENT_Y + 1.80
    bank_h = 0.55
    bank_x = CONTENT_X + 1.50
    bank_w = CONTENT_W - 3.00
    if word_bank:
        bk = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(bank_x), Inches(bank_top), Inches(bank_w), Inches(bank_h),
        )
        bk.adjustments[0] = 0.4
        bk.fill.solid()
        bk.fill.fore_color.rgb = RGBColor(*brand_rgb)
        bk.line.fill.background()
        bk.shadow.inherit = False
        tf = bk.text_frame
        tf.margin_left = tf.margin_right = Inches(0.15)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        # 水平排列：词之间用空格
        joined = "    ".join(word_bank)
        r = p.add_run()
        r.text = joined
        r.font.name = FONT
        r.font.size = Pt(BODY_PT)
        r.font.color.rgb = WHITE
        r.font.bold = False

    # 填空题（垂直排列）
    n = min(len(fills), 5)
    if n == 0:
        return
    # 有词库 → 题目区从词库下方开始；无词库（如"写出动词过去式"页）→ 紧贴标题下方，
    #   避免顶部大片空白（用户反馈：中间一大块空、不好看）。
    qa_top = (bank_top + bank_h + 0.45) if has_bank else (CONTENT_Y + 1.30)
    qa_bottom = CONTENT_Y + CONTENT_H - 0.30
    qa_h = qa_bottom - qa_top
    row_h = qa_h / n
    # 无词库时字号略大、每题下方补一条作答横线，把版面填得均衡好看
    fill_pt = BODY_PT if has_bank else (BODY_PT + 2)

    for i, qa in enumerate(fills[:n]):
        y = qa_top + i * row_h
        tb = slide.shapes.add_textbox(
            Inches(CONTENT_X + 0.80), Inches(y),
            Inches(CONTENT_W - 1.60), Inches(row_h),
        )
        tf = tb.text_frame
        tf.margin_left = tf.margin_right = Inches(0.05)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = 1.15
        sentence = capitalize_names(_ensure_blank(str(qa.get("sentence", ""))))
        _emit_with_underscore_lock(p, f"{i + 1}.  {sentence}", fill_pt, BLACK)


def _ensure_blank(text: str) -> str:
    """若 sentence 里没有 ____ 占位，自动加 underscores。"""
    if "____" in text or "_____" in text or "___" in text:
        return text
    # 把第一个 [blank] / [BLANK] / [BLK] 替换为 ____
    for token in ("[blank]", "[BLANK]", "[BLK]"):
        if token in text:
            return text.replace(token, "________", 1)
    return text


def _emit_with_underscore_lock(paragraph, text: str, size_pt: int, color: RGBColor) -> None:
    """把文本里连续的下划线段（____）切出来用 Arial 字体渲染（Poppins 下 _ 太扁），
    其余部分仍用 Poppins。"""
    import re as _re
    parts = _re.split(r"(_{3,})", text)  # 至少 3 个 _ 才视作占位
    if len(parts) == 1:
        # 无下划线段，直接整段 Poppins
        r = paragraph.add_run()
        r.text = text
        r.font.name = FONT
        r.font.size = Pt(size_pt)
        r.font.color.rgb = color
        return
    for chunk in parts:
        if not chunk:
            continue
        r = paragraph.add_run()
        r.text = chunk
        if chunk.startswith("___"):
            r.font.name = FONT_BLANK  # Arial，下划线粗实
        else:
            r.font.name = FONT
        r.font.size = Pt(size_pt)
        r.font.color.rgb = color


# ============================================================
#  Page 3 — Sentence MC (二选一 + 绘本配图)
# ============================================================

def _build_p3_sentence(slide, brand_rgb: tuple, mcs: list[dict], images: list[Path],
                       show_images: bool = True) -> None:
    """4 题二选一，每题左侧绘本图 + 右侧 A/B 选项 + 行首圆圈题号。

    show_images=False → 不配图（选项满宽展开），供老师在「配图来源」选『不配图』时使用。
    """
    _add_title(slide, "Sentence", "Tick (\u2713) the sentence that uses the correct past tense.")

    n = min(len(mcs), 4)
    if n == 0:
        return

    area_top = CONTENT_Y + 1.40
    area_bottom = CONTENT_Y + CONTENT_H - 0.30
    area_h = area_bottom - area_top
    row_gap = 0.10
    row_h = (area_h - row_gap * (n - 1)) / n

    qnum_size = 0.45
    qnum_x = CONTENT_X + 0.30
    img_x = qnum_x + qnum_size + 0.20
    img_w = 1.80 if show_images else 0.0
    opt_x = (img_x + img_w + 0.30) if show_images else (qnum_x + qnum_size + 0.30)
    opt_w = CONTENT_W - (opt_x - CONTENT_X) - 0.40

    # 自适应字号：配图时选项区变窄，长句易折行→拥挤重叠。按"最长选项 + 可用文字宽度"
    # 反推一个尽量让每条选项落在 1 行的字号（标定：18pt 时约 0.133in/字符），夹在 [12, BODY_PT]。
    cb_size = 0.22
    text_w = max(2.0, opt_w - cb_size - 0.20)
    max_chars = 1
    for _mc in mcs[:n]:
        for _j, _opt in enumerate((_mc.get("options") or [])[:2]):
            max_chars = max(max_chars, len(f"{chr(ord('A') + _j)}. {_opt}"))
    char_w_at_18 = 0.133
    fit_pt = text_w / (max_chars * (char_w_at_18 / 18.0))
    opt_pt = max(12.0, min(float(BODY_PT), fit_pt))

    for i, mc in enumerate(mcs[:n]):
        y = area_top + i * (row_h + row_gap)
        cy = y + (row_h - qnum_size) / 2

        # 圆形题号
        circle = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(qnum_x), Inches(cy),
            Inches(qnum_size), Inches(qnum_size),
        )
        circle.fill.solid()
        circle.fill.fore_color.rgb = RGBColor(*brand_rgb)
        circle.line.fill.background()
        circle.shadow.inherit = False
        tf = circle.text_frame
        tf.margin_left = tf.margin_right = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(i + 1)
        r.font.name = FONT
        r.font.bold = True
        r.font.size = Pt(QNUM_PT)
        r.font.color.rgb = WHITE

        # 图（复用绘本 page_02..page_05），保持长宽比，居中放入 img_w x (row_h-0.10) 框
        img_idx = i + 2  # P3 题 1 用绘本 page_02
        img_path = images[img_idx] if (img_idx < len(images) and images[img_idx]) else None
        max_box_w = img_w
        max_box_h = row_h - 0.10
        if not show_images:
            pass  # 不配图：跳过图片/占位，选项满宽展开
        elif img_path and img_path.exists():
            try:
                from PIL import Image as _PILImg
                with _PILImg.open(str(img_path)) as _pim:
                    iw, ih = _pim.size
                aspect = iw / ih if ih else 1.0
                # 尝试按宽适配
                fit_w = max_box_w
                fit_h = fit_w / aspect
                if fit_h > max_box_h:
                    fit_h = max_box_h
                    fit_w = fit_h * aspect
                off_x = img_x + (max_box_w - fit_w) / 2
                off_y = y + 0.05 + (max_box_h - fit_h) / 2
                slide.shapes.add_picture(
                    str(img_path),
                    Inches(off_x), Inches(off_y),
                    width=Inches(fit_w), height=Inches(fit_h),
                )
            except Exception:
                _draw_image_placeholder(slide, img_x, y + 0.05, max_box_w, max_box_h)
        else:
            _draw_image_placeholder(slide, img_x, y + 0.05, max_box_w, max_box_h)

        # 选项 A/B（垂直堆叠 + 复选框）
        options = mc.get("options") or []
        opt_h = (row_h - 0.05) / max(len(options), 1)
        for j, opt in enumerate(options[:2]):
            oy = y + j * opt_h
            # 复选框：对齐到选项【首行】（顶部），双行选项时不再悬在两行中间
            cb = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(opt_x), Inches(oy + 0.09),
                Inches(cb_size), Inches(cb_size),
            )
            cb.fill.solid()
            cb.fill.fore_color.rgb = WHITE
            cb.line.color.rgb = BLACK
            cb.line.width = Pt(1.0)
            cb.shadow.inherit = False
            # 选项文字（顶部对齐 + 行距，便于和复选框首行齐平）
            tb = slide.shapes.add_textbox(
                Inches(opt_x + cb_size + 0.15), Inches(oy),
                Inches(opt_w - cb_size - 0.20), Inches(opt_h),
            )
            tf = tb.text_frame
            tf.margin_left = tf.margin_right = 0
            tf.margin_top = tf.margin_bottom = 0
            tf.vertical_anchor = MSO_ANCHOR.TOP
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            p.line_spacing = 1.12
            r = p.add_run()
            letter = chr(ord("A") + j)
            r.text = f"{letter}. {opt}"
            r.font.name = FONT
            r.font.size = Pt(opt_pt)
            r.font.color.rgb = BLACK


def _draw_image_placeholder(slide, x: float, y: float, w: float, h: float) -> None:
    ph = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    ph.adjustments[0] = 0.05
    ph.fill.solid()
    ph.fill.fore_color.rgb = RGBColor(0xF0, 0xF0, 0xF0)
    ph.line.color.rgb = LIGHT_GRAY
    ph.line.width = Pt(1.0)
    ph.shadow.inherit = False


# ============================================================
#  Page 4 — Reading 全文 + 8 道 3 选
# ============================================================

def _build_p4_reading(slide, brand_rgb: tuple, text: str, mcs: list[dict]) -> None:
    _add_title(slide, "Reading", _get_subtitle("read_mc_questions", "Choose the correct answer for each question."))

    text = (text or "").strip()

    # 顶部红框 = Reading 全文。短文字数差异很大（长文会撑破固定框），
    # 按字符数自适应字号 + 行距，确保始终落在框内不压字。
    tlen = len(text)
    if tlen > 780:
        read_pt, read_ls = 10.5, 1.12
    elif tlen > 560:
        read_pt, read_ls = 11.5, 1.15
    elif tlen > 380:
        read_pt, read_ls = 12.5, 1.20
    else:
        read_pt, read_ls = float(READING_PT), 1.25

    text_top = CONTENT_Y + 1.35
    text_h = 2.15
    text_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X + 0.40), Inches(text_top),
        Inches(CONTENT_W - 0.80), Inches(text_h),
    )
    text_box.adjustments[0] = 0.03
    text_box.fill.solid()
    text_box.fill.fore_color.rgb = WHITE
    text_box.line.color.rgb = READ_BORDER
    text_box.line.width = Pt(1.5)
    text_box.shadow.inherit = False
    # python-pptx 不直接支持 dashed line per shape — 这里用实线代替

    tf = text_box.text_frame
    tf.margin_left = tf.margin_right = Inches(0.20)
    tf.margin_top = Inches(0.08)
    tf.margin_bottom = Inches(0.06)
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = text
    r.font.name = FONT
    r.font.size = Pt(read_pt)
    r.font.color.rgb = BLACK
    p.line_spacing = read_ls

    # 下方 4 道 MC（2x2 排版）
    n = min(len(mcs), 4)
    if n == 0:
        return
    mc_top = text_top + text_h + 0.20
    mc_bottom = CONTENT_Y + CONTENT_H - 0.25
    mc_h_total = mc_bottom - mc_top
    rows_per_col = (n + 1) // 2  # 4 题 → 2/2
    row_h = mc_h_total / max(rows_per_col, 1)

    col_w = (CONTENT_W - 0.80) / 2
    col_x = [CONTENT_X + 0.40, CONTENT_X + 0.40 + col_w]

    # 题干+选项字号按"最长一题"的总字符数自适应，避免换行后相互重叠/压页脚
    def _q_chars(mc: dict) -> int:
        return len(str(mc.get("q", ""))) + sum(
            len(str(o)) for o in (mc.get("options") or [])[:3]
        )

    max_chars = max((_q_chars(m) for m in mcs[:n]), default=0)
    if max_chars > 150:
        q_pt = 10.5
    elif max_chars > 115:
        q_pt = 11.5
    elif max_chars > 85:
        q_pt = 12.5
    else:
        q_pt = 14.0

    for i, mc in enumerate(mcs[:n]):
        col_idx = 0 if i < rows_per_col else 1
        row_idx = i if col_idx == 0 else (i - rows_per_col)
        x = col_x[col_idx] + 0.10
        y = mc_top + row_idx * row_h
        tb = slide.shapes.add_textbox(
            Inches(x), Inches(y),
            Inches(col_w - 0.20), Inches(row_h - 0.05),
        )
        tf = tb.text_frame
        tf.margin_left = tf.margin_right = 0
        tf.margin_top = tf.margin_bottom = 0
        tf.word_wrap = True
        # 第一段：题号 + 题干
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(2)
        p.line_spacing = 1.05
        r = p.add_run()
        r.text = f"{i + 1}. {mc.get('q', '')}"
        r.font.name = FONT
        r.font.size = Pt(q_pt)
        r.font.color.rgb = BLACK
        r.font.bold = False
        # 后续段：选项 A/B/C 每题占一段（避免选项过长被截断）
        opts = (mc.get("options") or [])[:3]
        for j, opt in enumerate(opts):
            po = tf.add_paragraph()
            po.alignment = PP_ALIGN.LEFT
            po.space_after = Pt(1)
            po.line_spacing = 1.05
            ro = po.add_run()
            ro.text = f"    {chr(ord('A') + j)}. {opt}"
            ro.font.name = FONT
            ro.font.size = Pt(q_pt)
            ro.font.color.rgb = BLACK


def _build_reading_page(
    slide, brand_rgb: tuple, text: str, questions: list[dict],
    *, subtitle: str = "Choose the correct answer for each question.",
    start_no: int = 1,
) -> None:
    """阅读页 v2.1：大标题 Reading + 灰副标题 + 完整原文框 + 原文下方【垂直列表】题目。
    题目 kind 支持 mc / tf / short，禁止网格卡片。题号从 start_no 起。"""
    _add_title(slide, "Reading", subtitle)

    text = (text or "").strip()
    tlen = len(text)
    if tlen > 780:
        read_pt, read_ls = 10.5, 1.12
    elif tlen > 560:
        read_pt, read_ls = 11.5, 1.15
    elif tlen > 380:
        read_pt, read_ls = 12.5, 1.20
    else:
        read_pt, read_ls = float(READING_PT), 1.25

    text_top = CONTENT_Y + 1.35
    text_h = 1.95
    text_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X + 0.40), Inches(text_top),
        Inches(CONTENT_W - 0.80), Inches(text_h),
    )
    text_box.adjustments[0] = 0.03
    text_box.fill.solid()
    text_box.fill.fore_color.rgb = WHITE
    text_box.line.color.rgb = READ_BORDER
    text_box.line.width = Pt(1.5)
    text_box.shadow.inherit = False
    tf = text_box.text_frame
    tf.margin_left = tf.margin_right = Inches(0.20)
    tf.margin_top = Inches(0.08)
    tf.margin_bottom = Inches(0.06)
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = text
    r.font.name = FONT
    r.font.size = Pt(read_pt)
    r.font.color.rgb = BLACK
    p.line_spacing = read_ls

    qs = [q for q in (questions or []) if q.get("q")]
    if not qs:
        return

    list_top = text_top + text_h + 0.18
    list_bottom = CONTENT_Y + CONTENT_H - 0.25
    avail_h = list_bottom - list_top

    # 估算每题"行数"——含自动换行（按字符数 / 每行容量），避免长题干换行后压到下一题
    box_w_in = CONTENT_W - 1.10
    # 用保守（偏小）的每行容量，宁可多留白也不压字重叠
    cpl_stem = 72
    cpl_opt = 66

    def _wrap(text_len: int, cpl: int) -> int:
        import math as _m
        return max(1, _m.ceil(text_len / max(1, cpl)))

    def _lines(q: dict) -> int:
        kind = q.get("kind", "mc")
        stem = str(q.get("q", ""))
        nl = _wrap(len(stem), cpl_stem)
        if kind == "mc":
            for opt in (q.get("options") or [])[:3]:
                nl += _wrap(len(f"    A. {opt}"), cpl_opt)
        else:  # tf / short：题干 + 一行作答
            nl += 1
        return nl
    # v2.2 防重叠：按"真实行高"选字号，并在放不下时裁掉末尾题目，
    #   绝不让 per_line < 真实行高（那会导致每个文本框溢出、压到下一题造成叠字）。
    GAP = 0.06          # 每题之间的固定间距（英寸）
    SPACE_PER_Q = 0.05  # 段后留白折算

    def _line_h(pt: float) -> float:
        # 单行真实占高（含 1.05 行距与少量段距余量）
        return pt / 72.0 * 1.05 + 0.035

    def _fits(qs_sel: list[dict], pt: float) -> bool:
        tl = sum(_lines(q) for q in qs_sel)
        need = tl * _line_h(pt) + (len(qs_sel)) * (GAP + SPACE_PER_Q)
        return need <= avail_h

    # 依次尝试 14 / 12.5 / 11 pt，挑能把【全部题目】塞下的最大字号
    q_pt = 11.0
    for cand in (14.0, 12.5, 11.0):
        if _fits(qs, cand):
            q_pt = cand
            break
    else:
        # 连 11pt 全题都塞不下 → 从末尾裁题，直到 11pt 能放下
        while len(qs) > 3 and not _fits(qs, 11.0):
            qs = qs[:-1]
        q_pt = 11.0

    line_h = _line_h(q_pt)

    y = list_top
    x = CONTENT_X + 0.55
    box_w = CONTENT_W - 1.10
    for i, q in enumerate(qs):
        kind = q.get("kind", "mc")
        n_lines = _lines(q)
        h = n_lines * line_h + SPACE_PER_Q
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(box_w), Inches(h))
        tfb = tb.text_frame
        tfb.margin_left = tfb.margin_right = 0
        tfb.margin_top = tfb.margin_bottom = 0
        tfb.word_wrap = True
        para = tfb.paragraphs[0]
        para.alignment = PP_ALIGN.LEFT
        para.line_spacing = 1.05
        para.space_after = Pt(2)
        run = para.add_run()
        run.text = f"{start_no + i}. {q.get('q', '')}"
        run.font.name = FONT
        run.font.size = Pt(q_pt)
        run.font.color.rgb = BLACK
        if kind == "mc":
            for j, opt in enumerate((q.get("options") or [])[:3]):
                po = tfb.add_paragraph()
                po.alignment = PP_ALIGN.LEFT
                po.line_spacing = 1.05
                po.space_after = Pt(1)
                ro = po.add_run()
                ro.text = f"    {chr(ord('A') + j)}. {opt}"
                ro.font.name = FONT
                ro.font.size = Pt(q_pt)
                ro.font.color.rgb = BLACK
        elif kind == "tf":
            po = tfb.add_paragraph()
            po.alignment = PP_ALIGN.LEFT
            ro = po.add_run()
            ro.text = "    True  /  False"
            ro.font.name = FONT
            ro.font.size = Pt(q_pt)
            ro.font.color.rgb = BLACK
        else:  # short：留作答横线（Arial 显得清晰）
            po = tfb.add_paragraph()
            po.alignment = PP_ALIGN.LEFT
            ro = po.add_run()
            ro.text = "    " + "_" * 46
            ro.font.name = FONT_BLANK
            ro.font.size = Pt(q_pt)
            ro.font.color.rgb = BLACK
        y += h + GAP


# ============================================================
#  Page 5 — Writing 脚手架
# ============================================================

def _build_p5_writing(slide, brand_rgb: tuple, writing: dict, title: str = "Reading") -> None:
    # 用户拍板：L4-6 第 2 阅读页 = 写作/PBL，但页面大标题仍叫 Reading（写作内嵌）
    # v2.2：写作任务必须【基于本文故事】（复述/分析），不再写空泛抽象题；
    #   副标题改成明确的复述指令，让孩子读完原文就知道怎么写。
    subtitle = writing.get("subtitle") or "Read the story again, then retell it in your own words."
    _add_title(slide, title, subtitle)

    # 中部黄虚线框 = 5 步骨架
    scaff_top = CONTENT_Y + 1.40
    scaff_h = 2.40
    scaff = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X + 1.20), Inches(scaff_top),
        Inches(CONTENT_W - 2.40), Inches(scaff_h),
    )
    scaff.adjustments[0] = 0.04
    scaff.fill.solid()
    scaff.fill.fore_color.rgb = RGBColor(0xFD, 0xF5, 0xE0)  # 浅黄
    scaff.line.color.rgb = RGBColor(0xE0, 0xC8, 0x80)
    scaff.line.width = Pt(1.5)
    scaff.shadow.inherit = False

    tf = scaff.text_frame
    tf.margin_left = Inches(0.25)
    tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.15)
    tf.word_wrap = True

    # Title 行
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    p.space_after = Pt(4)
    r = p.add_run()
    r.text = "Title: "
    r.font.name = FONT
    r.font.bold = True
    r.font.size = Pt(14)
    r.font.color.rgb = RGBColor(0x6B, 0x4D, 0xA8)  # 紫
    r2 = p.add_run()
    r2.text = writing.get("title", "_______________")
    r2.font.name = FONT
    r2.font.bold = True
    r2.font.size = Pt(14)
    r2.font.color.rgb = BLACK

    # 5 步
    step_colors = [
        RGBColor(0x4C, 0xA1, 0x65),  # Beginning - 绿
        RGBColor(0x4C, 0x8F, 0xD8),  # First event - 蓝
        RGBColor(0xE3, 0x76, 0x35),  # Second event - 橙
        RGBColor(0xC0, 0x39, 0x6F),  # Funny event - 红
        RGBColor(0x6B, 0x4D, 0xA8),  # Ending - 紫
    ]
    step_labels = writing.get("step_labels") or [
        "Beginning:", "First event:", "Second event:", "Funny event:", "Ending:",
    ]
    step_contents = writing.get("steps") or [""] * 5

    for i in range(5):
        pi = tf.add_paragraph()
        pi.alignment = PP_ALIGN.LEFT
        pi.space_after = Pt(2)
        rn = pi.add_run()
        rn.text = f"{i + 1}. "
        rn.font.name = FONT
        rn.font.bold = True
        rn.font.size = Pt(13)
        rn.font.color.rgb = BLACK
        rl = pi.add_run()
        rl.text = step_labels[i] + "  "
        rl.font.name = FONT
        rl.font.bold = True
        rl.font.size = Pt(13)
        rl.font.color.rgb = step_colors[i % len(step_colors)]
        # step content 里含 ________ 时切出来用 Arial 字体
        _emit_with_underscore_lock(
            pi, step_contents[i] if i < len(step_contents) else "", 13, BLACK
        )

    # 字数提示
    hint_y = scaff_top + scaff_h + 0.10
    hb = slide.shapes.add_textbox(
        Inches(CONTENT_X), Inches(hint_y),
        Inches(CONTENT_W), Inches(0.25),
    )
    p = hb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = f"Write {writing.get('min_words', 50)}-{writing.get('max_words', 80)} words."
    r.font.name = FONT
    r.font.bold = True
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(0xE6, 0xA8, 0x2B)

    # 蓝色横线写作区
    write_top = hint_y + 0.35
    write_bottom = CONTENT_Y + CONTENT_H - 0.30
    box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X + 0.40), Inches(write_top),
        Inches(CONTENT_W - 0.80), Inches(write_bottom - write_top),
    )
    box.adjustments[0] = 0.03
    box.fill.solid()
    box.fill.fore_color.rgb = WHITE
    box.line.color.rgb = RGBColor(0x8C, 0xB6, 0xE6)
    box.line.width = Pt(1.2)
    box.shadow.inherit = False

    # 内部横线（5-6 条）
    line_left = CONTENT_X + 0.70
    line_right = CONTENT_X + CONTENT_W - 0.70
    n_lines = 5
    line_step = (write_bottom - write_top - 0.30) / n_lines
    for k in range(1, n_lines + 1):
        ly = write_top + k * line_step
        ln = slide.shapes.add_connector(
            1,
            Inches(line_left), Inches(ly),
            Inches(line_right), Inches(ly),
        )
        ln.line.color.rgb = RGBColor(0xB7, 0xCD, 0xEC)
        ln.line.width = Pt(0.75)


# ============================================================
#  Page 6 (可选) — PBL 迷你项目（标题统一 Reading）
# ============================================================

def _build_pbl_page(slide, brand_rgb: tuple, data: dict, outline: BookOutline,
                    title: str = "Reading") -> None:
    """读后 PBL 迷你项目：项目目标 + 3 步骤脚手架 + 大块创作区 + 几条书写线。

    全程纯纸面、可独立完成；标题统一 Reading（大结构不变）。
    """
    theme = (outline.theme or "the story").strip()
    pbl = (data.get("pbl") if isinstance(data, dict) else None) or {}
    project = pbl.get("project") or f"Make a poster about {theme}."
    steps = pbl.get("steps") or [
        f"Draw the most important part of {theme}.",
        "Add labels for what you drew.",
        "Write one sentence about your picture.",
    ]
    _add_title(slide, title, f"Mini Project: {project}")

    # 步骤脚手架框（浅色底 + 主色边）
    brief_top = CONTENT_Y + 1.40
    brief_h = 1.75
    brief = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X + 0.45), Inches(brief_top),
        Inches(CONTENT_W - 0.90), Inches(brief_h),
    )
    brief.adjustments[0] = 0.05
    brief.fill.solid()
    brief.fill.fore_color.rgb = RGBColor(0xFD, 0xF5, 0xE0)
    brief.line.color.rgb = RGBColor(*brand_rgb)
    brief.line.width = Pt(1.5)
    brief.shadow.inherit = False
    tf = brief.text_frame
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.12)
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.alignment = PP_ALIGN.LEFT
    p0.space_after = Pt(4)
    r0 = p0.add_run()
    r0.text = "Steps:"
    r0.font.name = FONT
    r0.font.bold = True
    r0.font.size = Pt(15)
    r0.font.color.rgb = RGBColor(*brand_rgb)
    for i, step in enumerate(steps[:3]):
        pi = tf.add_paragraph()
        pi.alignment = PP_ALIGN.LEFT
        pi.space_after = Pt(3)
        ri = pi.add_run()
        ri.text = f"{i + 1}. {capitalize_names(str(step))}"
        ri.font.name = FONT
        ri.font.size = Pt(14)
        ri.font.color.rgb = BLACK

    # 大块创作区（白底 + 主色边）
    canvas_top = brief_top + brief_h + 0.25
    canvas_bottom = CONTENT_Y + CONTENT_H - 0.95
    canvas = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(CONTENT_X + 0.45), Inches(canvas_top),
        Inches(CONTENT_W - 0.90), Inches(canvas_bottom - canvas_top),
    )
    canvas.adjustments[0] = 0.03
    canvas.fill.solid()
    canvas.fill.fore_color.rgb = WHITE
    canvas.line.color.rgb = RGBColor(*brand_rgb)
    canvas.line.width = Pt(1.2)
    canvas.shadow.inherit = False
    ctf = canvas.text_frame
    ctf.margin_left = ctf.margin_right = Inches(0.20)
    ctf.margin_top = Inches(0.10)
    cp = ctf.paragraphs[0]
    cp.alignment = PP_ALIGN.LEFT
    cr = cp.add_run()
    cr.text = "Draw and make it here:"
    cr.font.name = FONT
    cr.font.italic = True
    cr.font.size = Pt(12)
    cr.font.color.rgb = RGBColor(0x5A, 0x5A, 0x5A)

    # 底部 2 条书写线
    line_top = canvas_bottom + 0.30
    line_left = CONTENT_X + 0.70
    line_right = CONTENT_X + CONTENT_W - 0.70
    for k in range(2):
        ly = line_top + k * 0.32
        ln = slide.shapes.add_connector(
            1, Inches(line_left), Inches(ly), Inches(line_right), Inches(ly),
        )
        ln.line.color.rgb = LIGHT_GRAY
        ln.line.width = Pt(0.9)


# ============================================================
#  Page 6 — Mind Map
# ============================================================

def _build_p6_mindmap(slide, rows: list[dict]) -> None:
    """故事复述思维导图 —— SWBST 框架（Somebody/Wanted/But/So/Then）。

    教学目的：用国际通行的『五步复述法』训练学生抓人物、目标、冲突、行动、结局，
    把读到的故事用自己的话有逻辑地概括出来（读后输出 / 写作前的结构脚手架）。
    rows 若带有 AI 提示，会作为浅灰提示词写入右侧引导问题后。
    """
    _add_title(slide, "Reading",
               "Retell the story in five steps: Somebody \u2013 Wanted \u2013 But \u2013 So \u2013 Then.")

    # 五步：关键词 + 引导问题 + 颜色
    steps = [
        ("Somebody", "Who is the story mainly about?", MM_PURPLE),
        ("Wanted",   "What did they want to do?",      RGBColor(0x4C, 0x8F, 0xD8)),
        ("But",      "What was the problem?",          RGBColor(0xE3, 0x76, 0x35)),
        ("So",       "What did they do about it?",     MM_GREEN),
        ("Then",     "How did it end? What did we learn?", RGBColor(0xC0, 0x39, 0x6F)),
    ]

    area_top = CONTENT_Y + 1.40
    area_bottom = CONTENT_Y + CONTENT_H - 0.35
    area_h = area_bottom - area_top
    gap = 0.16
    band_h = (area_h - gap * (len(steps) - 1)) / len(steps)

    left_x = CONTENT_X + 0.45
    label_w = 2.05
    right_x = left_x + label_w + 0.25
    right_w = CONTENT_X + CONTENT_W - 0.45 - right_x

    for i, (kw, question, color) in enumerate(steps):
        y = area_top + i * (band_h + gap)

        # 左：彩色关键词卡
        lab = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left_x), Inches(y), Inches(label_w), Inches(band_h),
        )
        lab.adjustments[0] = 0.18
        lab.fill.solid()
        lab.fill.fore_color.rgb = color
        lab.line.fill.background()
        lab.shadow.inherit = False
        tf = lab.text_frame
        tf.margin_left = tf.margin_right = Inches(0.05)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = f"{i + 1}. {kw}"
        r.font.name = FONT
        r.font.bold = True
        r.font.size = Pt(18)
        r.font.color.rgb = WHITE

        # 右：白底浅边书写区（引导问题 + 作答横线）
        ans = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(right_x), Inches(y), Inches(right_w), Inches(band_h),
        )
        ans.adjustments[0] = 0.10
        ans.fill.solid()
        ans.fill.fore_color.rgb = WHITE
        ans.line.color.rgb = color
        ans.line.width = Pt(1.5)
        ans.shadow.inherit = False
        tf2 = ans.text_frame
        tf2.margin_left = tf2.margin_right = Inches(0.16)
        tf2.margin_top = Inches(0.06)
        tf2.vertical_anchor = MSO_ANCHOR.TOP
        tf2.word_wrap = True
        pq = tf2.paragraphs[0]
        pq.alignment = PP_ALIGN.LEFT
        rq = pq.add_run()
        rq.text = question
        rq.font.name = FONT
        rq.font.size = Pt(12)
        rq.font.italic = True
        rq.font.color.rgb = RGBColor(0x5A, 0x5A, 0x5A)  # B&W 打印可读
        # 作答横线
        pl = tf2.add_paragraph()
        pl.alignment = PP_ALIGN.LEFT
        pl.space_before = Pt(2)
        rl = pl.add_run()
        rl.text = "_" * 60
        rl.font.name = FONT_BLANK
        rl.font.size = Pt(13)
        rl.font.color.rgb = RGBColor(0xC8, 0xC8, 0xC8)


# ============================================================
#  默认数据 fallback（AI 失败时也能出像样的 worksheet）
# ============================================================

def _resolve_worksheet_data(outline: BookOutline) -> dict:
    """优先用 outline._worksheet_data；否则用 outline 字段构造默认。
    在返回前统一做 v1.8 文本规整：美式拼写、答案格式、难度排序、剔除无效题型。"""
    data = getattr(outline, "_worksheet_data", None)
    if isinstance(data, dict) and data.get("match_pairs"):
        return _normalize_worksheet_data(data)
    return _normalize_worksheet_data(_build_default_data(outline))


# ----- v1.8 文本规整：所有英文走美式 + 答案格式 + 难度排序 -----

# 不允许的活动类型关键词（color / colour 只是涂色，不算 reading 输出）
_BANNED_PROMPT_PATTERNS = [
    "color the ", "colour the ",
    "color in ", "colour in ",
    "circle the picture",  # 仅涂圈没有输出
]


# v2.0 vocab 兜底真定义词典 — 防止 AI 输出 "meaning of X" 占位
# 数据源：常见低龄启蒙词汇 + L5-1 What Makes a Good Friend 词汇 + 高频感觉/动作/状态词
_KID_DICT: dict[str, str] = {
    # L5-1 What Makes a Good Friend
    "nervous":   "feeling worried and not calm",
    "shake":     "to move quickly from side to side or up and down",
    "recess":    "a short break at school for students to play outside",
    "a pile of": "many things lying one on top of another",
    "wooden":    "made of wood",
    # 高频形容词
    "excited":   "feeling very happy and full of energy",
    "amazed":    "feeling very surprised in a good way",
    "worried":   "feeling that something bad might happen",
    "happy":     "feeling glad and full of joy",
    "sad":       "feeling unhappy",
    "scared":    "feeling afraid",
    "tired":     "feeling like you need to rest or sleep",
    "kind":      "nice and caring to others",
    "quiet":     "making very little sound",
    "loud":      "making a lot of sound",
    "friendly":  "kind and nice to other people",
    "smart":     "able to think and learn quickly",
    "brave":     "not afraid of dangerous or difficult things",
    "shy":       "feeling not comfortable talking to new people",
    "gentle":    "kind and soft, not rough",
    # 高频动作
    "share":     "to give part of what you have to someone else",
    "help":      "to do something nice for someone who needs it",
    "listen":    "to pay attention to a sound or a person",
    "smile":     "to make a happy face with your mouth turned up",
    "laugh":     "to make a happy sound when something is funny",
    "look":      "to use your eyes to see something",
    "run":       "to move very fast on your feet",
    "walk":      "to move on your feet at a normal speed",
    "jump":      "to push yourself up into the air with your legs",
    "grab":      "to take hold of something quickly",
    "drop":      "to let something fall to the ground",
    "pick up":   "to lift something from the ground or a surface",
    "give":      "to let someone have something",
    # 高频名词
    "friend":    "someone you like and spend time with",
    "friendship": "the feeling of being friends with someone",
    "classmate": "a person in the same class as you at school",
    "kindness":  "the quality of being nice and caring",
    "teacher":   "a person whose job is to teach in a school",
    "student":   "a person who is learning at a school",
    "class":     "a group of students who learn together",
    "school":    "a place where children go to learn",
    "desk":      "a kind of table you sit at when you read or write",
    "chair":     "something you sit on",
    "book":      "pages with words and pictures joined together to read",
    "pencil":    "a thin stick used to write or draw",
    "eraser":    "a small piece of rubber used to remove pencil marks",
    "hamster":   "a small soft animal with short legs that people keep as a pet",
    # L1-L4 主题词
    "culture":   "the customs, beliefs, and ways of life of a group of people",
    "castle":    "a large old strong building where kings or queens used to live",
    "bagpipes":  "a musical instrument with a bag and pipes, played in Scotland",
    "journey":   "a trip from one place to another",
}


def _fix_vocab_def(word: str, def_text: str) -> str:
    """如果 def 是占位（meaning of X / definition of X / 空），用 _KID_DICT 兜底。"""
    bad = (
        not def_text
        or def_text.strip().lower().startswith("meaning of ")
        or def_text.strip().lower().startswith("definition of ")
        or def_text.strip().lower() == word.strip().lower()
    )
    if not bad:
        return def_text
    return _KID_DICT.get(word.strip().lower(), def_text or f"see story for the meaning of {word}")


# 词库里不该出现的"指令词"（说明这条不是单词、是任务说明，需剔除）
_BANK_STOPWORDS = {
    "sort", "into", "each", "circle", "match", "fill", "write", "draw",
    "choose", "feelings", "actions", "blank", "blanks", "category",
    "categories", "group", "groups", "using", "use", "them", "below",
    "word", "words",
}


def _clean_word_bank(words: list) -> list[str]:
    """清洗词库：只保留真正的单词（1-2 个 token、不过长、不含指令性停用词）。

    修复线上 bug：AI 偶尔把任务说明（如 'sort each word into feelings or actions'）
    塞进 word_bank，导致填空页词库里出现一整句指令、且后续填空题兜底只剩 1 题。
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for w in words or []:
        s = str(w or "").strip().strip(",.;:").strip()
        if not s:
            continue
        toks = s.split()
        low = s.lower()
        if len(toks) > 2 or len(s) > 22:
            continue
        if any(t.strip(",.").lower() in _BANK_STOPWORDS for t in toks):
            continue
        if low in seen:
            continue
        seen.add(low)
        cleaned.append(s)
    return cleaned


def _story_cloze_fills(reading_text: str, words: list, max_n: int = 4) -> list[dict]:
    """从本文里给每个目标词挖一句话做完形填空（扣住该词，挖空 → ____）。

    用户反馈：原来的兜底填空题 'I feel ____ when I see this.' 既不标准、又只有 1 题、
    版面大片留白。改成从故事原句里挖空，题目扣住本文、标准且能填满页面。
    答案取句中实际出现的词形（如 share→shared），保证句子语法通顺。
    """
    import re as _re
    sents = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", reading_text or "") if s.strip()]
    out: list[dict] = []
    used: set[str] = set()
    for w in words:
        wl = str(w or "").strip().lower()
        if not wl or " " in wl or wl in used:
            continue
        pat = _re.compile(r"\b(" + _re.escape(wl) + r"(?:s|es|ed|ing|d)?)\b", _re.I)
        for s in sents:
            if len(s) > 115:   # 太长的句子不适合做填空
                continue
            m = pat.search(s)
            if m:
                blanked = s[:m.start()] + "____" + s[m.end():]
                out.append({"sentence": blanked, "answer": m.group(1).lower()})
                used.add(wl)
                break
        if len(out) >= max_n:
            break
    return out


def _is_generic_fill(f: dict) -> bool:
    s = (f.get("sentence") or "").strip().lower()
    return ("when i see" in s) or ("see story" in s) or ("goes here" in s)


def _normalize_worksheet_data(data: dict) -> dict:
    out = dict(data)
    # v2.0：reading_q_count 在 data 上可配置（4/6/8），默认 4
    reading_q_count = max(4, min(8, int(data.get("_reading_q_count") or 4)))

    # 1) match_pairs：word 小写无标点；def 美式 + 首字母小写（更像词典定义）+ v2.0 兜底真定义
    pairs = []
    for p in (data.get("match_pairs") or []):
        word = format_word_answer(p.get("word", ""))
        definition = _to_us_spelling(str(p.get("def", "")).strip().rstrip("."))
        definition = _fix_vocab_def(word, definition)
        if word:
            pairs.append({"word": word, "def": definition, "_len": len(word)})
    # v2.0：题数上限改为 4（按官方模板，每页 3-4 题最佳）
    pairs.sort(key=lambda x: (x["_len"], x["word"]))
    for p in pairs:
        p.pop("_len", None)
    out["match_pairs"] = pairs[:4]

    # 2) word_bank：小写美式
    out["word_bank"] = [format_word_answer(w) for w in (data.get("word_bank") or []) if w]

    # 3) fill_blanks：句子格式 + 答案小写
    fills = []
    for q in (data.get("fill_blanks") or []):
        sent = format_sentence_answer(q.get("sentence", ""))
        ans = format_word_answer(q.get("answer", ""))
        # 难度启发：句长升序
        fills.append({"sentence": sent, "answer": ans, "_len": len(sent)})
    # v2.0：上限 4 题（对齐官方每页 3-4 题）
    fills.sort(key=lambda x: x["_len"])
    for x in fills:
        x.pop("_len", None)
    out["fill_blanks"] = fills[:4]

    # 4) sentence_mcs：每个 option 走句子格式；过滤 color-only 等无效题
    mcs = []
    for q in (data.get("sentence_mcs") or []):
        opts = [format_sentence_answer(o) for o in (q.get("options") or []) if o]
        # 过滤无效
        if any(any(bad in o.lower() for bad in _BANNED_PROMPT_PATTERNS) for o in opts):
            continue
        if len(opts) < 2:
            continue
        mcs.append({
            "options": opts[:2],
            "correct": q.get("correct", 0),
            "_len": sum(len(o) for o in opts),
        })
    mcs.sort(key=lambda x: x["_len"])
    for x in mcs:
        x.pop("_len", None)
    out["sentence_mcs"] = mcs[:4]

    # 5) reading_text：美式
    out["reading_text"] = _to_us_spelling(str(data.get("reading_text", "")).strip())

    # 5b) v2.3：词库清洗 + 填空题改为本文完形（修复"词库混入指令串/只有1题/中间大片留白"）
    out["word_bank"] = _clean_word_bank(out.get("word_bank") or [])
    fill_words = out["word_bank"] or [p.get("word", "") for p in out.get("match_pairs") or []]
    need_rebuild = (len(out.get("fill_blanks") or []) < 3
                    or any(_is_generic_fill(f) for f in (out.get("fill_blanks") or [])))
    if need_rebuild:
        cloze = _story_cloze_fills(out["reading_text"], fill_words, 4)
        if len(cloze) >= 2:
            out["fill_blanks"] = [
                {"sentence": format_sentence_answer(c["sentence"]),
                 "answer": format_word_answer(c["answer"])}
                for c in cloze
            ]
            # 词库直接用完形答案，避免占位/指令串混入
            out["word_bank"] = _clean_word_bank(
                [format_word_answer(c["answer"]) for c in cloze]
            )
    # 词库兜底：用填空答案凑齐（清洗后为空时），并打乱顺序避免与题目逐行对应
    if not out["word_bank"] and out.get("fill_blanks"):
        out["word_bank"] = _clean_word_bank([f.get("answer") for f in out["fill_blanks"]])
    if out["word_bank"]:
        import random as _rnd
        out["word_bank"] = list(dict.fromkeys(out["word_bank"]))[:6]
        _rnd.shuffle(out["word_bank"])

    # 6) reading_mcs：题干补问号 + 美式 + 首字母大写；选项 smart_format
    rmcs = []
    for q in (data.get("reading_mcs") or []):
        stem = _to_us_spelling(str(q.get("q", "")).strip().rstrip(".!?"))
        # 独立 i 大写
        import re as _re
        stem = _re.sub(r"\bi\b", "I", stem)
        stem = _re.sub(r"\bi(['\u2019])", r"I\1", stem)
        # 首字母大写
        if stem:
            stem = stem[0].upper() + stem[1:]
        if stem and stem[-1] not in "?？":
            stem += "?"
        opts = [smart_format_answer(o) for o in (q.get("options") or []) if o]
        # 过滤 color-only 活动
        stem_low = stem.lower()
        if any(bad in stem_low for bad in _BANNED_PROMPT_PATTERNS):
            continue
        if not stem or len(opts) < 2:
            continue
        rmcs.append({
            "q": stem, "options": opts[:3],
            "correct": q.get("correct", 0),
            "_len": len(stem),
        })
    # 题干越短越简单，放顶上；上限按 _reading_q_count 配置（4/6/8）
    rmcs.sort(key=lambda x: x["_len"])
    for x in rmcs:
        x.pop("_len", None)
    out["reading_mcs"] = rmcs[:reading_q_count]

    # 7) writing：theme/title/steps 美式；步骤句子格式
    writing = dict(data.get("writing") or {})
    writing["theme"] = _to_us_spelling(str(writing.get("theme", "the story")))
    writing["title"] = _to_us_spelling(str(writing.get("title", "")))
    steps_raw = writing.get("steps") or [""] * 5
    writing["steps"] = [
        format_sentence_answer(s) if s.strip() else "" for s in steps_raw
    ]
    out["writing"] = writing

    # 8) mind_map：character 短语形式（首字母大写、无句号）；problem/solution 句子形式
    mm = []
    for r in (data.get("mind_map") or [])[:5]:
        ch_raw = str(r.get("character", "")).strip().rstrip(".")
        ch = _to_us_spelling(ch_raw) if ch_raw else ""
        if ch:
            ch = ch[0].upper() + ch[1:]
        mm.append({
            "character": ch,
            "problem": format_sentence_answer(r.get("problem", "")),
            "solution": format_sentence_answer(r.get("solution", "")),
        })
    out["mind_map"] = mm

    return out


def _build_default_data(outline: BookOutline) -> dict:
    words = (
        outline.vocabulary_mastery
        or outline.vocabulary_simple
        or ["nervous", "shake", "recess", "wooden", "a pile of"]
    )[:5]
    words = list(words) + ["word"] * max(0, 5 - len(words))
    words = words[:5]

    pages = outline.pages or []
    story_text = capitalize_names(" ".join(
        (p.text or "").strip() for p in pages if (p.text or "").strip()
    ).strip())
    if not story_text:
        story_text = "Story text goes here."

    story_sents: list[str] = []
    for p in pages:
        if (p.text or "").strip():
            story_sents.append(capitalize_names(p.text.strip()))
    if not story_sents:
        story_sents = ["Story sentence goes here."]

    def _pair_sent(idx: int) -> dict:
        """从故事页取真句子做选项，避免 'Not X' 这种生硬兜底。"""
        correct = story_sents[idx % len(story_sents)]
        distractor_idx = (idx + 1) % len(story_sents)
        if len(story_sents) > 1 and distractor_idx == idx % len(story_sents):
            distractor_idx = (idx + 2) % len(story_sents)
        distractor = story_sents[distractor_idx]
        return {"options": [correct, distractor], "correct": 0}

    return {
        "match_pairs": [
            {"word": w, "def": f"definition of {w}"} for w in words
        ],
        "word_bank": list(words),
        "fill_blanks": [
            {"sentence": f"I _______ when I see {w}.", "answer": w} for w in words
        ],
        "sentence_mcs": [_pair_sent(i) for i in range(min(4, len(story_sents)))],
        "reading_text": story_text,
        "reading_mcs": [
            {
                "q": f"Question {i + 1}?",
                "options": ["Option A", "Option B", "Option C"],
                "correct": 0,
            }
            for i in range(8)
        ],
        "writing": _retell_writing_scaffold(outline),
        "mind_map": [
            {"character": "Main character", "problem": "Problem statement.",
             "solution": "Solution statement."},
        ] * 5,
    }


# ============================================================
#  工具
# ============================================================

def _level_label(level: str) -> str:
    s = (level or "").strip()
    if not s:
        return "Level 1"
    if s.lower().startswith("smart"):
        return "Smart"
    if s.lower().startswith("level"):
        return s
    digits = "".join(ch for ch in s if ch.isdigit())
    return f"Level {digits or '1'}"


def safe_filename(name: str) -> str:
    """与 ppt_builder.safe_filename 对齐，方便复用。"""
    import re
    safe = re.sub(r"[^\w\u4e00-\u9fff -]+", "_", name).strip("_ ")
    return safe + ".pptx"
