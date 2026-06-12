# RR/WS 校验 + 打包 PDF 集成方案（research note）

> 集成外部 skill：https://github.com/jeredithia-ai/worksheet-RR-checking
> 目标：把「出书的最后一步」做成 **校验 RR/WS → 合并打包成单一 PDF**。
> 状态：研究 + 骨架（`scripts/rr_ws_checker.py`），未接线进 UI，未提交。

## 1. 外部仓库到底做了什么

外部仓库是一套「(AI/人工)审核 + 数据驱动修正 + 高保真转 PDF + 合并」工作流，
面向 VIPKID Dino Reading Club，**没有通用的、读任意文件即给 pass/fail 的校验引擎**。

| 文件 | 作用 | 能否直接复用 |
|---|---|---|
| `extract_text.py` | 抽 storybook(PDF/PPTX)/WS(PPTX)/RR(DOCX) 成纯文本供审核 | ✅ 可复用思路 |
| `.cursor/rules/picture-book-workflow.mdc` | **真正的校验标准（散文）**，由 AI 读文本逐项判断 | ⚠️ 需落成代码 |
| `lessons.py` | 每节课手工硬编码的已知修正项配置 | ❌ 逐课配置，不通用 |
| `apply_corrections.py` | 按配置改 pptx/docx，保留排版；含「图片 drawing 数量前后一致」硬校验 | ⚠️ 思路可借 |
| `run_workflow.py` | **核心可复用**：WPS COM 转 PDF + pypdf 合并 | ✅ 已移植 |

**「校验」= .mdc 里的标准**，分三类：① 三方一致性（以绘本为基准，对照 WS+RR 的词汇/句型/
知识点/主题）；② 逐份语言错误（语法/拼写/APA 标点/大小写/风格）；③ 模板一致性（字体/字号/
颜色/页脚/shape 位置）。RR 关键断言：标题格式、Mastery 恰好 4 词、拼读小写、阅读表达 4/5 题
星级 1+2+2(+2)+3、logo 不丢、emoji 后空格。WS 关键断言：A4 横版、页脚命名、加粗规则、
书写横线连续（不裸 `_`）、词汇 100% 来自绘本。

**输入**：WS=.pptx、RR=.docx、绘本=.pdf 或 .pptx。**输出**：审核问题清单(markdown) +
`_corrected` 文件 + 各自 PDF + 合并 `L<级别>B<编号> Worksheet+RR Final.pdf`
（WS 横版在前，RR 竖版在后并 `/Rotate=270` 左转 90°）。

**依赖**：python-pptx / python-docx / pypdf / pywin32 + **WPS Office（必装）**。

## 2. 针对本 App 的集成设计

本 App 的优势：生成阶段已有结构化 `BookOutline` 与 `scripts/evals.py`（已有
`check_vocabulary/check_worksheet/check_reading_report`），校验可比「事后扒文本」更准。

- **新模块**：`scripts/rr_ws_checker.py`（已建骨架）。
  - `discover_book_files(book_dir)` —— 按本 App 固定命名定位 `_Worksheet.pptx`/`_Reading_Report.docx`/`_Reader.pptx`。
  - `check_worksheet / check_reading_report(path, outline, result)` —— 编程化落地 .mdc 规则，复用 evals，能拿到 outline 时优先比结构化字段。
  - `convert_to_pdf(src, dest)` —— WPS COM（KWPS docx / KWPP pptx）已移植；预留 docx2pdf fallback。
  - `merge_rr_ws_pdf(ws_pdf, rr_pdf, final, 270)` —— pypdf 合并（移植，零改动）。
  - `check_and_pack(book_dir, outline=...)` —— 编排：校验 → 转 PDF → 合并 → 返回 `CheckResult`。
- **插入点（两处，另一 agent 在改 web_app/workbench，先不动）**：
  1. **每本流水线末尾**：`scripts/batch_runner.py` 在生成四件套(≈L596-605)、跑完 `evals`、ZIP 打包(≈L632)**之前**调用 `check_and_pack`，把 `_Worksheet+RR_Final.pdf` 一并塞进 ZIP；校验结果并入现有 `needs_human_review` 逻辑。
  2. **上传组装模式**：`scripts/web_app.py::_render_upload_mode` / `_run_docs_assembly` 末尾调用同一函数（**本次不改 web_app**，留接口）。
- **pass/fail 暴露**：`CheckResult.passed`（无 error 即过，warn 不阻断）+ `issues` 列表（带稳定 code），UI 用 markdown 表格展示「文件/位置/类型/原文/建议」，error 时标「人工抽查」并默认跳过打包。

## 3. 依赖与外部工具（本机已探测）

| 项 | 状态 |
|---|---|
| python-pptx / python-docx / pypdf / pywin32 / docx2pdf / PyMuPDF | ✅ 已装 |
| WPS Office（KWPS/KWPP COM） | ✅ 已装（12.1）→ 首选转 PDF |
| soffice / libreoffice | ❌ 未发现 |
| MS Office/Word（docx2pdf 依赖） | ❓ 未确认；WPS 才是已验证方案 |

验证：`where soffice`；`py -c "import win32com.client as w; w.DispatchEx('KWPP.Application')"`。

## 4. 待用户决策的开放问题

1. **校验严格度**：error 是否硬阻断打包，还是「带警告也打包 + 标人工抽查」？（骨架默认：有 error 跳过打包）
2. **校验范围**：是否要做完整「三方一致性 + 语言/APA 标点」AI 审核，还是先只做结构化断言（更快、零额外成本）？
3. **修正 vs 只校验**：是否要移植 `apply_corrections` 的自动修正？本 App 是自己生成的文件，理论上「生成即合规」，建议**先只校验不自动改**。
4. **合并 PDF 规格**：沿用「WS 横版在前 + RR 竖版 `/Rotate=270`」？本 App RR 是 A4 竖版、WS 是 A4 横版，规格吻合。
5. **TG 是否进合并**：外部只合 WS+RR；本 App 还有 TG，是否也要一份合并 PDF？
6. **WPS 稳定性**：批量并发转 PDF 时 WPS COM 单实例可能冲突，是否需串行化转换/加锁（参考 .mdc 故障排查：先杀残留 wps/wpp 进程）。

---

## 用户已拍板（2026-06-12 · 实现时照此执行）

1. **校验严格度** → **带警告也打包 + 标「人工抽查」**，error 不硬阻断生产。
2. **校验范围** → **上完整 AI 三方一致性 + 语言/APA 标点审核**（不是只做结构化断言；需接 LLM，有 API 成本；建议仍并用 `evals.py` 结构化断言打底）。
3. **修正 vs 只校验** → **只校验，不自动改**（不移植 `apply_corrections`）。
4. **合并 PDF 规格** → 沿用「WS 横版在前 + RR 竖版 `/Rotate=270`」。
5. **合并范围** → **只合 WS + RR**（TG 不进合并 PDF）。
6. **WPS 稳定性** → **串行化转换**，转换前先清残留 `wps/wpp/et` 进程。

> 接入时机：等工作台三区重构落地后再动 `batch_runner.py` 末尾 + `web_app._render_upload_mode`，避免与重构抢同一文件。
