# picturebook-auto

英文启蒙绘本自动化流水线：**Markdown 大纲 → 即梦 4.6 / Doubao-Seedream-4.5 生 8 张水彩图 → 拼装 9 页 PPT**。

> **基线**：以 2026-05-26 完整跑通的 L4《Visiting Scotland》流程为冻结基线。
> **标准**：所有 L0–L6 必须遵守 [`STANDARD.md`](STANDARD.md)。

---

## 必读文档（按顺序）

| 文档 | 用途 |
|---|---|
| [`STANDARD.md`](STANDARD.md) | **核心规范**——版式、字体、画风、IP、prompt、Level 适配 |
| [`PIPELINE.md`](PIPELINE.md) | 流程图与模块职责 |
| [`CHECKLIST.md`](CHECKLIST.md) | 出书验收单 |
| [`inputs/TEMPLATE_OUTLINE.md`](inputs/TEMPLATE_OUTLINE.md) | 新书大纲模板 |
| [`INSTALL_FONT.txt`](INSTALL_FONT.txt) | 字体安装（Poppins SemiBold） |

---

## 5 步出一本书

1. 复制模板：`cp inputs/TEMPLATE_OUTLINE.md inputs/LX_BookNN_<Title>.md`
2. 改头部 + 填 7 页 Text/Scene
3. 跑：`python scripts\run.py -i inputs\LX_BookNN_<Title>.md --real-images`
4. 打开 PPT 按 `CHECKLIST.md` 自查
5. 不达标的页用 `--pages N` 重出

---

## 仓库结构

```
picturebook-auto/
├── STANDARD.md                       # ⭐ 标准规范
├── PIPELINE.md                       # 流程图
├── CHECKLIST.md                      # 验收单
├── README.md                         # 本文件
├── INSTALL_FONT.txt                  # Poppins SemiBold 安装
├── requirements.txt
├── .env.example
├── inputs/
│   ├── TEMPLATE_OUTLINE.md           # 新书模板
│   └── L4_Book13_Visiting_Scotland.md # 冻结基线样本
├── outputs/<slug>/                   # 每本一个子目录
│   ├── images/page_00..07.png
│   ├── prompts/page_NN_prompt.txt
│   └── <Title>.pptx
├── assets/
│   ├── characters/
│   │   ├── character_bible_l4-6.png  # 10/12 岁 IP 大表
│   │   ├── parents_reference.png
│   │   ├── kilt_men_reference.png    # 次要角色（已裁干净）
│   │   └── ...
│   └── style/
│       └── clean_watercolor_reference.png
├── scripts/
│   ├── config.py                     # 路径/API/Level→Age/字体几何
│   ├── parser.py                     # outline.md → BookOutline
│   ├── prompt_builder.py             # 五段式 prompt + 参考图
│   ├── seedream_client.py            # Doubao-Seedream-4.5
│   ├── ppt_builder.py                # 9 页 PPT，Poppins SemiBold
│   ├── run.py                        # 入口
│   └── check_pptx.py                 # 验证用
└── .github/workflows/
    └── build_book.yml                # workflow_dispatch 手动触发
```

---

## 本地运行

```powershell
cd C:\Users\Jered\picturebook-auto
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 配置 API
Copy-Item .env.example .env
# 编辑 .env，填 ARK_API_KEY=...

# 跑流水线
python scripts\run.py --outline inputs\L4_Book13_Visiting_Scotland.md --real-images
```

## CLI 选项

| 参数 | 作用 |
|---|---|
| `-i, --outline` | 大纲文件路径（必填） |
| `-o, --output` | 输出目录（默认 `outputs/<slug>/`） |
| `--real-images` | 强制调即梦 API 真实生图 |
| `--mock-images` | 占位图模式（秒出，调试版式用） |
| `--pages 0,4,5` | 仅重生指定页，其余沿用已有 png |
| `--no-images` | 完全跳过生图，只重组 PPT（改字体/版式后用） |

---

## GitHub Actions

1. 仓库 push 到 GitHub
2. Settings → Secrets → Actions → New: `ARK_API_KEY` = 火山方舟 Key
3. Actions → "Build Picture Book" → Run workflow → 填大纲文件名 + `mock_images=false`
4. 完成后下方 Artifacts 下载 zip

---

## PPT 版式快览

* 9 页：1 封面 + 7 故事 + 1 元信息
* 字体：Poppins SemiBold（全书统一）
* 字号：正文 22pt（20–24 区间）/ 书名 40pt / 徽章 16pt / 页码 14pt
* 颜色：橙胶囊 #F47332 / 黑字 #121212 / 白底 #FFFFFF
* 页码：偶数页左下 / 奇数页右下
* 文字框：白底矩形，落画面留白角（`Text_Position` 控制）
* 元信息：Level / Book / CEFR / Lexile / Word count / Vocabulary

> 完整细节见 [`STANDARD.md`](STANDARD.md)。
