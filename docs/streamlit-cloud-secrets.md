# Streamlit Cloud Secrets 配置指南

## 操作步骤

1. 打开 https://share.streamlit.io ，进入 picturebook-auto 应用。
2. 右上角菜单 → Settings → Secrets。
3. 将下方整段 TOML 粘贴到编辑框。
4. 将 API Key 占位符替换为与本机 .env 相同的真实值。
5. 为每位同事在 [APP_USERS] 下增加用户名与密码（勿提交 Git）。
6. 点击 Save，等待约 3–5 分钟自动重新部署。
7. 分享 URL：https://picturebook-auto-43fmumu7yf9lk5tfv2piug.streamlit.app

Suqianxue 账号仅写在 Cloud Secrets，不要写入 Git 仓库。

## Cloud Secrets 推荐全文粘贴

```toml
[APP_USERS]
Suqianxue = "VIPKID@2026"
colleague1 = "change_me"
colleague2 = "change_me"

IMAROUTER_API_KEY = "sk-替换为你的-imarouter-key"

TEXT_MODEL = "claude-opus-4-7"
EXTRACT_MODEL = "claude-opus-4-7"

IMAGE_MODEL = "gpt-image-2"
IMAGE_SIZE = "1536x1024"

ARK_API_KEY = "ark-替换为你的-ark-key"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
JIMENG_SEEDREAM_MODEL = "doubao-seedream-4-5-251128"
JIMENG_SEEDREAM_SIZE = "2304x1728"

DOUBAO_API_KEY = "ark-替换为你的-doubao-key-或留空"
DOUBAO_MODEL = "doubao-1-5-pro-32k-250115"
DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

IMAGE_SELF_REVIEW = "true"
VISION_REVIEW_MODEL = "claude-sonnet-4-6"
```

## 登录

同事使用 Secrets 中配置的用户名与密码登录（区分大小写）。

## 本地

复制 .streamlit/secrets.toml.example 为 .streamlit/secrets.toml（已在 .gitignore），勿 git add secrets.toml。