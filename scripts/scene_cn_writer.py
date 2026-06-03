"""DeepSeek 专用：写"中文画面描述 scene_cn"和"润色生图 prompt"。

核心思路：
- Doubao text 在写"详细中文画面"上能力一般，词汇朴素、缺空间感和氛围
- DeepSeek V4 Pro 在中文长文本理解 + 视觉描述上明显更强
- 用 DeepSeek 专门负责这两件事，最终 prompt 喂给 Seedream 4.5 出图

模块对外暴露 3 个函数：
  - write_scene_cn(...)              → 给一页故事 + 上下文，写 120-220 字 scene_cn
  - polish_image_prompt(...)         → 给当前完整 prompt，DeepSeek 润色到 Seedream 4.5 最佳实践
  - is_available()                   → 检查 DeepSeek 是否可用（key + 模型激活）

如果 DeepSeek 不可用，调用方应该 fallback 到 Doubao 或返回原 prompt。
"""
from __future__ import annotations

import json
from typing import Optional

from deepseek_client import DeepSeekError, deepseek_chat, is_deepseek_available


def is_available() -> bool:
    return is_deepseek_available()


# ============================================================
# 1. 写 scene_cn：给一页故事文本 + 上下文 → 120-220 字详细画面描述
# ============================================================

_SCENE_SYSTEM_PROMPT = """你是 VIPKID 儿童绘本视觉描述专家，专门为水彩童书风插画师写画面描述。

你的任务：根据老师给的英文故事句子 + 上下文（人物 IP、风格、必出现/必避免），
写一段 **100-180 字的中文画面描述**，作为画师作画的 brief。

【最高铁律 · 外观全部交给 IP 参考图，绝不描述人物长相】
- 人物的发型、发色、衣服、衣服颜色、配饰、眼镜、年龄长相、五官——**全部由参考图和 IP 锁定决定，你一个字都不许写**。
- 提到人物时**只用名字**（如 "Anna"、"Mia"、"Tommy"、"一个男孩"、"一个女孩"），后面**只接动作和表情**，绝不接外观。
- 反例（严禁）：「12岁Anna戴琥珀色眼镜、黑色双低马尾，穿黄毛衣」——这种重描外观会让画师把人画歪。
- 正例（应这样）：「Anna 双手交叠放在课桌上，肩膀微微缩起，眉头轻蹙」——只有动作+表情。

写作铁律（不可违反）：
1. 只写 3 个维度（按顺序），**不写"主体外观"**：
   - **动作**：每个人物的具体动词姿势 + 站位（如 "Anna 跪在地上伸右手去捡书，Mia 在她左侧蹲下递书"），不要"她在帮忙"这种泛词
   - **环境**：可见的具体物品/空间锚点（如 "走廊地上散落 5 本彩色课本，右侧大窗采光，背景几个孩子在玩"），不要"教室"这种泛词
   - **氛围**：光照方向 + 整体色调（如 "晨光从右侧斜射，整体明亮通透干净"）
2. 表情必须用**具体面部动作**表达，禁止抽象情绪词。映射参考：
   Happy=嘴角上扬眼睛弯起；Excited=眉毛上扬眼睛睁大；Focused=眉头轻收眼神向下专注；
   Peaceful=眉眼舒展嘴角平缓微扬；Curious=头微侧眼睛睁大眉毛轻抬；Sad/Nervous=嘴角微垂眉头轻蹙肩膀微缩
3. 禁止"教室一角"这种模糊空间词，必须给空间锚点（"靠窗第二排课桌"）
4. 必出现的元素放在第一句，避免漏掉
5. 字数 100-180，超出请精简

【安全与 IP 唯一性铁律（出题源头把关，绝不可违反）】
- IP 唯一性：画面里出现的儿童只能是本页给定的 IP 角色；**不要引入陌生同学/路人**。
  如剧情确需"其他孩子"，只能写成"远景一两个模糊淡化的孩子身影（可省略）"，绝不给他们具体动作/五官。
- 非必要人物尽量少出现，画面安静克制、留白充足，主角群体是绝对焦点。
- 内容安全（零触碰）：不写裸露/性感着装、血腥暴力惊悚怪兽、玩火/攀爬高空/持刀利器等危险动作、
  宗教/政治/成人隐喻；氛围必须阳光健康温暖，**绝不写阴郁/暗黑/惊悚/压抑**的画面与色调。
- 色调统一走低饱和柔和护眼路线，禁止荧光色、超高对比、暗沉黑底。

输出：纯文本，不要任何 markdown 符号、不要前缀（如"画面："），直接开始描述。"""


