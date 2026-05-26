"""即梦 4.6 单页 prompt 构造：style + IP + scene + tail，≤800 chars。"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from config import CHARACTERS_DIR, STYLE_DIR, TEXT_SAFE_RATIO_MIN, TEXT_SAFE_RATIO_MAX
from parser import BookOutline, PageSpec


# ---------- 风格基线（干净水彩，禁止色斑杂阴影）----------
STYLE_BIBLE = (
    "Clean watercolor children's book illustration, smooth even wash, "
    "flat soft color, gentle gradient, minimal background detail, "
    "no mottled patches, no scattered noise, no harsh shadow, "
    "rounded smooth lines, 4:3 horizontal"
)

STYLE_TAIL_TPL = (
    "Strictly follow character bible reference image: keep face shape, "
    "hairstyle and outfit identical across the series. "
    "Reserve {lo:.0%}-{hi:.0%} clean blank area at {corner_phrase} for caption "
    "(no people/props/text/watermarks there)."
)


# ---------- IP 描述（强化性别区分，靠参考图大表兜底视觉细节）----------
IP_BLOCKS: dict[tuple[str, int], str] = {
    ("mia", 8):    "Mia: 8y GIRL with long brown high ponytail, purple short-sleeve tee, denim jeans, white sneakers",
    ("tommy", 8):  "Tommy: 8y BOY (NOT a girl, NO ponytail) with short tidy brown hair, "
                   "blue-and-white horizontal striped tee, denim jeans, white sneakers",
    ("mia", 10):   "Mia: 10y GIRL with long brown high ponytail tied behind, "
                   "lavender purple long-sleeve sweatshirt, light gray sweatpants, white sneakers",
    ("tommy", 10): "Tommy: 10y BOY (NOT a girl, NO ponytail, never long hair) with short messy brown hair, "
                   "light blue long-sleeve sweatshirt, khaki straight pants, white sneakers",
    ("mia", 12):   "Mia: 12y GIRL with long brown high ponytail tied behind, "
                   "lavender purple knit top, white wide-leg trousers, white sneakers",
    ("tommy", 12): "Tommy: 12y BOY (NOT a girl, NO ponytail, never long hair) with short tidy brown hair, "
                   "navy blue short-sleeve polo, light blue jeans, white sneakers",
}

PARENTS_BLOCK = (
    "Mom: adult woman, long brown wavy shoulder-length hair, cream top, blue jeans, gentle smile. "
    "Dad: adult man, short tidy brown hair, gray polo, khaki trousers, warm smile"
)


# ---------- 角色识别（仅认显式人物词；代词 they/their 不算父母出场）----------
def detect_cast(text: str) -> dict[str, bool]:
    t = (text or "").lower()
    parent_words = ("mom", "mum", "dad", "parent", "mother", "father", "family")
    return {
        "mia": "mia" in t,
        "tommy": "tommy" in t,
        "parents": any(k in t for k in parent_words),
    }


_CORNER_PHRASE = {
    "top-left": "top-left",
    "top-right": "top-right",
    "bottom-left": "bottom-left",
    "bottom-right": "bottom-right",
}


@dataclass
class BuiltPrompt:
    prompt: str
    references: list[Path]


def build_page_prompt(page: PageSpec, book: BookOutline, ip_age: int) -> BuiltPrompt:
    cast_text = (page.text or "") + " " + (page.scene or "")
    cast = detect_cast(cast_text)

    # 封面默认所有主角出场
    if page.page_type == "cover" and not (cast["mia"] or cast["tommy"]):
        cast["mia"] = True
        cast["tommy"] = True

    blocks: list[str] = [STYLE_BIBLE]

    if cast["mia"]:
        blocks.append(IP_BLOCKS[("mia", ip_age)])
    if cast["tommy"]:
        blocks.append(IP_BLOCKS[("tommy", ip_age)])
    if cast["parents"] and page.page_type == "story":
        blocks.append(PARENTS_BLOCK)

    expression = page.expression or _infer_expression(page.text)
    if expression and page.page_type == "story":
        blocks.append(f"Expression: {expression}")

    scene = page.scene or page.text

    if page.page_type == "cover":
        cover_layout = (
            "Cover composition: upper 35% must be clean empty pale sky area, "
            "characters positioned in lower 65%. "
            "ABSOLUTELY NO TEXT, NO LETTERS, NO BOOK TITLE, NO WORDS rendered in the image"
        )
        corner_phrase = "top 35%"
        tail = STYLE_TAIL_TPL.format(
            lo=TEXT_SAFE_RATIO_MIN, hi=TEXT_SAFE_RATIO_MAX, corner_phrase=corner_phrase
        )
    else:
        cover_layout = ""
        corner = page.text_corner or "top-left"
        corner_phrase = _CORNER_PHRASE.get(corner, "top-left")
        tail = STYLE_TAIL_TPL.format(
            lo=TEXT_SAFE_RATIO_MIN, hi=TEXT_SAFE_RATIO_MAX, corner_phrase=corner_phrase
        )

    # 头部：风格 + IP（不可压缩）
    head = ". ".join(b.strip().rstrip(".") for b in blocks) + "."

    # 中段：scene + 封面布局（可压缩）
    mid_parts = []
    if scene:
        mid_parts.append(f"Scene: {scene.strip()}")
    if cover_layout:
        mid_parts.append(cover_layout)
    mid = (". ".join(p.rstrip(".") for p in mid_parts) + ".") if mid_parts else ""

    # 尾部（受保护，永不截断）。即梦 4.6 支持 ~2000 字符，这里给 1500 上限。
    LIMIT = 1500
    tail_full = tail.strip()
    budget = LIMIT - len(head) - len(tail_full) - 2  # 2 是连接空格
    if budget < 0:
        head = head[: max(0, LIMIT - len(tail_full) - 2)]
        mid = ""
    elif len(mid) > budget:
        mid = mid[: max(0, budget - 3)].rstrip() + "..."

    prompt = " ".join(part for part in (head, mid, tail_full) if part).strip()

    scene_text_for_refs = f"{page.text or ''} {page.scene or ''}"
    references = _collect_references(cast, ip_age, scene_text_for_refs)
    return BuiltPrompt(prompt=prompt, references=references)


_EMOTION_KEYWORDS: list[tuple[str, str]] = [
    ("excit",  "excited bright eyes, open joyful smile"),
    ("amaz",   "amazed wide eyes, open mouth in wonder"),
    ("surpr",  "surprised wide eyes, raised brows, open mouth"),
    ("worry",  "worried furrowed brows, tight mouth, anxious eyes"),
    ("scared", "scared wide eyes, slight frown"),
    ("happy",  "happy bright smile"),
    ("sad",    "sad downturned mouth, soft eyes"),
    ("curio",  "curious tilted head, soft interested smile"),
    ("relie",  "relieved gentle smile, soft eyes"),
    ("grate",  "grateful soft smile, warm eyes"),
    ("farewell", "warm bittersweet farewell smile, soft eyes"),
    ("unfor",  "warm fond smile, slightly wistful eyes"),
]


def _infer_expression(text: str) -> str:
    t = (text or "").lower()
    found: list[str] = []
    for key, phrase in _EMOTION_KEYWORDS:
        if key in t and phrase not in found:
            found.append(phrase)
    return "; ".join(found[:2])


def _select_character_bible(ip_age: int) -> Path | None:
    """按年龄优先取人物设定大表。"""
    candidates = [
        CHARACTERS_DIR / f"character_bible_l{_age_bracket(ip_age)}.png",
        CHARACTERS_DIR / "character_bible_l4-6.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _age_bracket(ip_age: int) -> str:
    if ip_age <= 8:
        return "0-3"
    if ip_age <= 10:
        return "4-5"
    return "6"


# 次要人物参考图：按场景关键词自动挂载
# 用 (pattern, filename)，pattern 走正则单词边界，避免 "Scottish/Scotland" 误命中 kilt 图
import re as _re_secondary  # 局部别名，避免污染

SECONDARY_CHAR_REFS: list[tuple[str, str]] = [
    (r"\bkilt\b",       "kilt_men_reference.png"),
    (r"\bscotsman\b",   "kilt_men_reference.png"),
    (r"\bscotsmen\b",   "kilt_men_reference.png"),
    (r"\bbagpip\w*\b",  "kilt_men_reference.png"),
    (r"\bsheep\b",      "sheep_reference.png"),
    (r"\bshepherd\b",   "shepherd_reference.png"),
]


def _detect_secondary_refs(scene_text: str) -> list[Path]:
    t = (scene_text or "").lower()
    refs: list[Path] = []
    seen_files: set[str] = set()
    for pattern, filename in SECONDARY_CHAR_REFS:
        if _re_secondary.search(pattern, t) and filename not in seen_files:
            p = CHARACTERS_DIR / filename
            if p.exists():
                refs.append(p)
                seen_files.add(filename)
    return refs


def _collect_references(
    cast: dict[str, bool], ip_age: int, scene_text: str = ""
) -> list[Path]:
    """参考图优先级（受 4 张上限约束，越靠前越保留）：
    1. character_bible  —— Mia/Tommy IP 主锚（绝不丢）
    2. parents_reference —— 父母 IP（出现时绝不丢）
    3. secondary refs   —— 苏格兰人/羊 等次要角色 IP
    4. clean_watercolor —— 风格兜底（不够位置时第一个被挤掉）
    """
    refs: list[Path] = []

    bible = _select_character_bible(ip_age)
    if bible:
        refs.append(bible)

    if cast["parents"]:
        p = CHARACTERS_DIR / "parents_reference.png"
        if p.exists():
            refs.append(p)

    for sec in _detect_secondary_refs(scene_text):
        refs.append(sec)

    style_clean = STYLE_DIR / "clean_watercolor_reference.png"
    if style_clean.exists():
        refs.append(style_clean)

    if not bible:
        if cast["tommy"]:
            p = CHARACTERS_DIR / f"tommy_age{ip_age}.png"
            if p.exists():
                refs.append(p)
        if cast["mia"]:
            p = CHARACTERS_DIR / f"mia_age{ip_age}.png"
            if p.exists():
                refs.append(p)

    seen = set()
    out: list[Path] = []
    for r in refs:
        k = str(r.resolve())
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out[:4]
