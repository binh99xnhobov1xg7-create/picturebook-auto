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
    r"police|officer|cop|driver|chef|cook|waiter|clerk|guard|pilot|sailor|knight|"
    r"fox|wolf|bear|bears|pig|pigs|goat|goats|cow|horse|sheep|duck|hen|rooster|"
    r"mouse|mice|rat|rabbit|bunny|hare|tortoise|turtle|lion|tiger|monkey|"
    r"elephant|frog|snake|owl|crow|bird|deer|eagle|cat|dog|goose|"
    r"giant|troll|ogre|dragon|fairy|elf|gnome|goblin|witch|robot|monster|alien|"
    r"gingerbread man|snowman)\b",
    re.I,
)
# 地名/国家/大洲/族裔/星期月份（是设定/场景/时间，绝不是角色）—— 整词匹配
_PLACE_OR_NONPERSON = re.compile(
    r"^(spain|canada|china|france|england|britain|scotland|ireland|wales|america|"
    r"usa|uk|mexico|japan|korea|india|italy|germany|spain|brazil|egypt|russia|greece|"
    r"peru|argentina|chile|colombia|bolivia|ecuador|venezuela|cuba|portugal|spain|"
    r"netherlands|belgium|sweden|norway|denmark|finland|poland|turkey|thailand|vietnam|"
    r"indonesia|philippines|malaysia|singapore|kenya|nigeria|morocco|ghana|"
    r"africa|asia|europe|antarctica|australia|oceania|"
    r"new zealand|new york|london|paris|tokyo|beijing|rome|cairo|earth|mars|moon|"
    r"spanish|english|french|chinese|canadian|american|mexican|italian|german|japanese|"
    r"peruvian|brazilian|argentine|portuguese|dutch|swedish|norwegian|polish|turkish|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)$",
    re.I,
)
# 句首常被大写的形容词/副词/泛指名词（不是专名角色）—— 整词匹配
_COMMON_NONNAME = re.compile(
    r"^(warm|cold|hot|cool|happy|sad|good|great|kind|clever|brave|gentle|quiet|loud|"
    r"always|never|often|usually|suddenly|together|finally|today|tomorrow|yesterday|"
    r"neighbor|neighbors|neighbour|neighbours|friend|friends|children|kids|people|"
    r"everyone|everybody|someone|somebody|nobody|family|families|class|team|group|"
    r"morning|afternoon|evening|night|summer|winter|spring|autumn|fall|"
    r"hello|goodbye|thanks|please|yes|no|okay|sure|maybe|because|while|during|"
    # 非角色噪声词（活动名/问句词等）：Safety(来自"Safety Day")、How/What/Why… 句首问句词，
    #   误判会生成 role_safety.png / role_how.png 这类垃圾一次性角色。
    r"safety|safe|day|days|how|what|why|when|where|who|whom|whose|which|whatever|"
    r"rule|rules|tip|tips|lesson|lessons|fun|nice|new|old|big|small|happy|"
    # 动名词/动作词、数量词（句首大写被误当人名）：Playing/Try/Cleaning/Several…
    r"playing|play|plays|try|tries|trying|cleaning|clean|cleans|helping|sharing|caring|"
    r"join|joins|joining|joined|teamwork|teams|sideline|sidelines|cheering|cheered|"
    r"several|many|much|few|lots|some|most|both|each|every|all|none|more|less|"
    # 场所/概念名词（非虚构书名常大写，绝不是角色）：Libraries/Museums/Sports…
    r"library|libraries|museum|museums|sport|sports|game|games|exercise|exercises|"
    r"park|parks|school|schools|store|stores|shop|shops|hospital|hospitals|"
    r"neighborhood|neighbourhood|community|communities|nature|world|earth)$",
    re.I,
)


# 剧情狗（如 Book63 走失小狗 Buddy）全书唯一形象锁——与家养柯基 Max 彻底区分。
#   家养柯基 Max 仅在正文显式点名 "Max" 时出现；其它走失/泛指小狗一律按本锁画，严禁画成柯基/Max。
STORY_DOG_LOCK_CN = (
    "【本书走失小狗·全书唯一形象锁】这只剧情宠物狗（不是家养柯基 Max）："
    "小型杏奶油色（apricot-cream）蓬松波浪卷毛混血犬，膝盖高，圆脸、黑色小鼻头，深褐色温柔圆眼，"
    "中等大小【半垂耳】（绝不是柯基的立耳），短腿圆润；脖子永远系【鲜明红色项圈 + 一枚小圆金色吊牌】；"
    "性格友善乖巧、略带怯生；治愈系水彩儿童绘本画风；全书每次出现（手机照片里/树后探头/被女孩抱住）"
    "都必须是同一只狗：同毛色、同半垂耳型、同红项圈金吊牌，严禁画成柯基/Max、严禁立耳、严禁换毛色或项圈颜色。"
)
STORY_DOG_LOCK_EN = (
    "the lost story dog (NOT Max, NOT a corgi): a small apricot-cream fluffy wavy-curly mixed-breed dog, "
    "knee-high, round face, small black nose, gentle dark-brown round eyes, medium SEMI-FLOPPY ears (never upright corgi ears), "
    "short rounded legs; always wears a bright RED collar with a small round GOLD tag; "
    "friendly, gentle, slightly timid; watercolor children's-book style; same dog every time."
)

