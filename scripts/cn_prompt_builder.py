"""v1.9 中文 prompt 生成器（针对 doubao-seedream-4-5-251128 优化）。

依据火山官方 prompt 优化指南：
  - 主体 + 行为 + 环境 自然连贯
  - 风格、色彩、构图、留白等美学元素明确
  - 简洁精确 > 堆叠冗余词
  - 文字内容（如有）用双引号
  - 编辑场景精准指明对象 + 保留要求

输出风格模板（每页 ≈ 200-400 字符）：

    【风格】温暖治愈水彩儿童绘本风格，柔和层次水彩晕染，低饱和度，人物面部清晰圆润...
    【画面】<一句话场景：主体+行为+环境>
    【主角形象】Anna：12 岁女孩...（以参考图为准）
    【必须包含】<must_include / 配角 / 道具>
    【构图】中景，主角占画面 40-55%...
    【留白】右上角预留 15% 干净空白用于配文字
    【禁止】画面内不要出现任何文字 / 字母 / 数字 / 水印

调用入口：
    build_cn_page_prompt(page, outline, ip_age) → BuiltPrompt
"""
from __future__ import annotations

import re as _re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from character_registry import (
    REGISTRY as CHAR_REGISTRY,
    get_description as registry_get_desc,
    get_reference_path as registry_get_ref,
)
from config import (
    CHARACTERS_DIR,
    STYLE_DIR,
    composition_prompt_cn,
    composition_negative_cn,
    smoothness_prompt_cn,
    smoothness_negative_cn,
    consistency_prompt_cn,
    child_safety_positive_cn,
    child_safety_negative_cn,
)
from parser import BookOutline, PageSpec


# ============================================================
#  风格 + 构图模板（中文，简洁固定）
# ============================================================

# v4 对齐官方 SOP 画风（来自《全级别每课Prompt》基准 Style Block）：
#   经典儿童图画书插图 + 精致墨水轮廓 + 纹理纸背景 + 自然笔触；低饱和「但丰富」的莫兰迪高级色系。
#   注意：是「丰富/饱满」的低饱和色，不是惨白；「纹理纸」是纸张肌理质感，不是脏噪点。
STYLE_CN = (
    "经典儿童图画书插图风格，轻透淡彩水彩——透明、清淡、干净的水彩晕染（颜料薄、层次轻盈通透，"
    "不要厚涂、不要浓重堆色），配精致清晰、干净利落的细墨线勾边，纹理纸张质感背景，自然手绘笔触。"
    "【整体统一·不碎片化】同一色块连贯完整、大面积平涂、水彩过渡平滑柔和自然，"
    "色彩衔接顺畅一体；绝不出现斑驳破碎的色块、割裂的色斑/碎块、拼贴补丁感、杂乱色点与噪斑、"
    "断裂破碎的轮廓；线条连续闭合、形体完整干净。"
    "颜色与质感：低饱和的高级莫兰迪色系（浅米、雾霾绿、藕灰紫、卡其、淡蓝等），整体偏明亮、清透、柔和耐看，"
    "颜色清晰可辨（不发灰惨白、也不刺眼高饱和）；画面精致细腻、边缘清晰、主体干净突出，背景温馨整洁有序、清爽不杂乱。"
    "人物面部柔和有立体感，大眼睛+淡淡腮红+小鼻子，亚洲儿童特征，五官清爽精致。"
    "拒绝厚重浓郁的颜料堆叠、浑浊脏色、斑驳破碎/拼贴补丁感、Q版贴纸、扁平动漫、3D渲染、像素风、"
    "塑料磨皮感、照片写实质感、AI脏噪乱纹"
)


# v2.0 环境元素库 — 根据故事文本关键词推断场景应有的具体环境物体
_ENV_HINTS: list[tuple[str, str]] = [
    (r"classroom|class\b|desk|recess|school|teacher",
     "教室环境：浅米/白墙面、几张浅木色课桌椅、一扇明亮窗户带淡蓝天空与窗外绿树、浅色地板，"
     "墙上可有白板或一两幅简洁的儿童画作点缀；背景温馨充实而整洁有序、清爽不杂乱，主体人物清晰"),
    (r"hallway|corridor",
     "走廊环境：长走廊延伸的空间感、浅色墙裙、右侧一排明亮窗户带窗外绿意、浅色地板，"
     "可见教室门与简洁的墙面布置；背景温馨整洁有秩序、不杂乱"),
    (r"playground|outside|park|yard",
     "户外环境：柔和的浅绿草地、一两棵舒展的树、淡蓝天空与几朵白云、暖阳，"
     "背景自然清新而整洁、不杂乱"),
    (r"home|house|bedroom|kitchen",
     "家庭环境：温馨的木质家具、窗台绿植、柔和阳光，"
     "书架/玩具/相框等温馨家居小物，背景充实而整洁"),
    (r"library|book",
     "图书馆/阅读角环境：木质书架配彩色书脊、暖光、可有绿植与地球仪等点缀，背景温馨充实而整洁"),
]


def _detect_environment(text: str) -> str:
    """根据故事文本推断必须包含的环境元素（中文一句话）。"""
    t = (text or "").lower()
    for pattern, desc in _ENV_HINTS:
        if _re.search(pattern, t):
            return desc
    return ""

