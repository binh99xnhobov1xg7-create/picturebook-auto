# 绘本制作标准 v1.0（L0–L6 统一规范）

> **冻结基线**：本规范以 2026-05-26 完整跑通的 **L4 Visiting Scotland** 流程为蓝本。
> 所有 Level 0 ～ Level 6 的英文启蒙绘本**必须**遵守本规范。

---

## 0. 一句话总览

> 输入「Level + 第几本 + 7 句英文台词 + 每页场景描述」
> → 自动按 Level 适配 IP 年龄/语言/词表
> → 即梦 4.6 (Doubao-Seedream-4.5) 生 8 张 4:3 水彩
> → 拼装 9 页 PPT（封面 1 + 故事 7 + 元信息 1）
>
> **整套版式、字体、颜色、页码、留白、画风、IP，全 Level 100% 一致。**

---

## 1. 不可变规则（所有 Level 共享）

### 1.1 PPT 版式

| 项 | 值 | 备注 |
|---|---|---|
| 总页数 | **9 页** | 封面 1 + 故事 7 + 元信息 1 |
| 幅面 | **10.0 × 7.5 in（4:3）** | `prs.slide_width / slide_height` |
| 字体 | **Poppins SemiBold** | 全篇统一，需本地安装（见 `INSTALL_FONT.txt`） |
| 字号 | 标题 **40pt（固定）** / 徽章 16pt / 正文 **22pt（20–24 区间，长文取 20，短文取 24）** / 页码 14pt / 元信息 18+16pt |
| 颜色 | 橙胶囊 `#F47332` / 黑字 `#121212` / 白底 `#FFFFFF` |

### 1.2 封面（page 1）

* 全幅插画铺底
* **书名**居中靠上，黑色 Poppins SemiBold 40pt
* **右上双胶囊**：「Level X」「Book NN」橙底白字黑边 16pt
* 上方 35% 必须为浅天空 / 留白（给标题安全区）

### 1.3 故事页（page 2–8）

* 全幅插画铺底
* 文字框：白底矩形，宽 = 页宽 40%，落在画面留白角
  * `Text_Position`：`top-left / top-right / bottom-left / bottom-right`
* 文字框内：英文台词，Poppins SemiBold 22pt（20–24 区间），黑色
* **页码圆**：白底黑字圆 0.55 in
  * **偶数页 → 左下** / **奇数页 → 右下**
  * 与底/侧边距各 0.30 in

### 1.4 元信息页（page 9）

左侧大黑边白底矩形（6 × 6 in），内含 6 项：

```
Level: X
Book: NN
CEFR: XX
Lexile: XXXL-XXXL
Word count: N
Vocabulary:
  Mastery: …, …, …      (低级别双行模式)
  Exposure: …, …, …
  或：a, b, c, d           (高级别单行模式)
```

### 1.5 画风（**所有 Level 强制相同**）

* 模型：火山引擎 **Doubao-Seedream-4.5**（即梦 4.6）
* 模型 ID：`doubao-seedream-4-5-251128`（在 `.env` 用 `JIMENG_MODEL` 覆盖）
* 尺寸：**2304 × 1728（4:3）**（最低 3.69M 像素门槛）
* 风格关键词（写入 prompt 头部）：
  ```
  Clean watercolor children's book illustration,
  smooth even wash, flat soft color, gentle gradient,
  minimal background detail, no mottled patches,
  no scattered noise, no harsh shadow, rounded smooth lines, 4:3 horizontal
  ```
* 风格参考图：`assets/style/clean_watercolor_reference.png` 自动挂载

### 1.6 留白

* 故事页：刻意预留 **10–15%** 角落留白，用于覆盖文字框
* 封面：上方 35% 留白，用于覆盖书名
* prompt 尾部强制声明：`Reserve X%-Y% clean blank area at <corner>`

### 1.7 IP 一致性强制条款

* Mia 永远 = 紫色系上衣 + 长棕马尾
* Tommy 永远 = 浅蓝系上衣 + 短棕发（**禁止马尾、禁止长发**）
* Mom 永远 = 长棕波浪发 + 奶白长袖上衣 + 蓝牛仔
* Dad 永远 = 短棕发 + 灰色 polo + 卡其裤
* 任何页面出现这 4 人 ⇒ 必须挂 `character_bible_l*-*.png`（自动）+ `parents_reference.png`（仅有父母出场时）

---

## 2. 按 Level 自动适配（**只这一项随级别变**）

### 2.1 Level → IP 年龄

