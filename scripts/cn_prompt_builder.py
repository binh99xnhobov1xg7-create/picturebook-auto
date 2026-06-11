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
    CONCISE_PROMPT as _CONCISE_PROMPT,
    enforce_prompt_budget as _enforce_prompt_budget,
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
    "讲究前中后景的空间层次与纵深【但全画面同清·深景深】——前景与远景同样锐利清晰、同等细节可读，绝不背景虚化/散景，画面层次干净耐看、高级；"
    "以平滑柔和的色块与渐变(smooth shading/gradients)塑形为主，线条以柔和简洁的描边为辅（克制、纤细、可有可无，绝不喧宾、不要粗重墨线），"
    "形体简洁完整、细节克制(controlled details)、纹理极简(minimal texture)；画面干净洁净、精致考究而不杂乱、不细碎。"
    "【细腻而不细碎·无噪点无颗粒·无脏块无碎块】上色细腻柔和、过渡干净自然、颜色分布匀净；"
    "绝不出现斑驳破碎的色块、割裂的色斑/碎块、拼贴补丁感、杂乱色点、噪点颗粒、可见笔触痕迹、"
    "水彩纸/纸张颗粒纹理、脏污纹理与断裂破碎轮廓；"
    "线条连续闭合、形体完整干净；画面洁净、过渡干净，可高分辨率打印——边缘与线条清晰锐利、绝不模糊发虚发糊。"
    "【色调】暖米低饱和主调（暖米白、奶油杏、浅卡其）+ 柔和莫兰迪点缀（雾霾绿、藕灰紫、淡蓝），"
    "颜色均匀简洁干净、整体明亮清透温暖耐看，颜色清晰可辨（不发灰惨白、也不刺眼高饱和）。"
    "【光线】明亮柔和的自然光，方向统一，做克制而细腻的明暗塑形带出体积与层次（轻盈不厚重）；阴影浅淡干净、绝不压暗。"
    "【背景】极简整洁、适度留白、清爽不杂乱：空墙面只留少量精简点缀，主体人物干净突出、边缘清晰、平涂干净。"
    "人物面部干净简洁（柔和线条平涂），柔和大眼睛+小鼻子，脸颊干净光洁、至多极淡的一点点脸颊红润（绝不要明显腮红/红脸蛋/圆形红晕色斑），五官清爽精致"
    "（主角相貌一律以角色定妆参考图为准；配角/路人可为多元族裔、体现国际化）。"
    "拒绝：浑浊脏色、过暗压抑、斑驳破碎/拼贴补丁感、噪点颗粒色斑、可见笔触/纸张纹理颗粒、Q版贴纸、"
    "厚重立体的3D塑料渲染、油画厚涂、强烈明暗体积塑形、写实光影、塑料磨皮感、照片写实质感、AI脏噪乱纹、打印模糊发糊。"
    "【画风锁定·低随机】严格复刻官方参考画风：干净平滑的治愈水彩、柔和层次与景深、暖米+柔蓝低饱和、明亮柔光、"
    "平滑柔和的色块与渐变塑形(clean illustration, smooth shading, minimal texture, controlled details, refined edges)、"
    "纤细克制的描边为辅；不要自由发挥、不要改变既定画风与配色、不要增添多余杂乱装饰、不要添加噪点颗粒与碎纹理。"
    "【高明度·明亮通透·绝不暗沉】整体高调明亮(high-key)、画面通透干净、像沐浴在柔和日光里；"
    "阴影极浅淡干净、绝无硬阴影/重阴影/暗角；严禁发暗、压暗、阴沉、灰暗、夜景、暖光过浓发黄、整体偏暗调。"
    "【构图·必须预留干净文字留白】主体人物明显偏置一侧(绝不铺满整幅、不要居中堵满)，画面另一侧(或顶部)必须预留"
    "【至少 20%、最好 20-25% 的一整块连续、彻底干净的浅色留白区域】(如天空、空墙面或地面)，"
    "这块留白区必须完全空净——绝对不能有任何物体伸入或遮挡：不许有树枝/枝叶/花草/云朵图案/道具/人物/手脚/建筑/家具的任何一部分探进这块区域，"
    "保证后期能在此整块叠放文字而不遮挡任何画面元素；背景极简整洁。"
    "【人物一致·只改表情动作】画面中出现的既有角色（Mia/Tommy/Anna 等）其发型、脸型、五官、肤色、"
    "服装款式与配色必须与其定妆参考图完全一致；本页仅改变其表情与肢体动作以贴合剧情，"
    "严禁改动长相、发型、服装与配色，严禁凭空新增或减少角色。"
)


# v2.0 环境元素库 — 根据故事文本关键词推断场景应有的具体环境物体
_ENV_HINTS: list[tuple[str, str]] = [
    (r"classroom|class\b|desk|recess|school|teacher",
     "教室环境（国际化现代校舍）：暖米白空墙面（不要写满字的黑板、不要密集装饰）、一两张浅色课桌椅、单侧一扇明亮窗户射入柔和自然光、"
     "带淡蓝天空与窗外绿意、干净的浅色地面（瓷砖或浅木地板皆可）；背景极简整洁、适度留白、清爽不杂乱，主体人物干净突出"),
    (r"hallway|corridor",
     "走廊环境（国际化现代校舍）：延伸的空间感、暖米白墙面、单侧一排明亮窗户射入柔和自然光带窗外绿意、干净的浅色地面，"
     "墙面极简少量点缀；背景整洁有序、适度留白、不杂乱"),
    (r"playground|outside|park|yard",
     "户外环境：柔和的浅绿草地、一两棵舒展的树、淡蓝天空与几朵白云、暖阳柔光，"
     "背景自然清新、极简整洁、不杂乱"),
    # home/house 加词界（修"homework/warehouse"等子串误触发）；再排除体育语境
    #   home team/home game/home run… 避免足球等户外页被塞家庭布景（Book57）。
    (r"\bhome\b(?!\s+(?:team|game|run|base|side|ground|field|crowd|stadium|win))|\bhouse\b|bedroom|kitchen",
     "家庭环境（温馨现代居家）：暖米白墙面、少量浅色家具、窗台绿植、单侧窗柔光，"
     "干净的浅色地面、少量温馨家居小物，背景极简整洁、适度留白"),
    (r"library|book",
     "图书馆/阅读角环境：浅色书架配柔色书脊、暖米墙面、单侧窗柔光、可有绿植点缀，"
     "干净的浅色地面，背景整洁、适度留白、不杂乱"),
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
    "close":  "中近景半身，主角胸部以上占画面 55-65%、明显偏置一侧，清晰饱满，另一侧留出排文字空间，背景有清晰可辨的环境元素",
    "medium": "中景，主角七分身或全身占画面 55-65% 高度、偏置画面一侧为视觉焦点（画得清晰饱满、不要缩小），仅在另一侧留约 20-25% 排文字空间，其余由环境充实饱满地填满、细节清晰",
    "full":   "全身中景，主角从头到脚完整可见、占画面 55-65% 高度、偏置一侧（画得饱满、不空旷），仅留约 20-25% 排文字空间，其余由环境充实填满",
    "wide":   "远景，主角占画面 35-45%（仍是视觉焦点），环境（教室全景、走廊、建筑、地标）占其余画面",
}
DEFAULT_SHOT = "medium"  # 中景为默认（主角 50-60%）

# v5 机位角度（镜头语言）— 让画面随剧情变化，不再全本平视。
# 由 AI/老师按本页内容选；eye 为默认平视。
CAMERA_ANGLE_CN: dict[str, str] = {
    "eye": "平视机位（镜头与人物视线齐平），自然亲切，适合对话、情感交流，以及孩子在场景里走动/寻找/探访的贴地剧情",
    "high": "轻俯视机位（镜头从斜上方略往下看），看清桌面/地面物件与场景布局，层次分明（轻微俯角，非航拍）",
    "birdseye": "鸟瞰/正俯视机位（镜头从正上方垂直俯瞰），仅用于地图/地理/地形/大场景全貌的科普展示",
    "low": "仰视机位（镜头从下往上看），强调高大宏伟（城堡/大树/高楼），画面更有气势",
    "over_shoulder": "越肩/主角视角（镜头越过主角肩膀或贴近主角视线），带观众代入主角去观察发现眼前事物",
}
DEFAULT_ANGLE = "eye"


# ============================================================
#  SOP 第7/二.5 条：情绪 → 固定面部细节词表（强制·禁抽象情绪词）
#  原文逐字固化：Happy/Excited/Focused/Peaceful/Curious/Sad 六类；
#  其余近义情绪词归并到最接近的一类（找不到则省略，交回 scene_cn 的具体描述）。
# ============================================================
SOP_EMOTION_FACE_CN: dict[str, str] = {
    "happy":    "嘴角上扬，眼眸明亮，眼角微弯，面带柔和笑意",
    "excited":  "眉毛微扬，眼睛睁大明亮，嘴角自然扬起",
    "focused":  "眉头轻收，眼神沉静向下凝视，神情专注安静",
    "peaceful": "眉眼放松舒展，嘴角平缓微扬，神态宁静安然",
    "curious":  "头部微侧，眼睛睁大带好奇，眉毛轻抬",
    "sad":      "嘴角微下垂，眼神柔和略沉静，眉头轻蹙",
}
# 近义情绪 → 六类归并（中英文都覆盖；只做保守映射，命中不了就留空）。
_EMOTION_ALIASES: list[tuple[str, str]] = [
    (r"happy|joy|joyful|glad|cheer|delight|smil|content|pleased|高兴|开心|快乐|愉快|欢喜|笑", "happy"),
    (r"excit|eager|thrill|amazed|astonish|wow|surpris|惊喜|兴奋|激动|期待|惊讶|雀跃", "excited"),
    (r"focus|concentrat|serious|think|determin|attentive|careful|专注|认真|思考|凝神|聚精会神|沉思", "focused"),
    (r"peace|calm|relax|gentle|serene|cozy|warm|safe|平静|安宁|放松|平和|安心|温馨|惬意", "peaceful"),
    (r"curious|wonder|interest|intrigu|puzzl|question|好奇|疑惑|纳闷|好奇心|探究", "curious"),
    (r"sad|worri|nervous|upset|scare|afraid|fear|anxious|shy|lonely|disappoint|难过|伤心|担心|紧张|害怕|焦虑|失落|沮丧|害羞|孤单", "sad"),
]


def _normalize_emotion(raw: str) -> str:
    """把任意情绪词（中/英、单词或短语）归并到 SOP 六类之一；归并不到返回空串。"""
    s = (raw or "").strip().lower()
    if not s:
        return ""
    if s in SOP_EMOTION_FACE_CN:
        return s
    for pat, cat in _EMOTION_ALIASES:
        if _re.search(pat, s):
            return cat
    return ""


def _emotion_face_cn(raw: str) -> str:
    """情绪词 → SOP 固定面部细节描述（命中六类才返回，否则空串）。"""
    cat = _normalize_emotion(raw)
    return SOP_EMOTION_FACE_CN.get(cat, "")


def _angle_phrase(angle: str) -> str:
    a = (angle or "").strip().lower()
    return CAMERA_ANGLE_CN.get(a, "")


_VALID_SHOTS = ("close", "medium", "full", "wide")
# 为打破"连续4页同景别"准备的替补轮转（SOP 第4/二.3 条：任意连续4页≥2种景别）。
_SHOT_ALTERNATES = ("wide", "close", "full", "medium")


def _ensure_shot_variety(outline: BookOutline) -> None:
    """SOP 第4条：任意连续 4 页内至少出现 2 种不同景别。

    等价条件 = 不允许任何【连续 4 页景别完全相同】。本函数只在检测到 4 连同景别时，
    把窗口末页换成一个不同的合法景别（情绪关键页的 CU/ECU 由 AI 在 shot 里另行指定，
    这里不动非默认的显式景别选择以外的语义）。幂等：用 outline 上的标记位防重复执行。
    """
    if getattr(outline, "_shot_variety_done", False):
        return
    try:
        story = [p for p in outline.pages
                 if getattr(p, "page_type", "") != "cover" and getattr(p, "index", 0) >= 1]
        # 归一化非法/空景别为默认 medium（与 build 主流程一致）。
        for p in story:
            s = (getattr(p, "shot", "") or "").strip().lower()
            if s not in _VALID_SHOTS:
                p.shot = DEFAULT_SHOT
        # 扫描每个 4 连窗口：若四页景别完全相同，把末页换成第一个不同的合法景别。
        for i in range(3, len(story)):
            window = [story[j].shot for j in range(i - 3, i + 1)]
            if len(set(window)) == 1:
                same = window[0]
                repl = next((a for a in _SHOT_ALTERNATES if a != same), "wide")
                story[i].shot = repl
    except Exception:
        pass
    try:
        setattr(outline, "_shot_variety_done", True)
    except Exception:
        pass


def _resolve_camera_angle(page: PageSpec, outline: BookOutline) -> str:
    """机位收口（用户拍板 2026-06-08）：航拍/大俯视只给【地图/大场景科普】；
    fiction 里"孩子贴地走动/寻找/探访/对话"即使 AI 误选 birdseye/high 也降级为越肩/平视。
    """
    a = (getattr(page, "camera_angle", "") or "").strip().lower()
    if a not in CAMERA_ANGLE_CN:
        return ""
    if _is_nonfiction(outline):
        return a  # 科普：尊重 AI 机位（地图/地形用鸟瞰合理）
    # fiction：禁止航拍/大俯视压在贴地剧情上
    if a == "birdseye":
        return "over_shoulder"
    if a == "high":
        return "eye"
    return a

def _blank_text(page_index: int) -> str:
    """根据页码返回文字留白说明（对齐官方 SOP）。

    官方铁律：禁止画纯白色块/白色矩形/空白方框/人工硬边留白；
    文字位置必须落在「场景原生空旷区域」（天空、草地、远山、墙面、地面、林间空地等），
    该区域保留场景真实色彩与纹理，只是没有主角/关键道具，方便后期排文字。
    """
    if page_index == 0:
        return ("利用场景顶部【约 20-25%（至少 20%）的一整条横带】留出文字区供后期叠加书名；"
                "这条带【绝不能是纯白/惨白的空色块】，必须是本页场景的自然延续、有色彩有质感（蓝天淡云 / 暖金黄昏 / 柔灰阴雨 / 有肌理的墙面天花板等，"
                "随场景天气来画、低饱和莫兰迪质感、与下方同一光源自然过渡）；这条带里只禁止【可识别的人物/动物/关键道具/文字，以及杂乱探入的树枝枝叶/招牌建筑】，"
                "但允许柔和的云、光晕、远处树梢顶端、墙面肌理等低饱和氛围元素；其余画面由主体与环境充实饱满地填满、不空旷；"
                "作画时这条带里绝对不要画任何文字/字母/书名/标题，也禁止纯白色块或硬边空白方框")
    side = "右侧" if page_index % 2 == 1 else "左侧"
    return (f"把主体偏置到画面一侧，在画面{side}（或顶部）留出【约 20-25%（至少 20%）的一整条区域】用于排文字："
            f"这块区域【绝不能是纯白/惨白的空色块】，要利用场景原生区域并保留真实色彩与质感（墙面 / 地面 / 天空 / 草地等，随本页场景天气自然延续、低饱和莫兰迪质感）；"
            f"这块区只禁止【可识别的人物/动物/关键道具/文字，以及杂乱探入的树枝枝叶/建筑】，但允许云、光晕、远处树梢顶端、墙面肌理等低饱和氛围元素，让它有质感、不空洞；"
            f"确保后期文字能整块落入、不遮挡主体；其余画面由主体与环境充实饱满地填满、不空旷；禁止纯白色块、白色矩形或人工硬边空白")


FORBID_CN = (
    "【绝对禁止任何文字】画面里绝对不要出现任何文字、字母、单词、英文、汉字、数字、书名、标题、"
    "印刷字、手写字、标语、字幕、签名、水印或 logo——一个字符都不要画；"
    "书名/标题一律由后期软件单独叠加，作画时留白处只保留干净的原生背景，绝不画字"
)


# ============================================================
#  角色检测（中文 alias）
# ============================================================

# 通用角色 → 默认套用的 registry key（系列连贯性原则）
_GENERIC_ROLE_MAP: list[tuple[str, str]] = [
    # (英文 + 中文匹配模式, registry key)
    (r"\b(?:a |an |the )?girl(?:s)?\b|女孩|小姑娘", "mia"),
    (r"\b(?:a |an |the )?boy(?:s)?\b|男孩|小男孩", "tommy"),
    # 系列铁律 §4：无名泛指的同辈孩子 sister/brother = 兄妹双主角 Mia/Tommy
    # （注意：grandmother/grandfather 不含 sister/brother，不会误命中）
    (r"\b(?:my |a |the )?(?:little |big |older |younger )?sister(?:s)?\b|妹妹|姐姐", "mia"),
    (r"\b(?:my |a |the )?(?:little |big |older |younger )?brother(?:s)?\b|弟弟|哥哥", "tommy"),
    # "parents/父母/爸妈" → 同时带出妈妈+爸爸（两条独立规则各按 key 去重命中）
    (r"\bparents\b|\bmom and dad\b|父母|爸妈", "mom"),
    (r"\bparents\b|\bmom and dad\b|父母|爸妈", "dad"),
    # 用户拍板 2026-06-07 同款决定的延伸（2026-06-11 修 L4·SYMPTOM2 根因）：裸词 "woman/阿姨/
    #   女老师" 不再映射成金发 IP Teacher Kim——否则任何含无名成年女性的故事（科学家/织布婆婆/
    #   讲解员…）都被画成 Teacher Kim，且与 book_cast 一次性女角并存导致逐页漂移。Teacher Kim 只认
    #   专名 Ms./Teacher Kim/Kim（仍由显式 IP 检测命中）；无名成年女性交给 book_cast【一次性成人锚】
    #   （全书统一外观 + 书内锚图）保持跨页一致，或由场景成人锁兜底。
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
                    "kind": char.get("kind", ""),
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
                "kind": char.get("kind", ""),
            })
            found_keys.add(default_key)

    return out


