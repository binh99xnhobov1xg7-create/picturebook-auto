"""官方角色注册表 v1.0 — 4 件套共用的唯一权威。

任何角色（主角 / 老师 / 宠物 / 配角 / 家庭）的形象描述、参考图、年龄档
都在这里登记。prompt_builder / web_app / ai_extractor 全部从这里读，
避免分散描述导致跨页跑帧。

字段：
  - description_by_age: {age: 长描述（用于场景 prompt）}
  - reference_by_age:   {age: 参考图文件名（相对 assets/characters/）}
  - kind:               "protagonist" / "supporting" / "adult" / "pet" / "family" / "brand"
  - gender:             "girl" / "boy" / "woman" / "man" / "pet" / "brand"
  - aliases:            可被识别为该角色的其他名字（小写）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import CHARACTERS_DIR

# 通用反例
NO_ACCESSORY = (
    "NO watch, NO bracelet, NO necklace, NO earrings, NO glasses, NO hat"
)

# 脸型/五官形态锁（用户拍板 2026-06-12）：把主角脸画成低龄圆润可爱、与定妆表一致，
# 杜绝写实/大龄脸。仅用于 Mia/Tommy 主角，不动服装/发型/配色。
FACE_CHILD_LOCK = (
    "FACE: round soft child face, soft rounded chin, big clean expressive eyes, "
    "a tiny nose, gentle childlike features (never a semi-realistic or adult/older-teen face)"
)


# ============================================================
#  主角（年龄分档 8 / 10 / 12，对应 L0-2 / L3-4 / L5-6）
# ============================================================

MIA = {
    "kind": "protagonist",
    "gender": "girl",
    "aliases": [],
    "reference_by_age": {
        8: "mia_age8.png",    # 官方正样 Mia8（水彩人物 PDF / 世界观 PPTX，L0-2 专用）
        10: "mia_age10.png",  # 官方正样 Mia10
        12: "mia_age12.png",  # 官方正样 Mia12
    },
    # HAIR LOCK（用户拍板 2026-06-09 改版）：half-up 语义模糊被模型画成丸子头/发髻，改为
    # 「高马尾 high ponytail」——全部头发在头顶/脑后高高束成一根马尾，不留任何披散散发；
    # 绝不是丸子头/发髻/half-up/半扎/散开。前面可留极少量碎发框脸或不留（以参考图为准）。
    "description_by_age": {
        8: (
            "Mia: 8y GIRL. HAIR LOCK (HIGH PONYTAIL): dark-brown hair gathered entirely into ONE "
            "single HIGH PONYTAIL tied high at the top/back of the head; ALL hair is pulled up and "
            "tied, with NO loose hair left hanging down; the tail falls naturally; a few face-framing "
            "strands at the front are optional. NOT a bun, NOT a top-knot, NOT a hair-bun, NOT half-up, "
            "NOT a low/side ponytail, NOT loose/undone hair. "
            "lavender purple LONG-SLEEVE sweatshirt, light gray/light pants, "
            "lilac-and-white sneakers, bare wrists, " + FACE_CHILD_LOCK + ", " + NO_ACCESSORY
        ),
        10: (
            "Mia: 10y GIRL. HAIR LOCK (HIGH PONYTAIL): dark-brown hair gathered entirely into ONE "
            "single HIGH PONYTAIL tied high at the top/back of the head; ALL hair is pulled up and "
            "tied, with NO loose hair left hanging down; the tail falls naturally; a few face-framing "
            "strands at the front are optional. NOT a bun, NOT a top-knot, NOT a hair-bun, NOT half-up, "
            "NOT a low/side ponytail, NOT loose/undone hair. "
            "lavender purple LONG-SLEEVE sweatshirt, light gray sweatpants, white sneakers, "
            "bare wrists, " + FACE_CHILD_LOCK + ", " + NO_ACCESSORY
        ),
        12: (
            "Mia: 12y GIRL. HAIR LOCK (HIGH PONYTAIL): dark-brown hair gathered entirely into ONE "
            "single HIGH PONYTAIL tied high at the top/back of the head with a purple hair tie; ALL hair is pulled up and tied, with NO loose hair left hanging down; the "
            "tail falls naturally; a few face-framing strands at the front are optional. NOT a bun, "
            "NOT a top-knot, NOT a hair-bun, NOT half-up, NOT a low/side ponytail, NOT loose/undone hair. "
            "lavender purple LONG-SLEEVE sweatshirt, light gray/light pants, white sneakers, "
            "bare wrists, " + FACE_CHILD_LOCK + ", " + NO_ACCESSORY
        ),
    },
}

TOMMY = {
    "kind": "protagonist",
    "gender": "boy",
    "aliases": [],
    "reference_by_age": {
        8: "tommy_age8.png",    # 官方正样 Tommy8（水彩人物 PDF / 世界观 PPTX，L0-2 专用）
        10: "tommy_age10.png",  # 官方正样 Tommy10
        12: "tommy_age12.png",  # 官方正样 Tommy12
    },
    "description_by_age": {
        8: (
            "Tommy: 8y BOY (NOT a girl, NO ponytail, NO long hair), short tidy brown hair, "
            "light blue LONG-SLEEVE sweatshirt, khaki straight pants, white sneakers, bare wrists, "
            + FACE_CHILD_LOCK + ", " + NO_ACCESSORY
        ),
        10: (
            "Tommy: 10y BOY (NOT a girl, NO ponytail, NO long hair), short messy brown hair, "
            "light blue LONG-SLEEVE sweatshirt, khaki straight pants, white sneakers, "
            "bare wrists, " + FACE_CHILD_LOCK + ", " + NO_ACCESSORY
        ),
        12: (
            "Tommy: 12y BOY (NOT a girl, NO ponytail, NO long hair), short messy brown hair, "
            "light blue LONG-SLEEVE sweatshirt, khaki straight pants, "
            "white sneakers, bare wrists, " + FACE_CHILD_LOCK + ", " + NO_ACCESSORY
        ),
    },
}


# ============================================================
#  老师（成人 IP）
# ============================================================

TEACHER_KIM = {
    "kind": "adult",
    "gender": "woman",
    # 用户拍板 2026-06-07：裸词 "teacher" 不再映射成金发女 IP Teacher Kim——否则任何
    # 出现"老师/teacher"的故事（如 Book03《The Sub Teacher》里的男代课老师）都会被错配成
    # Teacher Kim 女老师。只认其专名 Ms./Mrs./Teacher Kim / Kim。
    "aliases": ["ms. kim", "ms kim", "mrs. kim", "mrs kim", "teacher kim", "kim"],
    "reference_by_age": {"adult": "teacher_kim.png"},
    "description_by_age": {
        "adult": (
            "Teacher Kim: adult woman, late 20s, warm and playful authority (Ms. Frizzle vibe), "
            "shoulder-length GOLDEN BLOND WAVY HAIR, blue-green eyes, gentle freckles, "
            "ORANGE SHORT-SLEEVE button-up polo, BLUE wide-leg JEANS (high-waist, loose flare), "
            "white sneakers, friendly confident smile, bare wrists, " + NO_ACCESSORY
        ),
    },
}


# ============================================================
#  宠物（常驻 IP）
# ============================================================

WINNIE = {
    "kind": "pet",
    "gender": "pet",
    "aliases": ["winnie", "the cat", "kitty", "kitten"],
    "reference_by_age": {"pet": "winnie_cat.png"},
    "description_by_age": {
        "pet": (
            "Winnie: small grey tabby kitten, white belly and paws, large amber-brown eyes, "
            "pink nose, thin tabby stripes on gray fur, fluffy short tail. "
            "Watercolor children's book style, cute and soft, NOT photorealistic"
        ),
    },
}


# ============================================================
#  品牌（不可修改）
# ============================================================

DINO = {
    # 用户拍板 2026-06-07：Dino 是 VIPKID 专属冷门吉祥物，模型一画就崩（不在通用概念里）。
    # 以后【所有级别】都不让 Dino 作为故事角色出现；仅在确有需要时做角落小 logo。
    "kind": "brand",
    "gender": "brand",
    "aliases": ["dino", "vipkid dino"],
    "reference_by_age": {"brand": "dino_official.png"},
    "description_by_age": {
        "brand": (
            "Dino: VIPKID official mascot — small friendly YELLOW dinosaur with brown rounded "
            "back-spikes and a pale cream horizontally-striped belly, big round eyes. "
            "STRICTLY use official appearance (do NOT redesign shape, color, or proportions). "
            "DO NOT include Dino as a story character in ANY scene at ANY level "
            "(the model renders him incorrectly). Use ONLY as a tiny corner logo if ever needed."
        ),
    },
}


# ============================================================
#  狗（常驻 IP）—— Max，Tommy & Mia 家的柯基
# ============================================================

MAX = {
    "kind": "pet",
    "gender": "pet",
    "aliases": ["max"],
    "reference_by_age": {"pet": "max_dog.png"},
    "description_by_age": {
        "pet": (
            "Max: small friendly corgi-type dog, golden-tan fur with WHITE chest, belly and paws, "
            "large upright ears with pink inner ears, big round dark eyes, black nose, "
            "pink tongue often out in a happy smile, fluffy curled-up tail. "
            "Watercolor children's book style, cute and soft, NOT photorealistic"
        ),
    },
}


# ============================================================
#  预设配角（已有图片资源的友伴）
# ============================================================

ALI = {
    "kind": "supporting",
    "gender": "boy",
    "aliases": [],
    "reference_by_age": {6: "ali_age6.png"},
    "description_by_age": {
        # 官方定妆 Ali6.png：浅肤色 + 棕色微竖短发 + 蓝色短袖T + 卡其短裤（用户拍板 2026-06-07 订正）
        6: (
            "Ali: 6y BOY (NOT Tommy), short tousled/spiky BROWN hair, fair/light skin, "
            "warm brown eyes, BLUE short-sleeve t-shirt, KHAKI/tan shorts, white sneakers, "
            "cheerful smile"
        ),
    },
}

CATE = {
    "kind": "supporting",
    "gender": "girl",
    "aliases": [],
    "reference_by_age": {
        8: "cate_age8.png",
        10: "cate_age10.png",
        12: "cate_age10.png",  # 兜底
    },
    "description_by_age": {
        age: (
            f"Cate: {age}y GIRL (NOT Mia), brown CHIN-LENGTH wavy BOB (NOT a ponytail), "
            "small green clover earrings, blue-green eyes, rosy cheeks, "
            "WHITE long-sleeve top, PINK trousers, white sneakers"
        )
        for age in (8, 10, 12)
    },
}

# 多元化配角（黑人女孩/男孩，三档年龄）
BLACK_GIRL = {
    "kind": "supporting",
    "gender": "girl",
    "aliases": [],
    "reference_by_age": {
        8: "black_girl_age8.jpg",
        10: "black_girl_age10.jpg",
        12: "black_girl_age12.jpg",
    },
    "description_by_age": {
        # 官方定妆图（8/10/12 一致，用户拍板 2026-06-07 订正）：
        #   深棕肤色 + 黑色长卷发散开（非丸子头）+ 淡紫长袖上衣 + 浅蓝牛仔裤 + 粉色鞋
        age: (
            f"a young Black girl ({age}y, NOT Mia, NOT Anna), warm dark-brown skin, "
            "LONG voluminous CURLY black hair worn LOOSE (NOT buns, NOT an afro puff), "
            "large bright eyes, LAVENDER / light-purple LONG-SLEEVE top, light-blue jeans, "
            "PINK sneakers, friendly smile"
        )
        for age in (8, 10, 12)
    },
}

BLACK_BOY = {
    "kind": "supporting",
    "gender": "boy",
    "aliases": [],
    "reference_by_age": {
        8: "black_boy_age8.jpg",
        10: "black_boy_age10.jpg",
        12: "black_boy_age12.jpg",
    },
    "description_by_age": {
        # 官方定妆图（8/10/12 一致，用户拍板 2026-06-07 订正）：
        #   深棕肤色 + 黑色短卷发 + 白色长袖上衣 + 蓝色长牛仔裤 + 白鞋
        age: (
            f"a young Black boy ({age}y, NOT Tommy), warm dark-brown skin, "
            "short CURLY black hair, large bright eyes, "
            "WHITE LONG-SLEEVE top, BLUE full-length jeans, white sneakers, cheerful smile"
        )
        for age in (8, 10, 12)
    },
}


# ============================================================
#  家庭
# ============================================================

MOM = {
    "kind": "family",
    "gender": "woman",
    "aliases": ["mother", "mum"],
    "reference_by_age": {"adult": "mom.png"},
    "description_by_age": {
        "adult": (
            "Mom: a MATURE ADULT woman in her early thirties (clearly a grown-up parent, "
            "an adult face and adult body proportions — NOT a child, NOT a teenager, "
            "and absolutely NOT an enlarged version of the girl Mia), "
            "long brown WAVY hair worn LOOSE and DOWN over the shoulders "
            "(NEVER a ponytail, NEVER tied up, NEVER a bun), gentle warm adult face, "
            "loose WHITE long-sleeve top, light-blue straight jeans, white sneakers, "
            "gentle smile, bare wrists"
        ),
    },
}

DAD = {
    "kind": "family",
    "gender": "man",
    "aliases": ["father"],
    "reference_by_age": {"adult": "dad.png"},
    "description_by_age": {
        "adult": (
            "Dad: adult man, short tidy brown hair, gray SHORT-SLEEVE POLO shirt, "
            "khaki trousers, brown shoes, NO glasses, warm fatherly smile, bare wrists"
        ),
    },
}

GRANDMA = {
    "kind": "family",
    "gender": "woman",
    "aliases": ["grandmother", "granny"],
    "reference_by_age": {"adult": "grandma.png"},
    "description_by_age": {
        "adult": (
            "Grandma: elderly woman, SILVER-GRAY hair in a BUN, gentle wrinkles, kind smile, "
            "LAVENDER cardigan over cream top, OLIVE-GREEN long SKIRT, brown shoes"
        ),
    },
}

GRANDPA = {
    "kind": "family",
    "gender": "man",
    "aliases": ["grandfather"],
    "reference_by_age": {"adult": "grandpa.png"},
    "description_by_age": {
        "adult": (
            "Grandpa: elderly man, SILVER-GRAY short hair, friendly weathered face, "
            "ROUND glasses, gray V-NECK sweater-vest over navy collared shirt, "
            "khaki trousers, brown shoes"
        ),
    },
}


# ============================================================
#  总注册表
# ============================================================

# ============================================================
#  专书新主角（沉淀自具体绘本，下次复用）
# ============================================================

# Anna — 出场绘本：L5 "What Makes a Good Friend?"
# v4.0 改版 (2026-06-03，用户拍板)：Anna 形象改为「绿毛衣 + 黑色短发 bob + 白色发箍」，
# 参考图换成用户提供的新定妆图 anna_age12.png（黑 bob + 白发箍 + 绿毛衣 + 卡其裤）。
# （旧 v3.0 是黄毛衣+黑双低马尾，已废弃。）
#
# Anna 锁定形象（与新 anna_age12.png 参考图完全一致）：
#   - 黑色「齐下巴直发 bob」+ 斜刘海，头顶戴一条「细白色发箍」—— 永远如此（发箍是识别符号）
#   - 纯绿色长袖圆领毛衣（plain，颜色稳定）
#   - 卡其/驼色直筒长裤 + 白色低帮运动鞋
#   - 圆脸 + 腮粉 + 棕色大眼 + 小鼻子 + 温和微笑，亚洲女孩
#   - 绝不：马尾 / 双低马尾 / 麻花辫 / 长发披肩 / 眼镜
ANNA = {
    # 用户拍板 2026-06-06：Anna 是【朋友/配角】，不是主角（不抢主角锚位）
    "kind": "supporting",
    "gender": "girl",
    "aliases": [],
    "reference_by_age": {
        12: "anna_age12.png",      # 新定妆图（黑 bob + 白发箍 + 绿毛衣 + 卡其裤）
        10: "anna_age12.png",      # 暂用同图（10/12 都按 12 岁定妆）
        8: "anna_age12.png",
    },
    "description_by_age": {
        12: (
            "Anna: 12y Asian GIRL (a NEW character, NOT Mia, NOT Cate, NOT Tommy). "
            "HAIR LOCK: straight BLACK CHIN-LENGTH BOB with soft side bangs, ALWAYS wearing a thin "
            "WHITE / light hairband (headband) across the top of the head. "
            "NEVER pigtails, NEVER a ponytail, NEVER braids, NEVER long flowing hair, NEVER glasses. "
            "OUTFIT LOCK: plain GREEN crew-neck long-sleeve knit sweater, "
            "KHAKI / camel-tan straight-leg long trousers (NOT a skirt), white low-top sneakers. "
            "FACE: large round warm-brown eyes, tiny dot nose, soft rosy cheeks, light Asian skin tone, "
            "round face with gentle smile. "
            "EXPRESSION DEFAULT: kind observant smile; when nervous a small worried frown but eyes stay soft. "
            + NO_ACCESSORY
        ),
        10: (
            "Anna: 10y Asian GIRL. "
            "Straight BLACK chin-length BOB with side bangs + a thin WHITE headband (always). "
            "Plain GREEN crew-neck knit sweater, khaki straight-leg trousers, white sneakers. "
            "No glasses, NO pigtails, NO ponytail. Large brown eyes, small nose, rosy cheeks, gentle smile"
        ),
        8: (
            "Anna: 8y Asian GIRL. "
            "Straight BLACK chin-length BOB with side bangs + a thin WHITE headband (always). "
            "Plain GREEN crew-neck knit sweater, khaki trousers, white sneakers. "
            "No glasses, NO pigtails, NO ponytail. Round face, large eyes, gentle smile"
        ),
    },
}


REGISTRY: dict[str, dict] = {
    "mia": MIA,
    "tommy": TOMMY,
    "anna": ANNA,
    "teacher_kim": TEACHER_KIM,
    "winnie": WINNIE,
    "max": MAX,
    "dino": DINO,
    "ali": ALI,
    "cate": CATE,
    "black_girl": BLACK_GIRL,
    "black_boy": BLACK_BOY,
    "mom": MOM,
    "dad": DAD,
    "grandma": GRANDMA,
    "grandpa": GRANDPA,
}


def get_character(key: str) -> Optional[dict]:
    """按 key 查角色定义。"""
    return REGISTRY.get(key.lower())


def get_description(key: str, age) -> Optional[str]:
    """按 key + age 取形象描述（age 可为 int 8/10/12 或 'adult'/'pet'/'brand'）。"""
    char = get_character(key)
    if not char:
        return None
    desc_map = char.get("description_by_age", {})
    if age in desc_map:
        return desc_map[age]
    # 退化策略：对人类角色取最接近年龄；对成人/宠物/品牌取第一个
    if isinstance(age, int):
        ages = sorted(k for k in desc_map.keys() if isinstance(k, int))
        if ages:
            closest = min(ages, key=lambda a: abs(a - age))
            return desc_map[closest]
    return next(iter(desc_map.values()), None) if desc_map else None


def get_reference_path(key: str, age) -> Optional[Path]:
    """按 key + age 取参考图绝对路径。"""
    char = get_character(key)
    if not char:
        return None
    ref_map = char.get("reference_by_age", {})
    filename = ref_map.get(age)
    if not filename and isinstance(age, int):
        ages = sorted(k for k in ref_map.keys() if isinstance(k, int))
        if ages:
            closest = min(ages, key=lambda a: abs(a - age))
            filename = ref_map[closest]
    if not filename:
        # 取第一个非 int 的（adult/pet/brand）
        for v in ref_map.values():
            if v:
                filename = v
                break
    if not filename:
        return None
    p = CHARACTERS_DIR / filename
    return p if p.exists() else None


def list_available() -> list[dict]:
    """列出所有可用角色（供 UI 显示）。"""
    out: list[dict] = []
    for key, char in REGISTRY.items():
        ref_any = next(
            (CHARACTERS_DIR / fn for fn in char.get("reference_by_age", {}).values() if fn),
            None,
        )
        out.append({
            "key": key,
            "kind": char.get("kind"),
            "gender": char.get("gender"),
            "aliases": char.get("aliases", []),
            "age_options": list(char.get("reference_by_age", {}).keys()),
            "reference_exists": bool(ref_any and ref_any.exists()),
            "sample_reference": str(ref_any) if ref_any else None,
        })
    return out


def resolve_name(name: str) -> Optional[str]:
    """把任意叫法（含别名）解析为 registry key。

    例如 'Mom' -> 'mom', 'Ms. Kim' -> 'teacher_kim'。
    """
    if not name:
        return None
    n = name.strip().lower()
    if n in REGISTRY:
        return n
    for key, char in REGISTRY.items():
        for alias in char.get("aliases", []):
            if alias.lower() == n:
                return key
    return None