| Level | IP 年龄 | Mia 套装 | Tommy 套装 | 人物设定大表 |
|---|---|---|---|---|
| L0 – L3 | **8 岁** | 紫短袖 T + 牛仔 + 白鞋 | 蓝白条纹 T + 牛仔 + 白鞋 | `character_bible_l0-3.png` |
| L4 – L5 | **10 岁** | 淡紫长袖卫衣 + 灰运动裤 | 浅蓝卫衣 + 卡其直筒裤 | `character_bible_l4-5.png` 或 `character_bible_l4-6.png` |
| L6 | **12 岁** | 淡紫毛衣 + 白阔腿裤 | 深蓝 polo + 浅蓝牛仔 | `character_bible_l6.png` 或 `character_bible_l4-6.png` |

* 大纲里写 `IP_Age: N` 可覆盖默认
* 代码位置：`scripts/config.py` 的 `LEVEL_TO_AGE_DEFAULT`

### 2.2 Level → 语言难度

| Level | CEFR | Lexile | 每页词数 | 每页句数 | 词汇配置 | 总词数目标 |
|---|---|---|---|---|---|---|
| L0 | Pre-A1 | BR-100L | ≤ 3 | 1 | Mastery + Exposure 双行 (3+5) | ≤ 25 |
| L1 | Pre-A1 | BR-200L | ≤ 5 | 1 | Mastery + Exposure 双行 (4+6) | ≤ 35 |
| L2 | A1 | 100L-300L | ≤ 7 | 1–2 | Mastery + Exposure 双行 (5+7) | ≤ 50 |
| L3 | A1 | 200L-400L | ≤ 9 | 1–2 | Mastery + Exposure 双行 (5+7) | ≤ 65 |
| L4 | A2 | 410L-600L | ≤ 15 | 1–2 | Vocabulary 单行 (4 词) | ≤ 100 |
| L5 | A2-B1 | 500L-700L | ≤ 18 | 2 | Vocabulary 单行 (5 词) | ≤ 130 |
| L6 | B1 | 600L-800L | ≤ 25 | 2–3 | Vocabulary 单行 (6 词) | ≤ 180 |

> 系统不强制校验词数，但 prompt builder 会根据 `CEFR` / `Lexile` 调整画面复杂度（未来版本）。

### 2.3 词汇展示规则

* **低级别（L0–L3）**：元信息页两行，第一行 Mastery，第二行 Exposure
  ```
  Vocabulary:
    Mastery: a, b, c
    Exposure: d, e, f, g
  ```
* **高级别（L4–L6）**：元信息页一行
  ```
  Vocabulary: a, b, c, d
  ```
* 大纲对应字段：
  * 双行：`Vocabulary_Mastery:` + `Vocabulary_Exposure:`
  * 单行：`Vocabulary:`

---

## 3. Prompt 拼装结构（所有 Level 共用）

### 3.1 五段式（按顺序）

```
[1] STYLE_BIBLE          头部·受保护  ← 干净水彩基线
[2] IP Block × N         头部·受保护  ← 按 ip_age 选 8/10/12
[3] PARENTS_BLOCK        头部·受保护  ← 仅检测到 mom/dad/family 时
[4] Expression           头部·受保护  ← 每页情绪
[5] Scene + Cover Layout 中段·可压缩  ← 大纲场景描述
[6] STYLE_TAIL           尾部·受保护  ← 留白 + 一致性强制 + 禁文字
```

* 总长度上限 **1500 字符**
* 超长时只截中段（scene），头部和尾部永不被截
* 代码位置：`scripts/prompt_builder.py:build_page_prompt`

### 3.2 IP 描述强化（防止性别串号）

```
Mia: 10y GIRL with long brown high ponytail tied behind, ...
Tommy: 10y BOY (NOT a girl, NO ponytail, never long hair) with short messy brown hair, ...
```

* 必须显式标 `GIRL` / `BOY`
* Tommy 必须显式禁止 `ponytail` / `long hair`

### 3.3 参考图优先级（即梦上限 4 张）

| 优先级 | 文件 | 何时挂载 |
|---|---|---|
| 1 | `character_bible_l*-*.png` | 主 IP 出现（**绝不丢**） |
| 2 | `parents_reference.png` | 显式 mom/dad/family（**绝不丢**） |
| 3 | 次要角色参考图 | 关键词命中（kilt / scotsman / bagpipes / sheep / shepherd…） |
| 4 | `clean_watercolor_reference.png` | 风格兜底（满 4 张时被挤掉） |