# 把一个 token 在【该书全文】里判定为剧情狗的上下文线索（命中即把该角色标为 species="dog"）。
_STORY_DOG_CTX_RE = re.compile(
    r"\b(lost\s+dog|small\s+dog|little\s+dog|her\s+dog|his\s+dog|the\s+dog|a\s+dog|stray\s+dog|"
    r"puppy|doggy|red\s+collar|behind\s+a\s+tree|find\s+it|found\s+the\s+dog)\b|"
    r"走失|走丢|丢失|小狗|狗狗|红色?项圈|树后", re.I)


def _detect_story_dog_names(text: str) -> set[str]:
    """从全文里找剧情狗的专名（如 Buddy），用于把对应一次性角色标为 species="dog"。

    命中模式："dog/puppy named/called X"、"X, the dog/puppy"、"her/his/the dog/puppy X"、
    "小狗X"、"X 这只(小)狗"等；返回小写名字集合。
    """
    names: set[str] = set()
    t = text or ""
    for m in re.finditer(r"\b(?:dog|puppy)\s+(?:named|called)\s+([A-Z][a-z]+)\b", t, re.I):
        names.add(m.group(1).lower())
    for m in re.finditer(r"\b([A-Z][a-z]+)\s*,?\s+(?:the|her|his|a)\s+(?:dog|puppy)\b", t, re.I):
        names.add(m.group(1).lower())
    for m in re.finditer(r"\b(?:her|his|the|a)\s+(?:dog|puppy)\s+(?:named\s+|called\s+)?([A-Z][a-z]+)\b", t, re.I):
        names.add(m.group(1).lower())
    for m in re.finditer(r"小狗\s*([A-Z][a-z]+)|([A-Z][a-z]+)\s*这只小?狗", t):
        nm = m.group(1) or m.group(2)
        if nm:
            names.add(nm.lower())
    return names


# 泛指儿童词（无专名）——不登记为一次性角色（交给配角配色轮+多元化处理）。
_GENERIC_CHILD = {
    "boy", "girl", "kid", "kids", "child", "children", "boys", "girls",
    "little boy", "little girl", "young boy", "young girl", "small boy", "small girl",
    "男孩", "女孩", "孩子", "小孩", "小男孩", "小女孩",
}


@dataclass
class OneOffRole:
    rid: str                       # 归一 id，如 "goldilocks" / "fox" / "officer"
    display: str                   # 展示名，如 "Goldilocks" / "the fox" / "Officer Buckle"
    desc_en: str                   # 锁定外观（取自官方最丰富的一次提及，英文短语）
    page_indexes: list[int] = field(default_factory=list)
    anchor_path: str | None = None  # 书内定妆锚图（生成后回填）
    aliases: set[str] = field(default_factory=set)  # 别名（如 Officer Buckle 的裸名 "buckle"），供本页命中
    species: str = "human"          # "human" / "dog" / "animal"——动物走犬种/物种锁，不套人类儿童反克隆锁

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
    t = re.sub(r"\s+", " ", t).strip()
    return t


# 警察家族同义词 → 统一稳定 rid "officer"（Book63 根因：the officer / a police officer /
#   Officer Buckle 之前各自归一成不同 rid，导致锚与外观锁逐页错配/漏注入）。
_POLICE_RE = re.compile(r"\b(police\s*officer|police|officer|policeman|policewoman|cop)\b", re.I)


def _canon_rid(rid: str) -> tuple[str, set[str]]:
    """把双词职业专名/同义词归一到稳定 rid，返回 (canonical_rid, 别名集合)。

    目前覆盖【警察家族】(officer/police/cop/police officer/Officer Buckle…) → "officer"，
    并把 "officer buckle" 的裸名 "buckle" 作为别名，使 the officer / a police officer /
    Officer Buckle / Buckle 全部命中同一锚。其它角色保持原 rid 不变（避免误并不同人）。
    """
    low = re.sub(r"\s+", " ", (rid or "").strip().lower())
    aliases: set[str] = set()
    if _POLICE_RE.search(low):
        m = re.match(r"(?:police\s+)?officer\s+([a-z]+)$", low)  # Officer Buckle → 别名 buckle
        if m:
            aliases.add(m.group(1))
        return "officer", aliases
    return low, aliases


