# 绘本制作工作流 - 今日沉淀（2026-05-27）

> 这份文档总结了今天调试 **L5 Book01「What Makes a Good Friend?」** 期间发现的关键问题、解决方案、以及后续制作绘本时**必须遵守的规则**。每次跑新书前请先复习这份文档。

---

## 一、最重要的代码层 Bug Fix（影响所有书）

### 1. 参考图自相矛盾的污染问题

**现象**：Mia 在不同页面发型飘忽（一会高马尾、一会散发、一会低马尾）。

**根因**：`character_bible_l4-6_clean.png` 这张多角色合体设定图里，Mia 的 4 个视角（正面/3-4/侧面/背面）发型并不一致 —— 正面看像散发，侧面才是清晰的高马尾。当模型同时收到这张 bible **和** 单独的 `mia_age12.png` 作为参考时，会在两张图之间做线性插值，结果发型在每一页都不稳定。

**修复**（`scripts/prompt_builder.py`：`_collect_references_v2`）：
> 当 Mia 和 Tommy 各自都已有对应年龄档的专属设定图（`mia_age{N}.png` / `tommy_age{N}.png`）时，**跳过 bible 兜底**，避免参考图自相矛盾。

```python
needs_bible = (cast["mia"] and not mia_individual_ok) or (cast["tommy"] and not tommy_individual_ok)
if needs_bible:
    bible = _select_character_bible(ip_age)
    if bible:
        refs.append(bible)
```

### 2. Prompt 长度限制截断了关键身份描述

**现象**：Page 7 模型把 Tommy 渲染成穿黄色毛衣（和 Anna 同色）。

**根因**：单页 prompt 超过 2000 字符上限时，截断逻辑会把 mid（场景描述）整块或部分截掉，但保留 anchor（角色身份）。但当 anchor 本身就很长（Custom_Anna + Mia + Tommy 全文），剩下的预算不够装下完整 scene，截断后只剩下 Tommy 的开头描述、丢掉 Mia 的详细描述，模型就开始乱套。

**修复**：
- 上限从 2000 提到 **4000** 字符
- 截断优先级：anchor > tail > lock > mid，**anchor 永远完整保留**
- 单页 scene 字数控制在 **1500 字以内**，把"必现要素"压在最前面

---

## 二、Prompt 写作必守规则

### A. 角色名字必须出现在 scene 文本里

**为什么**：`prompt_builder.detect_cast()` 是靠扫描 scene 文本里的 `Anna` / `Mia` / `Tommy` 关键词来决定挂哪些 IP 锚和参考图。**只要名字一去掉，IP 锚就空，模型立刻乱画**。

✅ 正确："In a classroom, Anna sits next to Tommy, sharing pencils."
❌ 错误："In a classroom, the girl sits next to the boy, sharing pencils."（IP 没挂上）

### B. 但绝对不要用英文引号

**为什么**：模型会把引号内的英文短语**直接画进图里**当成文字水印。

✅ 正确：`Anna asked questions about pets and games`
❌ 错误：`Anna said, "Tell me more," and asked about "pets and games"` → 图上会出现 "Tell me more" 和 "pets and games" 文字

### C. 必加负面词

每页 scene 末尾必须加：
> `ABSOLUTELY NO English words, NO letters, NO names, NO captions, NO labels of any kind anywhere in the image`

### D. 强调关键道具时把它放在 scene 第一句

**为什么**：模型对 scene 开头的内容关注度最高。要求"递铅笔/胶水"这种交互动作时，把 `The CENTRAL VISIBLE ACTION of this image is …` 写在最前面，并明确说**道具是空中可见的**。

### E. 多人同框时避免身体接触

**为什么**：当 Tommy 的"手臂搭在 Anna 肩上"时，模型会把两人的服装混色（让 Tommy 也穿黄毛衣）。

✅ 正确：三人之间留出**明显间距**，各自独立动作
❌ 错误：手臂搭肩、抱在一起、紧贴

### F. 不要用"列表式"描述位置

**为什么**：写成 `From LEFT to RIGHT: (1) Mia; (2) Anna; (3) Tommy` 时模型经常**乱序**，比如把 Anna 画到了左边。

✅ 更可靠：把 Anna 当主角放中间，配角分两边，并描述**他们之间的互动方向**（"Anna sitting between Mia and Tommy, turned to face Mia on her left"）

### G. 圆形/三角形构图比"板凳一字排开"更能体现"在讨论"

板凳一字排开 → 模型默认画三个人面朝镜头微笑（看不出在聊天）
草地三角形圈状 → 模型自动给出身体朝向对方、手势动作

---

## 三、Anna（Custom IP）必守规则

Anna 是 **L5 Book01 的独立 IP**，不能继承 Mia 的视觉。她的 HAIR RULE LOCK 已写死在 outline 的 `Custom_Anna:` 字段：