# v3.3 镜头景别（用户拍板：主角是画面视觉中心，占画面 50-60%，背景 40-50%）
COMPOSITION_CN: dict[str, str] = {
    "close":  "中近景半身，主角胸部以上占画面 60-70%，清晰饱满，背景有清晰可辨的环境元素",
    "medium": "中景，主角七分身或全身占画面 50-60% 高度、居中为视觉焦点，背景环境占 40-50%、细节清晰",
    "full":   "全身中景，主角从头到脚完整可见、占画面 45-55% 高度，周围留出环境空间",
    "wide":   "远景，主角占画面 35-45%（仍是视觉焦点），环境（教室全景、走廊、建筑、地标）占其余画面",
}
DEFAULT_SHOT = "medium"  # 中景为默认（主角 50-60%）

# 留白位置（中文）
BLANK_CN: dict[int, str] = {
    0: "右上角预留 15% 干净空白用于配文字",  # cover
    # 故事页：左下/右下交替
}


def _blank_text(page_index: int) -> str:
    """根据页码返回文字留白说明（对齐官方 SOP）。

    官方铁律：禁止画纯白色块/白色矩形/空白方框/人工硬边留白；
    文字位置必须落在「场景原生空旷区域」（天空、草地、远山、墙面、地面、林间空地等），
    该区域保留场景真实色彩与纹理，只是没有主角/关键道具，方便后期排文字。
    """
    if page_index == 0:
        return ("利用场景顶部的原生空旷区域（天空 / 明亮的天花板 / 大片墙面等，"
                "保留真实色彩与纹理、其上无人物与关键道具）作为书名的文字留白，"
                "禁止画任何纯白色块或空白方框")
    side = "右侧" if page_index % 2 == 1 else "左侧"
    return (f"在画面{side}利用场景原生的空旷区域（如墙面 / 地面 / 天空 / 草地等，"
            f"保留该处真实场景色彩与纹理、其上无人物与关键道具）自然留出排文字的位置，"
            "禁止画纯白色块、白色矩形或人工硬边空白")


FORBID_CN = "画面内不要出现任何文字、字母、数字、水印"


# ============================================================
#  角色检测（中文 alias）
# ============================================================

# 通用角色 → 默认套用的 registry key（系列连贯性原则）
_GENERIC_ROLE_MAP: list[tuple[str, str]] = [
    # (英文 + 中文匹配模式, registry key)
    (r"\b(?:a |an |the )?girl(?:s)?\b|女孩|小姑娘", "mia"),
    (r"\b(?:a |an |the )?boy(?:s)?\b|男孩|小男孩", "tommy"),
    (r"\b(?:a |an |the )?woman\b|阿姨|女老师", "teacher_kim"),
    (r"\b(?:a |an |the )?cat\b|kitten|猫", "winnie"),
]


def _detect_characters_v2(
    text: str,
    ip_age: int,
    cast_pool: list[str],
    generic_overrides: dict[str, str],
) -> list[dict]:
    """v2.1: 基于「老师勾选的 IP 池」+「无名角色映射」识别本页角色。

    流程：
      1. 显式名字（Anna/Mia/Tommy/Mom 等）→ 直接命中 IP 库的对应 entry
      2. 无名角色（"a girl" / "a boy" / "an old woman" / "a cat"）→
         先查 generic_overrides 是否指定，否则按默认规则
      3. 只返回在 cast_pool 里的角色（cast_pool 限制本页可用 IP 范围，避免乱拉人）

    Returns: 列表 [{name, key, description_cn, ref_path, is_generic}, ...]
    """
    from ip_library import get_ip, resolve_name_to_ip, resolve_generic_role

    text_low = (text or "").lower()
    found: dict[str, dict] = {}  # ip_key → entry dict
    pool_set = set(cast_pool)

    # 1) 显式名字命中
    name_aliases = [
        ("mia", "Mia"), ("tommy", "Tommy"), ("anna", "Anna"),
        ("ali", "Ali"), ("cate", "Cate"),
        ("mom", "Mom"), ("mommy", "Mommy"), ("mother", "Mother"),
        ("dad", "Dad"), ("daddy", "Daddy"), ("father", "Father"),
        ("grandma", "Grandma"), ("granny", "Granny"),
        ("grandpa", "Grandpa"), ("grandfather", "Grandfather"),
        ("teacher", "Teacher"), ("ms. kim", "Ms. Kim"), ("mrs. kim", "Mrs. Kim"),
        ("dino", "Dino"),
    ]
    for alias_low, display in name_aliases:
        if not _re.search(rf"\b{_re.escape(alias_low)}\b", text_low):
            continue
        ip = resolve_name_to_ip(alias_low, ip_age)
        if not ip or ip.key not in pool_set:
            continue
        if ip.key in found:
            continue
        found[ip.key] = {
            "name": display,
            "key": ip.key,
            "description_cn": ip.desc,
            "ref_path": ip.image_path,
            "is_generic": False,
        }

    # 2) 无名角色 → 用 overrides 或默认规则
    generic_patterns = [
        (r"\b(?:a |an |the )?girl(?:s)?\b", "girl"),
        (r"\b(?:a |an |the )?boy(?:s)?\b",  "boy"),
        (r"\b(?:a |an )?old woman\b",        "old woman"),
        (r"\b(?:a |an )?old man\b",          "old man"),
        (r"\b(?:a |an |the )?woman\b",       "woman"),
        (r"\b(?:a |an |the )?man\b",         "man"),
        (r"\b(?:cat|kitty|kitten)\b",        "cat"),
    ]
    for pat, role in generic_patterns:
        if not _re.search(pat, text_low):
            continue
        override_key = generic_overrides.get(role, "")
        ip = get_ip(override_key) if override_key else resolve_generic_role(role, ip_age)
        if not ip:
            continue
        # v3.4 系列默认主角规则（用户拍板）：故事里只要出现 girl/boy，
        # 就分别默认套 Mia / Tommy 形象 —— 这是系列硬规则，**永远允许**，
        # 即使老师没把 mia/tommy 勾进 cast_pool，也要带上参考图，避免「只有主角没有 Mia/Tommy」。
        series_default = role in ("girl", "boy")
        if not series_default and ip.key not in pool_set:
            continue
        if ip.key in found:
            continue
        found[ip.key] = {
            "name": ip.name_base,
            "key": ip.key,
            "description_cn": ip.desc,
            "ref_path": ip.image_path,
            "is_generic": True,
        }

    return list(found.values())