# 成人/职业类一次性角色（用于给锚图加"成年人/身高"锁，避免把成人画成小孩）。
#   关键：职业名必须同时匹配【单复数】（firefighter / Firefighters / Officers / Doctors…），
#   否则复数大写词会漏过成人判定、被后面"单词专名→儿童"兜底误锁成 10 岁儿童（Book66 根因）。
_ADULT_ROLE_RE = re.compile(
    r"\b(officers?|police|policeman|policewoman|policemen|policewomen|cops?|"
    r"firefighters?|firemen|fireman|"
    r"postmen|postman|mailmen|mailman|mail ?carriers?|doctors?|nurses?|farmers?|teachers?|bakers?|"
    r"chefs?|cooks?|waiters?|waitress(?:es)?|drivers?|pilots?|sailors?|guards?|clerks?|shopkeepers?|"
    r"vendors?|grocers?|captains?|sergeants?|mayors?|kings?|queens?|princes?|princess(?:es)?|knights?|"
    r"volunteers?|cleaners?|workers?|helpers?|visitors?|librarians?|curators?|gardeners?|painters?|"
    r"man|woman|men|women|lady|ladies|gentleman|gentlemen|adults?|grandpa|grandma|grandmother|grandfather|"
    r"警察|警官|消防员|邮递员|医生|护士|农夫|农民|司机|店员|厨师|面包师|志愿者|清洁工|工人|管理员|讲解员|馆员|"
    r"老师|队长|国王|王后|王子|公主|大人|成年|叔叔|阿姨)\b",
    re.I,
)


def is_adult_role(role: "OneOffRole") -> bool:
    """该一次性角色是否为【成人/职业类】（决定锚图是否加成人锁、是否避开儿童风格参考）。"""
    blob = " ".join([role.rid or "", role.display or "", role.desc_en or ""])
    return bool(_ADULT_ROLE_RE.search(blob))


# 动物类一次性角色（fox/rabbit…）——不适用"国际化儿童/不撞主角"这套人类儿童锁。
_ANIMAL_RE = re.compile(
    r"\b(fox|wolf|bear|bears|pig|pigs|goat|goats|cow|cows|horse|horses|sheep|duck|ducks|"
    r"hen|hens|rooster|mouse|mice|rat|rats|rabbit|rabbits|bunny|hare|tortoise|turtle|"
    r"lion|tiger|monkey|elephant|frog|snake|owl|crow|bird|birds|deer|eagle|cat|cats|"
    r"dog|dogs|goose|geese|dragon|dino|dinosaur|fish|bee|bees|ant|ants|spider|butterfly|"
    r"puppy|kitten|pony|squirrel|hedgehog|panda|koala|kangaroo|penguin|whale|dolphin)\b",
    re.I,
)
# 命名儿童线索（同学/朋友/队友等）——决定是否给"全新国际化、不撞主角"锁。
_CHILD_HINT_RE = re.compile(
    r"\b(boy|girl|kid|kids|child|children|classmate|classmates|friend|friends|"
    r"teammate|teammates|student|students|pupil|pupils|"
    r"男孩|女孩|孩子|小孩|同学|朋友|队友|学生)\b",
    re.I,
)


def is_animal_role(role: "OneOffRole") -> bool:
    """该一次性角色是否为【动物】（剧情狗/狐狸/兔子…）。

    动物走【物种/犬种外观锁】，绝不套"国际化儿童反克隆"那套人类锁，也不拟人成小孩。
    判定：显式 species 标记（如剧情狗 Buddy）优先，其次按 rid/display/desc 命中动物名词。
    """
    if getattr(role, "species", "human") != "human":
        return True
    blob = " ".join([role.rid or "", role.display or "", role.desc_en or ""])
    return bool(_ANIMAL_RE.search(blob))


def is_story_dog_role(role: "OneOffRole") -> bool:
    """该一次性角色是否为【本书剧情狗】（如 Book63 走失小狗 Buddy）——输出 Buddy 犬种锁、严禁画成 Max/柯基。"""
    if getattr(role, "species", "human") == "dog":
        return True
    blob = " ".join([role.rid or "", role.display or "", role.desc_en or ""]).lower()
    return bool(re.search(r"\b(dog|puppy|doggy)\b|小狗|犬", blob))