### 3.4 次要角色关键词触发表

| 关键词（正则） | 自动挂载 |
|---|---|
| `\bkilt\b` `\bscotsman\b` `\bbagpip\w*\b` | `kilt_men_reference.png` |
| `\bsheep\b` | `sheep_reference.png` |
| `\bshepherd\b` | `shepherd_reference.png` |

> 添加新次要角色：在 `assets/characters/` 放图 + 在 `scripts/prompt_builder.py:SECONDARY_CHAR_REFS` 加一行

### 3.5 表情自动推断

如果大纲 `Expression:` 留空，按页内文本关键词自动推断：

| 文本关键词 | 自动表情 |
|---|---|
| excit | excited bright eyes, open joyful smile |
| amaz / surpr | amazed wide eyes, open mouth in wonder |
| worry | worried furrowed brows, tight mouth, anxious eyes |
| happy / curio / relie / grate / unfor | 对应表情短语（详见代码） |

---

## 4. 多人物场景硬性约束

> 这一节是今天 Visiting Scotland 折腾出来的血泪经验。

### 4.1 单页人物上限

* **每页同框人物 ≤ 4 个**（含次要角色）
* 5+ 人物 → 模型会丢角色或把次要角色克隆成主角

### 4.2 次要角色出场写法

* 必须用**反例句**：
  ```
  ... TWO adult Scotsmen (mature adult men, NOT children, NOT Mia, NOT Tommy, 
  completely different from the kids, wearing tartan kilt) ...
  ```
* 推荐使用 LEFT/RIGHT 分区结构：
  ```
  LEFT SIDE: Mia and Tommy waving.
  RIGHT SIDE: Two adult Scotsmen in kilts waving back.
  ```

### 4.3 当次要角色与 Mia/Tommy 强冲突时

* **必须**：把次要角色参考图先用 PIL 裁掉任何 Mia/Tommy 元素
* 单独保存为 `<role>_reference.png`
* 关键词触发自动挂载

### 4.4 父母自动检测词表

```
mom, mum, dad, parent, mother, father, family
```

* **代词 they / their / them 不算父母出场**（避免误挂参考图挤掉次要角色）
* 不想要父母出现的页面，scene 描述中**不要**出现上述词

---

## 5. 输入：大纲文件格式

文件名规范：`LX_BookNN_Title_With_Underscores.md`，放在 `inputs/`。

### 5.1 元信息头

```markdown
Title: Visiting Scotland
Level: 4
Book: 13
CEFR: A2
Lexile: 410L-600L
IP_Age: 10                          # 可选，覆盖默认
Vocabulary: culture, castle, bagpipes, journey
# 或低级别用：
# Vocabulary_Mastery: I, like, my, dad
# Vocabulary_Exposure: love, happy, home, family, smile, hug
```

### 5.2 封面块

```markdown
# Cover
Scene: <封面画面描述，可中可英>
```

### 5.3 故事页块（共 7 个）

```markdown
# Page N
Text: <英文台词，按 Level 控制词数>
Scene: <场景描述，重要次要角色用反例句标注>
Expression: <情绪短语，可省略>
Text_Position: top-left | top-right | bottom-left | bottom-right
```

完整范例见 `inputs/L4_Book13_Visiting_Scotland.md`。

---

## 6. 目录结构（每本书产出）

```
outputs/
└── <slug>/                            # 由书名生成的 slug
    ├── images/
    │   ├── page_00.png                # 封面
    │   ├── page_01.png ... page_07.png # 7 个故事页
    │   └── ...
    ├── prompts/
    │   └── page_NN_prompt.txt         # 8 个 prompt 存档
    ├── <Book_Title>.pptx              # 9 页 PPT
    └── README.txt                     # 本次生成元信息
```

---

## 7. 资产目录（assets/）

```
assets/
├── characters/
│   ├── character_bible_l0-3.png       # ⚠️ 待补
│   ├── character_bible_l4-5.png       # 或共用 l4-6
│   ├── character_bible_l4-6.png       # 当前使用
│   ├── character_bible_l6.png         # ⚠️ 待补
│   ├── parents_reference.png
│   ├── kilt_men_reference.png         # 苏格兰人（已裁去 Mia/Tommy）
│   ├── mia_age8/10/12.png             # 备用单角色图
│   └── tommy_age8/10/12.png
└── style/
    ├── clean_watercolor_reference.png # 当前风格基线
    └── watercolor_style_sheet.png     # 备用
```