def _detect_characters(text: str, ip_age: int) -> list[dict]:
    """识别故事文本里的所有角色（含已注册 IP + 通用 girl/boy）。

    返回每项：
      {
        "name": str,              # 在故事里出现的名字
        "key":  str,              # registry key
        "description_cn": str,    # 中文形象描述
        "ref_path": Path | None,  # 参考图
        "is_generic": bool,       # 是否通过 girl/boy 等通用词命中
      }
    """
    text_low = (text or "").lower()
    found_keys: set[str] = set()
    out: list[dict] = []

    # 1) 显式 IP（按 registry 的 key + alias 匹配）
    for key, char in CHAR_REGISTRY.items():
        names = [key.replace("_", " ")] + list(char.get("aliases", []))
        for name in names:
            if _re.search(rf"\b{_re.escape(name.lower())}\b", text_low):
                if key in found_keys:
                    break
                age_key = ip_age if char.get("kind") not in ("adult", "pet", "brand", "family") else \
                          next(iter(char.get("description_by_age", {}).keys()), "adult")
                en_desc = registry_get_desc(key, age_key) or ""
                ref = registry_get_ref(key, age_key)
                out.append({
                    "name": name.capitalize(),
                    "key": key,
                    "description_cn": _en_to_cn_desc(en_desc, key, age_key),
                    "ref_path": ref,
                    "is_generic": False,
                })
                found_keys.add(key)
                break

    # 2) 通用角色（girl / boy / cat / woman）→ 默认套 IP
    for pattern, default_key in _GENERIC_ROLE_MAP:
        if _re.search(pattern, text_low):
            if default_key in found_keys:
                continue
            char = CHAR_REGISTRY.get(default_key)
            if not char:
                continue
            age_key = ip_age if char.get("kind") not in ("adult", "pet", "brand", "family") else \
                      next(iter(char.get("description_by_age", {}).keys()), "adult")
            en_desc = registry_get_desc(default_key, age_key) or ""
            ref = registry_get_ref(default_key, age_key)
            out.append({
                "name": default_key.replace("_", " ").capitalize(),
                "key": default_key,
                "description_cn": _en_to_cn_desc(en_desc, default_key, age_key),
                "ref_path": ref,
                "is_generic": True,
            })
            found_keys.add(default_key)

    return out


# ============================================================
#  英文 IP 描述 → 中文简化描述（核心外观锚定）
# ============================================================

