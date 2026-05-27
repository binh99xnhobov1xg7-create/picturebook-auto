Title: <书名 English>
Level: <0-6>
Book: <编号 NN>
CEFR: <Pre-A1 / A1 / A2 / B1>
Lexile: <如 100L-300L>
IP_Age: <8 / 10 / 12，可省略：L0-3→8, L4-5→10, L6→12>

# 单行词汇（L4-L6 用）
Vocabulary: word1, word2, word3, word4

# 双行词汇（L0-L3 用，注释上一行用下面两行替代）
# Vocabulary_Mastery: a, b, c, d
# Vocabulary_Exposure: e, f, g, h, i

# Cover
Scene: <封面画面描述。Mia + Tommy 必须出现。上方 35% 留白做标题安全区。中英均可>
Shot: medium

# Page 1
Text: <英文台词。L0:≤3词 / L1:≤5词 / L2:≤7词 / L3:≤9词 / L4:≤15词 / L5:≤18词 / L6:≤25词>
Scene: <场景。次要角色用反例句明确身份，如 "two adult Scotsmen (NOT children, NOT Mia, NOT Tommy)">
Expression: <情绪短语，可省略，系统会从 Text 自动推断>
Shot: <close | medium | full | wide，可省略，默认 medium>
Text_Position: top-left

# Page 2
Text: 
Scene: 
Expression: 
Shot: 
Text_Position: top-right

# Page 3
Text: 
Scene: 
Expression: 
Shot: 
Text_Position: bottom-right

# Page 4
Text: 
Scene: 
Expression: 
Shot: 
Text_Position: top-right

# Page 5
Text: 
Scene: 
Expression: 
Shot: 
Text_Position: top-right

# Page 6
Text: 
Scene: 
Expression: 
Shot: 
Text_Position: top-left

# Page 7
Text: 
Scene: 
Expression: 
Shot: 
Text_Position: top-right

# ────────────────────────────────────────────
# 写作 checklist（提交前自查）
# 1. Page 数严格 = 7 个（+ 1 个 Cover = 8 块）
# 2. 单页人物 ≤ 4 个（含次要角色）
# 3. 次要角色出场必须写反例句 "NOT a child / NOT Mia / NOT Tommy"
# 4. 不想要爸妈出现的页面，scene 里不写 mom / dad / family
# 5. Text_Position 4 个角分散使用，避免连续两页同位置
# 6. Vocabulary 词数：L0-3 双行(M+E) / L4-6 单行(4-6词)
# 7. 词数按 Level 上限严格控制
#
# ── Shot 字段速查（v1.1 新增）──
#   close   主角头肩占画面 60-75%   情绪近景（开心/惊讶/担忧/感动）
#   medium  主角占 55-65%         ⭐默认。找东西、对话、看物体、互动
#   full    全身可见，占 45-55%    跳舞、奔跑、挥手告别、合影
#   wide    主角占 30-40%         地标全景（城堡、海边、广场）
#   留空则用 medium，绝不会让人物缩到画面 30% 以下
# ────────────────────────────────────────────
