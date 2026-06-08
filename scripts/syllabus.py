"""官方 S&S 大纲的运行期加载器与匹配器。

读取 references/syllabus/syllabus.json（由 _build_syllabus_snapshot.py 生成），
按 (level, title) 模糊匹配出一条 SyllabusEntry，作为 TG / 题目 / 画面的权威数据源。
匹配不到返回 None，调用方回退到 AI 抽取 / 启发式。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_JSON = Path(__file__).resolve().parents[1] / "references" / "syllabus" / "syllabus.json"


def _norm_title(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


@dataclass
class SyllabusEntry:
    level: str = ""
    title: str = ""
    book_number: str = ""   # 官方 Book No.（L3-6 大纲列；用于"按级别+编号取本"）
    genre: str = ""
    # --- L3-6 主字段 ---
    sentence_pattern: str = ""
    example_sentence: str = ""
    teaching_focus: str = ""
    core_vocab: list[dict] = field(default_factory=list)
    text_7page: str = ""
    pure_text: str = ""
    word_count: str = ""
    lexile: str = ""
    cefr: str = ""
    decoding_label: str = ""          # "Phonics Rule" / "Word Formation"
    phonics_rule: str = ""
    phonics_examples: str = ""
    reading_strategy: str = ""
    reading_skill: str = ""
    questions_type: str = ""
    rr_questions: str = ""
    graphic_organizer: str = ""
    go_description: str = ""
    go_usage: str = ""
    # --- L0-2 专属 ---
    reader_text: str = ""
    objective: str = ""
    core_vocab_raw: str = ""
    vocab_mastery: list[str] = field(default_factory=list)
    vocab_exposure: list[str] = field(default_factory=list)
    sentence_frames: str = ""
    sor: str = ""
    oral_prompts: str = ""
    extension: str = ""
    answers: str = ""
    syntax_focus: str = ""
    morphology_focus: str = ""
    comprehension_tier: str = ""
    cognitive_demand: str = ""
    # 该级别公共 SoR 前/中/后策略（仅 L0-2）
    sor_strategies: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict, sor_strategies: dict | None = None) -> "SyllabusEntry":
        known = {f for f in cls.__dataclass_fields__}
        kw = {k: v for k, v in d.items() if k in known}
        e = cls(**kw)
        if sor_strategies and e.level in sor_strategies:
            e.sor_strategies = sor_strategies[e.level]
        return e

    # ---- 便捷方法 ----
    def vocab_words(self) -> list[str]:
        if self.core_vocab:
            return [v.get("word", "") for v in self.core_vocab if v.get("word")]
        return list(self.vocab_mastery) + list(self.vocab_exposure)

    @property
    def is_nonfiction(self) -> bool:
        return self.genre.lower() == "nonfiction"

    @property
    def is_low_band(self) -> bool:
        return self.level in ("0", "1", "2")


@lru_cache(maxsize=1)
def load_syllabus() -> dict:
    """读取并缓存快照 JSON。文件缺失返回空结构。"""
    if not _JSON.exists():
        return {"books": {}, "sor_strategies": {}, "_meta": {}}
    try:
        return json.loads(_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"books": {}, "sor_strategies": {}, "_meta": {}}


def _level_digit(level: str) -> str:
    digits = "".join(ch for ch in str(level or "") if ch.isdigit())
    return digits[:1] if digits else ""


def match(level: str, title: str) -> SyllabusEntry | None:
    """按 (level, title) 匹配大纲条目；命中返回 SyllabusEntry，否则 None。

    匹配顺序：
      1. 同级别精确归一化标题
      2. 同级别标题互为子串（处理副标题/问号差异）
      3. 跨级别精确归一化标题（级别标注偶有偏差时兜底）
    """
    data = load_syllabus()
    books: dict = data.get("books", {})
    sor: dict = data.get("sor_strategies", {})
    if not books or not title:
        return None

    lvl = _level_digit(level)
    nt = _norm_title(title)
    if not nt:
        return None

    # 1) 同级别精确
    key = f"{lvl}::{nt}"
    if key in books:
        return SyllabusEntry.from_dict(books[key], sor)

    # 预先按级别分组
    same_level = {k: v for k, v in books.items() if k.startswith(f"{lvl}::")}

    # 2) 同级别子串匹配（取最长公共、避免太短误配）
    best = None
    best_len = 0
    for k, v in same_level.items():
        kt = k.split("::", 1)[1]
        if len(nt) >= 4 and len(kt) >= 4 and (nt in kt or kt in nt):
            score = min(len(nt), len(kt))
            if score > best_len:
                best, best_len = v, score
    if best is not None:
        return SyllabusEntry.from_dict(best, sor)

    # 3) 跨级别精确
    for k, v in books.items():
        if k.split("::", 1)[1] == nt:
            return SyllabusEntry.from_dict(v, sor)

    return None


def get_by_number(level: str, number: int | str) -> SyllabusEntry | None:
    """按【官方 Book No.】取本（唯一权威编号；解决重名书/位置错位）。命中返回 SyllabusEntry。"""
    data = load_syllabus()
    books: dict = data.get("books", {})
    sor: dict = data.get("sor_strategies", {})
    lvl = _level_digit(level)
    want = str(number).strip()
    try:
        want = str(int(float(want)))
    except Exception:
        pass
    for k, v in books.items():
        if not k.startswith(f"{lvl}::"):
            continue
        if str(v.get("book_number", "")).strip() == want:
            return SyllabusEntry.from_dict(v, sor)
    return None


def list_level(level: str) -> list[SyllabusEntry]:
    """按书号升序列出某级别全部条目（无书号的排末尾）。"""
    data = load_syllabus()
    books: dict = data.get("books", {})
    sor: dict = data.get("sor_strategies", {})
    lvl = _level_digit(level)
    entries = [SyllabusEntry.from_dict(v, sor) for k, v in books.items()
               if k.startswith(f"{lvl}::")]

    def _key(e: SyllabusEntry) -> int:
        try:
            return int(e.book_number)
        except Exception:
            return 10_000
    return sorted(entries, key=_key)


if __name__ == "__main__":
    for lv, t in [("4", "Mia and Tommy Travel the World"),
                  ("Level 5", "What Makes a Good Friend"),
                  ("0", "My Toys"),
                  ("3", "this book does not exist")]:
        e = match(lv, t)
        if e:
            print(f"HIT  L{lv} {t!r} -> strategy={e.reading_strategy!r} skill={e.reading_skill!r} "
                  f"GO={e.graphic_organizer!r} vocab={e.vocab_words()[:4]} sor_phases={list(e.sor_strategies)}")
        else:
            print(f"MISS L{lv} {t!r}")