---

## 8. 工作流

### 8.1 本地运行

```powershell
cd C:\Users\Jered\picturebook-auto
.\.venv\Scripts\Activate.ps1
python scripts\run.py --outline inputs\L4_Book13_Visiting_Scotland.md --real-images
```

某页效果不佳，只重出该页：
```powershell
python scripts\run.py -i inputs\L4_Book13_Visiting_Scotland.md --real-images --pages 5,7
```

调试版式（占位图，秒出）：
```powershell
python scripts\run.py -i inputs\L4_Book13_Visiting_Scotland.md --mock-images
```

### 8.2 GitHub Actions

1. Settings → Secrets → Actions → New secret
   * Name: `ARK_API_KEY`
   * Value: 你的火山方舟 Key
2. Actions → "Build Picture Book" → Run workflow → 填大纲文件名 + `mock_images=false`
3. 完成后下方 Artifacts 下载 zip

工作流文件：`.github/workflows/build_book.yml`

---

## 9. 新书 5 步法

1. **复制模板**：`cp inputs/TEMPLATE_OUTLINE.md inputs/LX_BookNN_<Title>.md`
2. **改头部**：Title / Level / Book / CEFR / Lexile / Vocabulary
3. **填 8 页**：1 个 Cover + 7 个 Page，每页给 Text + Scene（可加 Expression / Text_Position）
4. **跑流水线**：`python scripts\run.py -i inputs\LX_BookNN_<Title>.md --real-images`
5. **打开 PPT 校对**：按 `CHECKLIST.md` 逐项打勾，不达标的页用 `--pages N` 单独重出

---

## 10. 已知限制 + 工程对策

| 限制 | 触发条件 | 对策 |
|---|---|---|
| 手指畸形 / 多手 | 任何复杂动作页 | 场景描述避免 close-up of hands；prompt 加 "natural human hands"；接受 1–2 页轻微瑕疵 |
| 次要角色被克隆成 Mia/Tommy | 单页 ≥ 5 人物 + 强 IP 锚 | 减人 + 裁干净次要参考图 + 反例句 |
| 模型把"reserved for title"理解成画上书名 | 封面 prompt 提到 title | 改为"clean empty sky area + ABSOLUTELY NO TEXT" |
| 文字 / 字母被画到图里 | 任何页面 | tail 强制 `no text, no letters, no watermarks` |
| 单张图最低像素门槛 | < 3.69M px | 用 ≥ 2304×1728 |
| 服装跑色（Tommy 变紫 / Mia 变蓝） | 角色描述不够明显 | IP block 用大写 `GIRL` / `BOY` + 反例 `NOT a girl` |

---

## 11. 与原 v1.0 规范的对照

| 规则 | 原 v1.0 | 当前标准 v1.0 | 说明 |
|---|---|---|---|
| 总页数 4 的倍数 | 要求 | 当前 9 页（非 4 倍） | 包含元信息页；如需 12 页可加封底/空白页/词汇页，目前不强制 |
| Mia 紫上衣 | ✓ | ✓ | |
| Tommy 蓝上衣 | ✓ | ✓ | |
| 即梦 4.6 水彩 | ✓ | ✓ | 模型 ID `doubao-seedream-4-5-251128` |
| 文字留白 | ✓ | ✓ 10–15% | |
| 句式重复 | 推荐 | 大纲填写责任 | 系统不强制 |
| 页码左右下交替 | ✓ | ✓ 偶左/奇右 | |

---

## 12. 规范版本与更新

* **v1.0** 2026-05-26 ——以 L4 Visiting Scotland 完整跑通为基线冻结
* 未来变更：必须先在 `STANDARD.md` 提案 → 跑测试本验证 → 合并

---

## 附录 A：今天验收的 L4 Visiting Scotland 8 张图清单

| 页 | 关键场景 | 评分 | 备注 |
|---|---|---|---|
| Cover | 老街看地图 | A+ | 零文字渗漏，留白完美 |
| 1 | 一家走街上 | A | 兴奋表情 |
| 2 | 仰望湖边古堡 | A | wonder 表情 |
| 3 | 风笛手 | A | 好奇围观 |
| 4 | kilt 起舞 | A | 苏格兰人动感 |
| 5 | 羊叼地图 | A | 担忧追逐 |
| 6 | 祖母递地图 | A− | 茶具被换成锅，IP 一致 |
| 7 | 山地告别苏格兰人 | A | 两位 kilt 苏格兰人挥手 |
