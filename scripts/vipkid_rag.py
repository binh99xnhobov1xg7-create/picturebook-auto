# -*- coding: utf-8 -*-
"""VIPKID 权威资料检索层（RAG）。

读取 references/vipkid_index.json，提供「先检索再生成」的取证接口：
  - search(query, category=None, kind=None, k=8)  关键词检索文档/资料
  - reference_images(tags, k=6)                   按主题取官方参考图（场景/角色定妆）
  - style_guide_text()                            取编辑/排版/画风规范正文（拼接）

设计原则：纯本地、零依赖、确定性，作为生成前的 grounding 证据源。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "references" / "vipkid_index.json"

_CJK = re.compile(r"[\u4e00-\u9fff]")


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    if not INDEX.exists():
        return []
    return json.loads(INDEX.read_text(encoding="utf-8"))


def _tokens(s: str) -> list[str]:
    """中英混合分词：英文按词，中文按 1-gram + 2-gram（够用的轻量检索）。"""
    s = (s or "").lower()
    toks = re.findall(r"[a-z0-9]+", s)
    cjk = _CJK.findall(s)
    toks += cjk
    cjk_str = "".join(cjk)
    toks += [cjk_str[i:i + 2] for i in range(len(cjk_str) - 1)]
    return toks


def _score(entry: dict, q_toks: list[str]) -> float:
    if not q_toks:
        return 0.0
    title = entry.get("title", "")
    tags = " ".join(entry.get("tags", []))
    text = entry.get("text", "")
    hay_strong = _tokens(title + " " + tags)        # 标题/标签权重高
    hay_text = set(_tokens(text))
    score = 0.0
    strong_set = set(hay_strong)
    for t in q_toks:
        if t in strong_set:
            score += 3.0
        if t in hay_text:
            score += 1.0
    return score


def search(query: str, *, category: str | None = None,
           kind: str | None = None, k: int = 8) -> list[dict]:
    """关键词检索。返回 [{title, rel_path, abs_path, category, kind, tags, snippet, score}]。"""
    q = _tokens(query)
    rows = []
    for e in _load():
        if category and e.get("category") != category:
            continue
        if kind and e.get("kind") != kind:
            continue
        sc = _score(e, q)
        if sc <= 0:
            continue
        text = e.get("text", "")
        rows.append({
            "title": e.get("title"),
            "rel_path": e.get("rel_path"),
            "abs_path": e.get("abs_path"),
            "category": e.get("category"),
            "kind": e.get("kind"),
            "tags": e.get("tags", []),
            "snippet": (text[:200] + "…") if len(text) > 200 else text,
            "score": round(sc, 1),
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:k]


def reference_images(tags, *, k: int = 6) -> list[str]:
    """按主题关键词取官方参考图的绝对路径（优先 character_art 场景/角色图）。"""
    if isinstance(tags, str):
        tags = [tags]
    query = " ".join(tags)
    hits = search(query, kind="image", k=k)
    return [h["abs_path"] for h in hits]


def style_guide_text(limit: int = 6000) -> str:
    """拼接编辑/排版/画风规范正文，供生成前对齐格式与画风。"""
    cats = ("editing_standard", "layout_spec")
    parts = []
    for e in _load():
        if e.get("category") in cats and e.get("text"):
            parts.append(f"## {e.get('title')}\n{e['text']}")
    return "\n\n".join(parts)[:limit]


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "Mia Tommy 家庭场景"
    print(f"== search: {q!r} ==")
    for r in search(q, k=8):
        print(f"  [{r['score']}] ({r['category']}/{r['kind']}) {r['rel_path']}")
        if r["snippet"]:
            print(f"        {r['snippet'][:120]}")
    print("\n== reference_images(['家庭','场景']) ==")
    for p in reference_images(["家庭", "场景"]):
        print("  ", p)
