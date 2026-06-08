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
    "高级精致的经典儿童图画书插图风格，干净清新的【治愈水彩】——通透柔和的水彩晕染，大面积色块干净通透："
    "色块干净不脏、以细腻柔和的水彩过渡做克制而精致的明暗与体积（轻盈不厚重），"
    "讲究前中后景的空间层次与景深（近景清晰精致、远景柔和虚化），画面有丰富耐看的层次感与高级感；"
    "配精致清晰、干净利落的细墨线勾边，线条连续闭合、形体简洁完整；画面干净细腻、精致考究而不杂乱。"
    "【细腻而不细碎·无噪点无颗粒·无脏块无碎块】上色细腻柔和、过渡干净自然、颜色分布匀净；"
    "绝不出现斑驳破碎的色块、割裂的色斑/碎块、拼贴补丁感、杂乱色点、噪点颗粒、可见笔触痕迹、"
    "水彩纸/纸张颗粒纹理、脏污纹理与断裂破碎轮廓；"
    "线条连续闭合、形体完整干净；画面洁净、过渡干净，可高分辨率打印——边缘与线条清晰锐利、绝不模糊发虚发糊。"
    "【色调】暖米低饱和主调（暖米白、奶油杏、浅卡其）+ 柔和莫兰迪点缀（雾霾绿、藕灰紫、淡蓝），"
    "颜色均匀简洁干净、整体明亮清透温暖耐看，颜色清晰可辨（不发灰惨白、也不刺眼高饱和）。"
    "【光线】明亮柔和的自然光，方向统一，做克制而细腻的明暗塑形带出体积与层次（轻盈不厚重）；阴影浅淡干净、绝不压暗。"
    "【背景】极简整洁、适度留白、清爽不杂乱：空墙面只留少量精简点缀，主体人物干净突出、边缘清晰、平涂干净。"
    "人物面部干净简洁（柔和线条平涂），大眼睛+淡淡腮红+小鼻子，亚洲儿童特征，五官清爽精致。"
    "拒绝：浑浊脏色、过暗压抑、斑驳破碎/拼贴补丁感、噪点颗粒色斑、可见笔触/纸张纹理颗粒、Q版贴纸、"
    "厚重立体的3D塑料渲染、油画厚涂、强烈明暗体积塑形、写实光影、塑料磨皮感、照片写实质感、AI脏噪乱纹、打印模糊发糊。"
    "【画风锁定·低随机】严格复刻官方参考画风：干净细腻的治愈水彩、柔和层次与景深、暖米+柔蓝低饱和、明亮柔光、"
    "干净细墨线；不要自由发挥、不要改变既定画风与配色、不要增添多余杂乱装饰、不要添加噪点颗粒。"
    "【高明度·明亮通透·绝不暗沉】整体高调明亮(high-key)、画面通透干净、像沐浴在柔和日光里；"
    "阴影极浅淡干净、绝无硬阴影/重阴影/暗角；严禁发暗、压暗、阴沉、灰暗、夜景、暖光过浓发黄、整体偏暗调。"
    "【构图·预留文字留白】主体人物适度偏置(不要铺满整幅)，画面预留约 20% 干净的浅色留白区域"
    "(如天空、空墙面或地面)，背景极简整洁、便于后期叠放文字，留白处不放杂物。"
    "【人物一致·只改表情动作】画面中出现的既有角色（Mia/Tommy/Anna 等）其发型、脸型、五官、肤色、"
    "服装款式与配色必须与其定妆参考图完全一致；本页仅改变其表情与肢体动作以贴合剧情，"
    "严禁改动长相、发型、服装与配色，严禁凭空新增或减少角色。"
)


