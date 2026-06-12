"""解析 9 页绘本大纲（Markdown）。

支持的字段：
  Title / Level / Book / CEFR / Lexile / Word_count / IP_Age
  Vocabulary  或  Vocabulary_Mastery + Vocabulary_Exposure
  # Cover  + Scene:
  # Page 1..7  + Text: + Scene:  + Text_Position: (可选)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PageSpec:
    index: int               # 0 = 封面，1-7 = 故事页
    page_type: str           # "cover" | "story"
    text: str = ""           # 英文台词
    scene: str = ""          # 场景描述（英文，AI 抽取的简短 visual hint）
    scene_cn: str = ""       # v1.9 新增：中文画面描述（120-220 字，主体+动作+环境+氛围），喂给 Doubao Seedream
    text_corner: str = ""    # "top-left" | "top-right" | "bottom-left" | "bottom-right"
    expression: str = ""     # 该页人物情绪（如 "excited" / "worried" / "amazed"）
    shot: str = ""           # "close" | "medium" | "full" | "wide"，留空走默认 medium
    # v5 新增：机位角度（俯视/仰视/平视/越肩…），由 AI 按剧情选，避免全本平视
    camera_angle: str = ""   # "eye" | "high" | "low" | "birdseye" | "over_shoulder"，留空走 eye
    # v5 新增：本页画面 hook（一句话趣味彩蛋，如"桌下卡着橡皮的小仓鼠"），增强趣味性
    hook: str = ""
    # v6 新增：本页"高潮/焦点动作"——本页最具视觉张力的那一下，作为画面主体居中动作（如"Tommy 俯身扑向逃窜的小仓鼠"）
    focus: str = ""
    # 块4（用户拍板 2026-06-08）：生图前给老师确认的"简体中文场景安全线"（谁+在哪+做什么）。
    # 非空时作为本页画面的权威核心注入 prompt 最前；老师可在生图前逐页编辑确认。
    safety_line: str = ""
    # 科普/历史书的【本页年代/时代】标签（如 "long-ago one-room schoolhouse era" / "modern present-day"
    # / "past-vs-present contrast" / "ancient" / "future"）。由 AI 按本页文字推断，留空=无特定历史设定。
    # 出图时据此把本页布景/家具/器物/服装/科技锁到该年代，避免"过去页画成现代/现代页画成过去"。
    era: str = ""
    # 角色猜测/想象画面：真实人物仍按本页现实衣着画；这里描述小型 thought bubble 内的想象内容。
    thought_bubble: str = ""
    # 本页贯穿道具状态补充：朝向/装订边/内容是否朝内或不可读等，供 recurring_props 逐页复用。
    prop_state: str = ""

    @property
    def label(self) -> str:
        return "Cover" if self.page_type == "cover" else f"Page {self.index}"

    @property
    def word_count(self) -> int:
        return len(re.findall(r"\b\w+\b", self.text))


@dataclass
class BookOutline:
    title: str
    pages: list[PageSpec] = field(default_factory=list)
    level: str = ""
    book_number: str = ""
    cefr: str = ""
    lexile: str = ""
    lexile_source: str = ""   # 块11：来源审计 syllabus / analyzer / manual / na（禁止编造）
    word_count_override: str = ""
    ip_age: int | None = None

    vocabulary_mastery: list[str] = field(default_factory=list)
    vocabulary_exposure: list[str] = field(default_factory=list)
    vocabulary_simple: list[str] = field(default_factory=list)  # 单行模式

    # v1.4 新增：教学元信息
    phonics: str = ""              # 自然拼读规则（如 'consonant blend "fr" (friendship)'）
    grammar_focus: str = ""        # 主语法点（如 "一般现在时态" / "Simple past tense"）
    reader_type: str = ""          # 读者类型（覆盖 _default_reader_type 推断）
    fiction_type: str = ""         # v1.8：L3-L6 用，取值 "fiction" / "non-fiction"
    lesson_time: str = "60 mins"   # 默认 60 分钟
    theme: str = ""                # 主题（如 "friendship"）

    # 角色别名映射（如 {"anna": "mia", "kevin": "tommy"}）
    aliases: dict[str, str] = field(default_factory=dict)

    # 自定义独立角色（v1.3.2）
    custom_characters: dict[str, str] = field(default_factory=dict)

    # v7 新增：官方 S&S 大纲注入（命中 references/syllabus 时为真值，未命中保持空/None）
    reading_strategy: str = ""       # 大纲精确策略名（如 "Visualizing (视觉化)"）
    reading_skill: str = ""          # 大纲精确技能名（如 "Main Idea and Supporting Details"）
    graphic_organizer: str = ""      # GO 名称（如 "Bubble Map (气泡图)"）
    graphic_organizer_desc: str = "" # GO 使用说明（大纲"描述"列）
    syllabus: object | None = None   # 命中的 SyllabusEntry（teacher_guide 直接取用），未命中 None
    official_image_prompt: object | None = None  # 命中的官方每课出图 Prompt（OfficialImagePrompt），出图时权威参考注入
    book_cast: dict | None = None    # 书内角色册：反复出场的一次性/非 IP 角色 → 全书形象锁 + 书内定妆锚图
    frame_mode: str = "A+"           # 框架寓言呈现模式（老师拍板 2026-06-08 默认 A+）：封面=拿书引子+中间纯故事+末页故事结尾&合书；B/A 备选
    # SOP「关键贯穿物件统一描述」：若全书围绕【同一个反复出现的关键物件】（味道/气味等抽象描述会变、
    #   但实物始终是同一个），AI 在此给出该物件【唯一固定的视觉描述】（造型/颜色/大小/材质/盛器，不含抽象感受词）
    #   + 出现页 + 各页允许的【具体物理状态变化】（盖着→揭开、整个→切开…）。出图时逐页复用同一描述、只改状态。
    #   形如 {"present": bool, "name": str, "unified_desc_cn": str, "pages": [int], "states": [{"pages":[int], "state": str}]}。
    key_object: dict | None = None
    # 固定班级/群像册：本书内部固定 exactly 4 classmates + 1 teacher，跨页复用，不跨书复用。
    class_ensemble: dict | None = None
    # 贯穿多页的普通道具（非唯一关键物件）：统一外观 + 朝向/装订/内容朝内不可读等约束。
    recurring_props: list[dict] = field(default_factory=list)

    @property
    def slug(self) -> str:
        safe = re.sub(r"[^\w\s-]", "", self.title, flags=re.UNICODE)
        safe = re.sub(r"\s+", "_", safe.strip()) or "picturebook"
        return safe[:80]

    @property
    def total_words(self) -> int:
        if self.word_count_override:
            try:
                return int(self.word_count_override)
            except ValueError:
                pass
        return sum(p.word_count for p in self.pages if p.page_type == "story")

    @property
    def has_double_vocab(self) -> bool:
        return bool(self.vocabulary_mastery or self.vocabulary_exposure)

    @property
    def vocabulary_for_display(self) -> list[str]:
        if self.vocabulary_simple:
            return self.vocabulary_simple
        return self.vocabulary_mastery + self.vocabulary_exposure

    @property
    def level_key(self) -> str:
        """返回 'smart' / '0' / '1' / ... / '6' 用于查表。"""
        s = (self.level or "").strip().lower()
        if "smart" in s:
            return "smart"
        digits = "".join(ch for ch in s if ch.isdigit())
        return digits or "1"

    @property
    def is_dual_vocab_level(self) -> bool:
        """L0/L1/L2 用双行 Mastery+Exposure；L3-L6 用单行 Vocabulary 4 词。"""
        return self.level_key in ("smart", "0", "1", "2")

    @property
    def story_text(self) -> str:
        return " ".join(p.text for p in self.pages if p.page_type == "story" and p.text).strip()

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("大纲缺少 Title")
        if len(self.pages) != 8:
            raise ValueError(
                f"需要 1 封面 + 7 故事 = 8 个页面节点，当前 {len(self.pages)} 个"
            )


# ---------- 解析入口 ----------
def parse_outline_file(path: Path) -> BookOutline:
    return parse_outline_text(path.read_text(encoding="utf-8"))


def parse_outline_text(text: str) -> BookOutline:
    lines = text.replace("\r\n", "\n").split("\n")

    meta: dict[str, str] = {}
    pages_raw: list[dict] = []

    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            current["text"] = " ".join(
                s.strip() for s in current.get("_text_lines", []) if s.strip()
            )
            current.pop("_text_lines", None)
            pages_raw.append(current)
            current = None

    field_re = re.compile(
        r"^(Title|Level|Book|CEFR|Lexile|Word_?count|IP_?Age|Theme|"
        r"Phonics|Grammar(?:_?Focus)?|Reader_?Type|Lesson_?Time|"
        r"Vocabulary_?Mastery|Vocabulary_?Exposure|Vocabulary|Aliases|Custom_\w+)\s*:\s*(.*)$",
        re.I,
    )
    page_header_re = re.compile(
        r"^#+\s*(Cover|封面|Page\s*(\d+)|第\s*(\d+)\s*页)\s*$", re.I
    )
    text_re = re.compile(r"^Text\s*:\s*(.*)$", re.I)
    scene_re = re.compile(r"^Scene\s*:\s*(.*)$", re.I)
    pos_re = re.compile(r"^Text_?Position\s*:\s*(.*)$", re.I)
    expr_re = re.compile(r"^Expression\s*:\s*(.*)$", re.I)
    shot_re = re.compile(r"^Shot\s*:\s*(.*)$", re.I)
    angle_re = re.compile(r"^(?:Camera_?Angle|Angle)\s*:\s*(.*)$", re.I)
    hook_re = re.compile(r"^Hook\s*:\s*(.*)$", re.I)

    for raw in lines:
        line = raw.rstrip()
        s = line.strip()
        if not s and current is None:
            continue

        m_header = page_header_re.match(s)
        if m_header:
            flush()
            name = (m_header.group(1) or "").lower()
            if name in ("cover", "封面"):
                current = {"kind": "cover", "_text_lines": []}
            else:
                num = m_header.group(2) or m_header.group(3)
                current = {"kind": "story", "index": int(num), "_text_lines": []}
            continue

        if current is None:
            m_field = field_re.match(s)
            if m_field:
                raw_key = m_field.group(1)
                # Custom_<Name> 保留下划线（之后特殊处理）
                if raw_key.lower().startswith("custom_"):
                    key = raw_key.lower()
                else:
                    key = raw_key.replace("_", "").lower()
                meta[key] = m_field.group(2).strip()
                continue
            # markdown 一级标题作书名
            if s.startswith("# "):
                meta.setdefault("title", s[2:].strip())
            continue

        # 在 page 块内
        m_text = text_re.match(s)
        if m_text:
            current["_text_lines"].append(m_text.group(1))
            continue
        m_scene = scene_re.match(s)
        if m_scene:
            current["scene"] = m_scene.group(1).strip()
            continue
        m_pos = pos_re.match(s)
        if m_pos:
            current["text_corner"] = m_pos.group(1).strip().lower()
            continue
        m_expr = expr_re.match(s)
        if m_expr:
            current["expression"] = m_expr.group(1).strip()
            continue
        m_shot = shot_re.match(s)
        if m_shot:
            current["shot"] = m_shot.group(1).strip().lower()
            continue
        m_angle = angle_re.match(s)
        if m_angle:
            current["camera_angle"] = m_angle.group(1).strip().lower()
            continue
        m_hook = hook_re.match(s)
        if m_hook:
            current["hook"] = m_hook.group(1).strip()
            continue
        # 其它行：拼到 text
        if s:
            current["_text_lines"].append(s)

    flush()

    title = meta.get("title", "").strip() or "Picture Book"
    level = meta.get("level", "").strip()
    book_number = meta.get("book", "").strip()
    cefr = meta.get("cefr", "").strip()
    lexile = meta.get("lexile", "").strip()
    word_count_override = meta.get("wordcount", "").strip()
    ip_age_raw = meta.get("ipage", "").strip()
    ip_age = int(ip_age_raw) if ip_age_raw.isdigit() else None

    voc_simple = _split_words(meta.get("vocabulary", ""))
    voc_mastery = _split_words(meta.get("vocabularymastery", ""))
    voc_exposure = _split_words(meta.get("vocabularyexposure", ""))

    phonics = meta.get("phonics", "").strip()
    grammar_focus = (
        meta.get("grammarfocus", "").strip() or meta.get("grammar", "").strip()
    )
    reader_type = meta.get("readertype", "").strip()
    lesson_time = meta.get("lessontime", "").strip() or "60 mins"
    theme = meta.get("theme", "").strip()

    # 角色别名：解析 "anna=mia, kevin=tommy" 形式
    aliases = _parse_aliases(meta.get("aliases", ""))

    # 自定义独立角色：解析所有 custom_<name> 字段
    custom_characters: dict[str, str] = {}
    for k, v in meta.items():
        if k.startswith("custom_") and v.strip():
            name = k[len("custom_"):]  # "anna"
            custom_characters[name] = v.strip()

    # 整理 pages：始终 1 cover + 7 story
    pages = _normalize_pages(pages_raw, title)

    book = BookOutline(
        title=title,
        pages=pages,
        level=level,
        book_number=book_number,
        cefr=cefr,
        lexile=lexile,
        lexile_source=("manual" if lexile else ""),  # 块11：大纲头里手填即视为人工有依据
        word_count_override=word_count_override,
        ip_age=ip_age,
        vocabulary_mastery=voc_mastery,
        vocabulary_exposure=voc_exposure,
        vocabulary_simple=voc_simple,
        phonics=phonics,
        grammar_focus=grammar_focus,
        reader_type=reader_type,
        lesson_time=lesson_time,
        theme=theme,
        aliases=aliases,
        custom_characters=custom_characters,
    )
    book.validate()
    return book


def _split_words(s: str) -> list[str]:
    if not s:
        return []
    parts = re.split(r"[,，、;；/]+", s)
    return [p.strip() for p in parts if p.strip()]


def _parse_aliases(s: str) -> dict[str, str]:
    """解析 'anna=mia, kevin=tommy' 形式的别名映射。
    只接受 mia/tommy 作为目标 IP。"""
    if not s:
        return {}
    out: dict[str, str] = {}
    for pair in re.split(r"[,，;；]+", s):
        pair = pair.strip()
        if "=" not in pair:
            continue
        alias, target = pair.split("=", 1)
        alias = alias.strip().lower()
        target = target.strip().lower()
        if alias and target in ("mia", "tommy"):
            out[alias] = target
    return out


_DEFAULT_CORNERS = [
    "top-left", "bottom-right", "top-right", "top-right",
    "top-right", "top-left", "top-right",
]


_VALID_ANGLES = ("eye", "high", "low", "birdseye", "over_shoulder", "")


def _norm_angle(raw: str) -> str:
    a = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    # 常见同义词归一
    alias = {
        "level": "eye", "eye_level": "eye", "front": "eye", "straight": "eye",
        "overhead": "birdseye", "top_down": "birdseye", "top": "birdseye", "aerial": "birdseye",
        "high_angle": "high", "looking_down": "high",
        "low_angle": "low", "looking_up": "low", "worms_eye": "low",
        "over_the_shoulder": "over_shoulder", "ots": "over_shoulder", "pov": "over_shoulder",
    }
    a = alias.get(a, a)
    return a if a in _VALID_ANGLES else ""


def _normalize_pages(raw: list[dict], title: str) -> list[PageSpec]:
    cover_scene = ""
    cover_text = title
    cover_shot = ""
    cover_angle = ""
    cover_hook = ""
    story: list[dict] = []

    for blk in raw:
        if blk["kind"] == "cover":
            cover_text = blk.get("text") or title
            cover_scene = blk.get("scene") or "Mia and Tommy on cover, friendly cover composition"
            cover_shot = (blk.get("shot") or "").strip().lower()
            if cover_shot not in ("close", "medium", "full", "wide", ""):
                cover_shot = ""
            cover_angle = _norm_angle(blk.get("camera_angle", ""))
            cover_hook = (blk.get("hook") or "").strip()
        else:
            story.append(blk)

    story.sort(key=lambda b: b.get("index", 0))
    if len(story) > 7:
        story = story[:7]
    while len(story) < 7:
        story.append({"kind": "story", "index": len(story) + 1, "text": "", "scene": ""})

    pages: list[PageSpec] = [
        PageSpec(
            index=0, page_type="cover", text=cover_text, scene=cover_scene, shot=cover_shot,
            camera_angle=cover_angle, hook=cover_hook,
        ),
    ]
    for i, blk in enumerate(story, start=1):
        corner = (blk.get("text_corner") or _DEFAULT_CORNERS[i - 1]).strip()
        if corner not in ("top-left", "top-right", "bottom-left", "bottom-right"):
            corner = _DEFAULT_CORNERS[i - 1]
        shot_raw = (blk.get("shot") or "").strip().lower()
        if shot_raw not in ("close", "medium", "full", "wide", ""):
            shot_raw = ""
        pages.append(
            PageSpec(
                index=i,
                page_type="story",
                text=blk.get("text", "").strip(),
                scene=blk.get("scene", "").strip() or blk.get("text", "")[:120],
                text_corner=corner,
                expression=blk.get("expression", "").strip(),
                shot=shot_raw,
                camera_angle=_norm_angle(blk.get("camera_angle", "")),
                hook=(blk.get("hook") or "").strip(),
            )
        )
    return pages


# ---------- 官方 S&S 大纲注入 ----------
def enrich_from_syllabus(outline: BookOutline) -> bool:
    """用官方 S&S 大纲（references/syllabus）补强 outline。

    命中时把权威的 Reading Strategy / Skill / GO 写入 outline，并仅在 outline
    对应字段为空时回填 cefr/lexile/word_count/phonics/theme/fiction_type/vocab。
    把整条 SyllabusEntry 挂在 outline.syllabus 上供 teacher_guide_builder 取用。

    返回 True 表示命中（注入了真值），False 表示未命中（调用方维持现有启发式）。
    """
    # 官方每课出图 Prompt（独立检索，按 level+title；与 S&S 命中无关）
    try:
        from image_prompts import match as _img_match
        oip = _img_match(outline.level, outline.title)
        if oip is not None:
            outline.official_image_prompt = oip
    except Exception:
        pass

    try:
        from syllabus import match as _match
    except Exception:
        return False

    entry = _match(outline.level, outline.title)
    if entry is None:
        return False

    outline.syllabus = entry
    if entry.reading_strategy:
        outline.reading_strategy = entry.reading_strategy
    if entry.reading_skill:
        outline.reading_skill = entry.reading_skill
    if entry.graphic_organizer:
        outline.graphic_organizer = entry.graphic_organizer
    if entry.go_description:
        outline.graphic_organizer_desc = entry.go_description

    # 仅在 outline 缺失时回填（不覆盖用户大纲里的显式值）
    if not outline.cefr and entry.cefr:
        outline.cefr = entry.cefr
    if not outline.lexile and entry.lexile:
        outline.lexile = entry.lexile
        outline.lexile_source = "syllabus"   # 块11：大纲官方值（有依据）
    if not outline.word_count_override and entry.word_count:
        outline.word_count_override = entry.word_count
    if not outline.phonics and entry.phonics_rule:
        outline.phonics = entry.phonics_rule
    if not outline.fiction_type and entry.genre in ("fiction", "nonfiction"):
        outline.fiction_type = "non-fiction" if entry.genre == "nonfiction" else "fiction"

    # 词汇/拼读【权威逐字覆盖】（用户拍板 2026-06-08）：命中大纲时，词形以大纲为准 verbatim，
    #   覆盖 AI 抽取的词表与拼读规则（释义无官方源时保留下游 _KID_DICT/AI def，仅词形 verbatim）。
    if outline.is_dual_vocab_level:
        # L0-2：分别覆盖 Mastery / Exposure（大纲有才覆盖，避免清空）
        if entry.vocab_mastery:
            outline.vocabulary_mastery = list(entry.vocab_mastery)
        if entry.vocab_exposure:
            outline.vocabulary_exposure = list(entry.vocab_exposure)
        if not (entry.vocab_mastery or entry.vocab_exposure):
            words = entry.vocab_words()
            if words and not outline.vocabulary_simple:
                outline.vocabulary_simple = words
    else:
        # L3-6：单行 Vocabulary —— 用大纲 core_vocab 词形 verbatim 覆盖
        words = entry.vocab_words()
        if words:
            outline.vocabulary_simple = words
    # 拼读规则：大纲有就以大纲原文为准（覆盖 AI 推断）
    if entry.phonics_rule:
        outline.phonics = entry.phonics_rule
    return True