# ============================================================
#  Mia 发型铁律（用户拍板 2026-06-10：以官方 Age10 定妆表为准对齐）
#  Mia = 后脑【中高位】马尾，用【紫色发圈】束发：发髻明显在后脑、位置适中
#  （不在颅顶正上方、也不在后颈低处）；马尾辫中等长度、略带波浪、垂至肩部/上背。
#  前面留少量碎发框脸。绝不丸子头/发髻/half-up/披散不扎/颅顶超高马尾。
# ============================================================
MIA_HAIR_LOCK = (
    "棕色头发在后脑束成一根马尾，用一根【紫色发圈】束发：发髻明显在后脑、位置适中——"
    "【不在颅顶正上方，也不在后颈低处】；马尾辫【中等长度、略带波浪】、自然垂落至【肩部/上背】"
    "（以定妆表为准，长度明显可见、不是一小撮短穗）；前面留少量碎发框脸；"
    "绝不是丸子头/发髻/half-up 半扎、绝不大片披散不扎（以参考图为准）"
)
MIA_HAIR_NEG = (
    "禁止丸子头/发髻/top-knot、禁止 half-up 半扎、禁止只扎上层而下半部分头发披散、"
    "禁止【颅顶/头顶正中的超高马尾】、禁止发髻在头顶正上方、禁止仅 3–5cm 的短马尾穗、"
    "禁止头发完全散开不扎、禁止大量披散的散发、禁止双马尾/麻花辫、禁止脏辫乱团/头发糊成一团、"
    "禁止用非紫色的发圈（必须紫色发圈）（允许并必须：后脑中高位马尾 + 紫色发圈 + 垂至肩/上背的中长辫）"
)


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
        # 官方 Age10 定妆表对齐（用户拍板 2026-06-10）：三档【同一形象·衣色发型一致】，
        #   仅体型随年龄变化——紫色长袖圆领卫衣 + 浅灰白直筒裤 + 紫色发圈马尾。
        outfit = "紫色长袖圆领卫衣（哑光素色）+浅灰白色直筒长裤"
        return (
            f"Mia：{age_n}岁女孩（体型为{age_n}岁），{MIA_HAIR_LOCK}；{MIA_HAIR_NEG}；"
            f"穿{outfit}，白色低帮运动鞋，不戴手表/手链/项链/耳环/眼镜/帽子"
        )
    if key == "tommy":
        # 官方 Age10 定妆表对齐（用户拍板 2026-06-10）：三档【同一形象·衣色发型一致】，
        #   仅体型随年龄变化——浅天蓝长袖圆领卫衣 + 卡其直筒裤（旧的"8岁条纹T/12岁深蓝polo"已废弃）。
        outfit = ("【浅天蓝 pale sky-blue / light powder-blue】长袖圆领卫衣（哑光、无翻领、无门襟拉链）"
                  "+卡其色直筒裤（色值锚定近 #5FA8D6~#8EC0ED；绝不深蓝/藏青/navy/钴蓝/靛蓝/teal、"
                  "绝不短袖polo翻领、绝不牛仔裤；上衣的蓝必须明显浅于任何成人制服蓝与背景深蓝物体）")
        return (
            f"Tommy：{age_n}岁亚洲男孩（体型为{age_n}岁，必须是男孩，不能有马尾，不能长发，绝不戴眼镜，不戴帽子），"
            f"棕色蓬乱蓬松短发，穿{outfit}，白色低帮运动鞋，"
            f"且 Tommy 是画面里唯一穿【浅天蓝卫衣】的人，其蓝明显浅于任何成人制服蓝/警服蓝/背景深蓝物体"
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
        return ("妈妈：成熟成年女性（约35岁，是大人，绝不是小孩、绝不是青少年/teenager、绝不是大学生），"
                "成年人脸庞与身材比例、身高明显高于孩子，棕色长波浪发，"
                "白色宽松长袖上衣+浅蓝色牛仔裤+白色运动鞋，温柔微笑")
    if key == "dad":
        return ("爸爸：成熟成年男性（约38岁，是大人，绝不是小孩、绝不是青少年/teenager、绝不是大学生），"
                "成年人脸庞与身材比例、身高明显高于孩子，棕色短发，"
                "灰色短袖polo衫+卡其色长裤+棕色皮鞋，不戴眼镜，温和微笑")
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
        return (
            f"（{age_n}岁女孩，{MIA_HAIR_LOCK}；{MIA_HAIR_NEG}；不戴眼镜，不戴任何饰品）"
        )
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

def safety_line_default(page: PageSpec) -> str:
    """块4：从 scene_cn 提炼一句给老师确认的【简体中文场景安全线】（谁+在哪+做什么）。

    取 scene_cn 第一句主干、去掉画风/留白/框架等技术性措辞，控制在约 50 字内。
    仅作默认草稿，老师可自由编辑。
    """
    raw = (getattr(page, "safety_line", "") or "").strip()
    if raw:
        return raw
    s = (page.scene_cn or "").strip()
    if not s:
        return (page.text or "").strip()[:50]
    # 去掉框架/画风类前缀片段
    s = _re.sub(r"【[^】]*】", "", s)
    # 取第一句（到第一个句号/分号）
    first = _re.split(r"[。；;\n]", s, maxsplit=1)[0].strip()
    if len(first) > 56:
        first = first[:56].rstrip("，,、 ") + "…"
    return first


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
    """v3：拆成正向/反向两段，最终 prompt = 正向(1-19 段公式) + 第 20 段【不要改变/不要出现】负向锁。"""
    positive: str                  # v3: 正向 prompt（火山风单段流畅）
    negative: str                  # v3: 反向 prompt（分类禁忌）
    prompt: str                    # v3: 最终拼接后字符串（实际发送给 Seedream）
    references: list[Path]
    used_characters: list[dict]    # 调试用
    scene_cn: str = ""             # 本页【13·必出细节】场景意图（供视觉自审判"剧情是否画对"）
    story_lock: str = ""           # 本页【剧情/场景必演】锁（含非虚构主题标志道具，供自审参照）

    @staticmethod
    def join(positive: str, negative: str) -> str:
        """把正向(1-19 段) + 反向(第 20 段·负向锁)拼成最终 prompt。"""
        pos = (positive or "").strip()
        neg = (negative or "").strip()
        if not neg:
            return pos
        return f"{pos}\n\n【20·不要改变/不要出现】（负向锁·以下内容一律不得出现）\n{neg}"


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


# 配角【确定性配色轮】（用户拍板 2026-06-09）——
#   旧做法靠"各自改穿绿/黄/橙…彼此不同"的软描述，模型仍易给男孩默认蓝、女孩默认紫而撞主角专属色。
#   改为按出场序硬指派一个互不相同、且【刻意避开主角专属色（紫/蓝/绿/粉）】的确定色相轮转。
_EXTRA_COLOR_WHEEL: list[str] = ["橙色", "黄色", "青绿色", "红色", "米色", "棕色", "灰色"]
# 主角专属色（配角一律禁穿）：紫=Mia / 蓝=Tommy / 绿=Anna / 粉=Cate。
_LEAD_RESERVED_COLORS: list[str] = ["紫色系", "蓝色系", "绿色系", "粉色系"]


def _extra_color_assignment_cn() -> str:
    """生成配角【确定性硬指派】配色正向句（替换原"彼此不同"软描述）。"""
    seq = "、".join(f"第{i+1}个配角穿{c}" for i, c in enumerate(_EXTRA_COLOR_WHEEL))
    reserved = "、".join(_LEAD_RESERVED_COLORS)
    return (
        f"【配角配色·硬指派】配角按出场顺序依次穿：{seq}（多于7个按色轮循环、相邻必不同），主色互不相同；"
        f"一律严禁穿主角专属色：{reserved}（紫=Mia、蓝=Tommy、绿=Anna、粉=Cate），不与主角撞色；"
        "上色仍像水彩般柔和自然，不画成生硬色块。"
    )


def _extra_diversity_cn() -> str:
    """配角多元/各异硬约束（与确定性配色配套，明显区别于主角）。"""
    return (
        "【配角各异】非 IP 配角国际化、多元族裔、彼此各异且明显区别于主角，绝不复制 Mia/Tommy 脸或发型，不抢主体。"
    )


# ============================================================
#  v3 角色特征锁短语（用于反向区"防止跑帧"）
# ============================================================
# 每个角色 base key 对应一段否定锁（明确说不戴眼镜、不变发型等）
_CHAR_NEGATIVE_LOCK: dict[str, str] = {
    "mia":     (
        f"Mia戴眼镜、Mia丸子头/发髻/top-knot、Mia是half-up半扎（只扎上层下半披散）、"
        f"Mia头发完全散开不扎、Mia大量披散的散发、Mia低马尾或侧马尾、Mia双马尾或三辫子、"
        f"Mia脏辫乱团、Mia头发糊成一团、Mia颅顶/头顶正中超高马尾、Mia发髻在头顶正上方、Mia仅短马尾穗、Mia用非紫色发圈、"
        f"（Mia必须是后脑中高位马尾+紫色发圈、辫尾垂至肩/上背：{MIA_HAIR_LOCK}）、"
        f"Mia穿裙子、Mia穿黄色或绿色或其他非紫色上衣（Mia上衣必须是紫色系）、"
        f"Mia被画成幼儿或青少年（必须是8/10/12岁同龄儿童）"
    ),
    "tommy":   "Tommy戴任何眼镜或墨镜（Tommy绝不戴眼镜）、Tommy长发、Tommy扎马尾、Tommy被画成女孩、Tommy穿其他颜色上衣（必须是蓝色系）、Tommy被画成幼儿或青少年或成年人（必须是与Mia同龄的儿童）",
    "anna":    "Anna扎马尾或双低马尾或辫子、Anna长发披肩、Anna不戴白发箍、Anna戴眼镜、Anna穿裙子、Anna穿黄色或紫色或其他颜色上衣（必须纯绿色毛衣）",
    "cate":    "Cate散发不扎、Cate穿其他颜色上衣",
    "ali":     "Ali被画成深肤色或黑色卷发（应浅肤色+棕色短发）、Ali穿黄色上衣（应蓝色短袖T+卡其短裤）",
    "teacher": "Teacher Kim 穿太花哨或显得太年轻",
    "mom":     "妈妈被画成小孩或青少年/teenager、妈妈与孩子同高同龄、妈妈像大学生（妈妈必须是成熟成年人且明显比孩子高）",
    "dad":     "爸爸被画成小孩或青少年/teenager、爸爸与孩子同高同龄、爸爸像大学生（爸爸必须是成熟成年人且明显比孩子高）",
    "grandma": "奶奶发色过深（应是白发）、奶奶被画成年轻人或小孩（奶奶是明显年长的老人）",
    "grandpa": "爷爷发色过深（应是白发）、爷爷被画成年轻人或小孩（爷爷是明显年长的老人）",
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
        return ("儿童头身比约 5.5-6 头身（学龄期 10 岁），身体比例已接近少年——"
                "头部相对身体不要过大、腿身要修长，绝不是大头娃娃/Q版4头身的幼态矮小比例")
    # 11-14：少年
    return "少年头身比约 6.5-7 头身（青春期前期），身体修长、四肢比例匀称，但保留少年面部特征"


def _furniture_scale_lock(ip_age: int) -> str:
    """场景家具/物件按主角年龄的真实身高比例（用户拍板 2026-06-08）。

    关键：家具（桌/椅/床/门/把手/书架/橱柜/楼梯扶手等）的尺寸要相对【该年龄孩子的真实身高】
    合理——孩子站立时到桌沿/床沿/门把手的相对高度要符合现实，避免"巨人家具+小人国孩子"或反之。
    """
    if ip_age <= 8:
        ref = "8 岁孩子（约 125-130cm）：站立时课桌面大约到其腰部、普通椅面到其膝盖、门把手在其肩—头之间"
    elif ip_age <= 10:
        ref = "10 岁孩子（约 138-142cm）：站立时课桌面大约到其腰—髋部、椅面到其膝盖、门把手约在其肩部高度"
    else:
        ref = "12 岁少年（约 150-155cm）：站立时课桌面约到其髋部、椅面到其膝下、门把手约在其胸—肩部高度"
    return (
        f"【家具按龄比例·硬约束】场景里的家具与物件尺寸要符合{ref}；"
        "桌、椅、床、门、把手、书架、橱柜、楼梯扶手等都按这个孩子的真实身高来确定相对大小，"
        "孩子坐到椅上时脚能自然接近地面、趴在桌上比例合理；"
        "严禁把家具画得相对孩子过大（孩子像小人国）或过小（孩子像巨人），人与物比例要真实可信。"
    )


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


# 非虚构主题 → 标志性道具/场景（关键词命中即注入；通用对所有书生效，不写死某本）。
_THEME_SIGNATURE: list[tuple[str, str]] = [
    (r"museum|博物馆|展览|exhibit", "博物馆/展馆的标志性场景：玻璃展柜、恐龙骨架或文物雕塑、说明牌支架（无可读文字）、高挑展厅与射灯"),
    (r"librar|图书馆|借书|book.?shelf|阅览", "图书馆的标志性场景：成排高书架与满架书本、借书台/服务台、阅览桌椅、安静明亮的阅览空间"),
    (r"clean|tidy|litter|trash|garbage|rubbish|打扫|清洁|清扫|垃圾|捡|扫除", "清洁/社区服务的标志性场景：街道或公园 + 垃圾袋/垃圾桶/扫帚/夹子/手套，人物正在弯腰捡拾或打扫"),
    (r"sport|exercise|运动|锻炼|球|跑步|健身", "运动主题的标志性场景：运动场/操场/球场或器材，人物正在做该项运动（跑、跳、踢球、拉伸）"),
    (r"garden|plant|grow|farm|种|花园|农场|植物", "种植/园艺的标志性场景：花园/菜地/花盆 + 铲子/水壶/泥土/幼苗，人物正在浇水或栽种"),
    (r"market|shop|store|grocery|超市|商店|市场|购物", "商店/市场的标志性场景：货架/摊位/购物篮/价签牌（无可读文字）、琳琅商品"),
    (r"hospital|doctor|nurse|医院|医生|护士|看病", "医疗主题的标志性场景：诊室/医院走廊 + 听诊器/病床/医疗器械，医护为成年人"),
    (r"firefighter|fire\s?station|消防|救火", "消防主题的标志性场景：消防车/消防栓/消防站、消防员为成年人"),
    (r"police|officer|警察|警官|警", "社区/安全主题的标志性场景：社区活动现场或街道，成年警官在执勤/讲解"),
    (r"weather|season|rain|snow|天气|季节|四季", "天气/季节主题：明确的天气/季节标志（雨伞雨滴/积雪/落叶/烈日）贯穿画面"),
    (r"recycl|环保|回收|地球", "环保/回收主题：分类回收桶/可回收物/绿色环保标识（图形非文字）"),
    (r"community|neighbo|社区|邻里|helping\s?hand|帮助", "社区互助主题：街区/社区中心/邻里场景，人物在【具体地帮助他人/做社区服务】而非空场站立"),
]


def _scene_story_lock(outline: BookOutline, page: PageSpec, scene_cn: str, is_cover: bool) -> str:
    """本页【剧情/场景必演】锁（通用，对所有书生效）：

    1) 强制把本页关键动作/道具/场景"演"出来，禁止退化成主角在空旷/无关室内单纯站立摆拍/闲聊；
    2) 非虚构主题页：必须出现该主题的标志性道具/场景（按主题关键词注入）。
    """
    if _nf_body_page(page, outline):
        base = (
            "把本页【关键动作/道具/场景】真实演出来：科普对象/知识过程占画面主体、清晰可辨；"
            "专注知识可视化，不出现系列主角；绝不退化成空旷背景或跳题省略本页情节"
        )
    else:
        base = (
            "把本页【关键动作/道具/场景】真实演出来：主角在场、专注投入、与关键道具真实互动"
            "（动手就亲手操作、观看就专注看/指认）；关键道具/场景占画面主体、清晰可辨；"
            "绝不退化成空旷背景里呆站/摆拍/跳题省略本页情节"
        )
    if _is_nonfiction(outline):
        theme = (getattr(outline, "theme", "") or "")
        title = (getattr(outline, "title", "") or "")
        # 优先按【本页场景】匹配（图书馆页→书架、博物馆页→展柜，避免整本套同一主题道具）；
        #   本页场景无明确主题词时，再回退到全书主题/标题。
        scene_low = (scene_cn or "").lower()
        sig = next((desc for pat, desc in _THEME_SIGNATURE if _re.search(pat, scene_low)), "")
        if not sig:
            hay = f"{theme} {title}".lower()
            sig = next((desc for pat, desc in _THEME_SIGNATURE if _re.search(pat, hay)), "")
        if not sig:
            sig = f"必须出现与主题《{theme or title}》直接相关的标志性道具/场景，让人一眼看出主题"
        base += ("；【主题锁·标志场景与道具作为画面主体、占主要面积，主角置身其中专注参与】" + sig)
    return base


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


def _make_family_adult_entry(k: str, ip_age: int) -> dict | None:
    """构造一个家庭成年角色（妈妈/爸爸/爷爷/奶奶）的 cast 条目（成人定妆 + 锚图 + 形象锁）。
    用于"家人在家做饭/吃饭/团聚"等页面：把家长锁成系列固定 IP，避免模型自由画成陌生大人。"""
    char = CHAR_REGISTRY.get(k)
    if not char:
        return None
    age_key = next(iter(char.get("description_by_age", {}).keys()), "adult")
    desc_cn, ref = _curated_ref_desc(
        k, ip_age,
        _en_to_cn_desc(registry_get_desc(k, age_key) or "", k, age_key),
        registry_get_ref(k, age_key),
    )
    return {
        "name": k.capitalize(),
        "key": k,
        "description_cn": desc_cn,
        "ref_path": ref,
        "is_generic": False,
        "kind": char.get("kind", "family"),
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
    if _nf_body_page(page, outline):
        must_have_leads = False
    elif official_raw:
        low = _official_cast_text(official_raw).lower()
        official_names_leads = bool(_re.search(r"\b(mia|tommy)\b", low))
        # 有官方文本：仅当官方点到主角（或封面点到）才要求主角在场
        must_have_leads = official_names_leads
    else:
        must_have_leads = is_cover or _nf_intro_page(page, outline) or (
            not _is_nonfiction(outline)
            and _book_centers_on_leads(outline) and page_has_person
            and not _page_scopes_to_named_nonlead(page, cast)
            and not _page_names_specific_child(cast)
        )
    # 框架寓言纯故事页：他俩是读者、刻意不入场 → 不要求主角在场（避免误报）
    if _is_frame_fable(outline) and _frame_page_kind(
            outline, page, getattr(outline, "frame_mode", "A+")) == "pure":
        must_have_leads = False
    if must_have_leads:
        # 按四规则判定本书应出现的主角（可能只 Mia，如 Mia+具名朋友的故事）
        for who in _lead_keys_for_book(outline, page):
            if who not in base_keys:
                issues.append(f"应出现的主角缺失：{who}")

    # 4) 主角年龄档校验（参考图文件名应含 ip_age）
    for c in cast:
        base = (c.get("key") or "").split("_")[0]
        if base in ("mia", "tommy"):
            ref = str(c.get("ref_path") or "")
            if ref and str(ip_age) not in Path(ref).stem:
                issues.append(f"{base} 参考图年龄档不符（应 {ip_age} 岁）：{Path(ref).name}")

    # 5) 人数上限（只数 IP/注册角色；一次性角色不计入）。门限 3→5（用户拍板 2026-06-09）：
    #   参考图上限本就是 5，群像/家庭页常合法出现 4-5 个注册角色，门限 3 会误报人工抽查。
    n_main = sum(1 for c in cast if not c.get("is_oneoff"))
    if n_main > 5:
        issues.append(f"cast 超过 5 人（{n_main}）")

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
# 成人/老人 key（点名成人不算"点名孩子"，家庭页仍需补齐兄妹）
_ADULT_KEYS = {"mom", "dad", "grandma", "grandpa", "granny", "grandfather", "teacher", "teacher_kim"}


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


def _book_all_text(outline: BookOutline) -> str:
    parts = [outline.title or ""]
    oip = getattr(outline, "official_image_prompt", None)
    for p in outline.pages:
        parts.append(p.text or "")
        parts.append(getattr(p, "scene", "") or "")
        if oip is not None:
            try:
                parts.append(oip.page_scene(p.index) or "")
            except Exception:
                pass
    return " ".join(parts)


def _named_sibling_leads(outline: BookOutline) -> list[str]:
    """全书文本里【显式点名】的系列兄妹主角（mia/tommy 的子集，按出现顺序）。"""
    low = _book_all_text(outline).lower()
    return [k for k in ("mia", "tommy") if _re.search(rf"\b{k}\b", low)]


# 本页"单一主角焦点"显式标记：作者已写明画面只聚焦一个孩子（如 P1 的 "only ONE main character"）。
#   有此标记时，文本里出现的泛指 "girl/boy" 多半是对具名配角(如 Anna)的同位语指代，而非第二个孩子。
_SINGLE_FOCUS_RE = _re.compile(
    r"only one (?:main )?(?:character|child|kid|person|girl|boy)|"
    r"\bone main character\b|\bsits? alone\b|\bsitting alone\b|\bstands? alone\b|"
    r"\ball alone\b|\bby (?:her|him)self\b|\balone\b|"
    r"只有一个|仅一个|独自|单独",
    _re.IGNORECASE)


def _page_names_specific_child(cast: list[dict]) -> bool:
    """本页 cast 是否【显式点名了具体的"孩子"角色】(Anna/Mia/Tommy/Cate… 非泛指、非成人/宠物)。

    用户拍板 2026-06-08：点名了孩子 → 以本页点名名单为权威，不强行补齐未点名的另一位兄妹。
    """
    for c in cast:
        if c.get("is_generic"):
            continue
        base = (c.get("key") or "").split("_")[0]
        if base in _ADULT_KEYS:
            continue
        ch = CHAR_REGISTRY.get(base)
        if ch and ch.get("kind") not in ("pet", "brand", "family", "adult"):
            return True
    return False


def _page_scopes_to_named_nonlead(page: PageSpec, cast: list[dict]) -> bool:
    """本页是否【明确只围绕某具名非主角角色】（如 Anna 单人页）→ 不应硬塞 Mia/Tommy。

    用户拍板 2026-06-08（先理解文本→再修 IP）：内页"谁在场"先信本页文本。很保守：
      · 本页文本/Scene 没显式点名 Mia/Tommy、也没出现家人字样（妈妈/爸爸/爷爷/奶奶…）；
      · 本页 cast（注入主角前）里有至少 1 个【具名(非泛指)的人类配角】（如 Anna）；
      · 若本页还检测出【泛指小孩】(girl/boy→映射成 Mia/Tommy)：仅当 Scene 写明"单一主角焦点"
        （only ONE main character / alone / 独自…）时才判为同位语指代 → 仍可 scope（随后剔除这些泛指）；
        否则保守认为可能真有第二个孩子，不 scope。
    """
    txt = ((page.text or "") + " " + (getattr(page, "scene", "") or "")).lower()
    if _LEADS_RE.search(txt) or _FAMILY_RE.search(txt):
        return False
    named_nonlead = False
    has_generic_person = False
    for c in cast:
        base = (c.get("key") or "").split("_")[0]
        ch = CHAR_REGISTRY.get(base)
        if not ch or ch.get("kind") in ("pet", "brand"):
            continue
        if c.get("is_generic"):
            has_generic_person = True
        elif base in ("mia", "tommy"):
            # 真·具名主角在场（理论上已被 _LEADS_RE 拦下）→ 保险起见不 scope
            return False
        else:
            named_nonlead = True
    if not named_nonlead:
        return False
    if not has_generic_person:
        return True
    return bool(_SINGLE_FOCUS_RE.search(txt))


# 动物/非人物种词库（用于区分"人类具名朋友"与"动物寓言主角"）。
# 注意：绝不含 man/woman/boy/girl 等人类词——那些是人，不是动物。
_ANIMAL_SPECIES_RE = _re.compile(
    r"\b(llama|alpaca|ant|ants|grasshopper|bee|bees|butterfly|spider|snail|"
    r"fox|wolf|bear|bears|pig|pigs|piglet|goat|goats|cow|cows|horse|pony|sheep|lamb|"
    r"duck|duckling|hen|chick|rooster|chicken|mouse|mice|rat|rabbit|bunny|hare|"
    r"tortoise|turtle|lion|tiger|leopard|monkey|ape|gorilla|elephant|giraffe|zebra|"
    r"hippo|rhino|frog|toad|snake|lizard|owl|crow|bird|sparrow|robin|eagle|hawk|"
    r"deer|fawn|cat|kitten|dog|puppy|goose|swan|fish|whale|dolphin|shark|octopus|"
    r"crab|penguin|seal|otter|fox|squirrel|hedgehog|mole|bat|panda|koala|kangaroo|"
    r"camel|donkey|mule|ox|buffalo|bison|moose|raccoon|skunk|beaver|"
    r"dragon|dinosaur|dino|animal|creature)\b",
    _re.I,
)


def _recurring_human_friend_keys(outline: BookOutline) -> list[str]:
    """book_cast 里【反复出场、且是人类】的具名非 IP 朋友（如 Lucia）。

    动物/非人角色（蚂蚁/羊驼/狐狸…）不计入——它们走框架寓言逻辑，不影响"是否硬塞 Tommy"。
    """
    bc = getattr(outline, "book_cast", None) or {}
    out: list[str] = []
    for rid, role in bc.items():
        if not getattr(role, "needs_anchor", False):
            continue
        blob = f"{rid} {getattr(role, 'display', '')} {getattr(role, 'desc_en', '')}".lower()
        if _ANIMAL_SPECIES_RE.search(blob):
            continue  # 动物/非人 → 跳过（走框架寓言）
        out.append(rid)
    return out


def _nf_intro_page(page: PageSpec, outline: BookOutline) -> bool:
    """非虚构：封面或 P1（index≤1）保留 Mia+Tommy 探索引子。"""
    return _is_nonfiction(outline) and (page.page_type == "cover" or page.index <= 1)


def _nf_body_page(page: PageSpec, outline: BookOutline) -> bool:
    """非虚构正文内页（index≥2）：无主角，纯知识画面。"""
    return _is_nonfiction(outline) and page.page_type != "cover" and page.index > 1


_STANDALONE_I_RE = _re.compile(r"(?:^|[.!?]\s+|\n)I\s", _re.I)
_STANDALONE_WE_RE = _re.compile(r"(?:^|[.!?]\s+|\n)We\s", _re.I)


def _pronoun_lead_keys(page_text: str) -> list[str] | None:
    """本页正文独立 I/We 人称 → I=Tommy 单人；We=Mia+Tommy 双主角。无则 None。"""
    t = (page_text or "").strip()
    if not t:
        return None
    if _STANDALONE_WE_RE.search(t):
        return ["mia", "tommy"]
    if _STANDALONE_I_RE.search(t):
        return ["tommy"]
    return None


def _lead_keys_for_book(outline: BookOutline, page: PageSpec | None = None) -> list[str]:
    """这本书在【有人物的页/封面】上应出现的系列主角键（四规则自动判定，用户拍板 2026-06-08）。

      规则1 纯动物寓言 → 由框架逻辑在纯故事页移除主角（此函数仅决定读者页/封面带谁）。
      规则2/3 有具名人类朋友(Lucia)做主角之一 → 只带【被点名的那位兄妹】，绝不硬塞第二位
              （如《Mia and Her Spanish Friend》→ 只 Mia，配 Lucia；不加 Tommy）。
      规则4 科普封面/P1 → Mia & Tommy 双主角引子；科普正文内页 → 无主角。
      规则5 无具名朋友的兄妹·家庭故事 → 维持 Mia & Tommy 双主角。
    """
    if _is_nonfiction(outline):
        if page is not None and _nf_body_page(page, outline):
            return []
        return ["mia", "tommy"]
    friends = _recurring_human_friend_keys(outline)
    if friends:
        named = _named_sibling_leads(outline)
        return named or ["mia"]  # 至少保留 Mia 作系列主角之一
    return ["mia", "tommy"]


# ============================================================
#  框架式寓言（frame fable）：Mia/Tommy 是【读者】，寓言角色才是故事主角。
#  用户拍板 2026-06-07：读者不能同时是故事角色 —— 内页不得把他俩塞进寓言场景。
#  三种呈现模式（由 outline.frame_mode 选择）：
#    A+    ：封面=他俩拿书引子；中间页纯故事（他俩不入场）；末页=故事结尾内容+他俩合上书收尾。【默认·老师拍板 2026-06-08】
#    A     ：封面=他俩读书引子；内页全部纯故事（他俩不入场）。
#    B     ：每页都画“翻开的书+故事幻象”，他俩始终在画面一侧当读者。
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
    _anchored = [r for r in bc.values() if getattr(r, "needs_anchor", False)]
    if not _anchored:
        return False
    # 框架寓言的【反复出场主角】必须是非人类动物（狐狸/蚂蚁/羊驼…）。若锚定角色全是【人类】
    #   （如《The Library》里的真人馆员 Ms. Lee），这是普通真人故事，绝不是发光魔法书寓言——
    #   否则正文里满篇 "book / reading the / the book" 会被 _FRAME_MARKER 误判成寓言框架，
    #   把 Mia/Tommy 错当成"读者"、并经 _scrub_leads_clause 把含主角的场景句删成残句
    #   （Book09《The Library》整本误框 + P3/P5 场景被毁的根因·2026-06-10）。
    try:
        from book_cast import is_animal_role as _is_animal_role
        if not any(_is_animal_role(r) for r in _anchored):
            return False
    except Exception:
        pass
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
    """框架寓言里本页的呈现类型：
      'frame'       —— 他俩捧书阅读（封面：拿着书的引子）。
      'frame_close' —— 末页：既画故事结尾内容，也画他俩合上书的样子（老师拍板 2026-06-08）。
      'pure'        —— 纯故事页，他俩不入场。
    """
    is_cover = page.page_type == "cover" or page.index == 0
    mode = (mode or "A+").upper().replace("APLUS", "A+")
    if mode == "B":
        return "frame"
    if is_cover:
        return "frame"
    # A+（默认·老师拍板）：封面=拿书引子；中间纯故事；最后一个故事页=故事内容+合上书。
    if mode == "A+":
        if page.index == _last_story_index(outline):
            return "frame_close"
        return "pure"
    # mode A：封面之外全部纯故事
    return "pure"


# 英文称谓缩写里的句点（Ms./Mr./Mrs./Dr./St./Prof. 等）绝不能当成句末——
#   否则按句号切句时会把 "Ms. Lee 俯身……，Mia 看着" 切成 ["……Ms.", " Lee……Mia……"]，
#   前半截不含 Mia/Tommy 被保留、后半截被当"读者句"删掉，整页场景退化成 "……Ms." 残句
#   （Book09《The Library》P3/P5 根因·2026-06-10）。切句前先把缩写句点临时遮蔽，切完再还原。
_TITLE_ABBR_RE = _re.compile(r"\b(Mrs|Mr|Ms|Dr|St|Prof|Sr|Jr|Mt|vs|etc)\.", _re.IGNORECASE)
_ABBR_DOT = "\u0001"  # 占位符（正文不会出现的控制符）


def _protect_abbrev_dots(s: str) -> str:
    return _TITLE_ABBR_RE.sub(lambda m: m.group(0)[:-1] + _ABBR_DOT, s)


def _restore_abbrev_dots(s: str) -> str:
    return s.replace(_ABBR_DOT, ".")


def _scrub_leads_clause(s: str) -> str:
    """从寓言场景文本里删掉提及 Tommy/Mia 的句子（读者不进故事幻象内容）。"""
    if not s:
        return s
    protected = _protect_abbrev_dots(s)
    parts = _re.split(r"(?<=[。.!?！？\n])", protected)
    kept = [p for p in parts if not _re.search(r"\b(tommy|mia)\b", p, _re.IGNORECASE)]
    out = _restore_abbrev_dots("".join(kept).strip())
    return out or s


def _scrub_leads_fine(s: str) -> str:
    """【小句级】删掉提及 Tommy/Mia(或中文"米娅/汤米")的小句，但保留同句里其它角色/场景小句。

    用于【科普内页】(NF body)：AI 生成的 scene_cn 常把 Mia/Tommy 误写成动作执行者
    （"Mia 踮脚抽书…旁边 Tommy 蹲着…柜台后图书管理员阿姨…"），而科普内页规则是【主角不出场】。
    原 _scrub_leads_clause 只按句末标点切，会把整句(连同图书管理员)一起删光。这里按
    【，、；。.!?！？\n】更细地切，仅剔除含主角的小句，把动作归还给真正的科普对象（图书管理员等）。
    根治 Book18 P4 根因（2026-06-11·SYMPTOM3）：内页"主角不出场"与"Mia 抽书"自相矛盾 → 出错。
    """
    if not s:
        return s
    protected = _protect_abbrev_dots(s)
    parts = _re.split(r"(?<=[，,、；;。.!?！？\n])", protected)
    kept = [p for p in parts
            if not _re.search(r"\b(tommy|mia)\b", p, _re.IGNORECASE)
            and not _re.search(r"米娅|米雅|汤米|汤姆", p)]
    out = _restore_abbrev_dots("".join(kept).strip())
    # 收尾标点清理（避免删后留下孤立的 ，、；）
    out = _re.sub(r"^[，,、；;。\s]+", "", out).strip()
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


def _vision_frame_close_wrapper(tale_scene: str) -> str:
    """末页【合书收尾】框架（老师拍板 2026-06-08）：
    画面既呈现故事结尾的内容（发光幻象，仍是主体），也画出 Mia 和 Tommy 把那本魔法故事书
    【正在合上 / 刚刚合上】、相视微笑的满足样子——读者读完了这个故事。
    """
    return (
        "画面采用【合书收尾·读者框架】构图：\n"
        "① 故事结尾幻象（主体）——从那本魔法书里升起的柔和发光故事结尾画面，仍占画面约 65–75%、铺满主要区域并延伸到上/右边缘，"
        "呈现故事的结局：" + tale_scene.rstrip("。") + "。\n"
        "② 读者收尾（次要、约 25%）——Mia 和 Tommy 在画面【左下角】一起【正把那本会发光的魔法故事书轻轻合上】（或刚合上、双手按在书面上），"
        "相视而笑、神情满足温暖，像刚读完一个好故事；他们清晰可辨但明显小于故事幻象。\n"
        "③ 他们始终是【读者】，没有进入故事场景、不与故事角色互动；合书的现实读书区与故事幻象之间只用一道很细的柔和光晕过渡，"
        "除左下角读者一角外，其余画面被故事结尾幻象填满，不留大片空白。"
    )


# ============================================================
#  故事连续性层（用户拍板 2026-06-07）：画面必须跟住故事的连续设定。
#  典型坑：官方只在部分页标了「Rainy variant」，导致同一场雨里中间页突然放晴。
#  解决：扫全书天气/时间线索，把"同一场持续天气"贯穿到区间内的所有户外页。
# ============================================================
# 注意（2026-06-08 修）：原来裸的 pour|pouring 会把 "sunlight pouring from the window"（阳光倾泻）
#   误判成下雨，导致晴天页凭空下雨。现要求 pour 必须带"雨/水"语境才算下雨。
_RAIN_RE = _re.compile(
    r"\b(rain|rainy|raining|rainfall|storm|stormy|downpour|drizzle|drizzly|thunder|"
    r"soaked|drenched|wet (?:forest|ground|path|grass))\b|"
    r"\b(?:rain|water)\s+pour\w*|\bpour\w*\s+rain\b|"
    r"暴雨|大雨|下雨|雨中|雨水",
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


# ============================================================
#  场景/地点【布景连续性】层（用户拍板 2026-06-08）
#  典型坑：L3#9 同一条走廊，每页各画一条不同样子的走廊（墙色/地面/门窗/柜子都变）。
#  解决：识别连续多页发生在【同一地点】（走廊/教室/房间/图书馆…）的页区间，
#       给区间内的页注入"同一套实景的不同瞬间·布景完全一致"的硬指令，
#       并附该地点的【固定布景蓝本】（同一文案、跨页复用 → 模型每页画出一致的空间）。
# ============================================================
# 地点关键词 → (规范地点名, 固定布景蓝本)。蓝本跨页复用，保证同一地点每页长得一样。
_LOCATION_PATTERNS: list[tuple[_re.Pattern, str, str]] = [
    (_re.compile(r"hallway|corridor|走廊|长廊", _re.I), "学校走廊",
     "同一条学校走廊：暖米白上墙 + 浅色墙裙，米色/浅灰方砖地面，一侧一整排同款木质储物柜、"
     "另一侧一排明亮大窗（窗外淡蓝天空与绿意），天花板规则排列的方形吸顶灯，走廊尽头一扇带玻璃的门"),
    (_re.compile(r"classroom|\bclass\b|教室|课室", _re.I), "教室",
     "同一间教室：暖米白墙面，固定位置的一两组浅色课桌椅，一侧单扇明亮大窗（窗外淡蓝天空与绿意），"
     "前方一面简洁浅色墙（不写满字），浅木地板，墙角同一个矮书架"),
    (_re.compile(r"library|图书馆|阅读角|书架", _re.I), "图书馆",
     "同一处图书馆：成排浅色木书架配柔色书脊（位置固定），暖米墙面，一侧大窗柔光，"
     "中间同一组浅色阅读桌椅，浅色地面，角落同一盆绿植"),
    (_re.compile(r"\bkitchen\b|厨房", _re.I), "厨房",
     "同一间厨房：暖米白橱柜与浅色台面（布局固定），一扇窗台带绿植的窗，浅色地砖，同一组灶台与水槽位置"),
    (_re.compile(r"bedroom|卧室|睡房", _re.I), "卧室",
     "同一间卧室：暖色墙面，固定位置的一张小床与床头柜，一扇带浅色窗帘的窗，浅木地板，墙上同一幅小画"),
    (_re.compile(r"living ?room|客厅|起居室", _re.I), "客厅",
     "同一间客厅：暖米白墙面，固定位置的一张浅色沙发与矮茶几，一扇大窗柔光带绿植，浅木地板，墙上同一组装饰"),
    (_re.compile(r"museum|博物馆|展厅|展馆", _re.I), "博物馆展厅",
     "同一处博物馆展厅：高挑空间、浅色墙面与规则排列的展柜/展板（位置固定），柔和均匀的展陈灯光，浅色地面"),
]


def _page_location(outline: BookOutline, page: PageSpec) -> tuple[str, str] | None:
    """返回本页的 (规范地点名, 固定布景蓝本)；识别不到具体地点返回 None。"""
    txt = _page_full_text(outline, page)
    for rex, name, blueprint in _LOCATION_PATTERNS:
        if rex.search(txt):
            return name, blueprint
    return None


def _location_runs(outline: BookOutline) -> dict[int, tuple[str, str, int, int]]:
    """找出"连续多页处在同一地点"的页区间。

    返回 {page_index: (地点名, 布景蓝本, 区间首页index, 区间末页index)}，
    仅收录长度≥2 的同地点连续段（单页地点无需连续约束）。
    """
    story = [p for p in outline.pages if not (p.page_type == "cover" or p.index == 0)]
    out: dict[int, tuple[str, str, int, int]] = {}
    i = 0
    while i < len(story):
        loc = _page_location(outline, story[i])
        if loc is None:
            i += 1
            continue
        name, blueprint = loc
        j = i + 1
        while j < len(story):
            nxt = _page_location(outline, story[j])
            if nxt is None or nxt[0] != name:
                break
            j += 1
        if j - i >= 2:  # ≥2 连续页同地点 → 需要布景连续
            lo, hi = story[i].index, story[j - 1].index
            for k in range(i, j):
                out[story[k].index] = (name, blueprint, lo, hi)
        i = j
    return out


def _location_continuity_note(outline: BookOutline, page: PageSpec,
                              runs: dict[int, tuple[str, str, int, int]] | None = None) -> str:
    """本页若处于"同一地点连续区间"，返回一段【布景必须完全一致】的硬指令。"""
    if page.page_type == "cover" or page.index == 0:
        return ""
    runs = _location_runs(outline) if runs is None else runs
    info = runs.get(page.index)
    if not info:
        return ""
    name, blueprint, lo, hi = info
    return (
        f"【同一场景·布景连续】本页与第 {lo}–{hi} 页是【同一处{name}】的不同瞬间：{blueprint}——"
        "空间布局、墙面/地面/天花材质与颜色、门窗与固定陈设位置、整体配色与光照，与该场景其它页完全一致；"
        "只改人物动作/表情与机位，绝不重新设计这个场景。"
    )


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


# ── 可读文字清洗（用户拍板 2026-06-09）─────────────────────────────────
#   scene_cn 直接进正向 prompt 置顶段；"写着 Big Game 的横幅 / 记分牌""引号内英文台词"
#   会诱导模型在图里画出可辨认英文字母（绘本铁律是【全图无文字】）。这里做【通用】清洗：
#   把这类措辞改写成"抽象图案/色块装饰展板（无可辨认文字）""张嘴说话、不画字母"，不逐书硬编码。
_SIGN_NOUNS = (
    r"(海报|横幅|条幅|横额|旗帜|锦旗|标语|招牌|牌子|标牌|指示牌|路牌|门牌|"
    r"记分牌|计分牌|比分牌|价签|价格牌|标价牌|告示牌?|公告牌?|布告|通知|展板|"
    r"看板|黑板|白板|菜单|奖状|证书|徽章|条幅|banner|标题|字样)"
)
# "（上面）写着/印着 X 的<招牌类>" → 抽象图案、无文字
_SIGN_WRITE_RE = _re.compile(
    rf"(?:上面)?(?:写着|印着|标着|写有|印有|书写着|上书|标有)[\"“”'']?[^，。；、！？\n]{{0,40}}?[\"“”'']?的{_SIGN_NOUNS}",
    _re.I)
# "<招牌类>上写着/印着 X" → 招牌（上面只有抽象图案、无文字）
_SIGN_ON_RE = _re.compile(
    rf"{_SIGN_NOUNS}上(?:面)?(?:写着|印着|标着|写有|印有|书写着|标有)[\"“”'']?[^，。；、！？\n]{{0,40}}",
    _re.I)
# 引号内含连续英文字母（多为台词 / 招牌字样）→ 改"张嘴说话、不画字母"
_QUOTED_EN_RE = _re.compile(r"[\"“'']([^\"”'’\n]*[A-Za-z]{2,}[^\"”'’\n]*)[\"”'’]")


def _scrub_readable_text(scene_cn: str) -> str:
    """把会诱导画出可辨认文字的措辞改写为"抽象图案/张嘴说话不画字母"（通用，非逐书硬编码）。"""
    if not scene_cn:
        return scene_cn
    s = scene_cn
    s = _SIGN_WRITE_RE.sub(r"印有抽象图案与装饰色块的\1（无任何可辨认文字）", s)
    s = _SIGN_ON_RE.sub(r"\1（上面只有抽象图案与色块装饰、无任何可辨认文字）", s)
    s = _QUOTED_EN_RE.sub("（角色张嘴说话的神态，不要画出任何字母或文字）", s)
    return s


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
    # 上限 3→5（修 L3 #42 P7「全家餐桌」：官方点名 Mia/Tommy/Mom/Dad 4 人时，
    #   旧 [:3] 会丢掉第 4 人 → 无参考图只靠文字 → 形象漂移）。
    return out[:5]


# ============================================================
#  未成年安全·机位/姿态硬伤净化（2026-06-11 · L3 Book27 Morning Chaos P4 修复沉淀）
#  根因：未成年角色"趴地/钻床底 + 屁股撅起/撅臀" 与 "仰视(从下往上)低机位" 组合，
#  会触发图像 API 的未成年安全过滤（HTTP 400 拒绝 → 退化成 mock 占位）。
#  本函数只【软化/中性化既有措辞】，不新增任何对儿童身体的描述：
#    1) 一律删除"屁股撅起/撅起屁股/翘起屁股/撅臀"等措辞；
#    2) 当本页同时含"趴地/钻床底"类俯身线索时，把"仰视(从下往上)低机位"降为"平视机位"。
#  仅在命中危险组合时改写，其余页面零影响、不可回退误伤。
# ============================================================
_MINOR_BUTT_RE = _re.compile(r"[，,、；;\s]*(?:屁股撅起|撅起屁股|翘起屁股|撅臀)[^，。,.；;]*")
_MINOR_PRONE_HINTS = ("趴在地", "趴在床", "趴地", "钻进床底", "头钻进床", "把头探向床底",
                      "把头钻进床", "床底下", "探进床底")
_LOW_ANGLE_HINTS = ("仰视", "从下往上看", "low-angle", "low angle", "from below")


def _sanitize_minor_safety(text: str) -> str:
    """软化未成年"撅臀+低机位俯身"危险组合（防 API 未成年安全 400）。只中性化既有措辞。"""
    if not text:
        return text
    low = text.lower()
    has_butt = bool(_MINOR_BUTT_RE.search(text))
    has_prone = any(h in text for h in _MINOR_PRONE_HINTS)
    has_low = ("仰视" in text or "从下往上看" in text
               or "low-angle" in low or "low angle" in low or "from below" in low)
    out = text
    # 1) 永久剔除"撅臀"类措辞（未成年安全红线）
    if has_butt:
        out = _MINOR_BUTT_RE.sub("", out)
    # 2) 俯身趴地/钻床底 + 低机位仰视 → 机位降为平视（精确替换 CAMERA_ANGLE_CN['low'] 整句）
    if (has_prone or has_butt) and has_low:
        out = out.replace(CAMERA_ANGLE_CN["low"], CAMERA_ANGLE_CN["eye"])
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
    _lead_keys = _lead_keys_for_book(outline, page)

    def _inject_leads(base_cast: list[dict]) -> list[dict]:
        """把本书的系列主角（按四规则判定：双主角 / 仅 Mia 等）置于队首，再并入已有配角，去重，≤5 人。"""
        pair = [
            e for k in _lead_keys
            for e in (_make_protagonist_entry(k, ip_age),) if e
        ]
        lead_keys = {e.get("key") for e in pair}
        rest_named = [c for c in base_cast
                      if not c.get("is_generic") and c.get("key") not in lead_keys]
        rest_generic = [c for c in base_cast
                        if c.get("is_generic") and c.get("key") not in lead_keys]
        # 上限 3→5：一页可同时容纳 Mia/Tommy/Mom/Dad 等家人各带 1 张定妆图（修多人同框漂移）。
        return (pair + rest_named + rest_generic)[:5]

    def _is_person_entry(c: dict) -> bool:
        ch = CHAR_REGISTRY.get((c.get("key") or "").split("_")[0])
        return bool(ch) and ch.get("kind") not in ("pet", "brand")

    # 框架寓言判定（用户拍板 2026-06-07/08）：他俩是读者，内页不得入故事场景。
    #   默认 A+：封面=拿书引子；中间页纯故事；末页=故事结尾内容+合上书。
    _frame_fable = _is_frame_fable(outline)
    _frame_kind = (
        _frame_page_kind(outline, page, getattr(outline, "frame_mode", "A+"))
        if _frame_fable else None
    )
    # SOP 人称：独立 I=Tommy 单人；We=双主角（NF 正文内页无主角，不应用）
    if not _nf_body_page(page, outline):
        _pk = _pronoun_lead_keys(page.text or "")
        if _pk is not None and not (_frame_fable and _frame_kind == "pure"):
            _lead_keys = _pk
    if official_has_scene:
        # ★ 官方权威优先（用户拍板 2026-06-07）：本页"谁在场"以官方 prompt 点名为准。
        #   纯寓言页（官方没点到 Mia/Tommy）→ 不强塞主角；封面若官方漏写主角则补全双主角。
        cast = _cast_from_official(official_raw, ip_age)
        if _frame_fable:
            if _frame_kind == "pure":
                # 纯故事页：移除主角（读者不入场），只留寓言角色（由 book_cast 注入锚图）
                cast = [c for c in cast if c.get("key") not in ("mia", "tommy")]
            else:
                # 框架页/合书页：确保双主角作为【读者】在场（置顶），寓言角色作幻象（book_cast 注入）
                cast = _inject_leads(cast)
        elif (is_cover or _nf_intro_page(page, outline)) and not any(
                c.get("key") in ("mia", "tommy") for c in cast):
            cast = _inject_leads(cast)
    else:
        if _frame_fable:
            # story-only 框架寓言：同样按 A+ 处理（封面/末页带读者，中间纯故事）
            if _frame_kind == "pure":
                cast = [c for c in cast if c.get("key") not in ("mia", "tommy")]
            else:
                cast = _inject_leads(cast)
        else:
            _book_leads = _book_centers_on_leads(outline)
            _page_has_person = any(_is_person_entry(c) for c in cast)
            # 本页是否【显式点名了具体的"孩子"角色】（Anna/Mia/Tommy/Cate… 等，非泛指、非成人）。
            # 用户拍板 2026-06-08（先理解文本→只用 Scene 点名者）：点名了孩子 → 以本页在场名单为权威，
            # 不再强行补齐未点名的另一位兄妹（修“P2 只有 Anna+Mia 却乱入 Tommy / P4 只有 Anna+Tommy 却乱入 Mia”）。
            _names_child = _page_names_specific_child(cast)
            if is_cover or _nf_intro_page(page, outline):
                # 封面 / 科普开篇(P1)：双主角探索引子
                cast = _inject_leads(cast)
            elif _page_scopes_to_named_nonlead(page, cast):
                # 本页明确只围绕某具名配角（如 Anna 单人页）→ 信本页在场名单，不硬塞 Mia/Tommy。
                # 同时剔除把同位语"girl/boy"误映射出来的泛指主角（修“Anna 单人页凭空多出 Mia/Tommy”）。
                _named = [c for c in cast if not c.get("is_generic")]
                cast = _named or cast
            elif _names_child and _book_leads and len(_lead_keys) >= 2 and (
                    lambda _named_keys: bool(_named_keys) and _named_keys <= set(_lead_keys)
                )({
                    (c.get("key") or "").split("_")[0]
                    for c in cast
                    if (not c.get("is_generic"))
                    and (c.get("key") or "").split("_")[0] not in _ADULT_KEYS
                    and (CHAR_REGISTRY.get((c.get("key") or "").split("_")[0]) or {}).get("kind")
                        not in ("pet", "brand", "family", "adult")
                }):
                # 双主角书（Mia+Tommy）且本页点名的具名孩子【全是系列主角】（如只点名 Tommy）→
                #   补齐缺席的另一位兄妹（修 Book63 P3 只点名 Tommy 导致 cast 缺 Mia）。
                #   有具名非主角朋友（Anna/Lucia）的页不触发（朋友不在 _lead_keys），保持既有行为。
                cast = _inject_leads(cast)
            elif _names_child:
                # 本页已点名具体的孩子 → 以本页点名的在场名单为权威：不强行补齐缺席兄妹（防乱入）。
                # 但【仅剔除与已具名孩子同性别的泛指主角】(同位语 girl/boy 多指代那个已点名的同性别孩子)，
                # 绝不再无脑删掉所有 generic 主角——否则 "Anna and her brother"（brother→泛指 Tommy）
                # 会把哥哥/Tommy 一并误删（修：内页漏画第二个孩子）。真正被点名的 Mia/Tommy 始终保留。
                _named_child_genders = set()
                for _c in cast:
                    if _c.get("is_generic"):
                        continue
                    _b = (_c.get("key") or "").split("_")[0]
                    if _b in _ADULT_KEYS:
                        continue
                    _ch = CHAR_REGISTRY.get(_b) or {}
                    if _ch.get("kind") in ("pet", "brand", "family", "adult"):
                        continue
                    if _ch.get("gender") in ("girl", "boy"):
                        _named_child_genders.add(_ch.get("gender"))

                def _drop_coref_generic(c: dict) -> bool:
                    if not c.get("is_generic"):
                        return False
                    base = (c.get("key") or "").split("_")[0]
                    if base == "mia":
                        return "girl" in _named_child_genders
                    if base == "tommy":
                        return "boy" in _named_child_genders
                    return False

                cast = [c for c in cast if not _drop_coref_generic(c)]
            elif _book_leads and not _nf_body_page(page, outline):
                # 双主角系列故事的【代词页/未点名页】（如 Book63 P2/P4、Book69 P3/P4/P6：只用 They/them
                #   或只出现一次性成人/无 IP 人物）→ 强制让兄妹双主角到场并【挂新定妆锚图】，
                #   不再因 cast 无 IP 人物而落到过期 trio 兜底图导致 Tommy 漂深蓝/Mia 脱模（根因一·2026-06-10）。
                #   仅命中"以系列主角为中心的书"(_book_leads)，纯童话(_book_leads=False)不受影响。
                cast = _inject_leads(cast)
            # else: 纯童话内页 —— 保留通用映射（girl→Mia / boy→Tommy），单主角即可，不强制第二位

    # 1.9) 家长形象锁（用户拍板 2026-06-09）：页面是"和家人在家做饭/吃饭/团聚"等语境、
    #   但 cast 里没有任何家长时，注入系列固定的【妈妈】IP（波浪长发成年女性 + 锚图 + 成人年龄锁），
    #   避免模型自由发挥把家长画成扎马尾的陌生年轻女子（修 L3 #42 P7 妈妈形象不符）。
    if (not is_cover and not _frame_fable
            and _FAMILY_RE.search((cast_text or "").lower())
            and not any((c.get("key") or "").split("_")[0] in _ADULT_KEYS for c in cast)):
        _mom = _make_family_adult_entry("mom", ip_age)
        if _mom and not any((c.get("key") or "") == "mom" for c in cast):
            cast = (cast + [_mom])[:5]

    # 1.95) NF 分页收口：封面/P1 双主角引子；正文内页(P2-P7)剔除主角
    if _nf_body_page(page, outline):
        cast = [c for c in cast if c.get("key") not in ("mia", "tommy")]
    elif _nf_intro_page(page, outline) and not _frame_fable:
        if not any(c.get("key") in ("mia", "tommy") for c in cast):
            cast = _inject_leads(cast)

    # 2) 场景描述
    if is_cover:
        who = "、".join(c.get("name", "") for c in cast if c.get("name")) or "系列主角 Mia、Tommy"
        theme = (getattr(outline, "theme", "") or "").strip()
        nf = _is_nonfiction(outline)
        cover_action = (
            f"{who} 作为系列小主角，正投入地置身与主题相关的真实场景中、专注参与本主题的活动"
            "（动手做的事就动手操作、触碰、参与，观看/探索性质就专注地观察、指认或眺望眼前的事物；"
            "自然投入其中，不是面向镜头并排呆站摆拍、也不是远远旁观的路人）"
            if nf else
            f"{who} 一起投入在与故事主题相关的一个生动瞬间里——在做某件具体的事/彼此互动，神情自然鲜活，"
            "绝不是面向镜头并排站着摆拍"
        )
        scene_cn = (
            f"绘本封面，书名《{title}》" + (f"，主题：{theme}" if theme else "") + "。"
            f"{cover_action}；用有设计感的电影式取景——人物七分身或全身、带自然角度"
            "（三四分之一侧身，或轻微俯视/仰视/越肩主角视角，绝不正面呆板平视），"
            "前景—中景—背景拉出清晰的远近层次与景深，画面通透、有空间纵深与故事氛围，像高级精印实体绘本的封面；"
            "人物适度偏置于画面一侧，画面上方保留约 20-25% 一条干净的浅色原生留白区域（天空/远景等）用于排书名标题，其余画面由主体与环境充实饱满地填满、不空旷。"
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
            elif _frame_fable and _frame_kind == "frame_close":
                # 末页合书：故事结尾幻象 + 他俩合上书收尾
                scene_cn = _vision_frame_close_wrapper(_scrub_leads_clause(scene_cn))
        else:
            scene_cn = _scene_to_cn(page, outline)
            if _frame_fable and _frame_kind == "pure":
                scene_cn = _scrub_leads_clause(scene_cn)
            elif _frame_fable and _frame_kind == "frame":
                scene_cn = _vision_frame_wrapper(_scrub_leads_clause(scene_cn))
            elif _frame_fable and _frame_kind == "frame_close":
                scene_cn = _vision_frame_close_wrapper(_scrub_leads_clause(scene_cn))
    # 2.4) 配角存在判定【必须在注入负向样板前快照】：下面的非虚构/连续性注入会往 scene_cn
    #   追加"不要凭空添加陌生路人/围观人群…"等【负向指令文案】，其中"围观人群/路人"会被
    #   _scene_has_nonlead_extras 的人群正则【误判成"本页真有配角"】，从而在纯双主角内页错误
    #   触发"配角确定性配色轮 + 配角多元各异 + 封面/群像等高锁"整段噪声（修 2026-06-10）。
    #   故此处对【未被污染的真实场景】快照 has_extras，再传给 _build_positive_concise。
    _scene_extras_raw = (not is_cover) and _scene_has_nonlead_extras(scene_cn)
    # 主题锁匹配【必须用未被示例词污染的原始场景】快照：下面 2.4 会往 scene_cn 追加
    #   "(一起播种/采摘/清洗/搬运/挑选等)"这类示例动作词，其中"播种"含"种"会被 _THEME_SIGNATURE
    #   的"种植/园艺"正则误命中，把花盆/铲子/浇水硬贴到警察/消防/医生页（Book66 根因·2026-06-10）。
    #   故此处先存一份真实场景，专供 _scene_story_lock 做主题判定。
    _raw_scene_for_theme = scene_cn
    if not is_cover:
        if _nf_body_page(page, outline):
            # 科普内页【主角不出场】：先把 AI 误塞的"Mia/Tommy 在做某事"小句删掉，把动作归还给
            #   真正的科普对象（图书管理员/工人等），避免"内页不出现主角"与"Mia 抽书"自相矛盾
            #   （Book18 P4 根因·2026-06-11·SYMPTOM3）。
            scene_cn = _scrub_leads_fine(scene_cn)
            scene_cn = (
                scene_cn.rstrip("。") +
                "。本页为科普知识画面：以本页科普对象/场景/过程为主体（占画面主要面积、清晰可辨），"
                "专注呈现知识可视化（图解、实景、剖面、地图、工艺流程等），让观众直观理解本页知识点；"
                "不出现系列主角 Mia/Tommy（他俩仅在封面/开篇登场作探索引子，内页不出场）；"
                "未点名者不凭空新增路人；科普对象按真实比例样貌呈现。"
            )
        # Non-fiction 开篇(P1)：把双主角作为"小小探索家"自然织入画面
        elif _is_nonfiction(outline) and cast:
            names = "和".join(c["name"] for c in cast if c.get("name"))
            if names:
                # 用户拍板 2026-06-09（修克隆人根因）：当本页主体动作由【非主角成人】(农夫/工人/店员等)
                #   执行时，Mia/Tommy 退为画面一角的【小观察者】，主体是那 1-2 位国际化成人；
                #   并强制：除主角外不得再出现别的小孩、工人绝不能画成与主角雷同的人（防分身/克隆）。
                if _scene_lead_is_nonlead_actor(scene_cn, names):
                    # 用户拍板 2026-06-10（回退过度叠加）：不再写死"仅 1 位成年人/只 2 个孩子"——
                    #   按本页 scene_cn 实际点名的人物来画（多位职业角色都可同框），让 Mia/Tommy 作为
                    #   下场参与的主角与这些大人同框、一起做事或专注地看；未点名者不新增陌生路人。
                    scene_cn = (
                        scene_cn.rstrip("。") +
                        f"。按本页点名人物来画：出现的成年人（可一位或多位，国际化多元、彼此各异，且与主角 {names} "
                        "长相完全不同、绝不撞脸撞发色撞衣色)；"
                        f"{names} 作为下场参与的小主角与大人同框、就在身旁——动手就一起动手、看讲就专注地看/指认；"
                        f"{names} 始终是清晰主角之一（脸清晰、表情专注、正常 10 岁比例，成人与孩子约 4:3、孩子头顶到成人肩部），"
                        f"不画过小/脸糊；画面里小孩只有 {names}（各一个），不再出现别的小孩；"
                        "未点名者不凭空新增(不加路人/围观)，成年人不画成与主角雷同、背景不复制酷似主角的小孩；"
                        "科普对象按真实比例样貌呈现。"
                    )
                else:
                    scene_cn = (
                        scene_cn.rstrip("。") +
                        f"。本页主角与主体就是 {names}：作为下场参与的小主角全程在场、是画面焦点，专注参与本页这件事"
                        "——动手就亲手操作/触碰/翻动(手上有真实动作)，观看/参观就专注地看、俯身细看或用手指认；"
                        f"绝不被晾在远景当路人、也不并排呆站摆拍；默认整张画面只有 {names} 两个孩子，"
                        "不为凑场景凭空加陌生路人/围观人群；科普对象按真实比例样貌呈现，"
                        "让主角与该事物【正在发生的互动】成为画面焦点。"
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

    # 2.7) 场景布景连续层：同一地点连续多页 → 布景/建筑/配色完全一致（修 L3#9 走廊不连续）
    if not is_cover:
        _loc = _location_continuity_note(outline, page)
        if _loc:
            scene_cn = scene_cn.rstrip("。") + "。" + _loc

    # 2.8) 老师确认的【场景安全线】（块4·用户拍板 2026-06-08）：作为本页画面权威核心，置于最前
    _sl = (getattr(page, "safety_line", "") or "").strip()
    if _sl and not is_cover:
        scene_cn = f"【本页画面·老师已确认·必须照此】{_sl.rstrip('。')}。" + scene_cn

    # 2.9) 可读文字清洗：把"写着X的横幅/记分牌""引号内英文台词"等会诱导画英文字母的措辞，
    #   改写成"抽象图案/色块装饰（无可辨认文字）/张嘴说话不画字母"（通用清洗，非逐书硬编码）。
    scene_cn = _scrub_readable_text(scene_cn)

    # 3) 镜头 + 机位角度（v5）
    # SOP 第4条：先做一次全书景别多样性收口（任意连续4页≥2种景别），幂等。
    _ensure_shot_variety(outline)
    shot = (page.shot or DEFAULT_SHOT).strip().lower()
    if shot not in COMPOSITION_CN:
        shot = DEFAULT_SHOT
    composition_cn = COMPOSITION_CN[shot]
    angle_cn = "" if is_cover else _angle_phrase(_resolve_camera_angle(page, outline))
    focus_cn = "" if is_cover else (getattr(page, "focus", "") or "").strip()
    # 科普内页【主角不出场】：本页主体动作若由 Mia/Tommy 执行，清掉它（动作归还给科普对象），
    #   避免 image_prompts 的"本页主体动作：Mia 抽书"与"内页不出现主角"矛盾（SYMPTOM3·2026-06-11）。
    if focus_cn and _nf_body_page(page, outline) and (
            _re.search(r"\b(tommy|mia)\b", focus_cn, _re.IGNORECASE)
            or _re.search(r"米娅|米雅|汤米|汤姆", focus_cn)):
        focus_cn = ""
    hook_cn = "" if is_cover else (getattr(page, "hook", "") or "").strip()
    # SOP 第7/二.5 条：本页情绪 → 固定面部细节词表（封面不强加；归并不到六类则留空）。
    expr_face_cn = "" if is_cover else _emotion_face_cn(getattr(page, "expression", "") or "")

    # 4) 留白
    blank_cn = _blank_text(page.index) if not is_cover else (
        "利用画面上方场景原生的空旷区域（天空 / 明亮天花板 / 大片墙面等，保留真实色彩与纹理、其上无人物道具）"
        "留出一块干净留白供后期软件叠加书名；这块区域只保留干净的原生背景，"
        "作画时绝对不要在上面画任何文字 / 字母 / 书名 / 标题，也不要画纯白色块或空白方框"
    )

    # 5) 关键道具检测（v3 增强：从故事文本抓 hamster/eraser/books/cookies 等）
    key_props = [] if is_cover else _detect_key_props(cast_text)

    # 6) 环境推断（v2.0 新增）— 根据故事文本主动给"环境必须有 X/Y/Z"
    env_hint = "" if is_cover else _detect_environment((page.text or "") + " " + scene_cn)

    # 7) 参考图策略（v2.2：本页 cast 里每人 1 张，最多 5 张）。
    #   上限从 3→5（修 L3 #42 P7「全家餐桌」：一页含 Mia/Tommy/Mom/Dad 4 人时，
    #   第 4 个人没参考图只靠文字 → 形象漂移。下游 build_reference_sheet 把多张横向拼成
    #   1 张定妆合集，gpt-image-2 仍只收 1 张图，拼图只是更宽，不影响接口。
    _REF_CAP = 5
    refs: list[Path] = []
    for c in cast:
        if c.get("ref_path") and len(refs) < _REF_CAP:
            refs.append(c["ref_path"])

    # 7.5) 书内角色册（用户拍板 2026-06-07）：一次性/非 IP 角色的"书内锁"。
    #   反复出场角色 → 注入全书统一外观描述（防跨页漂移）+ 挂书内定妆锚图（与 IP 同等锁死）。
    #   先于正向段计算：concise 公式把该锁并入【3·主体角色】段（不再散落篇尾）。
    extra_note, extra_refs, oneoff_cast = _apply_book_cast(
        outline, page, official_raw, current_refs=len(refs))
    for rp in extra_refs:
        if len(refs) < _REF_CAP:
            refs.append(rp)

    # 8) 组装正向(1-19 段公式) + 反向(第 20 段)。
    #   CONCISE_PROMPT=True（用户拍板 2026-06-09，实测验证）→ 结构化公式·正向写法；
    #   False → 旧版冗长全锁写法（保留作回退）。
    story_lock = _scene_story_lock(outline, page, _raw_scene_for_theme, is_cover)
    if _CONCISE_PROMPT:
        # leads_active：本页主角是否“正在动手参与”的实施者（用于 ★0 段措辞）。
        #   框架寓言里 Mia/Tommy 是读者/旁观者，不能声称他们在做故事里的事 → 关闭该措辞。
        _leads_active = not bool(_frame_fable) and not _nf_body_page(page, outline)
        # 背景无关小动物默认关闭（用户拍板 2026-06-10）：本页无任何剧情动物时注入正向兜底。
        _inject_anim = not _has_registered_story_animal(cast, oneoff_cast)
        positive = _build_positive_concise(
            is_cover=is_cover, title=title, scene_cn=scene_cn, cast=cast, ip_age=ip_age,
            env_hint=env_hint, key_props=key_props, composition_cn=composition_cn,
            blank_cn=blank_cn, angle_cn=angle_cn, focus_cn=focus_cn, hook_cn=hook_cn,
            oneoff_note=extra_note, story_lock=story_lock, leads_active=_leads_active,
            has_extras=_scene_extras_raw, expr_face_cn=expr_face_cn,
            inject_anim_lock=_inject_anim,
            nf_body_no_leads=_nf_body_page(page, outline) and not is_cover,
        )
        negative = _build_negative_concise(cast=cast, page_text=(page.text or ""), ip_age=ip_age,
                                           oneoff_cast=oneoff_cast)
    else:
        positive = _build_positive_v3(
            is_cover=is_cover, title=title, scene_cn=scene_cn, cast=cast, ip_age=ip_age,
            env_hint=env_hint, key_props=key_props, composition_cn=composition_cn,
            blank_cn=blank_cn, angle_cn=angle_cn, focus_cn=focus_cn, hook_cn=hook_cn,
        )
        negative = _build_negative_v3(cast=cast, page_text=(page.text or ""), ip_age=ip_age)

    # 9) 最终 prompt = 正向 + 反向
    prompt_text = BuiltPromptCN.join(positive, negative)
    # 回退(verbose v3)路径：一次性角色锁仍按旧方式追加（concise 已并入【3·主体角色】段）。
    if not _CONCISE_PROMPT and extra_note:
        prompt_text = prompt_text + "\n\n" + extra_note

    # 10.5) 未成年安全净化：剔除"撅臀"类措辞、把"趴地/钻床底+低机位仰视"降为平视
    #   （2026-06-11·防 L3 Book27 P4 那类未成年安全 400 拒绝再次发生）。在预算裁剪前做，
    #   这样净化后的措辞也参与去重/预算统计。scene_cn 同步净化，供自审/定向修图复用。
    prompt_text = _sanitize_minor_safety(prompt_text)
    scene_cn = _sanitize_minor_safety(scene_cn)

    # 11) 超长保护：去重精简重复套话；超 3800 字符打告警（防下游 4000 截断切掉尾部铁律）。
    _tag = "封面" if is_cover else f"P{page.index}"
    prompt_text = _enforce_prompt_budget(prompt_text, label=f"{title} {_tag}")

    return BuiltPromptCN(
        positive=positive,
        negative=negative,
        prompt=prompt_text,
        references=refs,
        used_characters=cast + oneoff_cast,
        scene_cn=scene_cn,
        story_lock=story_lock,
    )


def _apply_book_cast(outline, page, official_raw: str, current_refs: int):
    """书内角色册接线：返回 (注入的锁定描述文本, 追加的锚图路径列表, 调试用一次性 cast)。

    一次性角色【永不映射成 Mia/Tommy】；这里只为它们补"全书统一外观 + 书内锚图"。
    """
    book_cast = getattr(outline, "book_cast", None)
    if not book_cast:
        return "", [], []
    try:
        from book_cast import (roles_on_page, is_adult_role, is_child_human_role,
                               is_animal_role, is_story_dog_role, oneoff_child_color,
                               oneoff_adult_appearance, STORY_DOG_LOCK_CN)
        # 无官方文本（如 Book63）时回退本页正文/scene/scene_cn 文本，否则书内角色锚/外观锁每页都漏注入。
        page_text = ((getattr(page, "text", "") or "") + " "
                     + (getattr(page, "scene", "") or "") + " "
                     + (getattr(page, "scene_cn", "") or ""))
        roles = roles_on_page(book_cast, official_raw, page_text=page_text)
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
        # 成人/职业类一次性角色：即使只出现 1 页（无锚图）也注入成人锁，防被画成穿制服的小孩。
        if is_animal_role(r):
            if is_story_dog_role(r):
                tag += STORY_DOG_LOCK_CN
            else:
                tag += ("（这是一只动物，按其真实物种外观绘制：四足、该物种的体型/毛色/耳型/尾巴，"
                        "绝不拟人化为人类小孩、不穿人类衣服、不直立行走。）")
        elif is_adult_role(r):
            _g = getattr(r, "gender", "")
            _gcn = "男性" if _g == "male" else "女性" if _g == "female" else ""
            _sex = (f"【这是一位成年{_gcn}】（成年{'男士' if _gcn=='男性' else '女士' if _gcn=='女性' else '人'}）"
                    if _gcn else "【这是一位成年人】")
            # 无官方外观文本 → 注入确定性稳定外观（与书内锚图共用同一句），全书每页一致防漂移。
            if not desc:
                tag += oneoff_adult_appearance(r) + "。"
            tag += (f"{_sex}成熟成人脸庞与成人身材比例，明显高于 10 岁儿童、"
                    "约为儿童身高的 4:3、孩子头顶大约到其肩部；绝不能画成小孩/儿童/青少年。"
                    + (f"性别锁：必须是成年{_gcn}，绝不画成另一性别。" if _gcn else ""))
        # 人类儿童命名角色（如 Ben）：页面级也带【全新独立·国际化·反克隆主角】锁，
        #   保证不仅锚图对、成图页也不会把 Ben 画成 Tommy/Mia 的翻版。颜色与锚图共用同一确定性指派。
        elif is_child_human_role(r):
            _c = oneoff_child_color(r.rid)
            tag += (f"【{r.display} 是一个全新独立的国际化儿童角色】与主角 Mia、Tommy 完全不同的另一个孩子，"
                    f"明确 10 岁学龄儿童比例（约 5.5-6 头身，绝不画成五六岁低龄/胖娃娃/Q版大头，也绝不画成 12 岁/青少年/成人），"
                    f"与本书同款治愈系手绘水彩画风（不要跑成别的风格）；外貌国际化/可外籍、多元长相，"
                    f"绝不撞 Tommy 的脸/棕色蓬松短发、绝不撞 Mia 的脸/发型；"
                    f"上衣用【{_c}】，绝不穿蓝色(Tommy 专属)、绝不穿紫色(Mia 专属)。")
        lines.append(tag)
        if r.anchor_path and (current_refs + len(extra_refs)) < 5:
            ap = Path(r.anchor_path)
            if ap.exists():
                extra_refs.append(ap)
        dbg.append({"key": f"oneoff:{r.rid}", "name": r.display, "is_oneoff": True,
                    "species": getattr(r, "species", "human"),
                    "is_story_dog": is_story_dog_role(r)})
    return ("\n".join(lines), extra_refs, dbg)


# ============================================================
#  v3 正向 prompt 构造（火山风单段流畅）
# ============================================================

# 场景里"主角之外的人"检测（用户拍板 2026-06-09）——
#   科普绘本常出现农夫/工人/店员/路人等【非IP配角】。这些有脸配角需要：
#   ① 成人:孩子 4:3 比例锁（哪怕没注册成 cast）；② 国际化/多元族裔、不撞主角、不默认中国人。
_SCENE_ADULT_RE = _re.compile(
    r"农夫|农民|工人|工匠|工厂工人|司机|店员|售货员|收银|服务员|厨师|面包师|医生|护士|"
    r"警察|警官|消防员|邮递员|快递员|邮差|"
    r"叔叔|阿姨|大人|成年|大叔|大妈|爷爷|奶奶|老人|路人|村民|顾客|"
    r"\bfarmer|worker|driver|clerk|cashier|chef|cook|baker|vendor|grocer|"
    r"police|officer|cop|firefighter|fire ?fighter|fireman|"
    r"postman|mailman|mail ?carrier|mail ?man|"
    r"adult|grown-?up|villager|customer|passer", _re.IGNORECASE)
_SCENE_CROWD_RE = _re.compile(
    r"人群|一群人|众人|路人们|同学们|大家|围观|crowd|people|villagers|customers", _re.IGNORECASE)
# 非主角【儿童群体】语境（2026-06-09 新增）——足球/运动/课堂群像里的
#   "其他小孩/队友/同学/球队/一群孩子"等。漏判会导致这类场景不触发"配角多元各异"，
#   配角于是克隆主角脸型/发型、撞主角配色（男孩穿蓝=Tommy / 女孩穿紫=Mia）。
#   注意：与成人/人群分开判定——这些是孩子，绝不能套用"成人:孩子 4:3"比例锁。
_SCENE_KIDS_RE = _re.compile(
    r"其他小孩|其他孩子|别的小孩|别的孩子|另一个(?:男孩|女孩|小孩|孩子)|"
    r"小伙伴|小朋友|伙伴们|同伴|队友|队员|球队|球员|同队|对手|"
    r"同学(?!们)|学生们?|孩子们|一群(?:孩子|小孩|小朋友|男孩|女孩)|几个(?:孩子|小孩|男孩|女孩)|"
    r"\bteamm?mates?|\bteammates?|\bclassmates?|\bschoolmates?|"
    r"other (?:kids?|children|child|boys?|girls?)|\bkids?\b|\bchildren\b|"
    r"\bplayers?\b|\bteam\b|\bpeers?\b|group of (?:kids?|children)", _re.IGNORECASE)


def _scene_has_nonlead_humans(scene_cn: str) -> bool:
    """本页场景里是否出现了主角之外的【成人/人群】（农夫/工人/店员/路人/人群等）。

    仅用于触发"成人:孩子 4:3 比例锁"，不含纯儿童群体（队友/同学）。
    """
    return bool(scene_cn and (_SCENE_ADULT_RE.search(scene_cn) or _SCENE_CROWD_RE.search(scene_cn)))


def _scene_has_nonlead_kids(scene_cn: str) -> bool:
    """本页场景里是否出现了主角之外的【其他小孩】（队友/同学/球队/一群孩子等）。"""
    return bool(scene_cn and _SCENE_KIDS_RE.search(scene_cn))


def _scene_has_nonlead_extras(scene_cn: str) -> bool:
    """本页场景里是否出现【任何非 IP 配角】（成人/人群【或】其他小孩）。

    用于触发"配角多元各异 + 主动指派异色 + 禁穿主角专属色"规则。
    """
    return bool(scene_cn and (_scene_has_nonlead_humans(scene_cn) or _scene_has_nonlead_kids(scene_cn)))


def _scene_lead_is_nonlead_actor(scene_cn: str, kid_names: str) -> bool:
    """本页【主体动作的执行者】是不是非主角（农夫/工人等），而 Mia/Tommy 只是旁观。

    判定：场景里出现了非主角成人，且主体动作句（"…正在/蹲下/弯腰/俯身…"）不是由主角发出。
    保守起见：只要场景明显以"农夫/工人在劳作"开头描述、且主角名没紧跟动作，就算非主角主体。
    """
    if not _scene_has_nonlead_humans(scene_cn):
        return False
    head = scene_cn[:120]
    # 主体动作由非主角发出（农夫蹲下/工人弯腰/司机打开…），且开头没有先点主角名
    actor_lead = bool(_SCENE_ADULT_RE.search(head))
    names = [n for n in (kid_names or "").split("、") if n]
    kid_first = any(n and n in head for n in names)
    return actor_lead and not kid_first


def _is_adult_cast_member(c: dict) -> bool:
    return (c.get("kind") in ("family", "adult")
            or c.get("key") in ("mom", "dad", "grandma", "grandpa",
                                 "granny", "grandfather", "teacher_kim"))


def _audience_cn(ip_age: int) -> str:
    """受众标签（按 IP 年龄映射级别段）。"""
    if ip_age <= 8:
        return "约 6-8 岁学龄前/低年级儿童（L0-2）"
    if ip_age <= 10:
        return "约 8-10 岁学龄儿童（L3-4）"
    return "约 10-12 岁学龄儿童（L5-6）"


_TIME_PATS = [
    (r"清晨|早晨|晨光|破晓|日出|一早", "清晨"),
    (r"上午|午前", "上午"),
    (r"正午|中午|当午", "正午"),
    (r"午后|下午", "午后"),
    (r"黄昏|傍晚|日落|夕阳|暮色", "黄昏"),
    (r"夜晚|夜里|深夜|夜色|星空|月光|晚上", "夜晚"),
]
_WEATHER_PATS = [
    (r"下雨|雨中|雨天|细雨|大雨|雨点|雨滴", "雨天"),
    (r"下雪|雪天|雪花|白雪", "雪天"),
    (r"阴天|乌云|灰云|阴沉", "阴天"),
    (r"晴朗|阳光|蓝天|晴空|金色的?阳光", "晴天"),
]


def _detect_time_cn(scene_cn: str) -> str:
    """从场景文本里轻量识别【时间/天气】（识别不到则留空，整段省略）。"""
    if not scene_cn:
        return ""
    parts: list[str] = []
    for pat, lab in _TIME_PATS:
        if _re.search(pat, scene_cn):
            parts.append(lab)
            break
    for pat, lab in _WEATHER_PATS:
        if _re.search(pat, scene_cn):
            parts.append(lab)
            break
    return "、".join(parts)


def _build_positive_concise(
    *, is_cover: bool, title: str, scene_cn: str, cast: list[dict], ip_age: int,
    env_hint: str, key_props: list[str], composition_cn: str, blank_cn: str,
    angle_cn: str = "", focus_cn: str = "", hook_cn: str = "", oneoff_note: str = "",
    story_lock: str = "", leads_active: bool = True, has_extras: bool | None = None,
    expr_face_cn: str = "", inject_anim_lock: bool = False, nf_body_no_leads: bool = False,
) -> str:
    """【结构化公式·正向】prompt（2026-06-10 用户拍板"按公式重排 + 精简"）。

    按固定 20 段顺序输出带中文标注的段落（缺省段省略、顺序不变），让 image_prompts.txt
    一眼可读；所有"硬锁"（IP 形象锁/10 岁比例+同龄等高/配角确定性配色轮/Ben 反克隆/
    防分身/禁文字/20-25% 留白/中低饱和暖中性）原样保留，只换位置 + 精简措辞。
    """
    kids = [c for c in cast if c.get("name") and c.get("kind") != "pet"
            and not _is_adult_cast_member(c)]
    adults = [c for c in cast if c.get("name") and _is_adult_cast_member(c)]
    kid_names = "、".join(c.get("name", "") for c in kids)
    # has_extras 优先用调用方在【注入负向样板前】快照好的真实值（避免"不要加围观人群"这类
    #   负向指令被人群正则误判成真有配角）；未传入时回退到就地检测（保持其它潜在调用方安全）。
    if has_extras is None:
        has_extras = (not is_cover) and _scene_has_nonlead_extras(scene_cn)

    sec: list[str] = []

    # ★铁律·最高优先（front-load·必存活）：把【IP 身份锁 + 防分身 + 防山寨脸 + 防多余路人 + 配色专属】
    #   压成最短一段置于全文最前。根因（2026-06-10 修）：下游英文画风前缀≈1550 字 + 4000 硬截断，
    #   中文正文只剩 ~2100 字可用，原本排在篇尾的负向段（防分身/防山寨脸/防乱入）被整段切掉 →
    #   出现 Mia/Tommy 分身、山寨脸、凭空多出的路人。把这几条核心锁前置即可绝不被截掉。
    _lock_bits: list[str] = []
    # 发色锁前置（2026-06-11 修 L4 根因·SYMPTOM1）：原 front-load 只锁"马尾+紫色/蓝衣"却漏掉
    #   【发色】，4000 截断时后段棕发锁虽多在存活窗口内，但 highest-priority 行不含发色 → 模型
    #   弱化发色、把 Mia 漂成红/橙/金色卷发。把【棕色发 + 反红橙金/反卷发蓬散】并入这一行，永不被截。
    if any((c.get("key") or "").split("_")[0] == "mia" for c in cast):
        _lock_bits.append(
            f"Mia＝{ip_age}岁女孩·【棕色头发(brown hair)】后脑中高位单束马尾+紫色发圈·穿紫色·"
            "发色绝不红/橙/金/banana黄·绝不卷发蓬乱/大片披散·全书同一人")
    if any((c.get("key") or "").split("_")[0] == "tommy" for c in cast):
        _lock_bits.append(
            f"Tommy＝{ip_age}岁男孩·【棕色(brown)】蓬松短发·穿浅天蓝长袖·"
            "发色绝不红/橙/金·全书同一人")
    _front = (
        "【★铁律·最高优先·必须遵守】"
        + ("；".join(_lock_bits) + "。" if _lock_bits else "")
        + "每个角色全图只出现一次，严禁分身/复制/双胞胎/镜像；"
        "除本页点名的主角外，禁止出现长得像 Mia/Tommy 的小孩（紫色马尾女孩、浅天蓝衣男孩）或任何山寨脸；"
        "不得为凑画面凭空添加未点名的陌生路人/围观人群/多余配角。"
    )
    _front_color = [f"只有 {c['name']} 穿{_signature_color_of(c['key'])}"
                    for c in cast if _signature_color_of(c.get("key", ""))]
    if _front_color:
        _front += "配色专属：" + "；".join(_front_color) + "（其他任何人不得穿这些专属色）。"
    sec.append(_front)

    # 1·类型
    sec.append(f"【1·类型】童书绘本插画（连续性系列绘本{'封面' if is_cover else '内页'}）")
    # 2·受众
    sec.append(f"【2·受众】{_audience_cn(ip_age)}")

    # ★ 0·本页核心画面（front-load【完整本页场景】，置于冗长 IP 外观锁之前抢占注意力）：
    #   复刻 Book54 成功配方——把【完整 scene_cn 场景 + 本页谁在做什么】提到最前、最高优先级，
    #   外貌锁(【3·主体角色】)移到其后；修“满足完人物锁就交差、退化成主角呆站空背景”根因。
    #   注意：完整场景只在此处出一次，下面第 13 段内页不再重复（同义只留一处）。
    if (not is_cover) and scene_cn.strip():
        sec.append(
            "【★0·本页核心画面·最高优先级·严格按此作画】" + scene_cn.rstrip("。") + "。"
            + (story_lock.rstrip("。") + "。" if story_lock else "")
            + "以上是画面【主体】、占主要面积、清晰有故事张力地演出来；绝不退化成主角呆站/摆拍/只露两张脸。"
        )

    # 3·主体角色（汇集所有【角色硬锁】：IP 形象锁 + 配色专属 + 宠物 + Ben 反克隆 +
    #            配角确定性配色轮/多元 + 10 岁比例/同龄等高/防分身）
    role_lines: list[str] = []
    for c in cast:
        d = (c.get("description_cn") or "").rstrip("。")
        if d:
            role_lines.append(f"· {c.get('name', '')}：{d}。")
    color = [f"{c['name']}是画面里唯一穿{_signature_color_of(c['key'])}的人"
             for c in cast if _signature_color_of(c["key"])]
    if color:
        role_lines.append("配色专属：" + "；".join(color) + "（其他任何人不得穿这些专属色）。")
    if any(c.get("key") == "max" for c in cast):
        role_lines.append("本页剧情需要的狗就是 Max（金棕色柯基犬），全图仅此一只狗，不要再画别的狗。")
    if any(c.get("key") == "winnie" for c in cast):
        role_lines.append("本页剧情需要的猫就是 Winnie（灰色虎斑小猫），全图仅此一只猫，不要再画别的猫。")
    # 背景双锁·正向兜底（用户拍板 2026-06-10）：放在【3·主体角色】存活窗口内（防被 L3-6 下游 ~2119
    #   字截断切掉尾部负向）。inject_anim_lock 由调用方按"本书无剧情动物"判定（剧情动物豁免，见
    #   _has_registered_story_animal）；海报脸一句全书通用。措辞精简，不挤占 IP/比例额度。
    if inject_anim_lock:
        role_lines.append("背景不要画与剧情无关的装饰性小动物（猫/狗/鸟/松鼠/老鼠等乱入点缀）。")
    role_lines.append("墙上/海报/画框里不要出现酷似主角(Mia/Tommy)的人脸。")
    # Ben 类一次性命名角色【反克隆锁】（来自 book_cast，并入主体角色段，而非散落篇尾）
    if oneoff_note:
        for _ln in oneoff_note.split("\n"):
            _ln = _ln.strip()
            if _ln:
                role_lines.append(_ln)
    # 非 IP 配角：确定性配色轮 + 多元各异 + SOP 第6条数量/占比量化
    if has_extras:
        role_lines.append(_extra_color_assignment_cn())
        role_lines.append(_extra_diversity_cn())
        # SOP 第6条（配角量化）：配角总数 ≤2 名、画面视觉占比 ≤15%、仅背景氛围点缀不抢主角。
        role_lines.append(
            "【配角上限】生活化配角总数≤2、占比≤15%，仅背景点缀，不抢主角、不遮挡主线；未点名者不凭空新增。"
        )
    # 10 岁比例 + 同龄等高 + 防分身
    if kids:
        has_adult = bool(adults) or ((not is_cover) and _scene_has_nonlead_humans(scene_cn))
        ratio = ("；画面出现成年人时，成人与孩子身高约 4:3、孩子头顶大约到成人肩部，"
                 "成人是成人头身比、孩子是孩子头身比" if has_adult else "")
        if has_extras:
            others = ("允许出现其他小孩/队友/同学，但必须与主角【明显不同】"
                      "（脸型/发型/发色/肤色/衣色各异），绝不撞主角脸/发/衣色，也不得彼此雷同。")
        else:
            others = (f"除 {kid_names} 外不再出现别的小孩，也不出现与主角撞脸/撞发/撞衣色的人；"
                      "本页文字未点名其他人物时，绝不为凑场景凭空添加陌生路人/围观人群/成年配角。")
        equal_height = ""
        if is_cover or has_extras:
            equal_height = (
                "【等高锁】Mia/Tommy 与同龄孩子站同一水平面、头顶齐平、体型一致，主角绝不比同龄人矮半头；"
                "透视缩小只用于明显更远的背景人影。"
            )
        # 精简（用户拍板 2026-06-10）：仅在有同龄队友/同学或封面群像时才补“同龄等高”整段，
        #   纯双主角内页省去这段噪声，把注意力让给本页故事动作。
        same_age_line = (
            f"同框所有 {ip_age} 岁孩子身高体型一致、与主角一样高（绝不更高大或更矮小）。{equal_height}"
        ) if (is_cover or has_extras) else ""
        role_lines.append(
            f"比例：孩子都是 {ip_age} 岁学龄期比例（{_head_body_ratio_lock(ip_age)}）{ratio}。"
            f"{same_age_line}"
            f"每个角色全图只出现一次（绝不分身/复制/双胞胎/镜像）；{others}"
        )
    # 科普内页【主角不出场】时，绝不再把 fallback 写成"系列主角 Mia、Tommy"（会与"内页不含主角"
    #   矛盾、并诱导模型把动作画到 Mia 身上）——改为中性的"本页科普对象/场景"（SYMPTOM3·2026-06-11）。
    _who_fallback = ("本页科普对象/场景主体（内页不含 Mia、Tommy）"
                     if nf_body_no_leads else "系列主角 Mia、Tommy")
    who = kid_names or "、".join(c.get("name", "") for c in cast) or _who_fallback
    sec.append("【3·主体角色】本页出场：" + who + "。\n" + "\n".join(role_lines))

    # 4·背景/环境
    if env_hint:
        sec.append(f"【4·背景/环境】{env_hint.rstrip('。')}。")
    # 5·时间（识别不到则省略）
    _t = _detect_time_cn(scene_cn)
    if _t:
        sec.append(f"【5·时间】{_t}")
    # 6·情绪/表情（SOP 第7/二.5 条：禁抽象情绪词，统一用固定面部细节词表；归并不到六类则省略）
    if expr_face_cn:
        sec.append(f"【6·情绪/表情】主角面部按固定情绪词表表达：{expr_face_cn}"
                   "（用具体面部细节呈现，绝不写抽象情绪形容词）")
    # 7·材质
    sec.append("【7·材质】纸上手绘水彩（柔和水痕、平滑渐变）")
    # 8·视角/机位
    if is_cover:
        sec.append("【8·视角/机位】电影式取景，人物七分身或全身带自然角度"
                   "（三四分之一侧身或轻微俯仰/越肩主角视角），绝不正面呆板平视")
    elif angle_cn:
        sec.append(f"【8·视角/机位】{angle_cn}")
    # 9·构图（景别 + 本页主体动作）
    _comp = composition_cn or ""
    if (not is_cover) and focus_cn:
        _act = f"本页主体动作：{focus_cn.rstrip('。')}——用动态有张力的姿态演出来"
        _comp = (_comp + "；" + _act) if _comp else _act
    if _comp:
        sec.append(f"【9·构图】{_comp}")
    # 10·主体位置
    sec.append("【10·主体位置】主角偏置一侧、约占 55-65%、清晰够大、是视觉焦点；其余 75-80% 由主体与环境填满、不空旷")
    # 11·留白（精简：英文 LAYOUT LOCK 已详述，这里只留中文核心锚点）
    sec.append("【11·留白】留一整条约 20-25%（≥20%）文字区，必须是本页场景向上延伸（户外天空树梢/室内天花板线·书架顶·墙面），"
               "有真实色彩质感，绝不是纯白/平涂纯色块或硬边方框；区内不放可识别人物/道具/文字")
    # 12·层次/景深
    sec.append("【12·层次/景深】前中后景拉开层次、画面通透有纵深；【全画面同清·深景深】前景与远景同样锐利清晰、同等细节可读，"
               "绝不背景虚化/散景bokeh/浅景深（绝非前景清晰后景糊成一片），也绝非扁平平铺")
    # 13·必须出现的细节（封面场景；内页完整场景已在 ★0 置顶，这里不再重复——同义只留一处）
    if is_cover:
        sec.append(f"【13·必须出现的细节·最高优先级】绘本封面《{title}》：{scene_cn.rstrip('。')}。"
                   + (story_lock + "。" if story_lock else "")
                   + "封面要有设计感与故事感、空间纵深，绝不是几人正面并排呆站的扁平合影")
    # 14·文字（NO-TEXT 锁）
    sec.append("【14·文字】无——全图不得出现任何文字/字母/单词/数字/书名/标题/水印/logo（NO-TEXT 锁）")
    # 15·配饰/道具（SOP 第13条：贯穿多页的关键物件，造型/颜色/大小/材质全书逐页一致）
    if key_props:
        sec.append("【15·配饰/道具】画面中应出现：" + "；".join(key_props)
                   + "。凡贯穿多页的关键道具/物件，其造型、颜色、大小、材质全书每页保持完全一致。")
    # 16·参数
    sec.append("【16·参数】生成尺寸 1536×1024，输出裁切为 4:3 横构图（绘本封面/内页）")
    # 17·色彩（精简：英文画风段已详述清透轻水彩；这里只留中文一句锚点）
    sec.append("【17·色彩】清透轻水彩——颜色像水彩自然晕开、柔和过渡、明亮通透不发灰，绝不是生硬色块/平涂色带/调色板拼贴")
    # 18·风格（精简：英文画风段已详述；保留细墨线/纸纹/可爱脸的中文锚点）
    sec.append("【18·风格】清透轻水彩绘本——细墨线（非黑硬线）、纸纹在水彩之下、明亮高调柔光，人物圆润可爱、脸颊干净，可高分辨率印刷")
    # 19·参考画风（参考图＝定妆表·1:1 还原）
    if cast:
        sec.append("【19·参考画风】所附参考图＝白底角色定妆表，按其 1:1 还原五官/发型/服装与配色、只改姿势表情、全书一致；"
                   "动作描述里若有冲突外观一律忽略，以形象锁与参考图为准")
    else:
        sec.append("【19·参考画风】贴合样图的清透轻水彩")

    return "\n".join(sec)


def _has_registered_story_animal(cast: list[dict], oneoff_cast: list[dict] | None) -> bool:
    """本书/本页是否登记了【剧情需要的动物】（家养狗 Max / 剧情狗 Buddy / 猫 Winnie /
    species=dog|animal 的一次性角色 / kind=pet 的 cast）。

    用作"背景无关小动物默认关闭"的豁免开关：返回 True → 不注入该负向（避免误删 Buddy/Max/Winnie）；
    返回 False → 本页无任何剧情动物 → 注入"无关装饰性小动物 off"。复用既有宠物按 cast 豁免机制。
    """
    _oneoff = oneoff_cast or []
    return (
        any((c.get("key") or "") in ("max", "winnie") for c in cast)
        or any(c.get("kind") == "pet" for c in cast)
        or any(c.get("is_story_dog") or c.get("species") in ("dog", "animal") for c in _oneoff)
    )


def _build_negative_concise(*, cast: list[dict], page_text: str, ip_age: int,
                            oneoff_cast: list[dict] | None = None) -> str:
    """【简短】反向 prompt：只保留 ~12 类最关键禁忌（对齐原生网页版的短负向表）。"""
    neg = [
        "任何文字/字母/数字/书名/水印/logo；",
        "主角在空旷/无关背景里呆站、并排摆拍或被晾成远景路人而脱离本页关键道具/动作/场景；"
        "画面跳题/省略本页情节；非虚构页缺少该主题标志道具/场景（退化成空泛无主题室内）；",
        "为凑场景凭空添加、与本页剧情无关的陌生路人/围观人群/多余配角（未点名的人不应出现）；",
        "细碎噪点、高频纹理、脏污颗粒、斑驳色块、密集小装饰、画面脏乱；",
        "生硬色块/平涂色带/调色板色卡/色轮拼贴/突兀撞色块面（颜色应像水彩柔和过渡、不要硬边色块）；",
        "纯白色块/白色方框/人工硬边留白；顶部大面积浅米/奶油/灰白平涂空色带、人物头顶被齐切、书架/墙/天花在头顶突变单色；",
        "过度锐化、HDR 浓艳滤镜、色彩断层、发糊不通透、发灰发闷发暗、低分辨率、边缘发虚；",
        "扁平平涂、缺层次景深、呆板正面证件照式摆拍；",
        "畸形/不对称的脸或手、多指缺指、五官歪斜、头身比例失调；",
        "明显腮红/红脸蛋/圆形红晕/脸颊红粉色块；",
        "与主角撞脸/撞发/撞衣色的小孩、复制 Mia/Tommy 脸或发型的配角、同一角色分身/复制/双胞胎/镜像；",
        "非 IP 配角穿主角专属色、配角千篇一律同一张脸（应多元各异）；",
        "写实照片感/写实皮肤、3D 塑料、油画厚涂、粗黑墨线、强烈硬光影；",
        "Q 版大头娃娃/4 头身幼态、把 10 岁画成青少年或幼儿；",
        f"Mia 丸子头/发髻/half-up/披散/低马尾/侧马尾/双马尾/戴眼镜、Mia 颅顶超高马尾、Mia 用非紫色发圈"
        f"（Mia 必须后脑中高位马尾+紫发圈：{MIA_HAIR_LOCK}）；Tommy 长发/马尾/戴眼镜；主角被画成成人或幼儿；",
        "配角超过 2 名、配角占比过大（>15%）喧宾夺主；",
        "反光塑料/玻璃高光、拥挤街道人潮、高耸现代高楼、夸张手势、漂浮断裂肢体；",
        "Dino 吉祥物入画（永久禁止）；",
    ]
    # Tommy 浅天蓝硬锁（用户拍板 2026-06-10：以 Age10 定妆表为准，三档统一浅天蓝，全年龄加权）：
    #   旧的"深蓝polo=12岁专属"已废弃，Tommy 任何年龄都不穿深蓝/navy/polo/牛仔。
    if any((c.get("key") or "").split("_")[0] == "tommy" for c in cast):
        neg.append(
            "Tommy 穿深蓝/藏青/navy/钴蓝/靛蓝/teal 上衣、Tommy 穿短袖 polo 翻领、Tommy 穿牛仔裤、"
            "Tommy 上衣比卡其裤更深或接近成人警服藏青——均禁（Tommy 任何年龄都必须【浅天蓝】长袖圆领卫衣 #5FA8D6~#8EC0ED）；"
        )
    # 宠物负向锁与剧情宠物对打修复（用户拍板 2026-06-09，2026-06-10 扩展剧情狗）：
    #   本页 cast 含 Max(狗)/Winnie(猫)，【或】书内登记了剧情狗(oneoff:dog / is_story_dog) 时，
    #   不再静态禁"狗/猫"——剧情狗=Buddy（由正向 Buddy 锁约束）、家养狗=Max、剧情猫=Winnie。
    #   只在"无任何已登记狗"时才禁狗，避免误删本页的 Buddy。
    _oneoff = oneoff_cast or []
    _has_story_dog = any(c.get("is_story_dog") or c.get("species") == "dog" for c in _oneoff)
    _has_dog = any(c.get("key") == "max" for c in cast) or _has_story_dog
    _has_cat = any(c.get("key") == "winnie" for c in cast)
    _banned_pets = [p for p, present in (("猫", _has_cat), ("狗", _has_dog)) if not present]
    if _banned_pets:
        neg.append("、".join(_banned_pets) + "等无关宠物；Dino 吉祥物（除非剧情明确需要）。")
    else:
        neg.append("剧情之外的多余宠物；Dino 吉祥物（除非剧情明确需要）。")
    # 背景双锁（用户拍板 2026-06-10）：
    #   ① 装饰性小动物默认关闭——修 Book66 背景乱入猫/鸟/松鼠/狗；复用剧情动物豁免：
    #      本书 cast/oneoff 登记了任何剧情动物（狗 Buddy/Max、猫 Winnie、species=dog/animal 等）时
    #      不注入，避免误删 Buddy 这类剧情需要的动物；只在“无任何已登记剧情动物”时才锁。
    #   ② 海报脸——墙上/背景海报或画框里酷似主角(Mia/Tommy)的人脸（Book72 验证发现），全书通用。
    #   注：L3-6 下游会把中文 body 截到 ~2119 字、本负向段在尾部多被切掉，故这两锁同时在
    #      _build_positive_concise 的【3·主体角色】段（存活窗口内）以正向短句兜底，确保真正生效。
    if not _has_registered_story_animal(cast, _oneoff):
        neg.append("与剧情无关的装饰性小动物乱入背景（猫/狗/鸟/松鼠/老鼠/兔子等点缀）；")
    neg.append("墙上/背景的海报、画框或招贴里出现酷似主角(Mia/Tommy)的人脸；")
    excl = [f"除 {c['name']} 外任何人穿{_signature_color_of(c.get('key',''))}"
            for c in cast if _signature_color_of(c.get("key", ""))]
    if excl:
        neg.append("；".join(excl) + "。")
    return "".join(neg)


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

    # 区分孩子 / 成人(家人/老师) / 宠物：年龄锁只能套在孩子身上，
    # 成人(妈妈/爸爸/爷爷/奶奶/老师)绝不能被当成 ip_age 岁的小孩来画（2026-06-08 修 IP 串龄 bug）。
    def _is_adult_cast(c: dict) -> bool:
        return (c.get("kind") in ("family", "adult")
                or c.get("key") in ("mom", "dad", "grandma", "grandpa",
                                     "granny", "grandfather", "teacher_kim"))
    kids = [c for c in cast if c.get("name") and c.get("kind") != "pet" and not _is_adult_cast(c)]
    adults = [c for c in cast if c.get("name") and _is_adult_cast(c)]
    kid_names = "、".join(c.get("name", "") for c in kids)
    adult_names = "、".join(c.get("name", "") for c in adults)
    n_kids = len(kids)

    # ① 本页画面（核心，最高权重，绝对置顶）
    if is_cover:
        parts.append(
            f"【画面 · 绘本封面 · 最高优先级】{(scene_cn or '').rstrip('。')}。"
            "封面要高级、有设计感、有故事感与空间纵深，绝不是几个人正面并排呆站摆拍的扁平合影；"
            "镜头自然带角度、画面分前中后景，人物生动投入在情境里、神情自然友好；"
            "画面上方保留【约 20-25%（至少 20%）的一整条横带】供后期叠加书名——但这条带【绝不能是纯白/惨白的空色块或硬边方块】，"
            "必须是本页场景在顶部的自然延续、有色彩有质感（晴天蓝天淡云 / 暖金黄昏 / 柔灰阴雨 / 有肌理的墙面天花板等，随场景天气来画，低饱和莫兰迪质感、与下方同一光源自然过渡）；"
            "这条带里只禁止【可识别的人物/动物/关键道具/文字，以及杂乱探入的树枝枝叶/招牌建筑】，但允许柔和的云、光晕、远处树梢顶端、墙面肌理等低饱和氛围元素；"
            "其余画面要由主体与环境充实饱满地填满、不空旷；作画时这条带里绝对不要画任何文字/字母/书名/标题。"
        )
    else:
        parts.append(
            f"【本页画面 · 必须如实呈现，最高优先级】{scene_cn.rstrip('。')}。"
            f"请严格按这段描述的动作、姿势、视线与站位作画——这是本页最重要、绝不能画错的内容。"
        )

    # ①.1 硬性留白（高优先级·紧跟画面）——用户拍板 2026-06-09：
    #   顶部留【≥20%、约 20-25%】文字区，但【绝不能是纯白/惨白的空色块】——
    #   必须是有色彩、有质感、随本页场景与天气自然延续的【原生场景带】（蓝天白云/暖金黄昏/柔灰阴雨天/有肌理的墙面或天花板）。
    #   该带只禁止"可识别的角色/动物/关键道具/文字"与杂乱探入的枝叶；允许云、光晕、远处树梢顶端、墙面肌理等低饱和氛围元素。
    if not is_cover:
        # 精简 2026-06-09：英文 NEGATIVE-SPACE LOCK 已在首尾完整描述留白规则，这里只留一句中文锚定，
        #   把额度让给"比例/防分身/国际化"等关键铁律（避免它们被 4000 字截断切掉）。
        parts.append(
            "【顶部文字区】画面最上方留一整条横带（约 20-25%、至少 20%）供后期叠字——"
            "这条带绝不能是纯白空色块，必须是本页场景在顶部的自然延续（随天气画蓝天淡云/暖金黄昏/柔灰阴雨/有肌理的室内墙面或天花板），"
            "带里不出现可识别的人物/动物/关键道具/文字；其余 75-80% 由主体人物与环境充实饱满地填满，中景/中近景，主角清晰够大、不要缩太小四周空一片。"
        )

    # ①.2 焦点/高潮（把本页最有张力的那一下做成画面主体，动态、有层次）
    if not is_cover and focus_cn:
        parts.append(
            f"【画面焦点 · 主体动作】本页的视觉主体与高潮是：{focus_cn.rstrip('。')}。"
            "把这个动作作为画面主体来构图——主角是视觉焦点、明显偏置画面一侧（不要居中、不要铺满整框，"
            "另一侧/顶部留出上述干净留白），"
            "用动态有张力的姿态（伸手/俯身/奔跑/惊喜等）把这一刻演出来，表情到位、情绪鲜活；"
            "并拉开前景—中景—背景的清晰层次、用构图与动势把焦点落在这个主体动作上（主体突出，但前景与远景同样锐利清晰·深景深，绝不背景虚化/散景），"
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
        # 配色专属锁上移（精简 2026-06-09）：紧跟 IP 锁，确保不被 4000 截断切掉——
        #   "只有 Mia 穿紫 / 只有 Tommy 穿蓝"能直接阻止配角/路人撞主角配色（防伪克隆）。
        _color_locks_early = [
            f"{c['name']}是画面里唯一穿{_signature_color_of(c['key'])}的人"
            for c in cast if _signature_color_of(c["key"])
        ]
        if _color_locks_early:
            parts.append("配色专属锁：" + "；".join(_color_locks_early)
                         + "；其他任何人（配角/路人）都不得穿这些专属色。")
        # 非 IP 配角【主动指派异色】——紧跟 IP 锁、靠前防截断（修足球/运动群像里
        #   "男孩穿蓝=Tommy / 女孩穿紫=Mia"的性别制服化克隆）。
        if (not is_cover) and _scene_has_nonlead_extras(scene_cn):
            parts.append(_extra_color_assignment_cn())

    # ③ 人数 + 年龄锁 + 比例 + 同尺度（合并成一句精炼硬约束）
    if cast:
        age_desc = ('12 岁是青春期前的少年/少女，身形修长、个子较高，绝不是矮小幼态的低龄小童'
                    if ip_age >= 12 else
                    ('10 岁是学龄期儿童' if ip_age >= 10 else '8 岁是低龄学童'))
        if kids:
            line = (
                f"人物与年龄（硬约束·绝不能错）：画面里的【儿童】只能是 {kid_names}，"
                f"且每个孩子都必须是【{ip_age} 岁】同龄、身高相近的样子——身高、脸型、身材比例都要符合 {ip_age} 岁"
                f"（{age_desc}）；{kid_names} 是同龄的兄妹/同学，彼此身高体型相近，"
                "绝不能一个画成幼儿(3-5岁)、另一个画成大孩子或青少年；"
            )
        else:
            line = "人物（硬约束·绝不能错）："
        # 成人/老人单独锁（关键修复：家人不是 ip_age 岁的小孩！）
        # 分两类：①成人/人群 → 触发 4:3 比例；②任何配角（含其他小孩）→ 触发多元/异色。
        scene_has_adult_extras = (not is_cover) and _scene_has_nonlead_humans(scene_cn)
        scene_has_extras = (not is_cover) and _scene_has_nonlead_extras(scene_cn)
        if adults:
            line += (
                f"画面里的【成年人/老人】是 {adult_names}，他们必须是成熟的大人或白发老人——"
                "妈妈/爸爸是 30 多岁的成年家长（成熟脸庞与成人体型，绝不是小孩、绝不是青少年/teenager、绝不是大学生模样），"
                "爷爷/奶奶是明显年长的老人（白/银发、慈祥皱纹）；"
                f"成年人与 {ip_age} 岁孩子的身高比例约为【4:3】——即孩子身高约为成人的四分之三、【孩子头顶大约到成人的肩部/上胸位置】，"
                "成人是成熟的成人头身比、孩子是孩子头身比，绝不能把大人和孩子画成同龄同高、也不要夸张到孩子只到大人腰部；"
            )
        elif kids and scene_has_adult_extras:
            # 场景里出现农夫/工人/店员/路人等【非注册成人】——同样必须锁成人:孩子 4:3 比例，
            #   修 P2-P5 这类"孩子站在弯腰大人旁却被放大成12岁"的漂移。
            line += (
                f"画面里若出现成年人（农夫/工人/店员/司机/路人等），他们都是【成熟的成年人】，"
                f"与 {ip_age} 岁孩子的身高比例约为【4:3】——孩子身高约为成人的四分之三、【孩子头顶大约到成人的肩部/上胸位置】，"
                "成人是成熟成人头身比、孩子是孩子头身比，绝不能把成年配角画得和孩子同龄同高、也绝不能把 10 岁孩子拔高成12岁青少年；"
            )
        # 非IP配角【国际化·多元族裔】铁律（用户拍板 2026-06-09）——
        #   除主角与已锁定家人外，其余人物必须是多元族裔的不同长相，不默认中国/亚洲面孔、不撞主角。
        if scene_has_extras:
            line += (
                f"【非IP配角·国际化多元且各异】画面里除 {names} 外的所有其他人物（其他小孩/队友/同学/球队成员/农夫/工人/店员/路人/其他大人），"
                "必须是【国际化、多元族裔】、彼此【各不相同】的不同长相——不同的肤色、发色、发型、脸型、五官、体型与服装，自然多样；"
                "明显区别于主角，绝不复制 Mia/Tommy 的脸或发型，多个配角也绝不长成同一个模子；"
                "绝不要默认画成中国人/亚洲面孔，也绝不能与主角撞脸、撞发型、撞衣色；不抢主体；"
            )
        # 软化（2026-06-09）：剧情需要"一群队友/同学"时不再一律禁止其他小孩，
        #   改为"允许出现但必须与主角明显不同"；只保留对【撞主角/分身】的硬禁。
        if scene_has_extras:
            line += (
                "本页剧情需要其他小孩/队友/同学时，他们可以清晰出现，但每个都必须与主角【明显不同】"
                "（不同脸型/发型/发色/肤色/衣色），且彼此各异、各自多元；"
            )
        else:
            line += (
                "不要出现有清晰五官/发型、与主角雷同的陌生同学或小孩；"
                "如剧情确需人群，只允许【远景、虚化、看不清脸】的多元族裔人影剪影做国际化氛围，"
                "且必须高度多样（不同年龄/身高/体型/发型/衣色，以成年人与不同长相为主）；不要凭空新增别的小孩；"
            )
        line += (
            f"绝不能出现与主角 {kid_names or names} 雷同的小孩——尤其严禁出现紫色上衣高马尾女孩、蓝色上衣蓬松短发男孩等酷似主角的身影（那会变成分身）；"
            "背景人物一律不得抢主体、不得与主角同款形象；"
            f"主角是画面视觉焦点、偏置画面一侧、占画面高度约 55-65%（画得清晰饱满、不要缩太小），仅在另一侧/顶部留出约 20-25% 排文字空间；"
            f"{_head_body_ratio_lock(ip_age)}；每只手 5 根手指、关节自然、双眼对称、五官端正不歪斜；"
            "头部与脖颈结构自然正确、头型圆润对称、头发与头部自然衔接（马尾/发辫根部连接处准确），"
            "侧脸或侧头视角下轮廓与五官也要准确、不变形不重叠。"
        )
        # 家具/物件按主角年龄真实比例（用户拍板 2026-06-08）：孩子与桌椅床门等大小要符合 ip_age
        line += _furniture_scale_lock(ip_age)
        if n_kids >= 2:
            line += "多个同龄主角必须同尺度、同景深、站在同一水平面，谁都不能比旁边的人明显大一圈。"
        if is_cover or scene_has_extras or n_kids >= 2:
            line += (
                "【封面/群像等高锁】Mia/Tommy 与所有同龄队友/同学/背景清晰儿童必须站在同一水平面、"
                "到镜头同一距离、头顶大致齐平、体型尺度一致；主角绝不比身后/身旁的同龄孩子矮半头，"
                "背景里的同龄队友/同学也绝不能比主角更高更大一圈；透视缩小只用于【明显更远】的背景人影，"
                "不得用于与主角同层、同框的同龄人。"
            )
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

    # ⑥ 配色锁定已上移到 IP 锁紧后（防被截断）；此处不再重复。

    # ⑥.5 儿童向柔化（动物/反派一律 friendly 可爱，去獠牙/凶相/恐怖）
    _soft = _child_safe_softening(scene_cn)
    if _soft:
        parts.append(_soft)

    # ⑥.8 构图 + 比例硬规则 + 留白 + 禁文字（优先级重排 2026-06-08：构图/镜头/留白属第 4 优先级，
    #   置于"画质/画风"块之前——scene+IP(最高) → 构图留白 → 画质画风(配合 seedream 首尾英文画风指令)）。
    # ⑥.8 构图 + 留白 + 禁文字（精简：主角占比/同尺度/4:3 已在 ③ 年龄块写过，这里不再重复 composition_prompt_cn）
    parts.append(
        f"构图：{composition_cn.rstrip('。')}。{blank_cn}。{FORBID_CN}。"
    )

    # ⑦ 画风（精简 2026-06-09 · 用户拍板"提示词必须瘦身"）：
    #   出图端 seedream_client 已在【首+尾】各注入一整段英文画风指令(GPT_CLEAN_STYLE_DIRECTIVE/ECHO)，
    #   覆盖了"治愈水彩/平滑色块/极简纹理/干净脸颊/无噪点色斑/可印刷"等全部画风约束；
    #   故中文正向此处只保留【一句】核心锚定，不再重复 STYLE_CN 长段 + 印刷优化长段(原约1500字冗余)，
    #   把宝贵的 4000 字额度让给"场景/IP/比例/防分身"等关键铁律，避免后段被截断。
    parts.append(
        "【画风】干净通透的治愈水彩：平滑柔和的色块与渐变塑形、细节克制、纹理极简、纤细描边为辅；"
        "配色统一目标：中低饱和、通透不发灰、暖中性白平衡，既不过饱和刺眼、也不发灰发闷；明亮柔光、阴影浅淡干净，边缘清晰可高分辨率印刷；"
        "保留适度景深与轻盈体积(反扁平)，但绝非油画厚涂/3D塑料/强烈硬光影；无色斑噪点碎纹理、脸颊干净。"
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

    # 1.5) 构图/比例禁忌（精简 2026-06-09）：只留"主角过小/留白被遮挡/顶部文字区不达标"等关键几条，
    #   细碎噪点/纹理类已由出图端英文画风指令(ECHO: "absolutely no noise/grain/texture/blotchy...")覆盖，
    #   composition_negative_cn / smoothness_negative_cn 长段不再重复注入，给关键 IP/比例禁忌腾出额度。
    parts.append(
        "主角被画得过小（主角应占画面 50–60%）；配角或动物比主角还大；同框同龄人身高差异过大；"
        "预留的文字区被可识别的人物/动物/关键道具或杂乱枝叶遮挡；顶部文字区是纯白/惨白空色块、不连续或不足20%；"
        "留白过多、主体缩太小四周空一大片；贴脸大特写或紧裁构图"
    )

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
            parts.append(
                "孩子被画成低龄幼儿/婴幼儿；年龄明显小于10岁；幼态大头矮小比例；"
                "大头娃娃/Q版chibi比例、4头身、头部相对身体过大；身体/腿过短显得矮小，"
                "应是约5.5-6头身、腿身修长、接近少年的10岁学龄期比例"
            )

    # 1.85) 主角服装统一锁（用户拍板 2026-06-10：以 Age10 定妆表为准，三档同一形象、衣色发型一致）——
    #   Tommy 任何年龄都是浅天蓝长袖圆领卫衣+卡其裤；Mia 任何年龄都是紫色长袖卫衣+浅灰白裤+紫色发圈马尾。
    _base_keys = {(c.get("key") or "").split("_")[0] for c in cast}
    if "tommy" in _base_keys:
        parts.append(
            "Tommy穿深蓝/藏青/navy/钴蓝/teal上衣、短袖polo翻领、牛仔裤、或条纹短袖T（均废弃，"
            "Tommy 任何年龄都必须【浅天蓝】长袖圆领卫衣 #5FA8D6~#8EC0ED +【卡其】直筒裤）；"
            "Tommy上衣比卡其裤更深或接近成人警服藏青"
        )
    if "mia" in _base_keys:
        parts.append(
            "Mia穿白色阔腿裤/翻领针织衫/牛仔裤/短袖T（均废弃，Mia 任何年龄都必须【紫色长袖圆领卫衣+浅灰白直筒裤】）；"
            f"Mia丸子头/发髻/top-knot/half-up半扎/只扎上层下半披散/低马尾/侧马尾/双马尾/脏辫乱团/头发糊成一团；"
            f"Mia颅顶或头顶正中超高马尾/发髻在头顶正上方/仅短马尾穗；用非紫色发圈；"
            f"Mia头发完全散开不扎或大量披散散发（必须是后脑中高位马尾+紫色发圈+中长辫垂至肩/上背：{MIA_HAIR_LOCK}）"
        )
    if "mom" in _base_keys:
        parts.append(
            "妈妈被画成扎马尾/丸子头/盘发/把头发扎起来（妈妈必须是披散的长波浪卷发）；"
            "妈妈被画成放大版的小女孩 Mia、和 Mia 撞脸撞发型；妈妈被画成小孩或青少年/teenager；"
            "妈妈五官身材过于幼态、不像成熟成年女性"
        )
    parts.append(
        "凭空新增与主角雷同的陌生小孩（剧情需要的其他小孩/队友/同学可出现，但须与主角明显不同、彼此各异，不要一律删光）；"
        "背景出现与主角雷同的小孩（紫色上衣高马尾女孩、蓝色上衣蓬松短发男孩等酷似 Mia/Tommy 的身影）；"
        "非 IP 配角穿紫色系或蓝色系（紫=Mia专属/蓝=Tommy专属，配角禁用）；"
        "把农夫/工人/店员/其他小孩等配角画成与主角同款长相/同脸；多个长得几乎一样的配角；"
        "非IP配角全画成同一种中国/亚洲面孔或彼此长成同一个模子（应国际化、多元族裔、各不相同）；"
        "背景人群清晰可辨的脸/与主角同款发型衣色；"
        "同一角色出现多个分身/复制/双胞胎/镜像；两个 Mia、两个 Tommy、同一主角同时出现在前景和背景；"
        "duplicate character, cloned person, twins, two identical girls, two identical boys, same character appearing twice, mirrored duplicate；"
        "明显的腮红/红脸蛋/红扑扑的脸颊/圆形红晕/脸颊上的红粉色块或腮红色斑（脸颊应干净、至多极淡一点点红润）；"
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