def _en_to_cn_desc(en_desc: str, key: str, age) -> str:
    """把 character_registry 里英文的形象描述压缩成中文一句话。

    这里不做机翻，而是按 key 手写中文摘要（更准、更短）。
    age 用于挑年龄分档。
    """
    # 按 key 维护中文摘要表（最权威）
    age_n = age if isinstance(age, int) else 12

    if key == "mia":
        # Mia: 三档年龄长袖/短袖、紫色，单束马尾必须有
        outfit = {
            8:  "薄紫色短袖T恤+牛仔裤",
            10: "薄紫色长袖卫衣+浅灰运动裤",
            12: "薄紫色长袖针织衫+白色阔腿裤",
        }.get(age_n, "薄紫色上衣")
        return (
            f"Mia：{age_n}岁女孩，棕色长发束成一束高马尾在脑后（必须是马尾，不能散开），"
            f"前额碎刘海+少许鬓发框脸，穿{outfit}，白色运动鞋，"
            f"不戴手表/手链/项链/耳环/眼镜/帽子"
        )
    if key == "tommy":
        # v2.0 修正：按官方 L5-1 image1 反推（蓝色短袖polo + 蓝色牛仔裤）
        outfit = {
            8:  "蓝白条纹短袖T恤+蓝色牛仔裤",
            10: "蓝色长袖卫衣+蓝色牛仔裤",
            12: "蓝色短袖polo衫+蓝色牛仔裤",
        }.get(age_n, "蓝色短袖polo衫+蓝色牛仔裤")
        return (
            f"Tommy：{age_n}岁亚洲男孩（必须是男孩，不能有马尾，不能长发，绝不戴眼镜，不戴帽子），"
            f"棕色蓬松短发清爽，穿{outfit}，白色低帮运动鞋"
        )
    if key == "anna":
        # v4.0 改版(2026-06-03)：以新定妆图为准——黑色短发bob+白发箍+绿毛衣
        return (
            f"Anna：{age_n}岁亚洲女孩（与Mia、Tommy完全不同的新角色），"
            f"黑色齐下巴直发bob+斜刘海，头顶戴一条细白色发箍（必须有发箍，是Anna的识别符号，不能丢），"
            f"穿纯绿色长袖圆领毛衣（plain，无图案）+卡其色直筒长裤+白色低帮运动鞋，"
            f"绝不扎马尾/双马尾/辫子、不戴眼镜，大眼睛圆脸小鼻子腮粉，温和微笑"
        )
    if key == "teacher_kim":
        return (
            "Teacher Kim：成年女老师（不是小孩），约30岁，"
            "金色波浪齐肩发，蓝绿色眼睛，亲切自信微笑，"
            "穿橙色短袖翻领衬衫+蓝色高腰阔腿牛仔裤+白色运动鞋，不戴眼镜"
        )
    if key == "winnie":
        return "Winnie：灰色虎斑小猫，白色肚皮和爪子，琥珀色大眼，粉色鼻子，体型小巧"
    if key == "mom":
        return "妈妈：成年女性（不是小孩），约35岁，棕色长波浪发，白色宽松长袖上衣+浅蓝色牛仔裤+白色运动鞋，温柔微笑"
    if key == "dad":
        return "爸爸：成年男性（不是小孩），约38岁，棕色短发，灰色短袖polo衫+卡其色长裤+棕色皮鞋，不戴眼镜，温和微笑"
    if key == "grandma":
        return "奶奶：年长女性（不是小孩，明显皱纹），银灰色发髻，淡紫色开衫+米色内搭+橄榄绿长裙+棕色鞋，慈祥微笑"
    if key == "grandpa":
        return "爷爷：年长男性（不是小孩，明显皱纹），银灰色短发+圆框眼镜，灰色V领毛背心+深蓝衬衫+卡其长裤+棕色鞋，慈祥微笑"
    if key == "dino":
        return "黄色小恐龙IP角色，圆脸大眼，棕色背鳍，憨态可掬"

    # 兜底：截断英文描述前 80 字符
    return en_desc[:80] + ("..." if len(en_desc) > 80 else "")


def _key_lock_phrase(key: str, age) -> str:
    """精简版的关键外观锁定（用在【角色外观锁定】块，避免与画面描述重复）。

    只列出"不能丢/不能错"的核心特征：年龄+发型+眼镜+主色调，不重复服装细节。
    """
    age_n = age if isinstance(age, int) else 12
    if key == "mia":
        return f"（{age_n}岁女孩，单束高马尾必须扎着，不戴眼镜，不戴任何饰品）"
    if key == "tommy":
        return f"（{age_n}岁男孩，棕色蓬松短发清爽，绝不戴眼镜，不能有马尾或长发，不戴帽子）"
    if key == "anna":
        # v4.0 改版(2026-06-03)：黑色短发bob+白发箍+绿毛衣（旧版黄毛衣双低马尾已废弃）
        return f"（{age_n}岁亚洲女孩，黑色齐下巴直发bob+斜刘海+头顶细白色发箍必须有+纯绿色长袖圆领毛衣+卡其裤+绝不扎马尾或辫子、绝不戴眼镜）"
    if key == "teacher_kim":
        return "（成年女老师，约30岁，栗色齐肩短发，黑色细框眼镜）"
    if key == "winnie":
        return "（橘白色家猫，圆脸大眼）"
    if key in ("mom", "dad"):
        return "（成年人，不是小孩）"
    if key in ("grandma", "grandpa"):
        return "（年长者，明显皱纹，不是小孩）"
    if key == "dino":
        return "（黄色卡通小恐龙IP）"
    return ""


# ============================================================
#  场景描述：从故事文本生成中文一句话
# ============================================================

def _scene_to_cn(page: PageSpec, outline: BookOutline) -> str:
    """v1.9：优先级 page.scene_cn > page.scene(中文) > 英文故事文本。

    AI 抽取阶段生成的 scene_cn 是连贯的中文画面描述（主体+动作+环境+氛围），
    最适合 Doubao Seedream 4.5 理解。
    """
    # 1) AI 生成的 scene_cn（最优）
    cn = (getattr(page, "scene_cn", "") or "").strip()
    if cn:
        return cn

    # 2) 用户在 page.scene 里写了中文 → 直接用
    scene = (page.scene or "").strip()
    if scene and _re.search(r"[\u4e00-\u9fff]", scene):
        return scene

    # 3) 兜底：用故事文本（英文）+ 中文导引
    text = (page.text or "").strip()
    if not text:
        return "（请补充画面描述）"
    return f"如实绘制以下故事场景（请按字面意思理解每个动作和物体）：{text}"


# ============================================================
#  主入口
# ============================================================

@dataclass
class BuiltPromptCN:
    """v3：拆成正向/反向两段，最终 prompt = positive + ==请勿出现== + negative。"""
    positive: str                  # v3: 正向 prompt（火山风单段流畅）
    negative: str                  # v3: 反向 prompt（分类禁忌）
    prompt: str                    # v3: 最终拼接后字符串（实际发送给 Seedream）
    references: list[Path]
    used_characters: list[dict]    # 调试用

    @staticmethod
    def join(positive: str, negative: str) -> str:
        """把正向 + 反向拼成最终 prompt。"""
        pos = (positive or "").strip()
        neg = (negative or "").strip()
        if not neg:
            return pos
        return f"{pos}\n\n==请勿出现==\n{neg}"


