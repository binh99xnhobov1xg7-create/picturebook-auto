# -*- coding: utf-8 -*-
"""官方每课出图 Prompt 检索层。

读取 references/syllabus/image_prompts.json（由 _build_image_prompts_snapshot.py 生成），
提供 match(level, title) → OfficialImagePrompt，供出图前"检索优先 / 权威参考注入"。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_JSON = Path(__file__).resolve().parent.parent / "references" / "syllabus" / "image_prompts.json"


def _norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _level_digit(level: str) -> str:
    s = (level or "").lower()
    if "smart" in s:
        return "0"
    d = "".join(c for c in s if c.isdigit())
    return d[:1] if d else ""


@dataclass
class OfficialImagePrompt:
    level: str
    title: str
    book_label: str
    full_text: str
    pages: list[dict] = field(default_factory=list)

    def page_scene(self, index: int) -> str:
        """按顺序对齐取第 index 页（0=封面）的官方画面要求/正文片段。"""
        if 0 <= index < len(self.pages):
            p = self.pages[index]
            return (p.get("scene") or p.get("text") or "").strip()
        return ""


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    if not _JSON.exists():
        return []
    try:
        return json.loads(_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


@lru_cache(maxsize=256)
def match(level: str, title: str) -> OfficialImagePrompt | None:
    data = _load()
    if not data or not title:
        return None
    lv = _level_digit(level)
    nt = _norm_title(title)
    if not nt:
        return None

    same_level = [e for e in data if e.get("level") == lv] if lv else []
    pools = [same_level, data] if same_level else [data]

    for pool in pools:
        # 1) 精确
        for e in pool:
            if e.get("norm_title") == nt:
                return _mk(e)
        # 2) 包含（标题去噪后互为子串）
        for e in pool:
            en = e.get("norm_title", "")
            if en and (en in nt or nt in en) and abs(len(en) - len(nt)) <= 8:
                return _mk(e)
    return None


def _mk(e: dict) -> OfficialImagePrompt:
    return OfficialImagePrompt(
        level=e.get("level", ""),
        title=e.get("title", ""),
        book_label=e.get("book_label", ""),
        full_text=e.get("full_text", ""),
        pages=e.get("pages", []) or [],
    )