def is_child_human_role(role: "OneOffRole") -> bool:
    """该一次性角色是否为【人类儿童】（命名同学/朋友/队友/玩伴等）。

    这类角色需要在锚图与页面 prompt 里加【全新独立·国际化·绝不撞主角(Mia/Tommy)】锁，
    根治"命名儿童(如 Ben)被画成 Tommy 12 岁翻版"。成人、动物不适用。
    """
    if is_adult_role(role):
        return False
    if getattr(role, "species", "human") != "human":
        return False
    blob = " ".join([role.rid or "", role.display or "", role.desc_en or ""])
    if _ANIMAL_RE.search(blob):
        return False
    if _CHILD_HINT_RE.search(blob):
        return True
    # 单词专有人名（Ben/Ravi/Sasha/Goldilocks…，非动物、非成人）→ 绘本里默认为儿童角色。
    disp = (role.display or "").strip().strip("*").rstrip(":").strip()
    disp = re.sub(r"\(.*?\)", "", disp).strip()
    if disp and " " not in disp and disp[:1].isupper():
        return True
    return False


# 配角确定性配色（避开主角专属：紫=Mia / 蓝=Tommy / 绿=Anna / 粉=Cate；绝不含蓝/紫）。
_ONEOFF_CHILD_COLORS = ["橙色", "红色", "黄色", "草绿色", "米色", "棕色", "青绿色"]


def oneoff_child_color(rid: str) -> str:
    """按 rid 确定性指派一个【非蓝非紫】服装色——锚图与页面 prompt 共用，保证全书一致。"""
    h = sum(ord(c) for c in (rid or "x"))
    return _ONEOFF_CHILD_COLORS[h % len(_ONEOFF_CHILD_COLORS)]


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
    # 地名/国家/族裔/时间词 与 句首形容词/泛指名词 → 不是角色（修 Spain/Canada/Warm/Neighbors 误判）
    if _PLACE_OR_NONPERSON.match(low) or _COMMON_NONNAME.match(low):
        return False
    if low in _IP_NAMES:
        return False
    # 泛指儿童词（无专名）：boy/girl/kid/child/孩子/男孩/女孩…不登记为一次性角色——
    #   避免生成 role_boy.png 这种泛指锚（再被主角三人组带成 Tommy 克隆）；泛指儿童交给
    #   cn_prompt_builder 的"配角确定性配色轮 + 多元化"处理。有专名的角色(如 Ben)仍照常登记。
    if low in _GENERIC_CHILD:
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
    "safety", "safe", "day", "how", "what", "why", "where", "who", "whose",
    "which", "rule", "rules", "tip", "tips", "lesson", "fun",
    "playing", "play", "try", "cleaning", "clean", "helping", "sharing",
    "join", "joins", "joining", "joined", "teamwork", "team", "teams",
    "sideline", "sidelines", "cheering", "cheered",
    "several", "many", "some", "most", "both", "each", "every", "more", "less",
    "library", "libraries", "museum", "museums", "sport", "sports",
    "game", "games", "park", "school", "store", "shop", "hospital",
    "neighborhood", "community", "nature",
}


_TITLE_PREFIX = re.compile(
    r"\b(mr|mrs|ms|miss|dr|sir|lady|aunt|uncle|captain|officer|farmer|king|queen|"
    r"prince|princess|grandpa|grandma|teacher)\.?\s+([A-Z][a-z]+)", re.I)


def _confirmed_proper_nouns(text: str) -> set[str]:
    """收集"确凿专名"：在句中（非句首）出现的大写词，或紧跟称谓(Mr./Farmer…)的大写词。

    句首单词天然大写，单凭句首大写无法判定是人名（如 'Warm hugs…' / 'Always be kind'）；
    只有当同一个词也在句中大写出现、或带称谓时，才认定为真正的专有名词/人名。
    """
    confirmed: set[str] = set()
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        words = sent.split()
        for i, w in enumerate(words):
            clean = re.sub(r"[^A-Za-z]", "", w)
            if i == 0 or len(clean) < 3:
                continue  # 跳过句首词（天然大写，不作数）
            if clean[:1].isupper() and clean[1:].islower():
                confirmed.add(clean.lower())
    for m in _TITLE_PREFIX.finditer(text or ""):
        confirmed.add(m.group(2).lower())
    return confirmed