# ============================================================
#  v3 角色专属配色锁定表
# ============================================================
# 每个角色的「专属色」 — 在 prompt 反向区会自动生成"除 X 外其他人禁止穿此色"
_SIGNATURE_COLOR: dict[str, str] = {
    "mia":   "紫色",
    "tommy": "蓝色",
    "anna":  "绿色",
    "cate":  "粉色",
    "ali":   "亮黄色",
}


def _signature_color_of(ip_key: str) -> str:
    """根据 ip_key（含 age 后缀，如 mia_12）查专属色。"""
    base = ip_key.split("_")[0]
    return _SIGNATURE_COLOR.get(base, "")


# ============================================================
#  v3 角色特征锁短语（用于反向区"防止跑帧"）
# ============================================================
# 每个角色 base key 对应一段否定锁（明确说不戴眼镜、不变发型等）
_CHAR_NEGATIVE_LOCK: dict[str, str] = {
    "mia":     "Mia戴眼镜、Mia散发不扎马尾、Mia扎双马尾或三辫子、Mia穿裙子、Mia穿其他颜色上衣",
    "tommy":   "Tommy戴任何眼镜或墨镜（Tommy绝不戴眼镜）、Tommy长发、Tommy扎马尾、Tommy被画成女孩、Tommy穿其他颜色上衣",
    "anna":    "Anna扎马尾或双低马尾或辫子、Anna长发披肩、Anna不戴白发箍、Anna戴眼镜、Anna穿裙子、Anna穿黄色或紫色或其他颜色上衣（必须纯绿色毛衣）",
    "cate":    "Cate散发不扎、Cate穿其他颜色上衣",
    "ali":     "Ali穿其他颜色上衣",
    "teacher": "Teacher Kim 穿太花哨或显得太年轻",
    "mom":     "妈妈年龄看起来过老或过年轻",
    "dad":     "爸爸年龄看起来过老或过年轻",
    "grandma": "奶奶发色过深（应是白发）",
    "grandpa": "爷爷发色过深（应是白发）",
}


def _char_negative_of(ip_key: str) -> str:
    base = ip_key.split("_")[0]
    return _CHAR_NEGATIVE_LOCK.get(base, "")


# ============================================================
#  v3 全局禁忌（永远要加）
# ============================================================
# v3.2 B 层：默认解剖锁（强约束，避免多手指/畸形/比例失衡）
_ANATOMY_NEGATIVE = (
    "多手指（每只手严格 5 根手指，不要 4 或 6 根）、"
    "缺手指、融合手指、第六根手指；"
    "畸形关节、错位手腕、扭曲手臂、不对称的双腿；"
    "双眼不对称、独眼、三只眼、瞳孔变形、嘴歪斜、表情僵硬；"
    "头身比例失调、头部过大、四肢过短或过长、躯干扭曲；"
    "成年化的儿童脸、肌肉发达的儿童身体；"
    "身体部位融合到背景中、肢体穿过物体；"
    "重影、模糊、人物失焦、低分辨率、像素化"
)

# v3.2 全局反向：风格/水印 + 解剖 + 质量
_GLOBAL_NEGATIVE = (
    "画面内任何文字、字母、数字、水印、签名、logo；"
    "塑料磨皮感、Q版贴纸风格、3D渲染、扁平动漫、像素风、油画厚涂、廉价 CG 感；"
    # 印刷级干净控制（用户拍板）：去细碎/斑驳/脏块/不匀色块
    "细碎噪点、高频纹理、脏污颗粒、斑驳色块、明暗不匀的脏块、过多杂乱阴影、"
    "色彩不均匀、画面脏乱、密集小装饰；"
    # 画面整洁控制（向目标淡彩绘本风靠拢）：背景可温馨充实，但要整洁不杂乱、不过饱和
    "背景杂乱无序、胡乱堆砌的杂物、贴满杂物的墙面、众多有清晰五官的陌生路人同学、"
    "高饱和浓郁刺眼色彩、厚重油画式明暗、生硬强烈对比；"
    # 官方 SOP 铁律：禁止人工硬边白色留白块（文字位用场景原生空旷区）
    "纯白色块、白色矩形、空白方框、人工硬边留白、突兀的白色空白区域；"
    # 比例控制（QA：人物与车/家具/道具比例不符日常逻辑）
    "人物与车辆/家具/道具的比例失真、比例不合常理、物体过大或过小；"
    + _ANATOMY_NEGATIVE
    + "；过于写实的照片感、写实皮肤纹理"
)


# v3.2 B 层：按 IP 年龄给头身比锁定（注入到正向 prompt）
def _head_body_ratio_lock(ip_age: int) -> str:
    """根据年龄给一个明确的头身比 + 比例描述（注入到正向 prompt）。"""
    if ip_age <= 6:
        return "儿童头身比约 4 头身（圆润幼态），头部略大、四肢短，整体可爱比例"
    if ip_age <= 8:
        return "儿童头身比约 5 头身（学龄前期），头身比例自然，四肢匀称"
    if ip_age <= 10:
        return "儿童头身比约 5.5-6 头身（学龄期），身体比例已接近少年"
    # 11-14：少年
    return "少年头身比约 6.5-7 头身（青春期前期），身体修长、四肢比例匀称，但保留少年面部特征"