def write_scene_cn(
    *,
    story_sentence: str,
    page_idx: int,
    book_title: str,
    level: str,
    ip_age: int,
    cast_descriptions: list[str],
    style_summary: str = "",
    must_include: str = "",
    must_avoid: str = "",
    previous_pages_summary: str = "",
) -> str:
    """用 DeepSeek 写一页的中文画面描述。

    Args:
        story_sentence: 当前页的英文故事原文
        page_idx: 页号（2-8 故事页；0 是封面）
        book_title: 书名（封面会用）
        level: VIPKID 级别（影响人物年龄/复杂度）
        ip_age: 当前 level 对应的 IP 年龄（如 L5=12）
        cast_descriptions: 已锁定的 IP 形象描述列表（如 ["12 岁 Anna，黑色双低马尾..."]）
        style_summary: Step 3 风格设定的一句话总结（"温暖水彩 + 学校教室 + 清新柔和"）
        must_include: 教师锁定的必出现元素（多行字符串）
        must_avoid: 教师锁定的必避免元素（多行字符串）
        previous_pages_summary: 前几页的简短摘要（保持连续性）

    Returns:
        120-220 字的中文画面描述。
        如果 DeepSeek 不可用，抛 DeepSeekError 让调用方 fallback。
    """
    if not is_available():
        raise DeepSeekError("DeepSeek 未激活，请回 fallback")

    page_label = "封面" if page_idx == 0 else f"Page {page_idx}"

    cast_block = "\n".join(f"  - {c}" for c in cast_descriptions) if cast_descriptions else "  - 无指定 IP，按 generic 儿童形象"

    must_inc_lines = "\n".join(f"  - {l.strip()}" for l in (must_include or "").splitlines() if l.strip())
    must_avd_lines = "\n".join(f"  - {l.strip()}" for l in (must_avoid or "").splitlines() if l.strip())

    user_msg = f"""# 任务背景
绘本《{book_title}》(Level {level}, IP 年龄 {ip_age} 岁)
现在为 **{page_label}** 写画面描述。

# 这一页的英文故事
{story_sentence}

# 这一页出场的人物（仅供你知道"谁在场"，外观由参考图决定，绝不要把发型/衣服/颜色/配饰写进描述）
{cast_block}

# 全局风格设定
{style_summary or "（无）"}

# 教师锁定 · 必出现元素
{must_inc_lines or "（无）"}

# 教师锁定 · 必避免元素
{must_avd_lines or "（无）"}

# 前几页摘要（保持人物形象/服装连续性）
{previous_pages_summary or "（首页）"}

请输出 120-220 字的中文画面描述。"""

    return deepseek_chat(
        system=_SCENE_SYSTEM_PROMPT,
        user=user_msg,
        temperature=0.4,
        max_tokens=600,
    ).strip()


# ============================================================
# 2. 润色生图 prompt：把当前 prompt 喂给 DeepSeek 强化
# ============================================================

