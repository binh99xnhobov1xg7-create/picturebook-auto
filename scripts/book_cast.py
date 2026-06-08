# -*- coding: utf-8 -*-
"""书内角色册（Book Cast Sheet）—— 一次性/非 IP 角色的"书内锁"。

用户拍板 2026-06-07：未来会有大量【一次性角色】（nurse / farmer Tom / Goldilocks /
Ravi / 店员 / 外星人……），它们不在 IP 注册表里、不可能提前定义。处理逻辑：

  · 第 ③ 层身份（见 cn_prompt_builder 的四层判定）：一次性角色【永不映射成 Mia/Tommy】，
    按它自己的身份画。
  · 跨页一致性根治：对【反复出场】（≥2 个故事页）的非 IP 角色，本模块为它在【这本书内】
    锁定一句统一外观描述，并（在 batch_runner 里）生成一张【书内定妆锚图】，
    后续每一页都复用同一描述 + 同一锚图 → 做到和主角一样稳，但只在本书有效。

数据来源优先级：官方每课 prompt 的逐页画面文本（作者已写明角色 + 外观）> 故事正文。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from character_registry import REGISTRY
from cn_prompt_builder import _official_positive

# 这些"加粗词"是道具/场景/身体部位，不是角色 —— 检测时剔除
_PROP_WORDS = re.compile(
    r"\b(bowl|bowls|chair|chairs|bed|beds|house|home|cottage|table|door|window|"
    r"river|stream|lake|sea|mountain|forest|tree|trees|garden|sky|cloud|road|path|"
    r"car|cars|bucket|trunk|water|stone|stones|pitcher|nest|egg|eggs|book|storybook|"
    r"fable book|magic storybook|pen pal package|letter|crane|paper crane|sticker|"
    r"battery|robot|poster|shelf|wall|grass|flower|flowers|rock|rocks|bridge|boat|"
    r"farm|market|town|village|city|kitchen|bedroom|doorway|woods|field|fields|barn|"
    r"hand|hands|arm|arms|foot|feet|face|eyes|head|leg|legs|finger|fingers|"
    r"kite|ball|top|key|plane|airplane|jet|train|bus|truck|bike|"
    r"journal|notebook|diary|map|binoculars|glass|lens|magnifying|telescope|"
    r"blanket|rug|mat|cave|canyon|ocean|river|lake|pond|reef|desert|habitat|"
    r"rainforest|jungle|savanna|savannah|grassland|wetland|tundra|island|valley|"
    r"cell|cells|germ|germs|virus|bacteria|atom|molecule|planet|star|sun|moon|"
    r"club|team|sport|sports|soccer|key|cog|gear|machine|engine|"
    r"camel|mammal|mammals|reptile|reptiles|"
    r"shot|view|scene|background|foreground|prompt|style|wash|space|title|text)\b",
    re.I,
)
# 官方常把【情绪/表情标签】也加粗（**Happy:** …）—— 不是角色，剔除
_EMOTION = re.compile(
    r"^(happy|sad|curious|excited|focused|peaceful|calm|surprised|shocked|angry|"
    r"scared|afraid|proud|shy|brave|gentle|confused|nervous|worried|frustrated|"
    r"greedy|joyful|cheerful|determined|thoughtful|amazed|delighted|content)$",
    re.I,
)
# 这些是 IP（已有定妆图，单独处理，不进"一次性角色册"）
_IP_NAMES = set(REGISTRY.keys()) | {
    "mia", "tommy", "anna", "cate", "ali", "grandma", "grandmother", "granny",
    "grandpa", "grandfather", "mom", "mommy", "mother", "dad", "daddy", "father",
    "ms. kim", "teacher kim", "kim", "max", "winnie", "dino", "cat",
}
# 动物/角色名词（用于判定一个加粗词是不是"角色"）
_ANIMATE = re.compile(
    r"\b(man|woman|boy|girl|lady|gentleman|king|queen|prince|princess|"
    r"nurse|doctor|farmer|teacher|baker|shopkeeper|mailman|postman|firefighter|"
    r"police|driver|chef|cook|waiter|clerk|guard|pilot|sailor|knight|"
    r"fox|wolf|bear|bears|pig|pigs|goat|goats|cow|horse|sheep|duck|hen|rooster|"
    r"mouse|mice|rat|rabbit|bunny|hare|tortoise|turtle|lion|tiger|monkey|"
    r"elephant|frog|snake|owl|crow|bird|deer|eagle|cat|dog|goose|"
    r"giant|troll|ogre|dragon|fairy|elf|gnome|goblin|witch|robot|monster|alien|"
    r"gingerbread man|snowman)\b",
    re.I,
)


@dataclass
class OneOffRole:
    rid: str                       # 归一 id，如 "goldilocks" / "fox" / "nurse"
    display: str                   # 展示名，如 "Goldilocks" / "the fox"
    desc_en: str                   # 锁定外观（取自官方最丰富的一次提及，英文短语）
    page_indexes: list[int] = field(default_factory=list)
    anchor_path: str | None = None  # 书内定妆锚图（生成后回填）

    @property
    def count(self) -> int:
        return len(self.page_indexes)

    @property
    def needs_anchor(self) -> bool:
        # 反复出场（≥2 个故事页）才值得生成书内锚图锁死；只出现 1 页的天然一致，不必锚
        return self.count >= 2


def _bold_tokens(text: str) -> list[str]:
    """抓官方 prompt 里 **加粗** 的词组。"""
    return [m.group(1).strip() for m in re.finditer(r"\*\*(.+?)\*\*", text or "")]


def _norm_rid(token: str) -> str:
    t = re.sub(r"\(.*?\)", "", token).strip().lower()           # 去掉 "(10 years old)"
    t = re.sub(r"^(the|a|an)\s+", "", t).strip()                 # 去冠词
    t = re.sub(r"[^a-z0-9 ]+", "", t).strip()
    return t


def _is_character_token(token: str) -> bool:
    """判断一个加粗词是不是"角色"（而非道具/场景/画面术语）。"""
    raw = token.strip()
    low = _norm_rid(raw)
    if not low or len(low) > 40:
        return False
    if _EMOTION.match(low):
        return False
    if _PROP_WORDS.search(low):
        return False
    if low in _IP_NAMES:
        return False
    # 任一单词是 IP（含 "Tommy and Mia" / "Tommy's" / 所有格）→ 属 IP，不进一次性册
    for w in re.split(r"[^a-z]+", low):
        if not w:
            continue
        if w in _IP_NAMES or (w.endswith("s") and w[:-1] in _IP_NAMES):
            return False
    # 含年龄标注（"(10 years old)"）→ 几乎肯定是人物
    if re.search(r"\d+\s*years?\s*old", raw, re.I):
        return True
    # 命中动物/职业/角色名词 → 是角色
    if _ANIMATE.search(low):
        return True
    # 【单词专有名词】（首字母大写、≥3 字母、非画面术语）→ 视为一次性人名（Goldilocks/Ravi/Sasha）。
    #   只认单词，避免把 "Picnic Blanket"/"Nature Journal"/"Grand Canyon" 等双词道具误当角色。
    name = re.sub(r"\(.*?\)", "", raw).strip().rstrip(":").strip()
    if name and " " not in name and name[:1].isupper() and len(low) >= 3:
        if not re.match(r"(ws|ms|mcu|cu|shot|close|wide|medium|low|high|eye)\b", low):
            return True
    return False


# 句首/常见大写词，纯文本模式下不算角色
_PLAIN_STOP = {
    "the", "a", "an", "one", "two", "three", "next", "first", "then", "finally",
    "together", "now", "here", "there", "this", "that", "these", "those", "when",
    "after", "before", "soon", "suddenly", "inside", "outside", "down", "up", "he",
    "she", "they", "it", "but", "and", "so", "water", "rain", "night", "day", "morning",
    "later", "once", "every", "all", "some", "many", "very", "just", "still", "yes", "no",
    "oh", "wow", "look", "come", "go", "let", "we", "you", "i", "my", "his", "her", "its",
    "their", "our", "home", "help", "story", "page", "the end", "chapter",
}


def _plain_text_tokens(text: str) -> list[str]:
    """无官方 prompt 时，从故事正文里抓候选角色词（首字母大写专名 + 'Farmer Tom' 式双词 + 角色名词）。"""
    toks: list[str] = []
    # "Farmer Tom" / "Clever Crow" 等 形容词/职业+大写名
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text or ""):
        cand = m.group(1)
        if cand.lower() in _PLAIN_STOP:
            continue
        toks.append(cand)
    # 角色名词（the fox / a rabbit）即便小写也算
    for m in re.finditer(r"\b(?:the|a|an)\s+([a-z]+)\b", text or "", re.I):
        if _ANIMATE.search(m.group(1)):
            toks.append(m.group(1))
    return toks


def build_book_cast(outline) -> dict[str, OneOffRole]:
    """扫描全书，登记【反复出场的非 IP 一次性角色】。

    有官方 prompt → 用其逐页画面文本的 **加粗** 角色（最准）；
    无官方 prompt（新书只有故事正文）→ 回退用故事正文里的专名/角色名词识别。
    返回 {rid: OneOffRole}（含 needs_anchor 候选 + 单页角色，便于注入锁定描述）。
    """
    oip = getattr(outline, "official_image_prompt", None)
    roles: dict[str, OneOffRole] = {}
    use_official = oip is not None

    for page in outline.pages:
        if use_official:
            try:
                raw = oip.page_scene(page.index) or ""
            except Exception:
                raw = ""
            pos = _official_positive(raw)
            tokens = _bold_tokens(pos)
        else:
            pos = (page.text or "") + " " + (getattr(page, "scene", "") or "")
            tokens = _plain_text_tokens(pos)
        if not pos:
            continue
        seen_on_page: set[str] = set()
        for tok in tokens:
            if not _is_character_token(tok):
                continue
            rid = _norm_rid(tok)
            if not rid or rid in _IP_NAMES or rid in seen_on_page:
                continue
            seen_on_page.add(rid)
            r = roles.get(rid)
            if r is None:
                r = OneOffRole(rid=rid, display=tok.strip().strip("*").rstrip(":").strip(),
                               desc_en=_extract_desc(pos, tok))
                roles[rid] = r
            if page.index not in r.page_indexes:
                r.page_indexes.append(page.index)
            cand = _extract_desc(pos, tok)
            if len(cand) > len(r.desc_en):
                r.desc_en = cand
    return roles


def _extract_desc(pos: str, token: str) -> str:
    """取官方文本里包含该角色的那一句作为外观锁定描述（去 markdown、限长）。"""
    plain = pos.replace("**", "")
    name = re.sub(r"\(.*?\)", "", token).strip().strip("*")
    for sent in re.split(r"(?<=[.!?])\s+", plain):
        if name and name.lower() in sent.lower():
            return sent.strip()[:240]
    return ""


def anchor_prompt(role: OneOffRole) -> str:
    """为一次性角色生成【书内定妆锚图】的 prompt（白底单人，治愈水彩，友善可爱）。"""
    desc = (role.desc_en or "").strip()
    who = role.display.strip()
    return (
        f"角色定妆参考图：{who}。{('外观依据：' + desc) if desc else ''} "
        "整张图只画这一个角色，单人全身居中、自然站姿、面向观众轻微侧身，纯白色背景、无任何其他人物/道具/文字。"
        "干净平滑、统一治愈系水彩儿童绘本画风，线条柔和、上色通透，"
        "角色表情友善温和、可爱亲切——绝不凶恶、不露獠牙、不阴森吓人（这是给低龄儿童看的绘本）。"
        "用于后续每一页该角色的形象锁定，请把脸型、五官、发型/毛色、肤色、服装款式与配色画清楚、明确、可复用。\n\n"
        "【负向】不要文字、不要多个角色、不要分镜/多视图排版、不要照片质感、不要恐怖/暴力/丑陋元素、不要复杂背景。"
    )


def roles_on_page(book_cast: dict[str, OneOffRole], official_raw: str) -> list[OneOffRole]:
    """本页官方文本里出现了哪些已登记的一次性角色。"""
    if not book_cast or not official_raw:
        return []
    low = _official_positive(official_raw).lower()
    out = []
    for r in book_cast.values():
        if re.search(rf"\b{re.escape(r.rid)}\b", low) or r.rid in low:
            out.append(r)
    return out