# ============================================================
#  v3 关键道具/动物检测（增强版）— 强制注入 prompt 正向区
# ============================================================
# 比 _AUTO_MUST_KEYWORDS 更细：除了道具名，还给出"画面应如何呈现"
_KEY_PROP_HINTS: list[tuple[str, str]] = [
    (r"\bhamster\b|仓鼠",
     "一只毛茸茸的小仓鼠（注意：体型很小，约人手掌大，不能画成猫或狗的大小）"),
    (r"\beraser\b|橡皮",
     "一块粉色或彩色橡皮"),
    (r"\bbook(s)?\b|书|绘本",
     "几本彩色精装书（散落或堆叠在地面/桌上）"),
    (r"\bpencil(s)?\b|铅笔",
     "几支削好的铅笔"),
    (r"\bglue\b|胶水",
     "一支胶水"),
    (r"\bcookie(s)?\b|饼干",
     "几块烤好的圆形饼干（黄褐色，带巧克力豆纹）"),
    (r"\bdesk(s)?\b|课桌",
     "几张木质课桌（浅棕色）"),
    (r"\bchair(s)?\b|椅子",
     "木质椅子"),
    (r"\bmap\b|地图",
     "一张纸质地图（折叠或展开）"),
    (r"\bcastle\b|城堡",
     "远景一座石质城堡"),
    (r"\bsheep\b|绵羊",
     "一只白色卷毛绵羊"),
    (r"\bbagpipe(s)?\b|风笛",
     "一支苏格兰传统风笛"),
]


def _detect_key_props(text: str) -> list[str]:
    """从文本里检测出现的关键道具，返回详细描述清单。"""
    t = (text or "").lower()
    out: list[str] = []
    for pat, desc in _KEY_PROP_HINTS:
        if _re.search(pat, t):
            out.append(desc)
    return out


def build_cn_page_prompt(
    page: PageSpec,
    outline: BookOutline,
    ip_age: int,
    *,
    cast_pool: list[str] | None = None,        # v2.1: 老师在 UI 勾选的全部 IP key 池
    generic_overrides: dict[str, str] | None = None,  # v2.1: girl/boy 等无名角色映射
) -> BuiltPromptCN:
    """生成单页的中文 prompt（v2.1：支持老师从 IP 库勾选人物池 + 无名角色映射）。"""
    is_cover = page.page_type == "cover" or page.index == 0
    title = (outline.title or "").strip()

    # 1) 检测角色（v2.1：优先用 cast_pool + overrides）
    cast_text = (page.text or "") + " " + (page.scene or "")
    if is_cover:
        all_text = " ".join((p.text or "") for p in outline.pages)
        cast_text = all_text + " " + cast_text

    if cast_pool:
        cast = _detect_characters_v2(
            cast_text, ip_age, cast_pool, generic_overrides or {},
        )
    else:
        cast = _detect_characters(cast_text, ip_age)

    if is_cover:
        if not cast:
            # cover 完全没角色 → Mia + Tommy 默认主角
            for k in ("mia", "tommy"):
                ch = CHAR_REGISTRY.get(k)
                if ch:
                    ref = registry_get_ref(k, ip_age)
                    cast.append({
                        "name": k.capitalize(),
                        "key": k,
                        "description_cn": _en_to_cn_desc(
                            registry_get_desc(k, ip_age) or "", k, ip_age
                        ),
                        "ref_path": ref,
                        "is_generic": True,
                    })
        else:
            # cover 已有正式主角（如 Anna）→ 正式主角优先，再带上故事里出现的
            # 系列默认主角(Mia/Tommy，来自 girl/boy 映射)，最多 3 人。
            # 修复：旧逻辑 named[:2] 会把 Mia/Tommy 整个丢掉，导致封面缺人/跳帧。
            named = [c for c in cast if not c.get("is_generic")]
            generic = [c for c in cast if c.get("is_generic")]
            if named:
                cover_cast = list(named)
                have = {c.get("key") for c in cover_cast}
                for g in generic:
                    if len(cover_cast) >= 3:
                        break
                    if g.get("key") not in have:
                        cover_cast.append(g)
                        have.add(g.get("key"))
                cast = cover_cast[:3]

    # 2) 场景描述
    if is_cover:
        scene_cn = f"绘本封面，主题为《{title}》。" + (
            "主角们温馨可爱地展示在画面中，"
            "上方留出大块空白用于书名" if cast else ""
        )
    else:
        scene_cn = _scene_to_cn(page, outline)

    # 3) 镜头
    shot = (page.shot or DEFAULT_SHOT).strip().lower()
    if shot not in COMPOSITION_CN:
        shot = DEFAULT_SHOT
    composition_cn = COMPOSITION_CN[shot]

    # 4) 留白
    blank_cn = _blank_text(page.index) if not is_cover else (
        "利用画面上方场景原生的空旷区域（天空 / 明亮天花板 / 大片墙面等，保留真实色彩与纹理、其上无人物道具）"
        "作为书名文字留白，禁止画纯白色块或空白方框"
    )

    # 5) 关键道具检测（v3 增强：从故事文本抓 hamster/eraser/books/cookies 等）
    key_props = [] if is_cover else _detect_key_props(cast_text)

    # 6) 环境推断（v2.0 新增）— 根据故事文本主动给"环境必须有 X/Y/Z"
    env_hint = "" if is_cover else _detect_environment((page.text or "") + " " + scene_cn)

    # 7) ============ v3: 组装正向 prompt（火山风单段流畅自然语言）============
    positive = _build_positive_v3(
        is_cover=is_cover,
        title=title,
        scene_cn=scene_cn,
        cast=cast,
        ip_age=ip_age,
        env_hint=env_hint,
        key_props=key_props,
        composition_cn=composition_cn,
        blank_cn=blank_cn,
    )

    # 8) ============ v3: 组装反向 prompt（分类禁忌）============
    negative = _build_negative_v3(cast=cast, page_text=(page.text or ""))

    # 9) 最终 prompt = 正向 + 反向
    prompt_text = BuiltPromptCN.join(positive, negative)

    # 10) 参考图策略（v2.1：本页 cast 里每人 1 张，最多 3 张）
    refs: list[Path] = []
    for c in cast:
        if c.get("ref_path") and len(refs) < 3:
            refs.append(c["ref_path"])

    return BuiltPromptCN(
        positive=positive,
        negative=negative,
        prompt=prompt_text,
        references=refs,
        used_characters=cast,
    )


