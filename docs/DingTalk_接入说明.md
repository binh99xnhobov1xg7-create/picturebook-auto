# 钉钉群机器人接入说明

> 更新日期：2026-06-11 · 出站推送 + 群内反馈收集方案

本仓库通过 **钉钉自定义机器人 Webhook** 在绘本/教辅生成完成时向群聊推送 Markdown 消息。  
**未配置 Webhook 时流水线照常运行**，不会报错或中断。

---

## 1. 创建群机器人并获取 Webhook

1. 打开目标 **钉钉群** → 右上角 **群设置** → **智能群助手** → **添加机器人**。
2. 选择 **自定义** 机器人，填写名称（如「绘本生产通知」）。
3. **安全设置**（推荐）：
   - **加签**：勾选后会得到 `SECxxxx` 密钥 → 填入 `DINGTALK_SECRET`。
   - 或 **自定义关键词**：消息标题/正文需含关键词（如「绘本」），本模块标题已含「绘本」。
4. 复制 **Webhook 地址**（形如 `https://oapi.dingtalk.com/robot/send?access_token=...`）。

⚠️ **切勿把真实 Webhook / Secret 提交到 Git**。只写在 Streamlit Cloud Secrets 或本机 `.env` / `.streamlit/secrets.toml`（已 gitignore）。

---

## 2. 配置 Secrets / 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DINGTALK_WEBHOOK_URL` | 是 | 机器人 Webhook 完整 URL |
| `DINGTALK_SECRET` | 否 | 加签密钥（安全设置选「加签」时必填） |
| `STREAMLIT_APP_URL` | 否 | 工作台链接，默认 Cloud 正式址 |
| `DINGTALK_FEEDBACK_FORM_URL` | 否 | 问题反馈表 URL（Google Form 等），推送里会带链接 |
| `DINGTALK_PROGRESS_NODE_ID` | 否 | 生产进度表/Timeline 表节点或 URL；默认使用 `Timeline -Dino Reading精读绘本课程整体排期` |
| `DINGTALK_PROGRESS_SOURCE_URL` | 否 | 生产进度表原始 URL，用于看板展示来源 |

### Streamlit Cloud

1. 打开 [share.streamlit.io](https://share.streamlit.io) → **picturebook-auto** → **Settings → Secrets**。
2. 在 **顶层**（`[APP_USERS]` 表之前）追加：

```toml
DINGTALK_WEBHOOK_URL = "https://oapi.dingtalk.com/robot/send?access_token=替换"
DINGTALK_SECRET = "SEC替换为加签密钥"
STREAMLIT_APP_URL = "https://picturebook-auto-43fmumu7yf9lk5tfv2piug.streamlit.app"
# DINGTALK_FEEDBACK_FORM_URL = "https://forms.google.com/..."  # 可选
# DINGTALK_PROGRESS_NODE_ID = "https://alidocs.dingtalk.com/i/nodes/7NkDwLng8ZMaj15pHaqGnz5jJKMEvZBY?utm_scene=person_space"
```

3. **Save**，等待约 3–5 分钟重新部署。

更多 Secrets 结构见 [`streamlit-cloud-secrets.md`](streamlit-cloud-secrets.md)。

### 进度看板同步

数据看板优先读取钉钉 Timeline 进度缓存，而不是本地输出目录。同步命令：

```powershell
py scripts/sync_progress_from_dingtalk.py
```

默认数据源为 `https://alidocs.dingtalk.com/i/nodes/7NkDwLng8ZMaj15pHaqGnz5jJKMEvZBY?utm_scene=person_space`。脚本会读取 `Level 0` 到 `Level 6` 及样书进度工作表，生成 `references/syllabus/progress_status.json`。若钉钉权限或字段映射不可用，网页会降级为本地输出扫描，并明确标注“本地输出扫描（降级）”。

### 本地开发

复制 [`.streamlit/secrets.toml.example`](../.streamlit/secrets.toml.example) 为 `.streamlit/secrets.toml`，或在项目根 `.env` 中设置同名变量。

---

## 3. 何时推送

| 场景 | 触发位置 | 推送内容 |
|------|----------|----------|
| CLI / `batch_runner` 批量 | 每本 `run_one` 完成 + 全部结束后 | 单本各一条 + **批量汇总**（含书目清单） |
| Streamlit **批量生产** | 同上（汇总由 `run_batch` 统一推送） | 单本各一条 + **批量汇总**（含书目清单） |
| Streamlit **单本组装 ZIP** | Step 7 四件套打包成功 | 单本 4 件套完成 |
| **上传绘本 · 教辅三件套** | 单本 / 批量上传完成 | 单本各一条；批量结束另有汇总 |

**状态说明**

- **成功**：四件套/三件套正常产出，无占位页。
- **部分完成**：有占位图页或流水线警告（eval warn），需回工作台重生。
- **失败**：整本异常退出。

---

## 4. 反馈如何收集

Streamlit Cloud **无法直接接收**钉钉 inbound 回调（需公网 HTTPS 独立服务），当前采用 **出站推送 + 人工/表单回流**：

### 方案 A：群内回复（推荐 · 已默认）

推送消息末尾含 **反馈指引**：

> 有问题请在群内回复或 @Selena；也可在 Streamlit 工作台使用「🚨 这张图有问题？」定向重生。

同事在群里 **直接回复** 或 **@机器人 / @Selena**，由 Selena 汇总处理。

### 方案 B：问题反馈表

若团队有 Google Form / 飞书表单 / 腾讯问卷，将链接写入 `DINGTALK_FEEDBACK_FORM_URL`，推送中会附带 **「问题反馈表」** 链接。

工作台内也可使用 [Streamlit 使用指南 §10 问题反馈清单](Streamlit_使用指南.md#10-问题反馈清单生图工作台) 勾选问题并 **保存并重生本页**。

### 方案 C：未来 · 企业应用 inbound 回调

若需 **自动** 把群内 @机器人 的消息写入工单/数据库，需：

1. 创建 **钉钉企业内部应用**（非仅 Webhook 机器人）；
2. 配置 **事件订阅 / 机器人消息回调 URL**（独立后端，如 Cloud Run / 轻量 VPS）；
3. 校验签名、落库、可选回推 Streamlit 或 GitHub Issue。

当前仓库 **未实现** inbound；如有需要可另开服务，本模块保持出站-only。

### 钉钉「Outgoing 机器人」说明

部分群可用 **Outgoing 机器人**（用户 @ 后 POST 到配置的 URL）。同样要求 **公网可访问的 HTTPS 端点**，与 Streamlit Cloud 架构不兼容，故文档仅作备选：可在独立服务上接 Outgoing，再转发到内部流程。

---

## 5. 实现文件

| 文件 | 作用 |
|------|------|
| `scripts/dingtalk_notify.py` | Webhook 读取、加签、Markdown 发送、消息模板 |
| `scripts/batch_runner.py` | 批量每本完成 + Web 批量汇总 |
| `scripts/web_app.py` | 单本组装、上传教辅单本/批量 |
| `scripts/config.py` | Secrets 水合说明 |
| `.streamlit/secrets.toml.example` | 配置占位示例 |

---

## 6. 自测

本地配置好 Secrets 后：

```powershell
py -c "from dingtalk_notify import send_dingtalk_markdown; send_dingtalk_markdown('测试', '### 绘本测试\n\n钉钉接入 OK')"
```

群聊收到消息即配置成功。未配置时命令静默返回 `False`，不影响其他脚本。
