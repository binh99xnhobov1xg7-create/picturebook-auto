"""项目配置：路径、IP 年龄档、即梦 4.6 API、PPT 几何与字体。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Streamlit Cloud 兼容：把 st.secrets 的值同步进 os.environ
# 这样 Cloud 上不用改 .env 就能读 ARK_API_KEY / DOUBAO_MODEL 等。
# 钉钉群机器人（可选）：DINGTALK_WEBHOOK_URL、DINGTALK_SECRET（加签）、
# STREAMLIT_APP_URL、DINGTALK_FEEDBACK_FORM_URL — 见 docs/DingTalk_接入说明.md
def _hydrate_from_streamlit_secrets() -> None:
    try:
        import streamlit as st
        if not hasattr(st, "secrets"):
            return
        for key, val in dict(st.secrets).items():
            if isinstance(val, (str, int, float, bool)) and not os.getenv(key):
                os.environ[key] = str(val)
    except Exception:
        pass


_hydrate_from_streamlit_secrets()

# ---------- 路径 ----------
INPUTS_DIR = ROOT / "inputs"
# 输出目录：可用环境变量 PB_OUTPUTS_DIR 覆盖（本机指向 D 盘，避免塞满 C 盘）。
# 未设置时回落到项目内 outputs（部署服务器/云端无此变量，默认行为不变）。
OUTPUTS_DIR = Path(os.getenv("PB_OUTPUTS_DIR") or (ROOT / "outputs"))
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = ROOT / "assets"
CHARACTERS_DIR = ASSETS_DIR / "characters"
STYLE_DIR = ASSETS_DIR / "style"
BRAND_DIR = ASSETS_DIR / "brand"
FONTS_DIR = ASSETS_DIR / "fonts"
POPPINS_DIR = FONTS_DIR / "Poppins"
TEMPLATES_DIR = ROOT / "templates"
WORKSHEET_TEMPLATE = TEMPLATES_DIR / "worksheet_a4.pptx"

# ============================================================
#  imarouter 统一 API（2026-06-02 迁移）
#  - 文本：Claude / GPT（OpenAI 兼容 /chat/completions）
#  - 生图：gpt-image-2（异步任务制，详见 seedream_client.py）
#  旧的火山（DeepSeek + Seedream）变量名保留，全部重指向 imarouter，
#  避免改动各 import 处。
# ============================================================
IMAROUTER_API_KEY = (
    os.getenv("IMAROUTER_API_KEY", "").strip()
    or os.getenv("ARK_API_KEY", "").strip()
)
IMAROUTER_BASE = os.getenv("IMAROUTER_BASE", "https://api.imarouter.com/v1").rstrip("/")
TEXT_MODEL = os.getenv("TEXT_MODEL", "claude-opus-4-7")
# 抽取/出题等结构化任务专用模型：默认用更快的 Sonnet（比 Opus 快数倍，质量足够），
# 把 Opus 留给画面描述润色 / 科学校验等更吃质量的环节。可用 EXTRACT_MODEL 覆盖。
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "claude-sonnet-4-6")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")

# 2026-06-08 供应商反馈 gpt-image-2 任务偶发超时/闪断 → 单次请求超时与重试次数双双放大。
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "4"))

# ---------- 生图（gpt-image-2 via imarouter，异步任务）----------
JIMENG_API_KEY = IMAROUTER_API_KEY                # 兼容旧名
JIMENG_BASE_URL = IMAROUTER_BASE
JIMENG_MODEL = IMAGE_MODEL

# ---------- 火山方舟 Ark 直连：即梦/Seedream（仅 L0-2 出图，2026-06-08 双模型）----------
# L0-2 走「即梦4.6(Ark)出草稿 → GPT(gpt-image-2) 图生图修图」双段；L3-6 维持纯 gpt-image-2。
# 注意：ARK_API_KEY 同时是 IMAROUTER 的兜底 key（见上），此处复用同一把 Ark key 直连火山。
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
ARK_API_KEY = os.getenv("ARK_API_KEY", "").strip()
# 即梦4.6 的 model id（火山方舟 endpoint/model 名，由 .env 配置；默认填 4.5 占位，待补 4.6 id）
JIMENG_SEEDREAM_MODEL = os.getenv("JIMENG_SEEDREAM_MODEL", "doubao-seedream-4-5-251128")
# 即梦 4:3 直出尺寸（火山支持 4:3 直出，无需后裁）
JIMENG_SEEDREAM_SIZE = os.getenv("JIMENG_SEEDREAM_SIZE", "2304x1728")

# ---------- L0-2 出图语义（用户拍板 2026-06-08）----------
# 即梦【全程出图】= 最终画风由即梦决定；GPT 只做【视觉自审】（IP是否统一/有无多指/图文是否匹配/有无分身），
# 仅当审出问题时才【定向修图】（图生图保留即梦构图与画风，只补/改有问题处），无问题则原样交付即梦图。
IMAGE_SELF_REVIEW = os.getenv("IMAGE_SELF_REVIEW", "true").lower() in ("1", "true", "yes")
# 视觉自审用的多模态模型（imarouter，需支持图片输入）。
# 注意：本账号 imarouter「vipkid」分组下 gpt-4o/gpt-5/gemini 等无渠道，可用的是 Claude 系（已支持图片输入）。
VISION_REVIEW_MODEL = os.getenv("VISION_REVIEW_MODEL", "claude-sonnet-4-6")

# L3-6（纯 gpt-image-2）专用·简明英文画风指令（用户拍板 2026-06-08：治"色斑/碎纹理"）。
# gpt-image-2 对【前置 + 英文】指令遵循度更高；又因最终 prompt 会被截断到 4000 字符，
# 故把这组画风词【首尾双置】：作为最高优先级前缀拼在最前(GPT_CLEAN_STYLE_DIRECTIVE)，
# 再在文末放一段简短回声(GPT_CLEAN_STYLE_ECHO)，防止中段大量场景/角色描述把画风词稀释掉。
# 用户原始画风词（这组关键词务必原样保留，是本指令的 SSOT）：
#   正向: clean illustration, smooth shading, soft lighting, controlled details,
#         minimal texture, high clarity, refined edges, smooth gradients
#   负向: noise, grain, artifacts, high frequency detail, dirty texture, oversharpen,
#         blotchy, chaotic details
GPT_STYLE_POSITIVE = (
    "clean illustration, smooth shading, soft lighting, controlled details, "
    "minimal texture, high clarity, refined edges, smooth gradients"
)
GPT_STYLE_NEGATIVE = (
    "noise, grain, artifacts, high-frequency detail, dirty texture, oversharpen, "
    "blotchy color patches, chaotic details, "
    # 即梦逐图反推补充负向（2026-06-08 同事反馈：人物偏写实/大龄、线偏硬、背景偏满）：
    "hard black ink outlines, thick black linework, semi-realistic or photorealistic faces, "
    "older teenage or adult-like face proportions, heavy detailed rendering, busy cluttered background"
)
# 画风目标锚（2026-06-08 逐图反推即梦4.6 样书校准）：柔和手绘水彩治愈绘本——
#   细软的棕/赭描边（非黑硬线）+ 柔水彩渐变 + 暖粉彩配色 + 明亮高调暖光 + 极少纸纹 + 淡而通透的低细节背景大留白。
GPT_STYLE_TARGET = (
    "Target look (match the reference style closely): a soft hand-painted watercolor children's "
    "storybook illustration, warm, cozy and gentle. Thin SOFT brown/sepia hand-drawn outlines "
    "(never hard black ink lines), smooth soft watercolor gradients with soft visible watercolor "
    "washes; a harmonious medium-low saturation color scheme where colors blend and transition softly "
    "like wet watercolor washes on paper (NOT separate hard color blocks, NOT a color palette/swatch chart) "
    "— clean and luminous, never greyish/muddy and never oversaturated, with a warm-neutral white balance; "
    "bright high-key warm lighting, "
    "minimal paper texture; keep backgrounds airy and low-detail with generous bright negative space"
)
# 即梦人物渲染（核心差距点：人物要低龄可爱、不能写实大龄）：
GPT_STYLE_CHARACTER = (
    "Character rendering: soft, cute, friendly storybook children with softly rounded faces, "
    "warm expressive dark eyes with small white catchlights, a tiny soft button nose, "
    "a gentle warm smile, and clean smooth cheeks with at most a VERY faint soft cheek tint "
    "(NO strong rosy/red/pink blush, NO round blush circles or blush patches on the cheeks); "
    "fluffy hair painted with soft brushy strokes; thin soft brown/sepia outlines on the characters "
    "(never hard black ink); keep faces gentle and storybook-stylized, never semi-realistic or photorealistic"
)
# 画风前缀（精简 2026-06-09 · 用户拍板"提示词必须瘦身"）：
#   原 DIRECTIVE/ECHO 合计约 3900 字，在 4000 上限下几乎把中文正文(场景/IP/比例/防分身)全部挤掉，
#   是"出图不可控/IP漂移/克隆/比例错"的真正根因。这里把英文画风首尾两段大幅压缩到约 700+850，
#   只保留画风核心 + 禁文字锁 + 留白锁，把宝贵额度让给中文关键铁律。
#
# 2026-06-10 用户给定永久"绘本提示词 SOP"，新增可切换画风（见 SOP_STYLE_MODE）：
#   现行【柔和水彩】画风 = 默认（_WATERCOLOR_STYLE_DIRECTIVE/ECHO）；
#   SOP【墨水轮廓+纹理纸+莫兰迪】新画风 = SOP_STYLE_MODE=true 时启用（_SOP_STYLE_DIRECTIVE/ECHO）。
# 两套都保留同一份【禁文字锁 NO-TEXT LOCK + 留白锁 NEGATIVE-SPACE LOCK】，不破坏 PPT 排文流程；
# 安全 IP 锁（Tommy 浅天蓝圆领卫衣 / Mia 后脑中高马尾+紫发圈 / 按级别年龄）由 cn_prompt_builder
# 的 cast 锁注入，两套画风通用、互不影响。

# 两套画风共用的【禁文字锁 + 留白锁】（PPT 排文流程依赖，绝不可丢）：
# 2026-06-10 精简（防 4000 截断）：保留核心语义，删冗长举例，从 ~1420 压到 ~430。
_NO_TEXT_AND_LAYOUT_LOCK = (
    "NO-TEXT LOCK: absolutely no text/letters/words/numbers/caption/signage/handwriting/watermark/logo anywhere; "
    "keep the reserved area as clean background.\n\n"
    "LAYOUT LOCK: reserve ONE continuous ~20-25% band (top or one side) for later text — NOT a flat white/blank box, "
    "but the page's real scene continuing into it with soft matching color and depth (clear sky / warm sunset / soft "
    "gray rain / indoor wall or ceiling), no people/animals/key props/text inside it; indoors keep ceiling/shelf tops/"
    "wall extending up, never a flat paint strip or a crop above the heads. Fill the other ~75-80% richly with the "
    "subject; main characters clear and large, medium or medium-close shot, never tiny in empty space."
)

# ---------- 现行【柔和水彩】画风（默认） ----------
_WATERCOLOR_STYLE_DIRECTIVE = (
    "Art-style directive (HIGHEST priority, overrides any conflicting style wording later): "
    "soft clean hand-painted healing watercolor children's storybook illustration — warm, cozy, gentle; "
    "thin SOFT brown/sepia outlines (never hard black ink), smooth soft watercolor gradients, "
    "a harmonious medium-low saturation color scheme where colors blend and transition softly like wet "
    "watercolor washes on paper (NOT a color palette/swatch chart, NOT separate hard color blocks) "
    "— clean and luminous, never greyish/muddy and never oversaturated, "
    "with a warm-neutral white balance; bright high-key lighting, minimal paper texture, "
    "airy low-detail backgrounds with generous bright negative space; "
    "characters: soft cute friendly children with softly rounded faces, warm dark eyes with small catchlights, "
    "a tiny button nose, gentle warm smile, clean smooth cheeks with at most a VERY faint natural cheek tint (no strong rosy/red/pink blush circles or patches), fluffy soft hair; "
    "keep faces storybook-stylized, never semi-realistic or photorealistic. "
    "Absolutely avoid: noise, grain, artifacts, dirty/high-frequency texture, oversharpen, blotchy color patches, "
    "hard-edged color-block patches, flat color bands, a color-palette/swatch/color-wheel look, "
    "hard black ink, thick linework, semi-realistic/photorealistic faces, older/adult-like child proportions, "
    "heavy detailed rendering, busy cluttered background.\n\n"
)
# 文末画风回声（精简）：放在末尾再压一遍画风 + 禁文字锁 + 留白锁。
_WATERCOLOR_STYLE_ECHO = (
    "\n\nFinal style lock (highest priority): soft clean healing watercolor with colors that blend and transition "
    "softly and harmoniously like watercolor washes on paper (never hard color blocks, never a color palette/swatch), "
    "smooth shading, minimal texture, "
    "thin soft brown outlines, cute storybook faces with clean cheeks (at most a very faint natural tint, no strong rosy blush circles); "
    "no noise, grain, dirty texture, blotchy patches, hard-edged color blocks, flat color bands, color-palette/swatch look, "
    "hard black ink, semi-realistic faces, adult-like child proportions.\n\n"
    + _NO_TEXT_AND_LAYOUT_LOCK
)

# ---------- SOP【细墨线 + 纸纹 + 清透轻水彩】正式画风（SOP_STYLE_MODE=true 启用） ----------
# 对齐官方水彩参考素材（VIPKID 场景图）：明亮、通透、纯净的轻水彩——纸白透气、wet-on-wet 轻水痕、
# 细墨线、低-中饱和干净不灰。2026-06-10 用户拍板【彻底去掉莫兰迪/muted/dusty/grey】，绝不发灰发闷发厚。
# 保留：细墨线轮廓 + 纸纹在水彩之下 + 可爱低龄脸 + 安全 IP 锚 + 禁文字/留白锁。提示词刻意精简（防 4000 截断）。
_SOP_STYLE_DIRECTIVE = (
    "Art-style (HIGHEST priority, override conflicting style later): bright, airy, clean children's storybook in "
    "CLEAR TRANSPARENT LIGHT WATERCOLOR — soft, elegant, gentle; fresh pure luminous colors, thin translucent washes, "
    "soft wet-on-wet blooms, white paper glowing through; simple uncluttered backgrounds kept in SHARP focus "
    "(deep depth of field — foreground AND background equally clear and readable, never blurred, no bokeh, no shallow "
    "depth of field), soft lighting, high clarity, minimal texture; delicate fine ink outlines (never heavy black ink), subtle paper grain; clean "
    "light-to-medium saturation, NOT dusty/grey/muted/muddy/dark/heavy, never neon. Characters: cute young kids, "
    "rounded faces, warm dark eyes, small nose, gentle smile, clean cheeks (no rosy circles), fluffy hair; storybook, "
    "never realistic. IP: Tommy, brown-haired, in a pale sky-blue crew-neck sweatshirt; Mia, brown-haired, with a mid-high ponytail tied with a "
    "purple hair tie, in purple; both age 10.\n\n"
)
_SOP_STYLE_ECHO = (
    "\n\nFinal style lock: bright airy CLEAR TRANSPARENT LIGHT WATERCOLOR — pure luminous colors, thin translucent "
    "washes, white paper glowing through, delicate fine ink outlines (never heavy black ink), clean light-to-medium "
    "saturation (never dusty/grey/muted/dark/neon); cute storybook faces; no noise, dirty texture, blotchy patches, "
    "hard color blocks, realistic/adult-like faces.\n\n"
    + _NO_TEXT_AND_LAYOUT_LOCK
)

# 画风开关（用户拍板 2026-06-10）：SOP_STYLE_MODE=true → SOP 新画风（B：经典墨线+纹理纸+莫兰迪）；
#   false → 旧版柔和水彩。2026-06-10 用户拍板【以 SOP 新画风 B 为正式默认】→ 默认改 true。
#   如需临时回退旧水彩画风，设 SOP_STYLE_MODE=false 即可。
SOP_STYLE_MODE = os.getenv("SOP_STYLE_MODE", "true").strip().lower() in ("1", "true", "yes")

if SOP_STYLE_MODE:
    GPT_CLEAN_STYLE_DIRECTIVE = _SOP_STYLE_DIRECTIVE
    GPT_CLEAN_STYLE_ECHO = _SOP_STYLE_ECHO
else:
    GPT_CLEAN_STYLE_DIRECTIVE = _WATERCOLOR_STYLE_DIRECTIVE
    GPT_CLEAN_STYLE_ECHO = _WATERCOLOR_STYLE_ECHO

# 提示词模式（用户拍板 2026-06-09，经实测验证）：
#   True  = 【简短·正向】提示词（对齐原生 GPT 网页版："短而干净"）——实测我们后端 + 简短正向提示词
#           即可出干净、可印刷的图；冗长密集的"几百条负向墙"反而会注入噪点、稀释主体、把画面搞糊。
#   False = 旧版【冗长·全锁】提示词（4000 字密集，易被截断且噪点多）。
CONCISE_PROMPT = os.getenv("CONCISE_PROMPT", "true").strip().lower() in ("1", "true", "yes")

# 提示词超长保护（用户拍板 2026-06-09）：API 端把最终 prompt 硬截到 4000 字符（含首尾英文画风段
#   GPT_CLEAN_STYLE_DIRECTIVE/ECHO 约 1550 字），中文正文若超长，尾部"画风/留白/防分身"会被悄悄切掉。
#   这里给一个软上限 + 去重精简 + 告警，供 cn_prompt_builder 与 seedream_client 共用同一策略。
PROMPT_SOFT_LIMIT = int(os.getenv("PROMPT_SOFT_LIMIT", "3800"))


def dedupe_prompt_sentences(text: str) -> str:
    """去掉完全重复的【长句】（按中英句末标点/换行切），保留首次出现，降冗余套话。

    只去较长(>8 字)的精确重复句，短连接词/标点不动，安全无损（重复句对模型无额外信息）。
    """
    if not text:
        return text
    import re as _re
    pieces = _re.split(r"(?<=[。！？!?\n])", text)
    seen: set[str] = set()
    out: list[str] = []
    for p in pieces:
        key = p.strip()
        if not key:
            out.append(p)
            continue
        if len(key) > 8 and key in seen:
            continue
        seen.add(key)
        out.append(p)
    return "".join(out)


def enforce_prompt_budget(text: str, label: str = "", soft_limit: int | None = None) -> str:
    """去重精简提示词；超软上限时打告警（提示下游可能被 4000 截断）。返回精简后的文本。"""
    limit = PROMPT_SOFT_LIMIT if soft_limit is None else soft_limit
    s = dedupe_prompt_sentences(text)
    if len(s) > limit:
        print(f"[prompt-budget] 警告：{label or '某页'} 提示词 {len(s)} 字符 > {limit}"
              f"（去重后仍偏长，下游 4000 截断可能切掉尾部画风/留白/防分身锁）", flush=True)
    return s

# 按 level 选出图后端（用户拍板 2026-06-08：A/B 对比后选定【全级别统一纯 GPT】）：
#   gpt = 纯 gpt-image-2（画风更干净、内容/人物遵循度高）。L0-2 不再走"即梦换皮"。
#   如需临时回退某级别到即梦双段，改这里或用 IMAGE_BACKEND_OVERRIDE=jimeng_refine。
LEVEL_IMAGE_BACKEND: dict[str, str] = {
    "smart": "gpt", "0": "gpt", "1": "gpt", "2": "gpt",
    "3": "gpt", "4": "gpt", "5": "gpt", "6": "gpt",
}

# L0-2 出图流程（用户拍板 2026-06-08）：
#   "gpt_then_jimeng"（默认·新）= gpt-image-2 先出底图(内容/人物/构图遵循度高) → 即梦图生图只换皮成治愈水彩 → GPT自审；
#   "jimeng_then_gpt"（旧）      = 即梦直出 → GPT自审定向修图。
L02_PIPELINE = os.getenv("L02_PIPELINE", "gpt_then_jimeng").strip().lower()


def resolve_image_backend(level: str) -> str:
    """返回该 level 的出图后端：'jimeng_refine'（双段）或 'gpt'（单段）。

    即梦双段需要 Ark key；缺失时自动回退纯 gpt-image-2，保证不阻断出图。
    可用 IMAGE_BACKEND_OVERRIDE 全局强制（gpt / jimeng_refine）。
    """
    override = os.getenv("IMAGE_BACKEND_OVERRIDE", "").strip().lower()
    if override in ("gpt", "jimeng_refine"):
        backend = override
    else:
        backend = LEVEL_IMAGE_BACKEND.get(_level_key(level), "gpt")
    if backend == "jimeng_refine" and not ARK_API_KEY:
        return "gpt"
    return backend
# 绘本正文页：gpt-image-2 仅支持 1024x1024 / 1024x1536 / 1536x1024（不支持 4:3 直出）
# 方案A：先出 3:2(1536x1024) → 居中裁 4:3 → 升 4K，详见 IMAGE_TARGET_* 常量
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1536x1024")
# 出图清晰度参数（用户拍板 2026-06-09）：gpt-image 系列支持 quality=low/medium/high/auto。
#   此前我们【完全没设】这个参数 → 走默认档，画面偏软/不够清晰。设为 high 显著提升清晰度与细节锐度。
#   置空字符串则不发送该参数（兼容不支持 quality 的接口/回退）。
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "high").strip().lower()
# 目标交付比例与分辨率（绘本幻灯片 10x7.5 = 4:3）
# 美工口径（2026-06-03）：精细印刷 2000×1500（正好 4:3）。出图后居中裁 4:3 → 放大到此尺寸。
IMAGE_TARGET_RATIO = (4, 3)
IMAGE_TARGET_PRINT = (2000, 1500)         # 工作图（进 PPT）尺寸：居中裁 4:3 后放大到此尺寸
IMAGE_UPSCALE_METHOD = os.getenv("IMAGE_UPSCALE_METHOD", "lanczos")  # lanczos | esrgan
IMAGE_DELIVER_PRINT = os.getenv("IMAGE_DELIVER_PRINT", "true").lower() in ("1", "true", "yes")
# 向后兼容别名（旧代码引用名）
IMAGE_TARGET_4K = IMAGE_TARGET_PRINT
IMAGE_DELIVER_4K = IMAGE_DELIVER_PRINT

# ---------- A5 印刷交付：300DPI + CMYK + TIFF/PDF（用户拍板 2026-06-04）----------
# 印刷专用高分辨率（4:3）：3000×2250 ≈ 10"×7.5" @300DPI（比工作图更大，专供印刷）
IMAGE_PRINT_DPI = int(os.getenv("IMAGE_PRINT_DPI", "300"))
IMAGE_PRINT_DELIVER_PX = (
    int(os.getenv("IMAGE_PRINT_W", "3000")),
    int(os.getenv("IMAGE_PRINT_H", "2250")),
)
IMAGE_DELIVER_CMYK = os.getenv("IMAGE_DELIVER_CMYK", "true").lower() in ("1", "true", "yes")
IMAGE_DELIVER_TIFF = os.getenv("IMAGE_DELIVER_TIFF", "true").lower() in ("1", "true", "yes")
IMAGE_DELIVER_PDF = os.getenv("IMAGE_DELIVER_PDF", "true").lower() in ("1", "true", "yes")
# 可选 CMYK ICC 描述文件路径（如 USWebCoatedSWOP.icc）；留空则用 Pillow 内置转换
IMAGE_CMYK_PROFILE = os.getenv("IMAGE_CMYK_PROFILE", "")
# 放大后做轻度 USM 锐化，弥补插值发虚（印刷无模糊）
IMAGE_PRINT_UNSHARP = os.getenv("IMAGE_PRINT_UNSHARP", "true").lower() in ("1", "true", "yes")

# ---------- 放大锐化/降噪后处理（用户拍板 2026-06-10：治"色斑/磕碎感"）----------
# 背景：ESRGAN 未装时回退 Lanczos + 全图 USM，USM 会把水彩底颗粒在大片渐变/平滑区放大成色斑、
#   制造斑驳割裂感。修复策略：① 优先探测 Real-ESRGAN（自带高质量超分，无需 USM）；
#   ② 不可用时【显著弱化 USM】（降 percent、提高 threshold）且默认【仅对边缘锐化】（EDGE_ONLY），
#   平滑/渐变区不锐化 → 不再放大颗粒成色斑；③ 可选对平滑区做轻度降噪，消除斑驳色斑、保留均匀细纸纹。
# 全部可调。把 IMAGE_USM_EDGE_ONLY=false 可回退旧式全图锐化。
IMAGE_USM_PERCENT = int(os.getenv("IMAGE_USM_PERCENT", "22"))        # 旧值 45 → 22，显著弱化
IMAGE_USM_RADIUS = float(os.getenv("IMAGE_USM_RADIUS", "1.0"))       # 旧值 1.2 → 1.0
IMAGE_USM_THRESHOLD = int(os.getenv("IMAGE_USM_THRESHOLD", "6"))     # 旧值 3 → 6，平滑区不动
IMAGE_USM_EDGE_ONLY = os.getenv("IMAGE_USM_EDGE_ONLY", "true").lower() in ("1", "true", "yes")
IMAGE_USM_EDGE_GAIN = float(os.getenv("IMAGE_USM_EDGE_GAIN", "2.6")) # 边缘掩膜增益（越大锐化区越宽）
# 平滑区轻度降噪（仅作用于非边缘区）：消除背景斑驳色斑/磕碎感；默认开、强度很轻。
IMAGE_FLAT_DENOISE = os.getenv("IMAGE_FLAT_DENOISE", "true").lower() in ("1", "true", "yes")
IMAGE_FLAT_DENOISE_RADIUS = float(os.getenv("IMAGE_FLAT_DENOISE_RADIUS", "0.7"))
IMAGE_WATERMARK = os.getenv("IMAGE_WATERMARK", "false").lower() in ("1", "true", "yes")
# gpt-image-2 异步轮询参数
IMAGE_POLL_INTERVAL = float(os.getenv("IMAGE_POLL_INTERVAL", "5"))
# 轮询更耐心：慢任务给到 ~15 分钟再判失败（供应商反馈 gpt-image-2 偶发任务超时），失败后还会自动补跑
IMAGE_POLL_MAX_TRIES = int(os.getenv("IMAGE_POLL_MAX_TRIES", "180"))
# 参考图托管（gpt-image-2 只收 URL，本地图需先托管；临时图床即可，生成时拉取一次）
IMAGE_HOST_PROVIDER = os.getenv("IMAGE_HOST_PROVIDER", "tmpfiles")

# ---------- 文本（Claude/GPT via imarouter；旧 DOUBAO_/DEEPSEEK_ 名重指向）----------
DOUBAO_API_KEY = IMAROUTER_API_KEY
DOUBAO_BASE_URL = IMAROUTER_BASE
DOUBAO_MODEL = TEXT_MODEL

DEEPSEEK_API_KEY = IMAROUTER_API_KEY
DEEPSEEK_BASE_URL = IMAROUTER_BASE
DEEPSEEK_MODEL = TEXT_MODEL
# 仍可用 DeepSeek 那套 scene_cn / 润色函数，只是底层模型换成 Claude/GPT
USE_DEEPSEEK_FOR_SCENE = (
    os.getenv("USE_DEEPSEEK_FOR_SCENE", "true").lower() in ("1", "true", "yes")
    and bool(IMAROUTER_API_KEY)
)

# 无 Key 时降级
MOCK_IMAGES = (
    os.getenv("MOCK_IMAGES", "false").lower() in ("1", "true", "yes")
    or not IMAROUTER_API_KEY
)
MOCK_AI_EXTRACT = (
    os.getenv("MOCK_AI_EXTRACT", "false").lower() in ("1", "true", "yes")
    or not IMAROUTER_API_KEY
)

# ---------- IP 年龄映射（可被大纲 IP_Age 字段覆盖）----------
# 美工口径（2026-06-03 拍板）：0/1/2=8 岁，3/4=10 岁，5/6=12 岁
LEVEL_TO_AGE_DEFAULT: dict[str, int] = {
    "smart": 8,
    "0": 8, "1": 8, "2": 8,
    "3": 10, "4": 10,
    "5": 12, "6": 12,
}


def resolve_ip_age(level: str, explicit_age: int | None = None) -> int:
    if explicit_age:
        return int(explicit_age)
    key = _level_key(level)
    return LEVEL_TO_AGE_DEFAULT.get(key, 10)


def _level_key(level: str) -> str:
    """把 'L5' / 'Level 5' / '5' / 'Smart' 统一成 dict key。"""
    s = str(level).strip().lower()
    if "smart" in s:
        return "smart"
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits or "1"


# ---------- VIPKID Dino 品牌色（每 Level 主题色，从 A4 模板提取） ----------
# 用作 Worksheet 外框 + footer 文字色等
BRAND_COLORS: dict[str, str] = {
    "smart": "#5E9F49",   # 绿
    "0":     "#5E9F49",   # 兼容 L0 = Smart
    "1":     "#F18200",   # 橙
    "2":     "#54C2F0",   # 浅蓝
    "3":     "#E94653",   # 红
    "4":     "#00B0C4",   # 青
    "5":     "#E95283",   # 粉
    "6":     "#0677B7",   # 深蓝
}


def brand_color_hex(level: str) -> str:
    return BRAND_COLORS.get(_level_key(level), "#E95283")


def brand_color_rgb(level: str) -> tuple[int, int, int]:
    h = brand_color_hex(level).lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------- Reading Report 题量梯度（按口径） ----------
# L0-L2 = 4 题（1×⭐ + 2×⭐⭐ + 1×⭐⭐⭐）
# L3-L6 = 5 题（1×⭐ + 3×⭐⭐ + 1×⭐⭐⭐）
def rr_question_distribution(level: str) -> list[int]:
    """返回每题星数列表，例: [1, 2, 2, 3]"""
    key = _level_key(level)
    if key in ("smart", "0", "1", "2"):
        return [1, 2, 2, 3]
    return [1, 2, 2, 2, 3]


# ============================================================
#  绘本画面 构图 / 比例策略（底层逻辑：只读展示 + 自动注入提示词）
#  用户拍板（2026-06-02）：
#   - 主角必须是画面唯一视觉中心，占画面高度约 50–60%（清晰饱满）
#   - 同框其他人物按真实身高比例：同龄人身高相近、成人比儿童高，
#     但任何人都不能比同框同龄人明显大一圈
#   - 动物按真实比例（仓鼠≈成人手掌大，不能画成猫狗大小）
#   - 背景占 40–50%，环境元素清晰可辨但不喧宾夺主
#   - 留约 20% 浅色区给文字；默认平视；水彩治愈童书风
#  ⚠️ 这些不是“仅展示”，会真正注入每页正向/反向提示词。
# ============================================================
COMPOSITION_POLICY: dict[str, str] = {
    "protagonist_pct": "55–65%",
    "background_pct": "40–50%",
    "text_safe_pct": "约 20–25%",
    "perspective": "默认平视（与儿童视线齐平）",
    "style": "温暖治愈水彩童书风（低饱和、柔和晕染、圆润线条）",
    "protagonist_rule": (
        "主角（单人或主角群体）是画面视觉焦点、清晰饱满，整体占画面高度约 55–65%（画得够大、不要缩太小显空）；"
        "主体偏置画面一侧（不要居中铺满），仅在另一侧或顶部留出约 20–25% 干净的排文字空间，其余区域由主体与环境充实饱满地填满"
    ),
    "scale_rule": (
        "同框其他人物按真实身高比例（同龄人身高相近，成人比儿童高），"
        "任何人都不能比同框同龄人明显大一圈；"
        "多个同等重要的人物必须按同一尺度绘制、到镜头距离相同、站在同一水平面，"
        "作为一个群体共同占据主体，禁止任何一个人物被放大或拉近；"
        "【封面/群像等高锁】封面及群像页里，Mia/Tommy 与所有同龄队友/同学/背景清晰儿童必须"
        "站在同一水平面、到镜头同一距离、头顶大致齐平、体型尺度一致；主角绝不比身后/身旁的同龄孩子矮半头，"
        "背景里的同龄人也绝不能更高更大一圈；透视缩小只用于【明显更远】的背景人影，"
        "不得用于与主角同层、同框的队友/同学"
    ),
    "animal_rule": "动物按真实比例（仓鼠≈成人手掌大小，不能画成猫狗大小）",
    "background_rule": "背景占画面 40–50%，有清晰可辨的环境元素，但不喧宾夺主",
}


def composition_prompt_cn() -> str:
    """构图/比例策略 → 注入正向 prompt 的中文硬性要求串。"""
    p = COMPOSITION_POLICY
    return (
        f"构图与比例（硬性要求）：{p['protagonist_rule']}；"
        f"{p['scale_rule']}；{p['animal_rule']}；{p['background_rule']}。"
    )


def composition_negative_cn() -> str:
    """构图/比例策略 → 注入反向 prompt 的中文禁忌串。"""
    return (
        "主角被画得过小（主角应占画面 50–60%）；"
        "配角或动物比主角还大；同框同龄人身高差异过大；"
        "多个同等重要人物尺寸不一（某个人物明显比旁边同龄人大一圈、被放大或拉近、到镜头距离不同）；"
        "动物体型失真（仓鼠被画成猫狗大小）；主角偏离画面视觉中心；"
        "画面被主体/背景元素铺满堵死、完全没有给文字留出区域；预留的文字区被可识别的人物/动物/关键道具，或杂乱探入的树枝枝叶/招牌/建筑/家具遮挡；"
        "顶部文字区是纯白/惨白/无质感的空色块或硬边方块、没有场景色彩与质感、与下方画面割裂；顶部文字区不连续/不足20%；"
        "留白过多、留出大半张空荡荡的画面、主体缩得太小四周空一大片、画面冷清空旷；"
        "贴脸的大特写或紧裁构图；人物头顶上方没有留出空白、头部顶到画面上边缘；"
        "画面顶部被天花板/货架/相框/窗户/树叶/招牌等占满"
    )


# ============================================================
#  画面「平滑/统一」控制（底层逻辑 · 用户拍板 2026-06-03）
#   gpt-image-2 容易出细碎噪点/高频纹理，强制走大色块叙事、干净平滑。
# ============================================================
SMOOTHNESS_PROMPT_CN = (
    # 平滑控制要求（用户拍板提示词 2026-06-06，原样并入）：
    "平滑控制要求：整体画面必须干净平滑统一，强调大色块叙事与整体轮廓，"
    "不要细碎槽点，不要高频脏纹理，不要脏污颗粒立体感，不要密集小装饰，"
    "边缘清晰利落，表面干净，画面呼吸感强、主次分明、一目了然；"
    "细节克制简洁(controlled details)、纹理极简(minimal texture)、质感简洁干净高级、画面干净通透，材质完整自然、纹理平滑统一，"
    "主体清晰、背景层次分明（前后景拉开）；"
    "以平滑柔和的色块与渐变(smooth shading/gradients)为主、清晰的整体轮廓，水彩层次过渡柔和克制（绝不细碎），可高分辨率印刷。"
    # 用户拍板 2026-06-08（L4 实测反馈）：把目标风格英文串原样并入，追求更干净平滑、少碎纹理
    " clean illustration, smooth shading, soft lighting, controlled details, "
    "minimal texture, high clarity, refined edges, smooth gradients."
)
SMOOTHNESS_NEGATIVE_CN = (
    "细碎噪点；高频纹理；脏污颗粒；密集小装饰；杂乱碎点；颗粒感；"
    "噪声；划痕；过度细节堆砌；脏乱表面；模糊脏污；细碎槽点；"
    "斑驳破碎的色块；割裂的色斑/碎块；拼贴补丁感；色彩割裂不连贯；"
    "断裂破碎的轮廓；形体破碎；马赛克/碎片化质感；"
    # 用户拍板 2026-06-06：过锐化 / 色斑 / 崩坏 / 畸变
    "过度锐化；色斑；噪点细碎；崩坏；畸变；结构崩坏；肢体畸变；"
    "AI 杂线、乱纹、无逻辑多余背景；"
    # 用户拍板 2026-06-08（L4 实测反馈）：目标风格负向英文串原样并入
    "noise, grain, artifacts, high frequency detail, dirty texture, oversharpen, "
    "blotchy, chaotic details"
)


# ============================================================
#  儿童内容安全红线 + 画风/色彩规范（底层逻辑 · 用户拍板 2026-06-03）
# ============================================================
# ⚠️ 注意：正负向会拼成整段文本发给 gpt-image-2（Azure），其图像安全审核只看“词本身”，
#   不识别否定语境——所以这里【绝不能写】裸露/性感/暴露/血腥/暴力/利器/成人隐喻等敏感词，
#   否则会被误判 safety_violations（如 sexual）整页拦截。安全意图改用“正向、得体、温馨”措辞达成。
CHILD_SAFETY_POSITIVE_CN = (
    "阳光、健康、温暖的孩童绘本画风，人物穿着得体的日常服装、表情友善积极、画面温馨平和、适合儿童；"
    "低饱和、柔和护眼配色，明亮通透；五官规整端正、肢体结构合理（手脚指头数量正确）。"
)
CHILD_SAFETY_NEGATIVE_CN = (
    # 画风/色彩规范（不含任何敏感词，避免触发图像安全审核）
    "阴郁、压抑、灰暗的画风；荧光色、超高对比度色块、暗沉黑底画面；"
    # 儿童向柔化（用户拍板 2026-06-07）：去恐怖/凶相/丑陋——动物与反派都要可爱友善
    "动物或角色露出尖牙、獠牙、利齿；张着大口作势扑咬；面露凶光、怒目圆睁、眉头紧锁的凶恶表情；"
    "狰狞、吓人、阴森、惊悚的氛围；动物显得凶猛具攻击性、龇牙咧嘴、扑扯撕咬的紧张姿态；"
    "丑陋、怪诞、扭曲变形的造型；尖锐獠牙的特写大口；"
    # IP 唯一性
    "非已选 IP 角色、却拥有清晰五官/发型/眼镜的陌生路人或同学；画面里人物过多杂乱"
)


def child_safety_positive_cn() -> str:
    return CHILD_SAFETY_POSITIVE_CN


def child_safety_negative_cn() -> str:
    return CHILD_SAFETY_NEGATIVE_CN


# ============================================================
#  系列默认 IP + 全本角色一致性（底层逻辑 · 用户拍板 2026-06-03）
# ============================================================
DEFAULT_IP_RULE_CN = (
    "系列固定主角是 Mia（女孩）和 Tommy（男孩）。"
    "若故事未出现命名主角，则画面里出现的任何女孩默认套用 Mia 的形象，"
    "任何男孩默认套用 Tommy 的形象，保持系列一致。"
)
CONSISTENCY_RULE_CN = (
    "全本角色一致性：本书一旦确定了某个角色形象，"
    "其发型、发色、服装风格、配饰、五官（眼型/鼻型/脸型/表情）在每一页都必须保持完全一致，绝不允许跨页跳变；"
    "全本统一光影方向与配色体系，画风、明暗、色调保持一致。"
)


def smoothness_prompt_cn() -> str:
    """平滑/统一控制 → 注入正向 prompt。"""
    return SMOOTHNESS_PROMPT_CN


def smoothness_negative_cn() -> str:
    """平滑/统一控制 → 注入反向 prompt。"""
    return SMOOTHNESS_NEGATIVE_CN


def consistency_prompt_cn() -> str:
    """全本角色一致性 → 注入正向 prompt。"""
    return CONSISTENCY_RULE_CN


# ---------- PPT 几何 ----------
SLIDE_WIDTH_IN = 10.0
SLIDE_HEIGHT_IN = 7.5

# 字体（Poppins SemiBold；若用户机器未安装会回退）
FONT_FAMILY = "Poppins SemiBold"
FONT_BOLD = False           # SemiBold 已是字面体，不要再叠加 PowerPoint bold

# 字号（pt）
FONT_SIZE_TITLE = 40       # 封面书名（固定）
FONT_SIZE_BADGE = 16       # Level/Book 徽章
FONT_SIZE_BODY = 22        # 正文（标准范围 20–24，长文取 20，短文取 24）
FONT_SIZE_PAGE_NUM = 14    # 页码
FONT_SIZE_META_HEAD = 18   # 元信息字段名
FONT_SIZE_META_BODY = 16   # 元信息值

# 颜色（RGB）
ORANGE_BADGE = (0xF4, 0x73, 0x32)  # 橙色胶囊填充
WHITE = (0xFF, 0xFF, 0xFF)
BLACK = (0x12, 0x12, 0x12)
LIGHT_GRAY_BORDER = (0x33, 0x33, 0x33)

# 留白与文字框
TEXT_SAFE_RATIO_MIN = 0.10   # 生图必须留出的最小留白比例
TEXT_SAFE_RATIO_MAX = 0.15
TEXT_BOX_WIDTH_RATIO = 0.40  # 文字框宽 = 40% 页宽
TEXT_BOX_PADDING_IN = 0.18

# 页码圆参数
PAGE_NUM_DIAMETER_IN = 0.55
PAGE_NUM_MARGIN_IN = 0.30


def text_box_position(corner: str) -> tuple[float, float]:
    """根据角位返回 (left_in, top_in)。"""
    margin = 0.35
    w = SLIDE_WIDTH_IN * TEXT_BOX_WIDTH_RATIO
    if corner == "top-left":
        return (margin, margin)
    if corner == "top-right":
        return (SLIDE_WIDTH_IN - w - margin, margin)
    if corner == "bottom-left":
        return (margin, SLIDE_HEIGHT_IN - margin - 1.6)
    if corner == "bottom-right":
        return (SLIDE_WIDTH_IN - w - margin, SLIDE_HEIGHT_IN - margin - 1.6)
    return (margin, margin)


# ============================================================
#  全局标准 · 单一数据源（网页只读面板 + 各 builder 共用，杜绝漂移）
#  与 STANDARD.md / 用户 2026-06-03 拍板的冻结表保持一致。
# ============================================================

# 一、全项目通用基础规则（所有交付物 100% 强制）
GLOBAL_BASE_RULES: list[tuple[str, str]] = [
    ("命名规范", "`Level X_BookXX_品类_标题.后缀`，非法字符自动替换为下划线"),
    ("模板约束", "严格套用原版模板：Logo / 页眉页脚 / 页边距 / 配色 / 底色 / 装饰元素完全不动"),
    ("视觉统一", "全系列共用一套水彩画风 + 固定 IP 人物，跨页/跨册/跨交付物 100% 一致"),
    ("内容保真", "所有文本优先取自大纲，无大纲不编造；习题答案与教学内容跨交付物完全一致"),
    ("新人物规则", "出现大纲外新人物，先确认形象设定再配图，禁止私自生成新人物形象"),
]

# 二、英文字体（全项目仅 Poppins 家族；中文仅 阿里巴巴普惠体 2.0 55 Regular）
FONT_CN_FAMILY = "阿里巴巴普惠体 2.0 55 Regular"
FONT_RULES: list[tuple[str, str]] = [
    ("绘本 PPT（封面+内文+封底）", "Poppins **SemiBold**，封面标题 40pt、内文 20–24pt"),
    ("Worksheet 大标题", "Poppins **Bold 40pt**，居中，#333333"),
    ("Worksheet 副标题/题目说明", "Poppins Regular 20–24pt，居中，#666666；题目文本左对齐黑色"),
    ("Worksheet 下划线占位 `____`", "Arial（Poppins 下划线字形会被压扁）"),
    ("Reading Report / Teacher Guide 标题", "Poppins **Bold**，层级清晰"),
    ("Reading Report / Teacher Guide 正文", "Poppins Regular（中文 阿里巴巴普惠体 2.0 55），行距 1.2–1.5"),
]

# 三、固定 IP 人物 + 年龄映射（L0-2=8 / L3-4=10 / L5-6=12）
IP_ROSTER: list[tuple[str, str]] = [
    ("MIA（主角·女孩）", "好奇乐观；后脑【中高位】马尾·用【紫色发圈】束发（发髻在后脑中上部·非颅顶顶髻也非低位、马尾辫中长略带波浪垂至肩/上背，绝不丸子头/发髻/half-up、绝不颅顶超高马尾）、紫色长袖卫衣+浅灰白裤；跨页 100% 一致"),
    ("TOMMY（主角·男孩）", "爱玩伙伴；棕色蓬乱短发、【浅天蓝】长袖圆领卫衣 #5FA8D6~#8EC0ED +卡其裤（绝不深蓝/navy/polo/牛仔）；与 Mia 年龄感匹配"),
    ("TEACHER KIM（成人女老师）", "温暖有创造力（Ms. Frizzle 风），成年女性形象统一"),
    ("WINNIE（猫）", "常驻软萌猫咪，偶尔客串，画风与主角匹配"),
    ("Dino（品牌吉祥物）", "VIPKID 官方形象，造型/配色/比例不得修改"),
]

# Level → CEFR / Lexile 自动映射（与 STANDARD.md 一致）
LEVEL_CEFR: dict[str, str] = {
    "smart": "Pre-A1", "0": "Pre-A1", "1": "Pre-A1", "2": "A1",
    "3": "A1+", "4": "A2", "5": "B1", "6": "B1+",
}
LEVEL_LEXILE: dict[str, str] = {
    "smart": "BR", "0": "BR-100L", "1": "100L-200L", "2": "200L-300L",
    "3": "300L-450L", "4": "450L-600L", "5": "600L-750L", "6": "750L-900L",
}

# 四、各交付物尺寸/规格 冻结表（key: book / worksheet / rr / tg）
DELIVERABLE_SPECS: dict[str, dict] = {
    "book": {
        "icon": "📖", "name": "绘本 PPT", "fmt": "PPTX",
        "size": "幻灯片 10 × 7.5 in（4:3）",
        "rules": [
            "结构：封面 + 7 页正文 + 封底；页数补足 4 的倍数",
            "页码：正文 Page 2 起，左下/右下交替；封面封底无页码",
            "封底 6 项：Level / Book / CEFR / Lexile / 总词数 / Vocabulary",
            "生图：gpt-image-2 出 1536×1024(3:2) → 居中裁 4:3 → 放大到精细印刷 2000×1500",
            "画风：明亮通透低饱和水彩；底部 15–20% 留白不遮文字",
            "词汇显示：L0-2 双行(Mastery+Exposure)，L3-6 单行(Vocabulary 4 词)；全部 lemma 小写无标点",
        ],
    },
    "worksheet": {
        "icon": "📝", "name": "练习册 Worksheet", "fmt": "PPTX",
        "size": "A4 横向 297 × 210mm（11.69 × 8.27 in）",
        "rules": [
            "固定 6 页 = 2 Vocabulary + 2 Sentence + 2 Reading（标题不变）",
            "题型按 Level 分难度；删除涂色/纯涂圈类无输出题",
            "阅读选择题默认 4 道，L5-6 可加到 6-8 道",
            "2 阅读：L0-3 = 2 页阅读理解；L4-6 = 阅读 1 页 + 写作/思维导图 1 页",
            "答案：单词小写无标点 / 句子首字母大写加句号 / 美式拼写",
            "配图：默认复用绘本图 → 缺则 AI 出同画风纯物体小图 → 可不配图（逐题切换）",
        ],
    },
    "rr": {
        "icon": "📄", "name": "阅读报告 Reading Report", "fmt": "DOCX",
        "size": "A4 竖向 210 × 297mm；边距 左右1.0 / 上下0.9cm；强制 1 页",
        "rules": [
            "Reader Type 按 Level 映射；阅读字数 = 纯故事字数",
            "词汇掌握 = Mastery 4-6 词；Phonics：L0-4 取大纲，L5-6 换构词法",
            "阅读流利度 = 大纲 Reader 栏一字不改",
            "阅读表达：L0-2 = 4 题、L3-6 = 5 题（1⭐+多⭐⭐+1⭐⭐⭐）",
            "页码：L0-3 标 (P#)，L4-6 不标页码",
            "双版本：空白版（教师手填）/ 示例答案版（演示）",
        ],
    },
    "tg": {
        "icon": "👩‍🏫", "name": "教师指南 Teacher's Guide", "fmt": "DOCX",
        "size": "A4 竖向 210 × 297mm；边距 四周 2.0cm",
        "rules": [
            "100% 英文，无中文、无 AI 元评论",
            "8 固定模块顺序：Lesson Guide → Pre-Reading → During Reading → "
            "Post-Reading → Reading Check → Portfolio → Independent Reading → Lesson Close",
            "内容 100% 取自大纲；Answer Key 与 Worksheet 逐题一致",
        ],
    },
}


def render_global_standards_md(level: str | None = None) -> str:
    """全局底层逻辑（只读）→ markdown。供网页最前面的『今日制作标准总览』。"""
    lk = _level_key(level) if level else None
    cefr = LEVEL_CEFR.get(lk, "") if lk else ""
    lexile = LEVEL_LEXILE.get(lk, "") if lk else ""
    lines: list[str] = []
    lines.append("#### 一、全项目通用基础规则（所有交付物 100% 强制）")
    for k, v in GLOBAL_BASE_RULES:
        lines.append(f"- **{k}**：{v}")
    lines.append("")
    lines.append("#### 二、英文字体统一（仅 Poppins 家族 / 中文 阿里巴巴普惠体 2.0）")
    for k, v in FONT_RULES:
        lines.append(f"- **{k}**：{v}")
    lines.append("")
    lines.append("#### 三、固定 IP 人物 + 年龄映射（L0-2=8 / L3-4=10 / L5-6=12）")
    for k, v in IP_ROSTER:
        lines.append(f"- **{k}**：{v}")
    if lk:
        lines.append("")
        lines.append(f"> 当前 Level 自动映射：**CEFR {cefr} · Lexile {lexile}**")
    lines.append("")
    lines.append("#### 四、画风 / 构图 / 平滑（自动注入每页提示词）")
    cp = COMPOSITION_POLICY
    lines.append(f"- 主角占画面 **{cp['protagonist_pct']}**、背景 **{cp['background_pct']}**、留白 **{cp['text_safe_pct']}**")
    lines.append(f"- 视角 {cp['perspective']}；画风 {cp['style']}")
    lines.append("- 干净平滑、大色块叙事；不要细碎噪点/高频纹理/脏污颗粒/密集小装饰")
    return "\n".join(lines)


def render_deliverable_spec_md(key: str, level: str | None = None) -> str:
    """单个交付物专属规格 → markdown。供各交付物 Tab 顶部展示。"""
    spec = DELIVERABLE_SPECS.get(key)
    if not spec:
        return ""
    lines = [f"**{spec['icon']} {spec['name']}** · 格式 {spec['fmt']} · 尺寸 {spec['size']}", ""]
    for r in spec["rules"]:
        lines.append(f"- {r}")
    return "\n".join(lines)