_POLISH_SYSTEM_PROMPT = """你是 Seedream 4.5（火山即梦 4.6）图像生成的提示词工程师。

你的任务：把老师/系统给的现有"绘本生图 prompt"重写一版，让它**更适合 Seedream 4.5 的生成习惯**，
画出的图人物更清晰、风格更稳定、细节更丰富。

Seedream 4.5 提示词最佳实践：
1. **单段流畅自然语言**，不要标签式 (a, b, c)、不要换行分点
2. 开头先说"风格 + 媒介"（如 "明亮通透水彩童书风插画，大色块平涂、颜色均匀干净"）
3. 然后写"主体"，每个人物：**只用姓名 + 当下动作姿势 + 具体表情**（绝不添加或改写发型/服装/颜色/配饰/年龄长相——这些由参考图决定）
4. 然后写"环境"：空间位置 + 可见物品（具体到数量和颜色）
5. 然后写"光线 + 氛围"
6. 最后写构图（人物占比 50-60%、留白位置）
7. 全程**中文为主**，少量必要英文术语（如 close-up / wide shot）可保留
8. 长度 300-600 字最佳
9. 严禁出现"模糊"、"不清楚"、"可能"等不确定词
10. 严禁出现矛盾约束（如同时"特写"和"远景"）

# 最高铁律：外观交给参考图，不要重描
- 原 prompt 里若已有【人物姓名 + 锁定外观】段落，**原样保留、不要改写、不要简化、不要扩写**
- 你新写的句子里提到人物时**只用名字 + 动作 + 表情**，绝不新增/修改任何外观细节（发型/衣服/颜色/眼镜/配饰）
- 必须保留【必出现】里的元素；不能新增故事中没有的人物或道具
- IP 唯一性与安全：不要新增陌生同学/路人（如需其他孩子只写"远景模糊淡化身影"）；
  不得引入危险动作、暗黑惊悚氛围、荧光/高对比/黑底；氛围保持阳光健康、低饱和柔和。

# 输出格式
直接输出润色后的 prompt 全文（一段），不要任何前缀、解释、markdown。"""


def polish_image_prompt(
    *,
    current_prompt: str,
    story_sentence: str = "",
    style_summary: str = "",
    must_include: str = "",
    must_avoid: str = "",
) -> str:
    """让 DeepSeek 润色当前 prompt，返回优化版。

    传入当前完整的正向 prompt（含人物锁定、必出现等）+ 故事上下文，
    DeepSeek 会按 Seedream 4.5 最佳实践重写成更适合出图的一段。

    Raises:
        DeepSeekError: DeepSeek 未激活或调用失败。
    """
    if not is_available():
        raise DeepSeekError("DeepSeek 未激活")

    user_msg = f"""# 当前正向 prompt（待润色）
{current_prompt}

# 这一页对应的英文故事原文
{story_sentence or "（无）"}

# 全局风格设定
{style_summary or "（无）"}

# 教师锁定 · 必出现
{must_include or "（无）"}

# 教师锁定 · 必避免（这些不要写进正向，只供你判断不要画什么）
{must_avoid or "（无）"}

请输出润色后的 prompt 全文，单段中文，300-600 字。"""

    return deepseek_chat(
        system=_POLISH_SYSTEM_PROMPT,
        user=user_msg,
        temperature=0.3,
        max_tokens=1200,
    ).strip()


# ============================================================
# 3. 给已有 Doubao scene_cn 做 DeepSeek 二次升级（fallback 链路用）
# ============================================================

def upgrade_doubao_scene_cn(*, doubao_scene: str, story_sentence: str,
                            cast_descriptions: list[str]) -> str:
    """如果 Doubao 已经生成了 scene_cn，让 DeepSeek 在其基础上加强。

    比 write_scene_cn 更轻量（不重写，只补充缺失维度）。
    """
    if not is_available():
        raise DeepSeekError("DeepSeek 未激活")

    cast_block = "\n".join(f"  - {c}" for c in cast_descriptions) if cast_descriptions else "（无）"

    user_msg = f"""请基于以下 Doubao 生成的中文画面描述做"轻度补强"：
- 检查 4 维度（主体/动作/环境/氛围）是否齐全，缺哪补哪
- 检查人物形象是否完整，没写到的标志性外观请补上
- 总字数控制在 120-220 字

# Doubao 生成的画面描述
{doubao_scene}

# 这一页的英文故事
{story_sentence}

# 已锁定的 IP 形象（用于补全人物外观）
{cast_block}

请直接输出补强后的画面描述（不要任何前缀）。"""

    return deepseek_chat(
        system=_SCENE_SYSTEM_PROMPT,
        user=user_msg,
        temperature=0.3,
        max_tokens=600,
    ).strip()