- **EXACTLY 2 LOW pigtails**（不是 3 个、不是 1 个、不是高马尾）
- 辫子位置：耳垂以下（NOT 颞部、NOT 耳侧、NOT 头顶）
- 长度：下垂至下巴-肩线之间
- 红色发圈
- 黑色头发 + 齐刘海
- 服装：芥黄色长袖纽扣开衫 + 白色 T 恤 + 白色宽松裤

**Scene 描述里如果场景涉及 Anna，必须用「Anna」这个名字**才能挂上她的 Custom IP 锚。

---

## 四、Mia 高马尾的视角理解（今天用户最后强调的点）

新的 Dino L4-6 参考图清楚展示了：

| 视角 | Mia 的发型呈现 |
|---|---|
| 正面 | 你看到刘海 + 脸两侧少量碎发，但**长发全在脑后绑起来**，正面看不到马尾尾巴 |
| 3-4 视角 | 头顶绑起来的位置已经可见，能看到马尾的一部分 |
| 侧面 | 高马尾**清清楚楚**绑在脑后顶部，发尾流下 |
| 背面 | 整条高马尾完整可见，从脑后顶部一直垂到肩下 |

**模型常犯的错**：以为 Mia 是散发，把长发画成两边垂在脸前面。**正确画法**：长发**全在脑后**绑起来，正面看脸两侧只有少量碎发框脸，头顶有发束被绑起来的轮廓。

Mia COMPACT IP 块（`prompt_builder.py` 第 126 行）已更新这条规则。

---

## 五、Vocabulary 规则（L3+）

**从 L3 开始**：元信息页**只显示 Mastery 词汇**，不再渲染 `Exposure:` 行。

- L1-L2：保留 Mastery + Exposure 两行
- L3+：删除 outline 里的 `Vocabulary_Exposure:` 字段，元信息页自动只显示 Mastery 这一行

修改点：`scripts/ppt_builder.py`：
```python
if level_num >= 3:
    line(", ".join(outline.vocabulary_mastery) or "-", head=False, indent=1)
elif outline.has_double_vocab:
    # L1-L2 双行
    ...
```

---

## 六、PPT 制作标准（与「绘本制作规范 v1.0」对齐）

- **总页数**：必须是 4 的倍数（封面 + 7 故事 + 元信息 = 9 页）
- **字体**：Poppins SemiBold（标题 40pt，正文 20-24pt）
- **页码**：正文第 2 页起，左下/右下交替
- **图片比例**：4:3，2304x1728 最低分辨率
- **画风**：温暖治愈水彩儿童绘本风格，低饱和度，柔和晕染，圆润线条

---

## 七、新书 onboarding 清单（每本必跑）

1. [ ] outline 已写好 `Title / Level / Book / CEFR / Lexile / IP_Age / Vocabulary_Mastery`
2. [ ] L1-L2 才加 `Vocabulary_Exposure`，L3+ 不加
3. [ ] 出现新主角 → 加 `Custom_<Name>:` 字段，详细写头发/服装/年龄锁
4. [ ] 新主角需要 `assets/characters/<Name>_age{N}.png` 参考图
5. [ ] 每页 scene 控制在 1500 字以内，必现要素放最前
6. [ ] scene 里 Anna/Mia/Tommy 名字至少出现一次（挂 IP 锚）
7. [ ] 不要用英文引号包短语（避免被画成图上文字）
8. [ ] 多人同框时不让角色身体接触
9. [ ] 跑完后比对图片：服装颜色、发型、配角数量

---

## 八、今天彻底学到的「不踩坑」反面教材

| 翻车场景 | 教训 |
|---|---|
| Anna 渲染成 Mia（高马尾紫衣） | 必须有 `Custom_Anna:` 字段 + 单独的 `anna_age12.png` 参考图 + 名字在 scene 里 |
| 图上出现"Mia"和"pets and games"文字 | 不要在 scene 里用英文引号、也不要孤立的人名作 caption |
| Tommy 穿成黄毛衣 | 不让 Tommy 的身体和 Anna 接触；scene 长度控在 4000 字以内防截断 |
| Page 5 板凳上三人不像在聊天 | 改成草地三角形圈状，身体朝向对方 |
| 仓鼠太大 | 明确写 "TINY palm-sized" + "takes up 10-15% of frame" + "child is dominant subject taking 50-60% of frame" |
| Anna 一会 3 辫子一会 2 辫子 | Custom_Anna 里写死 "EXACTLY 2 pigtails, NOT 3, NOT 1, NOT a single ponytail" |
| Mia 一会高马尾一会散发 | **关键 fix**：跳过 bible 兜底参考图（自相矛盾），只用单独的 `mia_age12.png` |
| Tommy 表情忧伤 | Expression 字段写明 "BIG OPEN LAUGHING HAPPY SMILE, definitely NOT sad, NOT frowning" |
| 饼干画了 7 片不是 4 片 | 模型对数量描述不敏感，能接受 ±2 偏差，过分追求精确数字反而不划算 |

