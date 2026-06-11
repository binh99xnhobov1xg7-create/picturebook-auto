"""钉钉群机器人：绘本生成完成推送（出站 only，未配置则静默跳过）。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
import urllib.parse
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_DEFAULT_APP_URL = "https://picturebook-auto-43fmumu7yf9lk5tfv2piug.streamlit.app"
_STATUS_LABEL = {
    "ok": "✅ 成功",
    "partial": "⚠️ 部分完成（含占位页或警告）",
    "failed": "❌ 失败",
}


def _cfg(key: str, default: str = "") -> str:
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default


def webhook_url() -> str:
    return _cfg("DINGTALK_WEBHOOK_URL")


def webhook_secret() -> str:
    return _cfg("DINGTALK_SECRET")


def streamlit_app_url() -> str:
    return _cfg("STREAMLIT_APP_URL", _DEFAULT_APP_URL)


def feedback_form_url() -> str:
    return _cfg("DINGTALK_FEEDBACK_FORM_URL")


def is_configured() -> bool:
    return bool(webhook_url())


def _signed_post_url(url: str, secret: str) -> str:
    if not secret:
        return url
    ts = str(round(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}timestamp={ts}&sign={sign}"


def send_dingtalk_markdown(title: str, text: str, *, timeout: float = 15.0) -> bool:
    """POST markdown 到钉钉群机器人。未配置 webhook 时返回 False 并打 debug 日志。"""
    url = webhook_url()
    if not url:
        logger.debug("DingTalk webhook 未配置，跳过推送")
        return False
    post_url = _signed_post_url(url, webhook_secret())
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title[:64], "text": text},
    }
    try:
        resp = requests.post(post_url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            logger.warning("DingTalk 推送被拒: errcode=%s errmsg=%s", data.get("errcode"), data.get("errmsg"))
            return False
        logger.info("DingTalk 推送成功: %s", title)
        return True
    except Exception as exc:
        logger.warning("DingTalk 推送失败（不影响流水线）: %s", exc)
        return False


def _feedback_footer() -> str:
    form = feedback_form_url()
    if form:
        return (
            f"> **反馈指引**：有问题请在群内回复 @机器人 或 Selena，"
            f"或填写 [问题反馈表]({form})"
        )
    return "> **反馈指引**：有问题请在群内回复或 @Selena；也可在 Streamlit 工作台使用「🚨 这张图有问题？」定向重生。"


def _level_book_line(level: str, book_number: str) -> str:
    lv = str(level or "").strip()
    bk = str(book_number or "").strip()
    if bk:
        return f"Level {lv} · Book {bk}"
    if lv:
        return f"Level {lv}"
    return "—"


def notify_book_complete(
    *,
    title: str,
    level: str,
    book_number: str = "",
    status: str = "ok",
    output_path: str = "",
    placeholder_pages: Optional[list[int]] = None,
    elapsed_s: Optional[float] = None,
    source: str = "batch",
    error: str = "",
    deliverable: str = "4 件套",
) -> bool:
    """单本生成完成推送。"""
    st_key = status if status in _STATUS_LABEL else "ok"
    label = _STATUS_LABEL.get(st_key, status)
    source_note = {
        "batch": "CLI / 批量流水线",
        "web": "Streamlit 工作台",
        "upload": "上传绘本 · 教辅三件套",
        "upload_batch": "批量上传 · 教辅",
    }.get(source, source)

    lines = [
        f"### 📚 绘本生成完成",
        "",
        f"- **书名**：{title}",
        f"- **级别**：{_level_book_line(level, book_number)}",
        f"- **状态**：{label}",
        f"- **产出**：{deliverable}",
        f"- **来源**：{source_note}",
    ]
    ph = placeholder_pages or []
    if ph:
        lines.append(f"- **占位页**：P{', P'.join(str(p) for p in ph)}（需回工作台重生）")
    if elapsed_s is not None and elapsed_s > 0:
        lines.append(f"- **用时**：{elapsed_s:.0f}s")
    if output_path:
        lines.append(f"- **输出路径**：`{output_path}`")
    else:
        lines.append("- **输出**：Streamlit Cloud 服务器（请登录工作台下载 ZIP）")
    if error.strip():
        lines.append(f"- **备注**：{error.strip()[:300]}")
    app = streamlit_app_url()
    if app:
        lines.append(f"- **工作台**：[打开 Streamlit]({app})")
    lines.extend(["", _feedback_footer()])
    md_title = f"绘本完成 · {title}"[:64]
    return send_dingtalk_markdown(md_title, "\n".join(lines))


def notify_batch_summary(
    *,
    total: int,
    ok: int,
    failed: int,
    out_root: str = "",
    need_review: int = 0,
    source: str = "batch",
) -> bool:
    """批量任务全部结束后的汇总推送（Web 批量模式用）。"""
    lines = [
        "### 📦 批量生成汇总",
        "",
        f"- **合计**：{total} 本",
        f"- **成功**：{ok} 本",
        f"- **失败**：{failed} 本",
    ]
    if need_review:
        lines.append(f"- **需人工抽查**：{need_review} 本")
    if out_root:
        lines.append(f"- **输出目录**：`{out_root}`")
    app = streamlit_app_url()
    if app:
        lines.append(f"- **工作台**：[打开 Streamlit]({app})")
    lines.extend(["", _feedback_footer()])
    return send_dingtalk_markdown("批量生成汇总", "\n".join(lines))