# ============================================================
#  v3 正向 prompt 构造（火山风单段流畅）
# ============================================================

def _build_positive_v3(
    *, is_cover: bool, title: str, scene_cn: str, cast: list[dict], ip_age: int,
    env_hint: str, key_props: list[str], composition_cn: str, blank_cn: str,
) -> str:
    """生成分层、关键约束前置加权的正向 prompt。

    v4 重构（2026-06-03）：把「本页画面动作 + 角色形象锁」置顶（gpt-image-2 对前置内容
    遵循度更高），风格/安全等"氛围块"压缩并后置，整体从 ~15 段降到 ~8 段，
    并纠正上一版过度"惨白/大留白/背景极简"——向参考实体绘本（饱满柔和+温馨充实）靠拢。
    """
    parts: list[str] = []
    names = "、".join(c.get("name", "") for c in cast if c.get("name"))
    n_kids = len([c for c in cast if c.get("name")])

    # ① 本页画面（核心，最高权重，绝对置顶）
    if is_cover:
        who = names or "系列主角 Mia、Tommy"
        parts.append(
            f"【画面 · 绘本封面】《{title}》封面：{who} 一起出现在画面中央，"
            f"神情友好、温馨微笑，面向观众；上方留出大块干净空白用于书名。"
        )
    else:
        parts.append(
            f"【本页画面 · 必须如实呈现，最高优先级】{scene_cn.rstrip('。')}。"
            f"请严格按这段描述的动作、姿势、视线与站位作画——这是本页最重要、绝不能画错的内容。"
        )

    # ② 角色形象锁（IP 外观；发型/服装/配色为识别核心，紧跟画面之后）
    for c in cast:
        parts.append(f"【{c.get('name','')} 形象锁定】{(c.get('description_cn') or '').rstrip('。')}。")
    if cast:
        parts.append(
            f"外观铁律：{names} 的发型、发色、服装与颜色、五官、配饰一律以上面各自的形象锁定与参考图为准、"
            "且全书逐页保持一致；画面动作描述里若出现冲突的外观（多余眼镜、不同发型或衣色），一律忽略、以形象锁定为准。"
        )

    # ③ 人数 + 比例 + 同尺度（合并成一句精炼硬约束）
    if cast:
        line = (
            f"人物与比例（硬约束）：画面里的儿童只能是 {names}，不要出现有清晰五官/发型的陌生同学或路人"
            f"（最多远景一两个极淡的人影剪影，可省略）；主角（群体）居中、是画面视觉焦点、占画面高度约 50-60%；"
            f"{_head_body_ratio_lock(ip_age)}；每只手 5 根手指、关节自然、双眼对称。"
        )
        if n_kids >= 2:
            line += "多个同龄主角必须同尺度、同景深、站在同一水平面，谁都不能比旁边的人明显大一圈。"
        parts.append(line)

    # ④ 环境（温馨充实而整洁，给具体锚点）
    if env_hint:
        parts.append("【环境】" + env_hint.replace("（必须可见）", "").rstrip("。") + "。")

    # ⑤ 关键道具
    if key_props:
        parts.append("画面里应出现：" + "；".join(key_props) + "。")

    # ⑥ 配色锁定（每个有专属色的角色）
    color_locks = [
        f"{c['name']}是画面里唯一穿{_signature_color_of(c['key'])}的人"
        for c in cast if _signature_color_of(c["key"])
    ]
    if color_locks:
        parts.append("配色锁定：" + "；".join(color_locks) + "。")

    # ⑦ 画风（一段：轻透淡彩水彩 + 精致清晰墨线 + 低饱和莫兰迪；明亮清透、精细干净 + 安全）
    parts.append(
        "【画风】" + STYLE_CN.split("。")[0] + "。"
        "轻透清淡的透明水彩（颜料薄、通透不厚重）、精致清晰的细墨线，低饱和的莫兰迪高级色系；"
        "画面明亮清透、精细干净、边缘清晰、主体突出；整体阳光健康温暖、"
        "人物穿着得体的日常服装、适合儿童，画面像精印实体绘本的内页。"
    )

    # ⑧ 构图 + 留白 + 禁文字
    parts.append(f"构图：{composition_cn.rstrip('。')}。{blank_cn}。{FORBID_CN}。")

    return "\n".join(parts)