# v2.0 环境元素库 — 根据故事文本关键词推断场景应有的具体环境物体
_ENV_HINTS: list[tuple[str, str]] = [
    (r"classroom|class\b|desk|recess|school|teacher",
     "教室环境：暖米白空墙面（不要黑板、不要密集装饰）、一两张浅色课桌椅、单侧一扇明亮窗户射入柔和自然光、"
     "带淡蓝天空与窗外绿意、亮光浅米瓷砖地面（不要木地板）；背景极简整洁、适度留白、清爽不杂乱，主体人物干净突出"),
    (r"hallway|corridor",
     "走廊环境：延伸的空间感、暖米白墙面、单侧一排明亮窗户射入柔和自然光带窗外绿意、亮光浅米瓷砖地面，"
     "墙面极简少量点缀；背景整洁有序、适度留白、不杂乱"),
    (r"playground|outside|park|yard",
     "户外环境：柔和的浅绿草地、一两棵舒展的树、淡蓝天空与几朵白云、暖阳柔光，"
     "背景自然清新、极简整洁、不杂乱"),
    (r"home|house|bedroom|kitchen",
     "家庭环境：暖米白墙面、少量弱木纹浅色家具、窗台绿植、单侧窗柔光，"
     "亮光浅米瓷砖地面、少量温馨家居小物，背景极简整洁、适度留白"),
    (r"library|book",
     "图书馆/阅读角环境：弱木纹浅色书架配柔色书脊、暖米墙面、单侧窗柔光、可有绿植点缀，"
     "亮光浅米瓷砖地面，背景整洁、适度留白、不杂乱"),
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

# v5 机位角度（镜头语言）— 让画面随剧情变化，不再全本平视。
# 由 AI/老师按本页内容选；eye 为默认平视。
CAMERA_ANGLE_CN: dict[str, str] = {
    "eye": "平视机位（镜头与人物视线齐平），自然亲切，适合对话与情感交流",
    "high": "俯视机位（镜头从斜上方往下看），看清桌面/地面物件与场景布局，层次分明",
    "birdseye": "鸟瞰/正俯视机位（镜头从正上方垂直俯瞰），展现大场景全貌、地图、地形与空间格局",
    "low": "仰视机位（镜头从下往上看），强调高大宏伟（城堡/大树/高楼），画面更有气势",
    "over_shoulder": "越肩/主角视角（镜头越过主角肩膀或贴近主角视线），带观众代入主角去观察发现眼前事物",
}
DEFAULT_ANGLE = "eye"


def _angle_phrase(angle: str) -> str:
    a = (angle or "").strip().lower()
    return CAMERA_ANGLE_CN.get(a, "")

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
        ("max", "Max"),
        # 用户拍板 2026-06-07：Dino 不再作为画面故事角色（模型一画就崩）→ 不进检测
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
        (r"\b(?:dog|puppy|doggy)\b",         "dog"),
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


def _curated_ref_desc(key: str, ip_age: int, fallback_desc: str, fallback_ref):
    """单一事实源(IP 一致性核心)：角色形象与参考图统一走【ip_library】(用户提供的官方定妆库,
    含 8/10/12 三档真图),无论网页路径还是批量路径都用同一套图与描述,保证全书/跨书完全一致。
    ip_library 没有的角色(如 winnie)回退 character_registry。

    返回 (description_cn, ref_path)。
    """
    try:
        from ip_library import resolve_name_to_ip
        ip = resolve_name_to_ip(key, ip_age)
        if ip:
            desc = ip.desc or fallback_desc
            ref = ip.image_path if (ip.image_path and ip.image_path.exists()) else fallback_ref
            return desc, ref
    except Exception:
        pass
    return fallback_desc, fallback_ref


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
        # 用户拍板 2026-06-07：brand（Dino）不进画面，只作品牌角落 logo
        if char.get("kind") == "brand":
            continue
        names = [key.replace("_", " ")] + list(char.get("aliases", []))
        for name in names:
            if _re.search(rf"\b{_re.escape(name.lower())}\b", text_low):
                if key in found_keys:
                    break
                age_key = ip_age if char.get("kind") not in ("adult", "pet", "brand", "family") else \
                          next(iter(char.get("description_by_age", {}).keys()), "adult")
                en_desc = registry_get_desc(key, age_key) or ""
                desc_cn, ref = _curated_ref_desc(
                    key, ip_age,
                    _en_to_cn_desc(en_desc, key, age_key),
                    registry_get_ref(key, age_key),
                )
                out.append({
                    "name": name.capitalize(),
                    "key": key,
                    "description_cn": desc_cn,
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
            desc_cn, ref = _curated_ref_desc(
                default_key, ip_age,
                _en_to_cn_desc(en_desc, default_key, age_key),
                registry_get_ref(default_key, age_key),
            )
            out.append({
                "name": default_key.replace("_", " ").capitalize(),
                "key": default_key,
                "description_cn": desc_cn,
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
            8:  "薄紫色短袖T恤+浅蓝色阔腿卷边牛仔裤",
            10: "薄紫色长袖卫衣+浅灰色运动裤",
            12: "薄紫色长袖翻领针织衫+白色阔腿裤",
        }.get(age_n, "薄紫色上衣")
        return (
            f"Mia：{age_n}岁女孩，棕色长发束成一束高马尾在脑后（必须是马尾，不能散开），"
            f"前额碎刘海+少许鬓发框脸，穿{outfit}，白色运动鞋，"
            f"不戴手表/手链/项链/耳环/眼镜/帽子"
        )
    if key == "tommy":
        # 官方定妆图三档配色（用户拍板 2026-06-07，严格区分年龄）：
        #   8岁=蓝白横条纹短袖T+浅蓝长裤；10岁=【浅蓝】长袖卫衣+【卡其】裤；
        #   12岁=【深蓝/藏青】短袖polo+蓝色牛仔裤。深蓝polo是12岁专属，10岁绝不能穿。
        outfit = {
            8:  "蓝白横条纹短袖T恤+浅蓝色长裤",
            10: "浅蓝色长袖圆领卫衣+卡其色直筒长裤（绝不是深蓝、绝不是polo、绝不是牛仔裤）",
            12: "深蓝色（藏青）短袖polo翻领衫+蓝色牛仔裤",
        }.get(age_n, "浅蓝色长袖卫衣+卡其色长裤")
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
        # 单一事实源(registry / ip_library)：金色波浪齐肩发、不戴眼镜（旧版"栗色短发+黑框眼镜"是错的，已纠正）
        return "（成年女老师，约30岁，金色波浪齐肩发，蓝绿色眼睛，不戴眼镜）"
    if key == "winnie":
        return "（灰色虎斑小猫，白色肚皮，圆脸琥珀色大眼）"
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
    # Ali 官方是蓝T+卡其短裤（与 Tommy 蓝色冲突），无独占色 → 不设招牌色（用户拍板 2026-06-07 订正）
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
    "ali":     "Ali被画成深肤色或黑色卷发（应浅肤色+棕色短发）、Ali穿黄色上衣（应蓝色短袖T+卡其短裤）",
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
    # 头部/侧脸/发型连接处畸变（用户反馈：侧头时女孩头型/马尾根部明显出错）
    "畸形或不对称的头部、头骨/头型轮廓异常、后脑或头顶异常凸起鼓包、头部有多余的块状结构；"
    "发型与头部结构脱节、马尾或发辫根部与头皮连接处畸变错位、头发像贴上去的两层；"
    "侧脸或三四分之一脸的轮廓错误、侧面多出一只眼睛或五官错位重叠、脸部左右不对称、"
    "下巴变形、脖颈扭曲过长或过短、头与脖子衔接不自然；"
    "头身比例失调、头部过大、四肢过短或过长、躯干扭曲；"
    "成年化的儿童脸、肌肉发达的儿童身体；"
    "身体部位融合到背景中、肢体穿过物体；"
    "重影、模糊、人物失焦、低分辨率、像素化"
)

# v3.2 全局反向：风格/水印 + 解剖 + 质量
_GLOBAL_NEGATIVE = (
    "画面内任何文字、字母、数字、水印、签名、logo；"
    "塑料磨皮感、Q版贴纸风格、冰冷生硬的3D塑料渲染、厚重立体的体积塑形、强烈明暗光影、写实光影渐变、"
    "可见笔触纹理、水彩纸/纸张颗粒纹理、像素风、油画厚涂、廉价 CG 感；"
    # 印刷级干净控制（用户拍板）：去细碎/斑驳/脏块/不匀色块
    "细碎噪点、高频纹理、脏污颗粒、斑驳色块、明暗不匀的脏块、过多杂乱阴影、"
    "色彩不均匀、画面脏乱、密集小装饰；"
    # 画面整洁控制（图34材质：极简留白、暖米低饱和、空墙无黑板、瓷砖地不要木地板）
    "背景杂乱无序、胡乱堆砌的杂物、贴满杂物的墙面、众多有清晰五官的陌生路人同学、密集墙面装饰；"
    "黑板/绿板/白板写满字、深色木地板、深色木纹地面；"
    "高饱和浓郁刺眼色彩、厚重油画式明暗、生硬强烈对比、画面过暗压抑发闷；"
    # 用户拍板 2026-06-06：拒绝过锐化/过度调色/色彩断层等后期瑕疵
    "过度锐化、锐化光晕/描边伪影、过度调色、HDR 浓艳滤镜、色彩断层(banding)、色阶断裂、"
    "材质断裂残缺、质感突兀断变、画面发糊不通透；"
    # 反扁平（用户反复强调"太平坦"）：拒绝单层平涂、缺层次、呆板正面平视
    "扁平单层平涂、缺乏体积与明暗、画面扁平死板、所有元素挤在同一平面、缺乏前中后景层次与景深、"
    "呆板的正面平视证件照式构图、人物僵硬呆站面向镜头摆拍；"
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
     "一只毛茸茸的小仓鼠（体型很小、约人手掌大，绝不能画成猫狗大小；"
     "身体完整自然地待在画面里——趴在桌面/地面/手心或从角落探头，体态正常可爱，"
     "绝不要把仓鼠卡进、穿模或融进家具/桌缝/物体里）"),
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


def _make_protagonist_entry(k: str, ip_age: int) -> dict | None:
    """构造一个系列默认主角的 cast 条目（带年龄对应参考图 + 形象锁），供封面/NF 注入复用。"""
    if not CHAR_REGISTRY.get(k):
        return None
    desc_cn, ref = _curated_ref_desc(
        k, ip_age,
        _en_to_cn_desc(registry_get_desc(k, ip_age) or "", k, ip_age),
        registry_get_ref(k, ip_age),
    )
    return {
        "name": k.capitalize(),
        "key": k,
        "description_cn": desc_cn,
        "ref_path": ref,
        "is_generic": True,
    }


def book_style_anchor_ref() -> Optional[Path]:
    """全书基本画风锚图（官方水彩三人组定妆）。仅当某页无任何角色参考时作画风兜底，
    避免与角色单锚冲突（gpt-image-2 只吃一张参考图）。"""
    try:
        # STYLE_DIR = <root>/assets/style → <root>/references/official_style/...
        root = Path(STYLE_DIR).resolve().parent.parent
        p = root / "references" / "official_style" / "trio_style_anchor.png"
        return p if p.exists() else None
    except Exception:
        return None


def book_primary_anchor_ref(outline: BookOutline, ip_age: int) -> Optional[Path]:
    """全书「最强单锚」：返回贯穿全书的主角定妆参考图路径（不依赖 Streamlit）。

    选取规则：扫全书文本识别角色，优先 protagonist（mia/tommy/anna），取在标题+正文
    出现次数最多者的定妆图；非虚构无命名主角时回退 Mia。供批量路径把主角锁成首张参考。
    """
    try:
        all_text = (outline.title or "") + " " + " ".join((p.text or "") for p in outline.pages)
        cast = _detect_characters(all_text, ip_age)
        text_low = all_text.lower()
        protag = [c for c in cast if c.get("key", "").split("_")[0] in ("mia", "tommy", "anna") and c.get("ref_path")]
        if protag:
            best = max(protag, key=lambda c: text_low.count((c.get("name") or "").lower()))
            return best.get("ref_path")
        # 非虚构 / 无命名主角 → 系列默认主角 Mia
        e = _make_protagonist_entry("mia", ip_age)
        if e and e.get("ref_path"):
            return e["ref_path"]
    except Exception:
        pass
    return None


def validate_page_ip_lock(
    built: "BuiltPromptCN", outline: BookOutline, ip_age: int, page: PageSpec,
) -> list[str]:
    """出图前自检门（用户拍板 2026-06-07）：校验本页 cast 是否守住主角铁律。

    返回违规信息列表（空 = 通过）。供 batch_runner / web_app 在出图前断言：
      1. 同一角色不得重复（防分身）
      2. Dino 不得作为画面角色
      3. 应出现双主角的页面（封面 / 科普 / 以兄妹/家庭为中心的有人页面）必须同时含 Mia + Tommy
      4. Mia / Tommy 的参考图年龄档必须 = 级别对应 ip_age（防 10 岁画成 12 岁）
      5. cast ≤ 3 人
    """
    issues: list[str] = []
    cast = built.used_characters or []
    base_keys = [(c.get("key") or "").split("_")[0] for c in cast]

    # 1) 重复角色（同一 base key 出现多次）
    dup = {k for k in base_keys if base_keys.count(k) > 1}
    if dup:
        issues.append(f"重复角色（防分身）：{'、'.join(sorted(dup))}")

    # 2) Dino 不进画面
    if "dino" in base_keys:
        issues.append("Dino 不得作为画面故事角色")

    # 3) 应含双主角的页面
    is_cover = page.page_type == "cover" or page.index == 0
    page_has_person = any(
        (CHAR_REGISTRY.get((c.get("key") or "").split("_")[0]) or {}).get("kind")
        not in ("pet", "brand", None)
        for c in cast
    )
    # 官方 prompt 优先：纯寓言页（官方没点 Mia/Tommy）不应强制双主角，避免误报
    oip = getattr(outline, "official_image_prompt", None)
    official_raw = ""
    if oip is not None:
        try:
            official_raw = (oip.page_scene(page.index) or "").strip()
        except Exception:
            official_raw = ""
    if official_raw:
        low = _official_cast_text(official_raw).lower()
        official_names_leads = bool(_re.search(r"\b(mia|tommy)\b", low))
        # 有官方文本：仅当官方点到主角（或封面点到）才要求主角在场
        must_have_leads = official_names_leads
    else:
        must_have_leads = is_cover or _is_nonfiction(outline) or (
            _book_centers_on_leads(outline) and page_has_person
        )
    # 框架寓言纯故事页：他俩是读者、刻意不入场 → 不要求主角在场（避免误报）
    if _is_frame_fable(outline) and _frame_page_kind(
            outline, page, getattr(outline, "frame_mode", "A")) == "pure":
        must_have_leads = False
    if must_have_leads:
        for who in ("mia", "tommy"):
            if who not in base_keys:
                issues.append(f"应出现的主角缺失：{who}")

    # 4) 主角年龄档校验（参考图文件名应含 ip_age）
    for c in cast:
        base = (c.get("key") or "").split("_")[0]
        if base in ("mia", "tommy"):
            ref = str(c.get("ref_path") or "")
            if ref and str(ip_age) not in Path(ref).stem:
                issues.append(f"{base} 参考图年龄档不符（应 {ip_age} 岁）：{Path(ref).name}")

    # 5) 人数上限（只数 IP/注册角色；一次性角色不计入）
    n_main = sum(1 for c in cast if not c.get("is_oneoff"))
    if n_main > 3:
        issues.append(f"cast 超过 3 人（{n_main}）")

    return issues


def _is_nonfiction(outline: BookOutline) -> bool:
    """判断是否 non-fiction：优先看 fiction_type，其次看 reader_type 关键词。"""
    ft = (getattr(outline, "fiction_type", "") or "").strip().lower()
    if ft:
        return ft.startswith("non")
    rt = (getattr(outline, "reader_type", "") or "").strip().lower()
    return any(x in rt for x in ("non-fiction", "nonfiction", "informational"))


# 家庭/家人字样（出现 = 这是“一家人”的写实故事 → 配套的孩子必然是 Mia & Tommy）
_FAMILY_RE = _re.compile(
    r"\b(mom|mommy|mother|dad|daddy|father|grandma|granny|grandmother|"
    r"grandpa|grandfather|parents|family)\b|妈妈|爸爸|奶奶|爷爷|外婆|外公|爸妈|父母"
)
_LEADS_RE = _re.compile(r"\b(mia|tommy)\b")


def _book_centers_on_leads(outline: BookOutline) -> bool:
    """这本书是否「以系列兄妹主角 Mia & Tommy 为中心」。

    用户拍板 2026-06-07：
      · 非虚构科普 → 永远是 Mia & Tommy 当小小探索家（True）。
      · 正文点名 Mia / Tommy → 当然是他俩的故事（True）。
      · 出现家庭成员（妈妈/爸爸/爷爷/奶奶）→ 这是“一家人”的写实故事，
        配套的孩子必然是 Mia & Tommy（True）。
      · 纯经典童话（如 Goldilocks，全程没点名他俩、也没家人）→ False：
        他俩只在封面作为“阅读者/共演”双主角出现；内页沿用 girl→Mia / boy→Tommy
        通用映射（保证每个孩子都是 IP，但不硬塞第二位主角、避免画出两个相同的人）。
    """
    if _is_nonfiction(outline):
        return True
    all_text = (outline.title or "") + " " + " ".join(
        (p.text or "") + " " + (getattr(p, "scene", "") or "") for p in outline.pages
    )
    low = all_text.lower()
    return bool(_LEADS_RE.search(low) or _FAMILY_RE.search(low))


# ============================================================
#  框架式寓言（frame fable）：Mia/Tommy 是【读者】，寓言角色才是故事主角。
#  用户拍板 2026-06-07：读者不能同时是故事角色 —— 内页不得把他俩塞进寓言场景。
#  三种呈现模式（由 outline.frame_mode 选择）：
#    A     ：封面=他俩读书引子；内页全部纯故事（他俩不入场）。【默认·推荐】
#    B     ：每页都画“翻开的书+故事幻象”，他俩始终在画面一侧当读者。
#    Aplus ：封面 + 首页开场读书 + 末页合书收尾；中间页纯故事。
# ============================================================
_FRAME_MARKER = _re.compile(
    r"fable book|magic storybook|story ?book|glowing book|the book|opening the|"
    r"starting to read|reading the|story vision|vision of the story|a vision|"
    r"from the (?:glowing )?book|inside the book|pages of the book",
    _re.IGNORECASE,
)


def _is_frame_fable(outline: BookOutline) -> bool:
    """是否「框架式寓言」：有反复出场的非 IP 寓言主角 + 文本含'读书/幻象'框架标记。

    有官方 prompt → 用官方逐页文本判定（最准）；
    无官方 prompt（新书只有正文）→ 回退用故事正文 + 标题判定（book_cast 已支持纯文本识别）。
    """
    if _is_nonfiction(outline):
        return False
    bc = getattr(outline, "book_cast", None) or {}
    if not any(getattr(r, "needs_anchor", False) for r in bc.values()):
        return False
    oip = getattr(outline, "official_image_prompt", None)
    txt = (outline.title or "")
    if oip is not None:
        for p in outline.pages:
            try:
                txt += " " + (oip.page_scene(p.index) or "")
            except Exception:
                pass
        return bool(_FRAME_MARKER.search(txt))
    # story-only（新书只有正文）：
    for p in outline.pages:
        txt += " " + (p.text or "") + " " + (getattr(p, "scene", "") or "")
    if _FRAME_MARKER.search(txt):
        return True
    # 回退：纯寓言（有非 IP 寓言主角、且全程没有人类主角 Mia/Tommy / 家人）→ 也按框架处理，
    #       让兄妹作为读者出现（满足系列"每本都有 Mia/Tommy"，又不把他俩塞进寓言场景）。
    low = txt.lower()
    return not (_LEADS_RE.search(low) or _FAMILY_RE.search(low))


def _last_story_index(outline: BookOutline) -> int:
    """最后一个有内容的故事页 index（跳过补白空页）。"""
    oip = getattr(outline, "official_image_prompt", None)
    last = 0
    for p in outline.pages:
        has = bool((p.text or "").strip())
        if not has and oip is not None:
            try:
                has = bool((oip.page_scene(p.index) or "").strip())
            except Exception:
                has = False
        if p.index > 0 and has:
            last = p.index
    return last


def _frame_page_kind(outline: BookOutline, page: PageSpec, mode: str) -> str:
    """框架寓言里本页的呈现类型：'frame'（他俩读书/幻象框架）或 'pure'（纯故事，他俩不入场）。"""
    is_cover = page.page_type == "cover" or page.index == 0
    mode = (mode or "A").upper().replace("APLUS", "A+")
    if mode == "B":
        return "frame"
    if is_cover:
        return "frame"
    if mode == "A+":
        return "frame" if page.index in (1, _last_story_index(outline)) else "pure"
    # mode A：封面之外全部纯故事
    return "pure"


def _scrub_leads_clause(s: str) -> str:
    """从寓言场景文本里删掉提及 Tommy/Mia 的句子（读者不进故事幻象内容）。"""
    if not s:
        return s
    parts = _re.split(r"(?<=[。.!?！？\n])", s)
    kept = [p for p in parts if not _re.search(r"\b(tommy|mia)\b", p, _re.IGNORECASE)]
    out = "".join(kept).strip()
    return out or s


def _vision_frame_wrapper(tale_scene: str) -> str:
    """把纯寓言场景包成「他俩在画面一角捧书阅读 + 故事从书页升起为发光幻象」的框架画面。

    用户拍板 2026-06-07：发光幻象（故事内容）是画面主体，占约 75%（60–80%）且【铺满画面】；
    读者 Mia/Tommy 缩到画面一角，约占 20–25%——明显比故事小，但仍清晰可见、不可过小。
    """
    return (
        "画面采用【读者框架】构图，且【故事幻象是画面绝对主体】：\n"
        "① 故事幻象（核心）——从翻开的魔法书页中升起的柔和发光故事幻象，"
        "占据整幅画面约 75%（不少于 60%、不超过 80%）的主要区域，是画面的视觉中心与主角，"
        "且【必须铺满画面、延伸到画面上/右/上方各个边缘】，把故事场景画满、画细腻、有纵深，"
        "呈现以下故事内容：" + tale_scene.rstrip("。") + "。\n"
        "② 读者（次要、缩小）——Mia 和 Tommy 只占画面【左下角】很小一块（约 20–25%），"
        "明显小于故事幻象，一起捧着 / 翻开那本会发光的魔法故事书在专注阅读，神情投入好奇；"
        "他们要清晰可辨、但不可过大、不可与故事幻象平分画面，更不可比故事还显眼。\n"
        "③ 他们始终是【读者】，绝不进入故事、绝不与故事角色互动或处在同一场景里；"
        "幻象与现实读书区之间只用一道很细的柔和光晕过渡，"
        "【除左下角读者那一小块外，其余画面全部被故事幻象填满，不留大片空白纸面/米色底/留白边】。"
    )


# ============================================================
#  故事连续性层（用户拍板 2026-06-07）：画面必须跟住故事的连续设定。
#  典型坑：官方只在部分页标了「Rainy variant」，导致同一场雨里中间页突然放晴。
#  解决：扫全书天气/时间线索，把"同一场持续天气"贯穿到区间内的所有户外页。
# ============================================================
_RAIN_RE = _re.compile(
    r"\b(rain|rainy|raining|storm|stormy|pour|pouring|downpour|drizzle|thunder|"
    r"soaked|drenched|wet (?:forest|ground|path|grass))\b|暴雨|大雨|下雨|雨中|雨水",
    _re.IGNORECASE)
_SNOW_RE = _re.compile(r"\b(snow|snowy|snowing|blizzard|snowstorm)\b|下雪|大雪|雪中", _re.IGNORECASE)
# 仅当主角真正"进入遮蔽/安全干燥处"时才排除天气延续。
# 用 "inside the … cave/den/home" 这种【已在里面】的措辞；
# 不匹配 "could not fit inside"(还在外面) 或 "find a dry cave"(还没进去)。
_INSIDE_RE = _re.compile(
    r"inside (?:the|a|its|his|her) (?:\w+\s+){0,2}(?:cave|den|burrow|hole|house|home|room|nest)|"
    r"\b(?:indoors|safe and dry|warm and dry|feels like home)\b|"
    r"洞里|洞内|室内|屋里|家里|安全干燥",
    _re.IGNORECASE)


def _page_full_text(outline: BookOutline, page: PageSpec) -> str:
    t = (page.text or "") + " " + (getattr(page, "scene", "") or "")
    oip = getattr(outline, "official_image_prompt", None)
    if oip is not None:
        try:
            t += " " + (oip.page_scene(page.index) or "")
        except Exception:
            pass
    return t


def _weather_arc(outline: BookOutline) -> tuple[set[int], set[int]]:
    """返回 (应下雨的页 index 集合, 应下雪的页 index 集合)。

    规则：找出明确出现某天气的页区间 [首次, 末次]，把区间内所有【户外页】都补上该天气，
    保证"同一场雨/雪"连续不中断；室内/洞内/已遮蔽页不强加。
    """
    def arc(rex: _re.Pattern) -> set[int]:
        hits = [p.index for p in outline.pages if rex.search(_page_full_text(outline, p))]
        if not hits:
            return set()
        lo, hi = min(hits), max(hits)
        out = set()
        for p in outline.pages:
            if lo <= p.index <= hi and not _INSIDE_RE.search(_page_full_text(outline, p)):
                out.add(p.index)
        return out
    return arc(_RAIN_RE), arc(_SNOW_RE)


def _continuity_note(outline: BookOutline, page: PageSpec) -> str:
    """本页若处于持续天气区间，返回一段"场景连贯"指令（不要突然放晴/变天）。"""
    if page.page_type == "cover" or page.index == 0:
        return ""
    rainy, snowy = _weather_arc(outline)
    if page.index in rainy:
        return (
            "【场景连贯·同一场雨】本页延续故事里同一场持续的雨：天色阴沉发灰、细密雨丝斜落、"
            "地面湿润泛光有小水洼、空气朦胧带薄雾；户外角色毛发/衣服带被雨打湿的潮湿感"
            "（仍保持清晰、可爱、友善）。务必与前后页天气一致，绝不突然放晴、绝不出现明亮蓝天大太阳。"
        )
    if page.index in snowy:
        return (
            "【场景连贯·同一场雪】本页延续故事里同一场雪：天色清冷、雪花飘落、地面与枝叶积雪，"
            "与前后页同一场雪连续，绝不突然放晴变成无雪场景。"
        )
    return ""


def _official_positive(raw: str) -> str:
    """取官方每课 prompt 的【正向部分】：截掉 `--ar` / `--no`（参数与负向词）之后的内容，
    并优先取 `**Prompt:**` 之后的画面描述（跳过 `Page N` / `**Text:**` 前缀）。

    关键：官方负向区常写 `--no text, ... , Tommy, Mia`（明确要求纯寓言页**不要**画主角），
    若不剔除会把"Tommy, Mia"误判成在场。
    """
    if not raw:
        return ""
    s = raw
    m = _re.search(r"\*\*\s*Prompt\s*:\s*\*\*", s)
    if m:
        s = s[m.end():]
    # 截掉 Midjourney 风格参数与负向区（--ar / --no / --v 等）
    s = _re.split(r"--(?:ar|no|v|niji|q|s|style)\b", s, maxsplit=1)[0]
    return s.strip()


def _scrub_official_scene(s: str) -> str:
    """清洗官方画面参考文本：只取正向、去 markdown、剔除含 Dino 的句子（不进画面）、限长。"""
    if not s:
        return ""
    s = _official_positive(s)
    s = s.replace("**", "").replace("> ", "").replace("`", "").strip()
    parts = _re.split(r"(?<=[。.!?！？\n])", s)
    parts = [p for p in parts if "dino" not in p.lower()]
    s = "".join(parts).strip()
    return s[:300]


# 官方 prompt 文本里可能出现的 IP 角色（别名 → registry key）。
# 非 IP 寓言/动物角色（gingerbread man / fox / bears / wolf…）不在此列——
# 它们由场景文字驱动、按本色画（并做儿童向柔化），绝不映射成 Mia/Tommy。
_OFFICIAL_IP_ALIASES: list[tuple[str, str]] = [
    ("tommy", "tommy"), ("mia", "mia"), ("anna", "anna"),
    ("cate", "cate"), ("ali", "ali"),
    ("grandma", "grandma"), ("grandmother", "grandma"), ("granny", "grandma"),
    ("grandpa", "grandpa"), ("grandfather", "grandpa"),
    ("mommy", "mom"), ("mother", "mom"), ("mom", "mom"),
    ("daddy", "dad"), ("father", "dad"), ("dad", "dad"),
    # 只认 IP 老师的专名 Ms./Teacher Kim；裸词 "teacher" 不再映射成 Teacher Kim，
    # 否则 "his teacher / a teacher"（剧情里的普通老师）会被误配成金发 IP（用户拍板 2026-06-07）。
    ("ms. kim", "teacher_kim"), ("teacher kim", "teacher_kim"), ("kim", "teacher_kim"),
    ("max", "max"), ("winnie", "winnie"),
]

# "X 不在画面/仅手部/背景剪影" 之类的从句——选角时必须剔除，
# 否则官方明写 "Tommy is not in the frame" 也会把 Tommy 当在场主角塞进去（用户拍板 2026-06-07）。
_NEG_PRESENCE = _re.compile(
    r"[^.!?\n]*\b(?:not in (?:the )?frame|is not in|are not in|isn't in|aren't in|"
    r"no longer in|not visible|without)\b[^.!?\n]*",
    _re.IGNORECASE,
)


def _official_cast_text(raw: str) -> str:
    """官方正向文本（去掉"某角色不在画面"的从句），专供"谁在场"的选角判定。"""
    return _NEG_PRESENCE.sub(" ", _official_positive(raw))


# 可能被画凶/吓人的主体（动物/反派）——出现时主动做"儿童向柔化"，永远 friendly 可爱。
_SCARY_SUBJECTS = _re.compile(
    r"\b(fox|wolf|wolves|bear|bears|lion|tiger|shark|snake|crocodile|alligator|"
    r"dragon|monster|giant|ogre|witch|ghost|goblin|troll|spider|dinosaur|"
    r"big bad|beast|creature)\b",
    _re.IGNORECASE,
)


def _child_safe_softening(scene_text: str) -> str:
    """检测场景里的动物/反派 → 返回一段'儿童向柔化'正向指令（去凶相/獠牙/恐怖）。

    用户拍板 2026-06-07：绘本要去恐怖/丑陋/暴力——即便是狐狸/狼/反派，
    也一律画成 friendly、可爱、表情温和，绝不獠牙凶相、绝不吓到孩子。
    """
    if not scene_text or not _SCARY_SUBJECTS.search(scene_text):
        return ""
    return (
        "【儿童向柔化·底线】本页若出现动物或'反派'角色（如狐狸/狼/熊等），"
        "一律画成 friendly、可爱、圆润亲和的卡通形象，表情温和友善、眼神柔和、嘴角自然微笑；"
        "绝不露出尖牙獠牙利齿、绝不张血盆大口扑咬、绝不怒目凶光或狰狞吓人；"
        "整体氛围温暖治愈、安全无攻击性，适合低龄儿童观看，绝不制造恐怖、惊悚、丑陋或暴力感。"
    )


def _make_cast_entry(key: str, ip_age: int) -> dict | None:
    """通用 cast 条目构造器（任意 registry key）：自动按 kind 选年龄档，挂 ip_library/registry 形象与参考图。"""
    char = CHAR_REGISTRY.get(key)
    if not char:
        return None
    age_key = ip_age if char.get("kind") not in ("adult", "pet", "brand", "family") else \
        next(iter(char.get("description_by_age", {}).keys()), "adult")
    en = registry_get_desc(key, age_key) or ""
    desc_cn, ref = _curated_ref_desc(
        key, ip_age, _en_to_cn_desc(en, key, age_key), registry_get_ref(key, age_key),
    )
    return {
        "name": key.replace("_", " ").capitalize(),
        "key": key,
        "description_cn": desc_cn,
        "ref_path": ref,
        "is_generic": False,
    }


def _cast_from_official(official_raw: str, ip_age: int) -> list[dict]:
    """从官方每课 prompt 的本页文本提取【在场的 IP 角色】（这是权威的'谁在场'文学分析）。

    用户拍板 2026-06-07：官方 prompt 已经写明本页谁在场（如封面 'Tommy and Mia'、
    内页 'The Gingerbread Man' / 'Pure fable world'）。出图时**以官方点名为准**：
      · 官方点到的 IP（Tommy/Mia/Grandma/…）→ 挂对应级别年龄的定妆锚图。
      · 官方没点到主角的页面（纯寓言页）→ 返回空，不强塞 Mia/Tommy。
      · 非 IP 寓言/动物角色不进 cast（由场景文字驱动、按本色画 + 儿童向柔化）。
    """
    low = _official_cast_text(official_raw).lower()
    found: set[str] = set()
    out: list[dict] = []
    for alias, key in _OFFICIAL_IP_ALIASES:
        if key in found:
            continue
        if _re.search(rf"\b{_re.escape(alias)}\b", low):
            e = _make_cast_entry(key, ip_age)
            if e:
                out.append(e)
                found.add(key)
    return out[:3]


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

    # 0) 官方每课 prompt：本页权威文本（已含"谁在场"的文学分析）
    oip = getattr(outline, "official_image_prompt", None)
    official_raw = ""
    if oip is not None:
        try:
            official_raw = (oip.page_scene(page.index) or "").strip()
        except Exception:
            official_raw = ""
    official_has_scene = bool(official_raw)

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

    # ============================================================
    #  系列主角铁律（用户拍板 2026-06-07）
    #  Mia + Tommy 是【每一本书】锁定的兄妹主角，必须按级别年龄出现
    #  （L0-2=8 / L3-4=10 / L5-6=12），衣服/脸型/身高/发型完全锁 IP。
    #
    #  规则：
    #   · 封面 & 非虚构：永远同时带上 Mia + Tommy（保证每本书都有他俩）。
    #   · 以他俩/家庭为中心的故事（正文点名 Mia/Tommy，或出现妈妈/爸爸/爷爷/奶奶）：
    #       每一页只要画面里有“人”，就强制把 Mia + Tommy（对应年龄定妆）放进本页，
    #       再带上本页点名的配角（如 Grandma / Anna），去重、最多 3 人，主角形象锁优先。
    #   · 纯经典童话（全书没点名他俩、也没家人，如 Goldilocks）：内页沿用
    #       girl→Mia / boy→Tommy 通用映射（保证每个孩子都是 IP，但不硬塞第二位主角，
    #       避免画出两个一模一样的人）。
    # ============================================================
    def _inject_leads(base_cast: list[dict]) -> list[dict]:
        """把 Mia + Tommy（按 ip_age 取对应年龄定妆图）置于队首，再并入已有配角，去重，≤3 人。"""
        pair = [
            e for k in ("mia", "tommy")
            for e in (_make_protagonist_entry(k, ip_age),) if e
        ]
        lead_keys = {e.get("key") for e in pair}
        rest_named = [c for c in base_cast
                      if not c.get("is_generic") and c.get("key") not in lead_keys]
        rest_generic = [c for c in base_cast
                        if c.get("is_generic") and c.get("key") not in lead_keys]
        return (pair + rest_named + rest_generic)[:3]

    def _is_person_entry(c: dict) -> bool:
        ch = CHAR_REGISTRY.get((c.get("key") or "").split("_")[0])
        return bool(ch) and ch.get("kind") not in ("pet", "brand")

    # 框架寓言判定（用户拍板 2026-06-07）：他俩是读者，内页不得入故事场景。
    _frame_fable = _is_frame_fable(outline)
    _frame_kind = None
    if official_has_scene:
        # ★ 官方权威优先（用户拍板 2026-06-07）：本页"谁在场"以官方 prompt 点名为准。
        #   纯寓言页（官方没点到 Mia/Tommy）→ 不强塞主角；封面若官方漏写主角则补全双主角。
        cast = _cast_from_official(official_raw, ip_age)
        if _frame_fable:
            _frame_kind = _frame_page_kind(outline, page, getattr(outline, "frame_mode", "A"))
            if _frame_kind == "pure":
                # 纯故事页：移除主角（读者不入场），只留寓言角色（由 book_cast 注入锚图）
                cast = [c for c in cast if c.get("key") not in ("mia", "tommy")]
            else:
                # 框架页：确保双主角作为【读者】在场（置顶），寓言角色作幻象（book_cast 注入）
                cast = _inject_leads(cast)
        elif is_cover and not any(c.get("key") in ("mia", "tommy") for c in cast):
            cast = _inject_leads(cast)
    else:
        _book_leads = _book_centers_on_leads(outline)
        _page_has_person = any(_is_person_entry(c) for c in cast)
        if is_cover or _is_nonfiction(outline):
            # 封面 / 科普：两位主角永远同框
            cast = _inject_leads(cast)
        elif _book_leads and _page_has_person:
            # 家庭/写实故事的内页：只要有人，兄妹双主角必到场（修掉“孩子没锚图→年龄漂移/乱入Anna”）
            cast = _inject_leads(cast)
        # else: 纯童话内页 —— 保留通用映射（girl→Mia / boy→Tommy），单主角即可，不强制第二位

    # 2) 场景描述
    if is_cover:
        who = "、".join(c.get("name", "") for c in cast if c.get("name")) or "系列主角 Mia、Tommy"
        theme = (getattr(outline, "theme", "") or "").strip()
        nf = _is_nonfiction(outline)
        cover_action = (
            f"{who} 作为系列小小探索家，正投入地在与主题相关的真实场景中观察、指认或眺望眼前的事物"
            if nf else
            f"{who} 一起投入在与故事主题相关的一个生动瞬间里——在做某件具体的事/彼此互动，神情自然鲜活，"
            "绝不是面向镜头并排站着摆拍"
        )
        scene_cn = (
            f"绘本封面，书名《{title}》" + (f"，主题：{theme}" if theme else "") + "。"
            f"{cover_action}；用有设计感的电影式取景——人物七分身或全身、带自然角度"
            "（三四分之一侧身，或轻微俯视/仰视/越肩主角视角，绝不正面呆板平视），"
            "前景—中景—背景拉出清晰的远近层次与景深，画面通透、有空间纵深与故事氛围，像高级精印实体绘本的封面；"
            "人物适度偏置于画面一侧，画面上方保留大片干净的浅色原生留白区域（天空/远景等）用于排书名标题。"
        )
    else:
        if official_has_scene:
            # ★ 官方为本页权威场景（已含"He=饼干人/狐狸/爸爸"等正确指代）；
            #   不叠加可能误解角色的 AI scene_cn，避免把寓言角色画成男孩。
            scene_cn = _scrub_official_scene(official_raw)
            if _frame_fable and _frame_kind == "pure":
                # 纯故事页：把"他俩在读书"的句子清掉，画面只有寓言角色的故事
                scene_cn = _scrub_leads_clause(scene_cn)
            elif _frame_fable and _frame_kind == "frame":
                # 框架页：他俩一侧读书 + 故事以发光幻象升起（读者不入故事）
                scene_cn = _vision_frame_wrapper(_scrub_leads_clause(scene_cn))
        else:
            scene_cn = _scene_to_cn(page, outline)
        # Non-fiction：把双主角作为"小小探索家"自然织入画面（主人公视角贯穿全书）
        if _is_nonfiction(outline) and cast:
            names = "和".join(c["name"] for c in cast if c.get("name"))
            if names:
                scene_cn = (
                    scene_cn.rstrip("。") +
                    f"。画面以 {names} 作为系列小小探索员的主人公视角来呈现这页科普内容："
                    f"{names} 一起在现场观察、用手指认、俯身细看或眺望眼前的事物，神情专注好奇、自然融入真实场景，"
                    "带着小读者一起去发现（他们是贯穿全书的学习者/探索者视角）；"
                    "科普对象（地理/动植物/自然现象等）按真实比例与真实科学样貌如实呈现，"
                    "镜头随内容选取最能说明事物的角度（看地理/全貌用俯视或鸟瞰、看细节用特写或越肩主角视角），主角不喧宾夺主。"
                )

    # 2.5) 封面：官方封面文本作为校准参考注入（内页已把官方设为主场景，无需重复叠加）。
    if is_cover and official_has_scene:
        off = _scrub_official_scene(official_raw)
        if off:
            scene_cn = (
                scene_cn.rstrip("。") +
                "。【官方封面参考·按此校准构图/场景/动作/道具（人物仍严格以参考图为准锁脸，"
                "画风仍干净平滑统一的治愈水彩，不照搬官方文字里的画风/负面词）】：" + off
            )

    # 2.6) 故事连续性层：把同一场雨/雪等持续天气贯穿到区间内的户外页（防中间页突然放晴）
    _cont = _continuity_note(outline, page)
    if _cont:
        scene_cn = scene_cn.rstrip("。") + "。" + _cont

    # 3) 镜头 + 机位角度（v5）
    shot = (page.shot or DEFAULT_SHOT).strip().lower()
    if shot not in COMPOSITION_CN:
        shot = DEFAULT_SHOT
    composition_cn = COMPOSITION_CN[shot]
    angle_cn = "" if is_cover else _angle_phrase(getattr(page, "camera_angle", "") or "")
    focus_cn = "" if is_cover else (getattr(page, "focus", "") or "").strip()
    hook_cn = "" if is_cover else (getattr(page, "hook", "") or "").strip()

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
        angle_cn=angle_cn,
        focus_cn=focus_cn,
        hook_cn=hook_cn,
    )

    # 8) ============ v3: 组装反向 prompt（分类禁忌）============
    negative = _build_negative_v3(cast=cast, page_text=(page.text or ""), ip_age=ip_age)

    # 9) 最终 prompt = 正向 + 反向
    prompt_text = BuiltPromptCN.join(positive, negative)

    # 10) 参考图策略（v2.1：本页 cast 里每人 1 张，最多 3 张）
    refs: list[Path] = []
    for c in cast:
        if c.get("ref_path") and len(refs) < 3:
            refs.append(c["ref_path"])

    # 10.5) 书内角色册（用户拍板 2026-06-07）：一次性/非 IP 角色的"书内锁"。
    #   反复出场角色 → 注入全书统一外观描述（防跨页漂移）+ 挂书内定妆锚图（与 IP 同等锁死）。
    extra_note, extra_refs, oneoff_cast = _apply_book_cast(
        outline, page, official_raw, current_refs=len(refs))
    if extra_note:
        prompt_text = prompt_text + "\n\n" + extra_note
    for rp in extra_refs:
        if len(refs) < 3:
            refs.append(rp)

    return BuiltPromptCN(
        positive=positive,
        negative=negative,
        prompt=prompt_text,
        references=refs,
        used_characters=cast + oneoff_cast,
    )


def _apply_book_cast(outline, page, official_raw: str, current_refs: int):
    """书内角色册接线：返回 (注入的锁定描述文本, 追加的锚图路径列表, 调试用一次性 cast)。

    一次性角色【永不映射成 Mia/Tommy】；这里只为它们补"全书统一外观 + 书内锚图"。
    """
    book_cast = getattr(outline, "book_cast", None)
    if not book_cast:
        return "", [], []
    try:
        from book_cast import roles_on_page
        roles = roles_on_page(book_cast, official_raw)
    except Exception:
        return "", [], []
    if not roles:
        return "", [], []

    lines, extra_refs, dbg = [], [], []
    for r in roles:
        desc = (r.desc_en or "").strip()
        tag = f"【一次性角色·全书形象锁定】{r.display}"
        if desc:
            tag += f"：{desc}"
        tag += ("（本故事内每次出现都必须是同一个角色：脸型/发型/发色/肤色/服装/配色完全一致；"
                "儿童绘本风格，友善可爱、绝不凶恶吓人）")
        lines.append(tag)
        if r.anchor_path and (current_refs + len(extra_refs)) < 3:
            ap = Path(r.anchor_path)
            if ap.exists():
                extra_refs.append(ap)
        dbg.append({"key": f"oneoff:{r.rid}", "name": r.display, "is_oneoff": True})
    return ("\n".join(lines), extra_refs, dbg)


# ============================================================
#  v3 正向 prompt 构造（火山风单段流畅）
# ============================================================

def _build_positive_v3(
    *, is_cover: bool, title: str, scene_cn: str, cast: list[dict], ip_age: int,
    env_hint: str, key_props: list[str], composition_cn: str, blank_cn: str,
    angle_cn: str = "", focus_cn: str = "", hook_cn: str = "",
) -> str:
    """生成分层、关键约束前置加权的正向 prompt。

    v4 重构（2026-06-03）：把「本页画面动作 + 角色形象锁」置顶（gpt-image-2 对前置内容
    遵循度更高），风格/安全等"氛围块"压缩并后置，整体从 ~15 段降到 ~8 段，
    画风对齐「图34材质」：更薄更透的吉卜力风水彩 + 暖米低饱和 + 单侧窗柔光 + 空墙无黑板 +
    亮光瓷砖地 + 弱木纹 + 背景极简适度留白（清透干净，但不惨白、不压暗）。
    """
    parts: list[str] = []
    names = "、".join(c.get("name", "") for c in cast if c.get("name"))
    n_kids = len([c for c in cast if c.get("name")])

    # ① 本页画面（核心，最高权重，绝对置顶）
    if is_cover:
        parts.append(
            f"【画面 · 绘本封面 · 最高优先级】{(scene_cn or '').rstrip('。')}。"
            "封面要高级、有设计感、有故事感与空间纵深，绝不是几个人正面并排呆站摆拍的扁平合影；"
            "镜头自然带角度、画面分前中后景，人物生动投入在情境里、神情自然友好；画面上方保留干净留白用于排书名。"
        )
    else:
        parts.append(
            f"【本页画面 · 必须如实呈现，最高优先级】{scene_cn.rstrip('。')}。"
            f"请严格按这段描述的动作、姿势、视线与站位作画——这是本页最重要、绝不能画错的内容。"
        )

    # ①.2 焦点/高潮（把本页最有张力的那一下做成画面主体，居中、动态、有层次）
    if not is_cover and focus_cn:
        parts.append(
            f"【画面焦点 · 主体动作】本页的视觉主体与高潮是：{focus_cn.rstrip('。')}。"
            "把这个动作作为画面的中心主体来构图——主角居中偏前、占据最大视觉权重，"
            "用动态有张力的姿态（伸手/俯身/奔跑/惊喜等）把这一刻演出来，表情到位、情绪鲜活；"
            "并拉开前景—中景—背景的清晰层次、用浅景深把焦点落在这个主体动作上（主体清晰、背景柔和虚化），"
            "让孩子一翻到这页就立刻被这一下抓住，绝不是呆板平铺、人物呆站。"
        )

    # ①.5 机位角度（镜头语言，让画面随剧情变化、有高级感）
    if not is_cover:
        if angle_cn:
            parts.append(f"【机位角度】采用{angle_cn}；镜头语言要贴合本页剧情，避免呆板的正面平视。")
        else:
            # 兜底（用户反馈：虚构书也不能全平视）——AI 未指定角度时仍强制反扁平
            parts.append(
                "【机位角度】按本页剧情自然选取一个有纵深、有镜头语言的视角"
                "（如三四分之一侧角 / 轻微俯视或仰视 / 越肩主角视角），并把前中后景拉开，"
                "避免呆板的正面平视与所有元素挤在同一平面。"
            )

    # ② 角色形象锁（IP 外观；发型/服装/配色为识别核心，紧跟画面之后）
    for c in cast:
        parts.append(f"【{c.get('name','')} 形象锁定】{(c.get('description_cn') or '').rstrip('。')}。")
    if cast:
        parts.append(
            f"外观铁律：{names} 的发型、发色、服装与颜色、五官、配饰一律以上面各自的形象锁定与参考图为准、"
            "且全书逐页保持一致；画面动作描述里若出现冲突的外观（多余眼镜、不同发型或衣色），一律忽略、以形象锁定为准。"
        )
        # 全本一致性硬规则（跨页/跨书身份与配色锁定 + 统一光影色温）——之前写好但未启用
        parts.append("【全本一致】" + consistency_prompt_cn())

    # ③ 人数 + 年龄锁 + 比例 + 同尺度（合并成一句精炼硬约束）
    if cast:
        line = (
            f"人物与年龄（硬约束·绝不能错）：画面里的儿童只能是 {names}，"
            f"且每个孩子都必须是【{ip_age} 岁】的样子——身高、脸型、身材比例都要符合 {ip_age} 岁"
            f"（{'12 岁是青春期前的少年/少女，身形修长、个子较高，绝不是矮小幼态的低龄小童' if ip_age >= 12 else ('10 岁是学龄期儿童' if ip_age >= 10 else '8 岁是低龄学童')}）；"
            f"不要出现有清晰五官/发型的陌生同学或路人（最多远景一两个极淡的人影剪影，可省略），不要凭空新增别的小孩；"
            f"主角（群体）居中、是画面视觉焦点、占画面高度约 50-60%；"
            f"{_head_body_ratio_lock(ip_age)}；每只手 5 根手指、关节自然、双眼对称、五官端正不歪斜；"
            "头部与脖颈结构自然正确、头型圆润对称、头发与头部自然衔接（马尾/发辫根部连接处准确），"
            "侧脸或侧头视角下轮廓与五官也要准确、不变形不重叠。"
        )
        if n_kids >= 2:
            line += "多个同龄主角必须同尺度、同景深、站在同一水平面，谁都不能比旁边的人明显大一圈。"
        # 反分身铁律（用户反馈 Goldilocks 出现“两个一模一样的 Mia”）
        line += (
            "【绝不分身】同一个角色在整张画面里只能出现一次——"
            "严禁出现两个长相相同或同一身份的人物（例如两个 Mia、两个 Tommy、主角的分身/双胞胎/镜像），"
            "也不要让主角既站在前景又出现在背景里。"
        )
        parts.append(line)

    # ④ 环境（温馨充实而整洁，给具体锚点）
    if env_hint:
        parts.append("【环境】" + env_hint.replace("（必须可见）", "").rstrip("。") + "。")

    # ⑤ 关键道具
    if key_props:
        parts.append("画面里应出现：" + "；".join(key_props) + "。")

    # ⑤.5 画面 hook（趣味彩蛋，增强绘本"抓人"细节，但不抢主体焦点）
    if not is_cover and hook_cn:
        parts.append(
            f"【趣味细节 hook】在画面合适的角落/远景自然加入一个有趣的小彩蛋：{hook_cn.rstrip('。')}。"
            "要可爱温馨、贴合剧情，小巧精致地点缀（小道具/小动物/小动作），绝不抢占主角的视觉焦点。"
        )

    # ⑥ 配色锁定（每个有专属色的角色）
    color_locks = [
        f"{c['name']}是画面里唯一穿{_signature_color_of(c['key'])}的人"
        for c in cast if _signature_color_of(c["key"])
    ]
    if color_locks:
        parts.append("配色锁定：" + "；".join(color_locks) + "。")

    # ⑥.5 儿童向柔化（动物/反派一律 friendly 可爱，去獠牙/凶相/恐怖）
    _soft = _child_safe_softening(scene_cn)
    if _soft:
        parts.append(_soft)

    # ⑦ 画风（细腻治愈水彩 + 柔和层次景深 + 暖米低饱和 + 明亮柔光 + 高级感可打印）
    parts.append(
        "【画风】" + STYLE_CN.split("。")[0] + "。"
        "干净细腻的治愈水彩（柔和晕染、克制而精致的明暗体积，前中后景有空间层次与景深：近景清晰精致、远景柔和虚化）、"
        "精致清晰的细墨线；暖米低饱和主调 + 柔和莫兰迪点缀，明亮柔光、阴影浅淡干净；"
        "画面细腻干净、过渡自然、颜色匀净，细腻而不细碎——无脏色斑、无破碎色块、无噪点颗粒，边缘线条清晰锐利、可高分辨率印刷不模糊；"
        "背景精致整洁、适度留白，主体人物干净突出、边缘清晰、上色细腻有层次；"
        "笔触干净利落、色面洁净均匀——绝无脏点、污渍、墨点、杂色斑、灰扑扑的脏块或可见颗粒，整体清透高级；"
        "人物穿着得体的日常服装、适合儿童，画面像高品质精印实体绘本的内页，阳光健康温暖、高级耐看。"
    )

    # ⑦.1 立体感/反扁平（用户反复强调"更高级、更立体、别全是扁平平视"）— 仍锁死水彩、不滑向塑料3D
    parts.append(
        "【立体层次·反扁平】画面要有明确的空间纵深与体积感（高级绘本质感，绝不是扁平贴纸/单层平涂）："
        "用柔和水彩的明暗渐层为人物与主体塑出轻盈而清晰的体积与受光面、暗面，"
        "前景—中景—背景分出清晰的远近层次与景深（近实远虚），加一点点环境投影/地面接触阴影让人物稳稳落在场景里；"
        "镜头取景错落有致、有纵深引导，避免呆板正面平视与所有元素挤在同一平面。"
        "（注意：是水彩式的柔和体积与景深，不是厚重油画、不是塑料3D渲染、不是强烈硬光影。）"
    )

    # ⑦.2 画质精修（用户拍板提示词 2026-06-06，原样注入正向）：
    #   补强 gpt-image-2 的成片质感——细节丰富、质感细腻、干净高级、通透，材质完整自然、
    #   顺滑均匀；主体清晰、背景层次分明；避免过锐化/过度调色/色彩断层；构图干净通透、
    #   细节饱满无断变无噪点，视觉舒适。
    parts.append(
        "【画质精修】细节丰富、质感细腻、干净高级，画面干净通透；材质完整自然、质感顺滑均匀；"
        "主体清晰锐利、背景层次分明（主次分明、前后景拉开）；避免过度锐化、避免过度调色、"
        "避免色彩断层(banding)与色阶断裂；构图干净通透、细节质感饱满、无突兀断变、无噪点颗粒，"
        "整体观感舒适饱满、高级耐看。"
    )

    # ⑦.5 印刷级平滑/大色块叙事（用户拍板提示词，原样注入正向）
    parts.append("【印刷优化】" + smoothness_prompt_cn())

    # ⑧ 构图 + 比例硬规则 + 留白 + 禁文字（composition_prompt_cn 之前写好但未启用）
    parts.append(
        f"构图：{composition_cn.rstrip('。')}。{composition_prompt_cn().rstrip('。')}。"
        f"{blank_cn}。{FORBID_CN}。"
    )

    return "\n".join(parts)


# ============================================================
#  v3 反向 prompt 构造（分类禁忌）
# ============================================================

def _build_negative_v3(*, cast: list[dict], page_text: str, ip_age: int = 12) -> str:
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

    # 1.8) v3.7 年龄锁 + 禁陌生小孩 + 去色斑/打印模糊（用户拍板 2026-06-04）
    if cast and ip_age:
        if ip_age >= 12:
            parts.append(
                "孩子被画成矮小幼态的低龄小童/学龄前儿童/婴幼儿；孩子年龄看起来明显小于12岁；"
                "圆脸大头的幼儿头身比；身材矮小不符合12岁少年比例"
            )
        elif ip_age >= 10:
            parts.append("孩子被画成低龄幼儿/婴幼儿；年龄明显小于10岁；幼态大头矮小比例")

    # 1.85) 主角【错龄服装】禁穿锁（用户拍板 2026-06-07）——
    #   深蓝/藏青短袖polo是【12岁】Tommy专属；L0-2(8)/L3-4(10) 绝不能出现。
    #   防止"孩子没锚图→默认画成12岁深蓝大男孩"那类漂移。
    _base_keys = {(c.get("key") or "").split("_")[0] for c in cast}
    if "tommy" in _base_keys and ip_age and ip_age < 12:
        if ip_age <= 8:
            parts.append(
                "Tommy穿深蓝/藏青色polo衫或短袖polo（那是12岁定妆，8岁绝不可以）；"
                "Tommy穿长袖卫衣（8岁是蓝白横条纹短袖T恤）；Tommy身材被画成青少年比例"
            )
        else:  # 10
            parts.append(
                "Tommy穿深蓝/藏青色短袖polo翻领衫或牛仔裤（那是12岁定妆，10岁绝不可以）；"
                "Tommy上衣是深蓝色（10岁必须【浅蓝】长袖圆领卫衣+【卡其】裤）；"
                "Tommy被画成12岁青少年的偏高身材"
            )
    if "mia" in _base_keys and ip_age and ip_age < 12:
        parts.append(
            "Mia穿白色阔腿裤或翻领针织衫（那是12岁定妆）；Mia被画成12岁青少年偏高身材；"
            "Mia扎侧马尾或散发披肩（必须高马尾·脑后正中）"
        )
    parts.append(
        "凭空新增陌生小孩/路人同学（有清晰五官发型的多余儿童）；同一角色出现多个分身；"
        "色斑、杂色斑块、噪点颗粒、脏污纹理、拼贴补丁、破碎割裂的色块；同一色块颜色不均匀的脏块；"
        "可见笔触/水彩纸纹理/颗粒感；厚重立体的体积塑形、强烈明暗阴影、写实光影渐变；"
        "打印模糊、发糊、低分辨率、边缘发虚、细节糊成一团；冰冷生硬的3D塑料渲染、塑料磨皮感"
    )

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
        page_neg.append(
            "把仓鼠画成狗、猫或其他动物；把仓鼠画得过大（大过手掌）；"
            "仓鼠身体卡进/穿模/融进家具、桌缝或物体里；仓鼠肢体残缺或扭曲变形"
        )
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
