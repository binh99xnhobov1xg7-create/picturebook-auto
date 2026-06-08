"""宏观 0-6 课程分级参数表（机器可读源）。

这是整套体系"难度阶梯"的单一事实来源（single source of truth）：
每个级别的 CEFR / Lexile / 词汇量 / 知识体系（自然拼读 vs 构词法）/ 题目难度配比 /
主题 / 课堂教学法 / 学完产出（得到·学到·练到）/ IP 形象年龄。

数据来自对官方三个 S&S Excel（Level 0-2、Level 3-6、全级别每课 Prompt）与
TG_SOP_Level3-4.docx 的研读结论：

  • 分水岭 L2→L3：预教词+4步Phonics+全页PictureWalk → 语境内学词+2步Phonics意识+
    体裁定范围+动态 Pause Point。
  • 分水岭 L4→L5：自然拼读(Phonics)→ 构词法(Word Formation)；核心词 4→5；
    文本 ~90 词 → ~130-200 词。

下游用途：TG（teacher_guide_builder）、题目难度（ai_extractor/worksheet/RR）、
画面复杂度（cn_prompt_builder）都应从这里取分级参数，避免各处写死、口径不一。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LevelProfile:
    level: str                      # "0".."6" / "smart"
    band: str                       # low(0-2) / mid(3-4) / high(5-6)
    cefr: str
    lexile: str
    word_count: str                 # 单本正文字数区间
    ip_age: int                     # 主角形象年龄（8/10/12）

    # 知识体系
    decoding_system: str            # 自然拼读 / 构词法 等
    decoding_detail: str            # 该级别的解码/构词重点
    syntax_focus: str               # 句法重点
    vocab_count: int                # 单本核心词数量
    vocab_model: str                # "mastery+exposure" / "single-4" / "single-5"
    vocab_teaching: str             # 预教 / 语境内自然引入

    # 阅读理解
    reading_skill_tier: str         # 命名识别 / 复述顺序 / 故事语法 / 推理分析 …
    cognitive_demand: str           # Recall / Inference / Analysis
    # 题目难度配比（L0 字面 / L1 推断 / L2 分析），三者和为 1.0
    question_mix: tuple[float, float, float] = (0.7, 0.3, 0.0)

    # 教学流程差异
    picture_walk: str = "全页"       # 全页 / 体裁定范围
    pause_points: str = "均匀分布"    # 均匀分布 / 动态结构点
    finger_tracking: bool = False    # 老师指读（仅低段）
    phonics_steps: int = 2           # 4 步(低段) / 2 步意识(中高段)

    themes: tuple[str, ...] = ()
    teaching_moves: tuple[str, ...] = ()

    # 学完产出
    outcome_get: str = ""            # 得到（成果物）
    outcome_learn: str = ""          # 学到（知识/技能）
    outcome_practice: str = ""       # 练到（迁移应用）


# ============================================================
#  L0 — L6 七级参数（外加 Pre-L0 / smart 走 L0 口径）
# ============================================================
LEVEL_PROFILES: dict[str, LevelProfile] = {
    "0": LevelProfile(
        level="0", band="low", cefr="Pre-A1", lexile="10L - 200L",
        word_count="9-33 词", ip_age=8,
        decoding_system="音素意识 (Phonemic Awareness)",
        decoding_detail="认读首音 /m/ /s/ /t/ /a/ /p/ 等，建立字母-声音对应，不做完整解码",
        syntax_focus="单词标签 + 句型框架（A ___ / I see ___ / I like ___）",
        vocab_count=8, vocab_model="mastery+exposure", vocab_teaching="读前预教（图片/手势/TPR）",
        reading_skill_tier="命名与识别（Tier 1 · 看图说话）",
        cognitive_demand="Recall（回忆）",
        question_mix=(0.85, 0.15, 0.0),
        picture_walk="全页", pause_points="均匀分布", finger_tracking=True, phonics_steps=4,
        themes=("颜色", "数字", "形状", "身体", "食物", "动物", "衣物", "学校", "家庭", "交通", "季节", "游戏"),
        teaching_moves=("图片漫步 Picture Walk", "point-and-name 指物命名", "TPR 全身反应",
                        "echo/choral 跟读齐读", "老师指读 Finger Tracking 建立印刷概念"),
        outcome_get="能用句型框架说出一页（A ___ / I see ___）",
        outcome_learn="高频词与主题词命名、字母-声音意识、从左到右的印刷概念",
        outcome_practice="看图用单一句型口头造句、跟读与指读",
    ),
    "1": LevelProfile(
        level="1", band="low", cefr="Pre-A1 → A1", lexile="10L - 200L",
        word_count="15-40 词", ip_age=8,
        decoding_system="自然拼读·解码 (Decoding)",
        decoding_detail="解码已学拼读规律：短元音 CVC、首尾辅音；不再只是音素意识",
        syntax_focus="可解码句型文本 + 顺序词（first/next）",
        vocab_count=6, vocab_model="mastery+exposure", vocab_teaching="读前预教 3-4 个具体词",
        reading_skill_tier="复述与中心意思（顺序词复述）",
        cognitive_demand="Recall → 简单 Inference",
        question_mix=(0.75, 0.25, 0.0),
        picture_walk="全页", pause_points="均匀分布", finger_tracking=True, phonics_steps=4,
        themes=("宠物", "日常", "动作", "家庭", "天气", "社区"),
        teaching_moves=("提示解码而非猜词", "指读强化印刷概念", "echo/choral 流畅度",
                        "读后用顺序词复述", "简单 text-to-self 联系"),
        outcome_get="能独立解码并跟读一本可解码绘本",
        outcome_learn="短元音/首尾辅音解码、3-4 个新词、用顺序词复述",
        outcome_practice="解码新词、复述故事顺序、找高频词",
    ),
    "2": LevelProfile(
        level="2", band="low", cefr="A1", lexile="10L - 200L",
        word_count="20-50 词", ip_age=8,
        decoding_system="自然拼读·规律复习 (Phonics Patterns)",
        decoding_detail="复习并自动化已学拼读规律；进入词组级朗读",
        syntax_focus="故事语法（问题/解决）+ 词组级句子",
        vocab_count=5, vocab_model="mastery+exposure", vocab_teaching="读前预教 3-5 个 Tier2+Tier3 词",
        reading_skill_tier="故事语法（识别问题与解决）",
        cognitive_demand="Inference（推断）开始显现",
        question_mix=(0.6, 0.35, 0.05),
        picture_walk="全页", pause_points="均匀分布", finger_tracking=True, phonics_steps=4,
        themes=("故事", "解决问题", "友谊", "探索", "自然"),
        teaching_moves=("先准确解码再查意义", "词组级朗读支持句法", "心象 mental imagery",
                        "显式追踪问题-解决", "decode→澄清意义循环"),
        outcome_get="能读懂一个有问题-解决结构的简单故事",
        outcome_learn="拼读规律自动化、问题/解决结构、3-5 个新词",
        outcome_practice="词组流畅朗读、追踪故事结构、写一句话回应",
    ),
    "3": LevelProfile(
        level="3", band="mid", cefr="A1+", lexile="210L - 400L",
        word_count="70-85 词", ip_age=10,
        decoding_system="自然拼读·意识 (Phonics Awareness)",
        decoding_detail="2 步意识检查（教师示范音 + 文中寻音），不再深度操练解码",
        syntax_focus="目标句型（一般/进行/将来时、方位介词、关系从句雏形）",
        vocab_count=4, vocab_model="single-4", vocab_teaching="语境内自然引入（不预教）",
        reading_skill_tier="阅读技能由大纲指定（顺序/分类/比较/因果/故事要素）",
        cognitive_demand="Inference 为主，开始 Analysis",
        question_mix=(0.45, 0.4, 0.15),
        picture_walk="体裁定范围（虚构留结局/非虚构全页）", pause_points="动态结构点",
        finger_tracking=False, phonics_steps=2,
        themes=("时间", "衣物", "我们的身体", "动物", "哺乳动物与鸟类", "鱼类与爬行动物", "五感", "季节与天气"),
        teaching_moves=("Reading to Learn 起点", "按体裁决定 Picture Walk 范围",
                        "动态 Pause Point", "[L0]/[L1]/[L2] 分层提问", "策略+技能贯穿提问"),
        outcome_get="能读懂 ~80 词的虚构/非虚构短文并完成 GO 图形组织器",
        outcome_learn="语境内学词、大纲指定阅读策略与技能、目标句型",
        outcome_practice="分层回答理解题、用 GO 整理信息、按句型迁移表达",
    ),
    "4": LevelProfile(
        level="4", band="mid", cefr="A2", lexile="410L - 600L",
        word_count="90-100 词", ip_age=10,
        decoding_system="自然拼读·意识 (Phonics Awareness)",
        decoding_detail="2 步意识检查；拼读规律更难（双元音、r 控制音、辅音连缀）",
        syntax_focus="关系从句（that）、时间状语从句（Before leaving,…）、定义句",
        vocab_count=4, vocab_model="single-4", vocab_teaching="语境内自然引入（不预教）",
        reading_skill_tier="主旨与细节 / 问题解决 / 故事要素 / 事实观点 / 分类",
        cognitive_demand="Inference + Analysis",
        question_mix=(0.4, 0.4, 0.2),
        picture_walk="体裁定范围", pause_points="动态结构点",
        finger_tracking=False, phonics_steps=2,
        themes=("世界旅行与地形", "海洋河流湖泊", "沙漠", "大峡谷", "雨林", "野生动物", "海洋动物", "栖息地"),
        teaching_moves=("同 L3 完整 SOP", "更长句子与从句", "主旨-细节网/问题-解决图",
                        "事实与观点辨析", "非虚构科学事实核对"),
        outcome_get="能读懂 ~95 词含从句的短文并完成对应 GO",
        outcome_learn="关系从句/时间从句、主旨细节、事实观点辨析、4 个新词",
        outcome_practice="推断与分析题、用从句句型写句、整理主旨与支撑细节",
    ),
    "5": LevelProfile(
        level="5", band="high", cefr="A2（延展）", lexile="410L - 600L",
        word_count="130-167 词", ip_age=12,
        decoding_system="构词法 (Word Formation)",
        decoding_detail="从自然拼读转向构词：词根词缀、复合词、派生词（不再做 Phonics）",
        syntax_focus="复合句、连接词、说明文与议论文句式",
        vocab_count=5, vocab_model="single-5", vocab_teaching="语境内自然引入（不预教）",
        reading_skill_tier="更高阶：推理、比较对比、作者意图、综合归纳",
        cognitive_demand="Analysis 为主",
        question_mix=(0.3, 0.4, 0.3),
        picture_walk="体裁定范围", pause_points="动态结构点",
        finger_tracking=False, phonics_steps=2,
        themes=("友谊与社交", "品格", "更抽象的社会与科学主题"),
        teaching_moves=("沿用完整 SOP，认知上调", "构词法替代自然拼读",
                        "更多 [L2] 分析/评价题", "更长文本的分段处理", "综合归纳与作者意图"),
        outcome_get="能读懂 ~150 词的较长文本并完成高阶 GO/写作",
        outcome_learn="构词法、复合句、推理与比较对比、5 个新词",
        outcome_practice="分析评价题、综合归纳、用复合句写较长回应",
    ),
    "6": LevelProfile(
        level="6", band="high", cefr="B1", lexile="600L+",
        word_count="200-210 词", ip_age=12,
        decoding_system="构词法 (Word Formation)",
        decoding_detail="进阶构词：学术词根词缀、专业术语构成；长难句解析",
        syntax_focus="长难句、被动语态、说明/议论复杂句式",
        vocab_count=5, vocab_model="single-5", vocab_teaching="语境内自然引入（不预教）",
        reading_skill_tier="批判性阅读：评价、论证、跨文本综合",
        cognitive_demand="Analysis / Evaluation",
        question_mix=(0.25, 0.4, 0.35),
        picture_walk="体裁定范围", pause_points="动态结构点",
        finger_tracking=False, phonics_steps=2,
        themes=("生存与适应", "结构性适应", "科学与社会议题"),
        teaching_moves=("最高阶 SOP", "学术构词与长难句", "批判性/评价性提问",
                        "论证与证据", "跨文本综合"),
        outcome_get="能读懂 ~200 词的说明/议论文本并完成批判性任务",
        outcome_learn="学术构词、长难句、批判性阅读与论证",
        outcome_practice="评价论证题、跨文本综合、写结构化长段落",
    ),
}


def _level_key(level: str) -> str:
    s = (level or "").strip().lower()
    if "smart" in s:
        return "0"
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits if digits in LEVEL_PROFILES else "3"


def get_profile(level: str) -> LevelProfile:
    """按级别字符串返回参数；smart/未知回退到 L0/L3 口径。"""
    return LEVEL_PROFILES[_level_key(level)]


# 宏观文档渲染顺序
ORDERED_LEVELS: tuple[str, ...] = ("0", "1", "2", "3", "4", "5", "6")
