# 绘本自动化流水线

> 输入：一份 9 页 Markdown 大纲
> 输出：1 个 9 页 PPT + 8 张水彩插画 + 8 个 prompt 存档

## 一、整体数据流

```mermaid
flowchart TD
    A[inputs/LX_BookNN_Title.md<br/>Markdown 大纲] -->|parser.py| B[BookOutline<br/>title · level · ip_age · pages 8]
    B -->|config.py<br/>resolve_ip_age| C[ip_age 8/10/12]
    B --> D{每页 PageSpec}
    C --> D
    D -->|prompt_builder.py| E[BuiltPrompt<br/>prompt 字符串<br/>references 1-4 张]
    E -->|seedream_client.py| F["生图(按 level 分流):<br/>L3-6 = gpt-image-2(imarouter)<br/>L0-2 = 即梦4.6(Ark)出图 + GPT修图双段"]
    F --> G[outputs/slug/images/page_NN.png]
    E --> H[outputs/slug/prompts/page_NN_prompt.txt]
    G -->|ppt_builder.py| I[9 页 PPT<br/>封面 + 7 故事 + 元信息]
    I --> J[outputs/slug/Title.pptx]
    B --> I
```

## 二、Prompt 拼装结构

```mermaid
flowchart LR
    subgraph 头部 受保护
        S[STYLE_BIBLE<br/>干净水彩基线]
        M[IP Block Mia<br/>按 8/10/12 选]
        T[IP Block Tommy<br/>按 8/10/12 选]
        P[PARENTS_BLOCK<br/>检测到才加]
        EX[Expression<br/>按页情绪]
    end
    subgraph 中段 可压缩
        SC[Scene<br/>大纲填写]
        CV[Cover Layout<br/>仅封面页]
    end
    subgraph 尾部 受保护
        TL[留白 + 一致性指令<br/>含 corner 位置]
    end
    S --> M --> T --> P --> EX --> SC --> CV --> TL
    OUT[最终 prompt ≤1500 字符]
    TL --> OUT
```

* 头部 + 尾部固定不能被截
* 仅中段 (`Scene + Cover Layout`) 超长时被 `...` 截尾

## 三、参考图收集策略

```mermaid
flowchart TD
    R{ip_age?}
    R -- 8 --> B1[character_bible_l0-3.png 占位]
    R -- 10 --> B2[character_bible_l4-5.png 或<br/>character_bible_l4-6.png 兜底]
    R -- 12 --> B3[character_bible_l6.png 或<br/>character_bible_l4-6.png 兜底]
    B1 & B2 & B3 --> ST[+ clean_watercolor_reference.png<br/>风格干净基线]
    ST --> PA{该页有 parents?}
    PA -- 是 --> PR[+ parents_reference.png]
    PA -- 否 --> SKIP[skip]
    PR & SKIP --> M[最多 4 张 references]
    M --> API["image2image: L3-6=gpt-image-2 / L0-2=即梦4.6+GPT修图"]
```

## 四、9 页 PPT 几何

```
+------------------------------------------------+ 10.0 in
|  Title 居中靠上            Lv X / Book N 橙胶囊 |     ↑
|                                                |
|                  全幅插画 (full-bleed)           |
|                                                |     7.5 in
|         [文字框 40% 宽 落留白角]                  |
|                                                |
|  页码圆 (偶数页 左下 / 奇数页 右下)                 |     ↓
+------------------------------------------------+

P1 封面     | 标题 + Level/Book 双胶囊 + 全幅图
P2-P8 故事  | 全幅图 + 文字框落 Text_Position 指定角 + 页码
P9 元信息   | Level / Book / CEFR / Lexile / Word count / Vocabulary
```

## 五、模块职责

| 文件 | 职责 | 关键产物 |
|---|---|---|
| `config.py` | 路径、API、IP 年龄映射、PPT 几何与字体 | `LEVEL_TO_AGE_DEFAULT`、`IMAGE_SIZE` |
| `parser.py` | Markdown → `BookOutline` (含 8 个 `PageSpec`) | 支持 `Text / Scene / Text_Position / Expression` 字段 |
| `prompt_builder.py` | 拼装单页 prompt + 收集参考图 | `BuiltPrompt(prompt, references)` |
| `seedream_client.py` | 按 level 分流：gpt-image-2(imarouter 异步) / 即梦4.6(Ark 同步)出图+GPT修图双段 + 重试 + 占位图降级 | PNG 落盘 |
| `ppt_builder.py` | 组装 9 页 PPT，Poppins Bold + 橙徽章 + 页码 | `*.pptx` |
| `run.py` | CLI 入口，串起所有步骤 | 控制台日志 + 输出目录 |

## 六、大纲字段对照

```mermaid
flowchart LR
    O[outline.md] --> M1[Title]
    O --> M2[Level + Book]
    O --> M3[CEFR + Lexile]
    O --> M4[Word_count 可选]
    O --> M5[IP_Age 可选<br/>覆盖默认]
    O --> M6[Vocabulary<br/>单行 或<br/>Mastery+Exposure 双行]
    O --> M7[# Cover<br/>Scene:]
    O --> M8["# Page 1..7<br/>Text:<br/>Scene:<br/>Expression: 可选<br/>Text_Position: 可选"]
```

## 七、Level → IP 年龄映射

| Level | IP 年龄 | 形象 |
|---|---|---|
| L0 – L3 | 8 岁 | Mia 紫T+牛仔 / Tommy 蓝白条纹T+牛仔 |
| L4 – L5 | 10 岁 | Mia 淡紫卫衣+灰运动裤 / Tommy 浅蓝卫衣+卡其 |
| L6 | 12 岁 | Mia 淡紫上衣+白阔腿裤 / Tommy 深蓝 polo+蓝牛仔 |

可在大纲里写 `IP_Age: N` 覆盖默认。

## 八、运行方式

```mermaid
flowchart LR
    L[本地 CLI] -->|python scripts/run.py -i ...| OUT1[outputs/]
    G[GitHub Actions<br/>workflow_dispatch] -->|secrets.ARK_API_KEY| OUT2[Artifact zip]
    L & G -.同代码同输出.-> SAME[一致的 PPT + 图]
```

## 九、扩展点

* **新书** = 加一份 `inputs/LX_BookNN_Title.md`，命令行换路径即可
* **新年龄档**：在 `IP_BLOCKS` 加 `(name, age)` 键、放 `character_bible_lX.png`
* **新版式**：改 `ppt_builder.py` 的 `_build_cover / _build_story / _build_metadata`
* **换底层模型**：改 `seedream_client.py` 的 `generate_image` + `config.JIMENG_MODEL`
