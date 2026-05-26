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

# ---------- 路径 ----------
INPUTS_DIR = ROOT / "inputs"
OUTPUTS_DIR = ROOT / "outputs"
ASSETS_DIR = ROOT / "assets"
CHARACTERS_DIR = ASSETS_DIR / "characters"
STYLE_DIR = ASSETS_DIR / "style"
TEMPLATES_DIR = ROOT / "templates"

# ---------- 即梦 4.6 / 火山方舟 ----------
JIMENG_API_KEY = (
    os.getenv("JIMENG_API_KEY", "").strip()
    or os.getenv("ARK_API_KEY", "").strip()
)
JIMENG_BASE_URL = os.getenv(
    "JIMENG_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
).rstrip("/")
JIMENG_MODEL = os.getenv("JIMENG_MODEL", "doubao-seedream-4-5-251128")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "2304x1728")  # 4:3, Seedream 要求 ≥3.69M 像素
IMAGE_WATERMARK = os.getenv("IMAGE_WATERMARK", "false").lower() in ("1", "true", "yes")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "240"))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "2"))

# 无 Key 时降级为占位图
MOCK_IMAGES = (
    os.getenv("MOCK_IMAGES", "false").lower() in ("1", "true", "yes")
    or not JIMENG_API_KEY
)

# ---------- IP 年龄映射（可被大纲 IP_Age 字段覆盖）----------
# 用户拍板：L0-L3=8岁 / L4-L5=10岁 / L6=12岁
LEVEL_TO_AGE_DEFAULT: dict[str, int] = {
    "0": 8, "1": 8, "2": 8, "3": 8,
    "4": 10, "5": 10,
    "6": 12,
}


def resolve_ip_age(level: str, explicit_age: int | None = None) -> int:
    if explicit_age:
        return int(explicit_age)
    key = "".join(ch for ch in str(level) if ch.isdigit()) or "1"
    return LEVEL_TO_AGE_DEFAULT.get(key, 10)


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