# ============================================================
#  v3 反向 prompt 构造（分类禁忌）
# ============================================================

def _build_negative_v3(*, cast: list[dict], page_text: str) -> str:
    """生成分类反向 prompt。

    模块：
      [全局禁忌] [角色特征锁] [配色禁穿锁] [本页道具禁忌]
    """
    parts: list[str] = []

    # 1) 全局禁忌
    parts.append(_GLOBAL_NEGATIVE)

    # 1.5) v3.3 构图/比例禁忌（主角过小、配角/动物过大等）
    parts.append(composition_negative_cn())

    # 1.6) v3.4 平滑控制禁忌（细碎噪点/高频纹理/脏污颗粒/杂线乱纹等）
    parts.append(smoothness_negative_cn())

    # 1.7) v3.6 儿童内容安全红线 + 画风/色彩禁忌 + IP 唯一性
    parts.append(child_safety_negative_cn())

    # 2) 角色特征锁（按 cast 自动）
    char_locks = []
    for c in cast:
        lock = _char_negative_of(c["key"])
        if lock:
            char_locks.append(lock)
    if char_locks:
        parts.append("；".join(char_locks))

    # 3) 配色禁穿锁（按 cast 自动 — "除 X 外其他角色禁止穿 X 的专属色"）
    color_bans: list[str] = []
    for c in cast:
        sig = _signature_color_of(c["key"])
        if sig:
            color_bans.append(f"除{c['name']}外任何人穿{sig}或类似{sig}调")
    if color_bans:
        parts.append("；".join(color_bans))

    # 4) 本页道具禁忌 — 故事没提到 hamster 就别画狗/猫，反之亦然
    t = page_text.lower()
    page_neg: list[str] = []
    if "hamster" in t:
        page_neg.append("把仓鼠画成狗、猫或其他动物；把仓鼠画得过大（大过手掌）")
    elif not any(w in t for w in ("cat", "dog", "rabbit", "bird", "pet")):
        page_neg.append("画面中出现宠物（本页不应有）")
    if page_neg:
        parts.append("；".join(page_neg))

    return "；\n".join(p.rstrip("；。") for p in parts) + "。"


# ============================================================
#  必须包含：从文本自动提取关键道具/配角
# ============================================================

_AUTO_MUST_KEYWORDS: list[tuple[str, str]] = [
    # 动物
    (r"\bhamster\b|仓鼠", "一只小仓鼠"),
    (r"\bdog\b|小狗", "一只可爱的小狗"),
    (r"\bcat\b|kitten|小猫", "一只小猫"),
    (r"\brabbit\b|bunny|兔子", "一只兔子"),
    (r"\bsheep\b|绵羊", "白色蓬松的绵羊"),
    (r"\bhorse\b|马", "一匹马"),
    (r"\bbird\b|鸟", "一只小鸟"),
    (r"\bfish\b|鱼", "一条鱼"),
    # 道具
    (r"\bdesk\b|课桌|桌子", "课桌"),
    (r"\bbook\b|书本|绘本", "若干本书"),
    (r"\bpencil\b|铅笔", "铅笔"),
    (r"\beraser\b|橡皮", "橡皮"),
    (r"\bglue\b|胶水", "胶水"),
    (r"\bcookie\b|饼干", "饼干"),
    (r"\bcake\b|蛋糕", "蛋糕"),
    (r"\bclassroom\b|教室", "教室背景"),
    (r"\bschool\b|学校", "学校背景"),
    # 配角
    (r"\bteacher\b|老师", "一位成年老师（不是小孩）"),
    (r"\bmom\b|mother\b|妈妈", "一位成年妈妈（不是小孩）"),
    (r"\bdad\b|father\b|爸爸", "一位成年爸爸（不是小孩）"),
    (r"\bgrandma\b|奶奶|外婆", "一位年长奶奶（皱纹明显，不是小孩）"),
    (r"\bgrandpa\b|爷爷|外公", "一位年长爷爷（皱纹明显，不是小孩）"),
]


def _auto_must_include(text: str) -> str:
    """从文本自动提取必须出现的元素，去重 + 中文化。"""
    if not text:
        return ""
    text_low = text.lower()
    seen: set[str] = set()
    items: list[str] = []
    for pattern, item in _AUTO_MUST_KEYWORDS:
        if _re.search(pattern, text_low) and item not in seen:
            items.append(item)
            seen.add(item)
    return "，".join(items[:6])  # 最多 6 个，避免过载


# ============================================================
#  辅助：页编号 → 业务显示名
# ============================================================

def page_display_name(page_index: int, total_pages: int = 8) -> str:
    """业务编号约定（用户视角）：
      index=0  → "Cover"（封面 = 第 1 页，但叫 Cover）
      index=1  → "Page 2"（故事第一句 = 印刷第 2 页）
      index=2  → "Page 3"
      ...
      index=7  → "Page 8"
    """
    if page_index == 0:
        return "Cover"
    return f"Page {page_index + 1}"