def _plain_text_tokens(text: str, confirmed: set[str] | None = None) -> list[str]:
    """无官方 prompt 时，从故事正文里抓候选角色词。

    收紧（2026-06-08）：单个大写词必须是"确凿专名"（句中大写出现过或带称谓），
    杜绝把句首形容词/副词（Warm/Always…）误当人名。双词 'Farmer Tom' 仍保留。

    confirmed: 全书级别的"确凿专名"集合（建议由 build_book_cast 预先按整本算好后传入）。
      —— 主角名（如 Lina）常出现在句首，单看一页会漏判；用全书集合可避免该漏判。
    """
    toks: list[str] = []
    if confirmed is None:
        confirmed = _confirmed_proper_nouns(text)
    # "Farmer Tom" / "Clever Crow" 等 形容词/职业+大写名（双词强信号，保留）
    for m in re.finditer(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", text or ""):
        cand = m.group(1)
        if cand.lower() in _PLAIN_STOP or _PLACE_OR_NONPERSON.match(cand.lower()):
            continue
        toks.append(cand)
    # 单个大写专名：必须是"确凿专名"才收（句首孤立大写词不收）
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\b", text or ""):
        cand = m.group(1)
        low = cand.lower()
        if low in _PLAIN_STOP or low not in confirmed:
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

    # 纯文本模式：先按【整本书】算一次"确凿专名"集合，避免句首出现的主角名（如 Lina）被逐页漏判。
    book_confirmed: set[str] = set()
    whole = " ".join(
        (p.text or "") + " " + (getattr(p, "scene", "") or "") + " "
        + (getattr(p, "scene_cn", "") or "") for p in outline.pages
    )
    if use_official and oip is not None:
        try:
            whole += " " + " ".join(oip.page_scene(p.index) or "" for p in outline.pages)
        except Exception:
            pass
    if not use_official:
        book_confirmed = _confirmed_proper_nouns(whole)

    # 剧情狗专名（如 Book63 的 Buddy）+ 是否有剧情狗上下文——用于把对应一次性角色标为 species="dog"，
    #   走 Buddy 犬种锁、严禁画成家养柯基 Max。
    _dog_names = _detect_story_dog_names(whole)
    _has_dog_ctx = bool(_STORY_DOG_CTX_RE.search(whole))

    for page in outline.pages:
        if use_official:
            try:
                raw = oip.page_scene(page.index) or ""
            except Exception:
                raw = ""
            pos = _official_positive(raw)
            tokens = _bold_tokens(pos)
        else:
            pos = ((page.text or "") + " " + (getattr(page, "scene", "") or "") + " "
                   + (getattr(page, "scene_cn", "") or ""))
            tokens = _plain_text_tokens(pos, confirmed=book_confirmed)
        if not pos:
            continue
        seen_on_page: set[str] = set()
        for tok in tokens:
            if not _is_character_token(tok):
                continue
            rid = _norm_rid(tok)
            rid, aliases = _canon_rid(rid)                 # 双词职业专名归一（Officer Buckle→officer）
            if not rid or rid in _IP_NAMES or rid in seen_on_page:
                continue
            seen_on_page.add(rid)
            r = roles.get(rid)
            if r is None:
                if rid in {"dog", "puppy", "doggy"} or rid in _dog_names:
                    _species = "dog"
                elif _ANIMAL_RE.search(rid):
                    _species = "animal"
                else:
                    _species = "human"
                r = OneOffRole(rid=rid, display=tok.strip().strip("*").rstrip(":").strip(),
                               desc_en=_extract_desc(pos, tok), species=_species)
                roles[rid] = r
            # 已登记角色若后续确认是剧情狗（专名出现在 dog 上下文），补标 species。
            if r.species == "human" and (rid in {"dog", "puppy", "doggy"} or rid in _dog_names):
                r.species = "dog"
            r.aliases |= aliases
            if page.index not in r.page_indexes:
                r.page_indexes.append(page.index)
            cand = _extract_desc(pos, tok)
            if len(cand) > len(r.desc_en):
                r.desc_en = cand

    # 合并"裸名"角色：若某 rid 恰是另一角色的别名（如 "Buckle" ↔ "officer"），
    #   把它并入规范角色，避免同一个人被登记成两个一次性角色（officer + buckle）。
    alias_to_canon: dict[str, str] = {}
    for r in roles.values():
        for a in r.aliases:
            alias_to_canon.setdefault(a, r.rid)
    for rid in list(roles.keys()):
        canon = alias_to_canon.get(rid)
        if canon and canon != rid and canon in roles:
            tgt, dup = roles[canon], roles[rid]
            for pi in dup.page_indexes:
                if pi not in tgt.page_indexes:
                    tgt.page_indexes.append(pi)
            tgt.page_indexes.sort()
            if len(dup.desc_en) > len(tgt.desc_en):
                tgt.desc_en = dup.desc_en
            tgt.aliases |= dup.aliases
            del roles[rid]
    return roles


# 仅保留【稳定外观属性】的关键词（年龄/身高/发型/肤色/服装/配饰），用于把混进角色
#   外观锁里的【一次性场景/动作/情节小句】剔除掉。
# Book63 根因：命名角色（Officer Buckle）的外观锁里被塞进整段场景描述
#   （"一位着急的居民正举着手机给警官看走丢小狗的照片…"），随该角色 anchor/每页 prompt
#   复述、压过各页自身剧情。外观锁只应描述【长期外观】，绝不含某一页的情节/动作/其它人物。
# 注意：只认【强外观属性词】（发型/服装/年龄数字/身高体格/五官配饰），不认裸"男孩/女孩/man/woman"
#   等纯人称名词或裸颜色词——否则像"一个小女孩飞奔抱住小狗"这类情节小句会被误当外观保留。
# 关键：只认【具体物理/服装属性】（发型/五官/肤色/具体服装/头身比例/显式年龄数字），
#   绝不认【年龄形容词】(年轻/中年/成年/old…) 与【性别/人称泛称】(男人/女人/女士/man/woman…)。
#   后两类会出现在情节小句里（如"一位焦急的年轻女士站在…比划着说话"），若保留它们就会把
#   整段场景当外观锁——这正是 Book63 P1/P6/P7 跑偏的根因。角色的年龄/成人身份由
#   _apply_book_cast 的【成人/儿童类型锁】单独注入，无需经由 desc。
_APPEARANCE_KEEP_RE = re.compile(
    r"("
    # —— 显式年龄数字（具体，安全；非"年轻/老"这类泛词）——
    r"\d+\s*岁|\byears?\s*old\b|"
    # —— 头发 ——
    r"头发|发型|短发|长发|卷发|直发|盘发|马尾|辫子|麻花辫|刘海|光头|秃顶|"
    r"金发|红发|棕发|黑发|白发|银发|灰发|栗色|"
    r"\bhair\b|\bbald\b|\bblonde?\b|\bbrunette\b|\bcurly\b|\bbrown-haired\b|\bgrey-haired\b|\bgray-haired\b|"
    # —— 面部 / 肤色 / 配饰 ——
    r"胡子|胡须|络腮|眼镜|雀斑|肤色|皮肤|黝黑|白皙|小麦色|"
    r"\bbeard\b|\bmoustache\b|\bmustache\b|\bglasses\b|\bfreckles?\b|\bskin\b|\bcomplexion\b|"
    # —— 身高 / 体型（仅不歧义的比例词 + 明确物理体格）——
    r"头身|身高|\btall\b|\bslim\b|\bstocky\b|\bmuscular\b|"
    # —— 服装 / 配饰 ——
    r"上衣|卫衣|衬衫|衬衣|T恤|外套|大衣|夹克|毛衣|马甲|背心|连衣裙|裙子|裙|裤子|裤|短裤|"
    r"帽子|鸭舌帽|头巾|围裙|围巾|披风|斗篷|制服|警服|工装|背带裤|领带|领结|"
    r"徽章|肩章|腰带|手套|靴子|皮鞋|运动鞋|球鞋|西装|长袍|"
    r"\bwears?\b|\bwearing\b|\bdressed\b|\bdress\b|\bshirt\b|\bt-?shirt\b|\bcoat\b|\bjacket\b|"
    r"\bsweater\b|\bhoodie\b|\bvest\b|\bskirt\b|\bpants\b|\btrousers\b|\bshorts\b|"
    r"\bhat\b|\bcap\b|\bbeanie\b|\bscarf\b|\bapron\b|\bcape\b|\bcloak\b|\brobe\b|\bgown\b|"
    r"\bsuit\b|\buniform\b|\boveralls\b|\bdungarees\b|\bboots?\b|\bshoes?\b|\bsneakers\b|"
    r"\btie\b|\bbadge\b|\bgloves?\b"
    r")",
    re.I,
)


# 动作 / 场景 / 情绪词（小句若命中即【判为情节】，一律剔除，哪怕它也含外观词）。
#   作用：① 兜底中文分词边界误命中（如"抬头发问"被"头发"误中→含"抬/发问"→剔除）；
#         ② 剔除"穿外观词的情节句"（如英文"...discovers a small dog wearing a red collar"含动作）。
#   只列【动作/方位/场景/情绪】，绝不含服装/发型/五官等外观词，避免误杀真外观小句。
_PLOT_DROP_RE = re.compile(
    r"("
    # —— 中文：动作 / 姿态 ——
    r"站|坐|走|跑|跳|蹲|跪|趴|躺|抱|举|抬|指|望|瞧|盯|凝视|注视|问|发问|说|喊|叫|哭|"
    r"拿|递|拨|找|寻|搜|奔|挥|招手|踮|俯|弯腰|转身|回头|点头|摇头|伸手|张开|比划|"
    r"带头|迈步|赶来|走向|凑|靠近|倾听|聆听|发现|"
    # —— 中文：方位 / 场景 / 时间 / 情绪（情节语境）——
    r"面前|身边|旁边|不远|远处|场地|广场|公园|横幅|气球|手机|照片|项圈|狗绳|公告|"
    r"长椅|草地|树后|树下|阳光|午后|傍晚|黄昏|早晨|清晨|微微|轻轻|开心|惊喜|焦急|"
    r"着急|担心|兴奋|好奇|"
    # —— English：动作 / 方位 ——
    r"\bwalk|\bwalked\b|\bran\b|\bruns?\b|\bstand|\bstood\b|\bsits?\b|\bsat\b|\bkneel|\bknelt\b|"
    r"\bjump|\blean|\bbend|\bbent\b|\bhold|\bheld\b|\blook|\bpoint|\basks?\b|\basked\b|"
    r"\bsays?\b|\bsaid\b|\bfinds?\b|\bfound\b|\bdiscover|\breach|\brush|\bhug|\bwave|"
    r"\bbehind\b|\bin front\b|\bbeside\b|\bnext to\b"
    r")",
    re.I,
)


def _appearance_only(sentence: str) -> str:
    """把一句话按中英标点切成小句，只保留【含具体外观词且不含动作/场景词】的小句。

    双重判定（缺一不可）：
      ① 命中 _APPEARANCE_KEEP_RE（含发型/五官/肤色/服装/头身/显式年龄等具体外观属性）；
      ② 不命中 _PLOT_DROP_RE（不含动作/姿态/方位/场景/情绪等情节词）。
    若整句都是情节（无纯外观小句）则返回 ""，此时角色形象由【角色类型锁(成人/儿童)+
    书内定妆锚图】承担，各页剧情由该页 scene 决定，不再被某一页情节跨页复述污染。
    """
    if not sentence:
        return ""
    parts = re.split(r"[，,、；;。.!?！？\n]+", sentence)
    kept = [p.strip() for p in parts
            if p.strip() and _APPEARANCE_KEEP_RE.search(p) and not _PLOT_DROP_RE.search(p)]
    return "，".join(kept).strip()


def _extract_desc(pos: str, token: str) -> str:
    """取文本里包含该角色的句子，但【只保留稳定外观属性】作为外观锁定描述（去 markdown、限长）。

    根治 Book63 根因：不再把整句场景/情节当外观锁（否则某一页剧情会随该角色每页复述、
    压过各页本身的 scene）。命名角色的长期外观（年龄/发型/服装/配饰…）才进锁，
    一次性情节（谁在做什么/举手机/丢狗/横幅…）一律剔除。
    """
    plain = pos.replace("**", "")
    name = re.sub(r"\(.*?\)", "", token).strip().strip("*")
    best = ""
    for sent in re.split(r"(?<=[.!?])\s+", plain):
        if name and name.lower() in sent.lower():
            appearance = _appearance_only(sent)
            if len(appearance) > len(best):
                best = appearance
    return best[:240]


def anchor_prompt(role: OneOffRole) -> str:
    """为一次性角色生成【书内定妆锚图】的 prompt（白底单人，治愈水彩，友善可爱）。"""
    desc = (role.desc_en or "").strip()
    who = role.display.strip()
    # 成人/职业类角色显式加成人锁——否则模型常把"警察/医生/农夫"画成穿制服的小孩。
    adult_lock = ""
    if is_adult_role(role):
        adult_lock = (
            "【这是一位成年人】成熟的成年人脸庞与成人身材比例，明显高于 10 岁儿童、约为儿童身高的 4:3，"
            "成人头身比（约 7-7.5 头身）、成熟体格；绝不能画成小孩、儿童、幼儿或青少年/teenager。"
        )
    # 动物角色（剧情狗 Buddy / 狐狸…）：走物种/犬种外观锁，绝不套人类儿童反克隆锁、不拟人成小孩。
    animal_lock = ""
    if is_animal_role(role):
        if is_story_dog_role(role):
            animal_lock = STORY_DOG_LOCK_CN + "（这是一只【狗】，不是人类小孩，绝不拟人化、不穿人类衣服。）"
        else:
            animal_lock = ("【这是一只动物】请按它的真实物种外观绘制（四足、该物种的体型/毛色/耳型/尾巴），"
                           "绝不拟人化为人类儿童、不穿人类服装、不直立行走。")
    # 人类儿童命名角色（如 Ben）：强制【全新独立·国际化·反克隆主角】——根治被画成 Tommy 翻版。
    child_lock = ""
    if (not animal_lock) and is_child_human_role(role):
        color = oneoff_child_color(role.rid)
        child_lock = (
            "【这是一个全新独立的儿童角色】是与系列主角 Mia、Tommy 完全不同的另一个孩子，"
            "明确为 10 岁学龄儿童（小学生）的身材比例——约 5.5-6 头身、四肢与身形都是 10 岁孩子的样子，"
            "绝不画成五六岁低龄幼儿/胖娃娃/Q 版大头娃娃，也绝不画成 12 岁/青少年/成人；"
            "严格使用与本书完全一致的治愈系手绘水彩儿童绘本画风（柔和线条、通透水彩、统一质感），"
            "绝不跑成 3D/写实照片/厚涂或其它风格；"
            "外貌国际化、可外籍——鼓励多元长相（金发/红发/卷发/深色卷发、浅肤或深肤、雀斑、不同脸型五官皆可），"
            "务必与 Tommy 截然不同：绝不撞 Tommy 的脸、绝不是棕色蓬松短发同款发型、也绝不撞 Mia 的脸与发型；"
            f"上衣用【{color}】，绝不穿蓝色(蓝=Tommy 专属)、绝不穿紫色(紫=Mia 专属)。"
        )
    return (
        f"角色定妆参考图：{who}。{('外观依据：' + desc) if desc else ''} {adult_lock}{child_lock}{animal_lock}"
        "整张图只画这一个角色，单人全身居中、自然站姿、面向观众轻微侧身，纯白色背景、无任何其他人物/道具/文字。"
        "干净平滑、统一治愈系水彩儿童绘本画风，线条柔和、上色通透，"
        "角色表情友善温和、可爱亲切——绝不凶恶、不露獠牙、不阴森吓人（这是给低龄儿童看的绘本）。"
        "用于后续每一页该角色的形象锁定，请把脸型、五官、发型/毛色、肤色、服装款式与配色画清楚、明确、可复用。\n\n"
        "【负向】不要文字、不要多个角色、不要分镜/多视图排版、不要照片质感、不要恐怖/暴力/丑陋元素、不要复杂背景。"
        + ("（负向追加：不要把这个成年人画成小孩/儿童/青少年、不要儿童身材比例。）" if adult_lock else "")
        + ("（负向追加：不要把这个孩子画成 Tommy 或 Mia 的翻版/撞脸/撞发型/撞衣色，不要棕色蓬松短发配浅蓝衣，"
           "不要穿蓝色或紫色，不要画成 12 岁/青少年/成人，也不要画成五六岁低龄幼儿/胖娃娃/Q 版大头，"
           "不要跑成 3D/写实/厚涂或与本书不一致的画风。）" if child_lock else "")
        + ("（负向追加：不要画成柯基犬/Max、不要立耳、不要换毛色或换项圈颜色、不要拟人化穿衣直立、"
           "不要画成人类小孩。）" if (animal_lock and is_story_dog_role(role)) else "")
    )


def _match_roles_in(book_cast: dict[str, OneOffRole], low: str) -> list[OneOffRole]:
    """在已小写化文本里命中已登记的一次性角色（按 rid 或别名整词匹配）。"""
    out = []
    for r in book_cast.values():
        keys = [r.rid] + sorted(r.aliases)
        if any(re.search(rf"\b{re.escape(k)}\b", low) or k in low for k in keys if k):
            out.append(r)
    return out


def roles_on_page(book_cast: dict[str, OneOffRole], official_raw: str,
                  page_text: str = "") -> list[OneOffRole]:
    """本页出现了哪些已登记的一次性角色。

    优先用官方逐页画面文本匹配；当【无官方文本】或官方文本无命中时，回退用【本页正文/scene
    文本】匹配——修 Book63 这类无官方 prompt 的书：之前 official_raw 为空直接 return []，
    导致每页都不注入书内角色锚与全书外观锁。
    """
    if not book_cast:
        return []
    out: list[OneOffRole] = []
    if official_raw:
        out = _match_roles_in(book_cast, _official_positive(official_raw).lower())
    if not out and page_text:
        out = _match_roles_in(book_cast, page_text.lower())
    return out
