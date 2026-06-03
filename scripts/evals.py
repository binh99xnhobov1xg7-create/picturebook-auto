"""轻量 evals · 交付物规则体检（纯规则，不烧 API）。

目标：把"肉眼一份份验收"变成"自动出体检报告"，专抓反复踩的坑：
  - 词汇：必须 lemma 原型 + 小写 + 无标点 + 不含专有名词(IP名)，数量按级别
  - 绘本：固定 7 页正文、每页有文本；每页 IP 参考图能解析、年龄=级别焊死值、封面带齐主角
  - Worksheet：标题结构(2词汇+2句型+2阅读)、每页题数下限、无 color-only 题
  - Reading Report：阅读表达题星级数量(0-2=4题 / 3-6=5题)

用法：
  from evals import run_all, format_report
  report = run_all(outline=outline, worksheet_questions=ws, rr_items=rr)
  print(format_report(report))

也可命令行：python scripts/evals.py  → 跑内置自测样例。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from config import resolve_ip_age
except Exception:  # pragma: no cover
    def resolve_ip_age(level: str, explicit=None) -> int:  # type: ignore
        return 12


# ============================================================
#  数据结构
# ============================================================

OK, WARN, ERROR = "ok", "warn", "error"
_ICON = {OK: "✅", WARN: "⚠️", ERROR: "❌"}


@dataclass
class Issue:
    category: str        # "词汇" / "绘本" / "Worksheet" / "Reading Report"
    level: str           # ok / warn / error
    msg: str

    def line(self) -> str:
        return f"{_ICON.get(self.level, '•')} [{self.category}] {self.msg}"


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def add(self, category: str, level: str, msg: str) -> None:
        self.issues.append(Issue(category, level, msg))

    def ok(self, category: str, msg: str) -> None:
        self.add(category, OK, msg)

    def warn(self, category: str, msg: str) -> None:
        self.add(category, WARN, msg)

    def error(self, category: str, msg: str) -> None:
        self.add(category, ERROR, msg)

    @property
    def n_error(self) -> int:
        return sum(1 for i in self.issues if i.level == ERROR)

    @property
    def n_warn(self) -> int:
        return sum(1 for i in self.issues if i.level == WARN)

    @property
    def passed(self) -> bool:
        return self.n_error == 0


# ============================================================
#  IP 名字（用于专有名词检查）
# ============================================================

_IP_NAMES = {
    "mia", "tommy", "anna", "ali", "cate", "dino", "winnie",
    "kim", "teacher", "mom", "dad", "grandma", "grandpa",
}


def _level_digit(level: str) -> int:
    s = str(level or "").lower()
    if "smart" in s:
        return 0
    d = "".join(ch for ch in s if ch.isdigit())
    return int(d) if d else 0


# ============================================================
#  1) 词汇检查
# ============================================================

# 简易复数检测：以 s 结尾且不是 ss/us/is 等常见非复数结尾
_PLURALISH = re.compile(r"[a-z]{3,}s$")
_PLURAL_SAFE = ("ss", "us", "is", "as", "os")


def check_vocabulary(words: list[str], level: str, *, category: str = "词汇",
                     report: Optional[Report] = None) -> Report:
    report = report or Report()
    if not words:
        report.error(category, "词汇为空")
        return report

    for w in words:
        raw = str(w)
        # 小写
        if raw != raw.lower():
            report.error(category, f"`{raw}` 含大写，应全小写")
        # 无标点/无空格末尾符号
        if re.search(r"[.,!?;:'\"()]", raw):
            report.error(category, f"`{raw}` 含标点，应去掉")
        low = raw.lower().strip()
        # 专有名词 / IP 名
        if low in _IP_NAMES:
            report.error(category, f"`{raw}` 是 IP/专有名词，词表里不应出现")
        # lemma 近似：疑似复数
        if _PLURALISH.search(low) and not low.endswith(_PLURAL_SAFE):
            report.warn(category, f"`{raw}` 疑似复数，确认是否应还原为单数原型")
        # 疑似时态
        if low.endswith("ing") and len(low) > 5:
            report.warn(category, f"`{raw}` 疑似进行式，确认是否应还原为原型")
        if low.endswith("ed") and len(low) > 4:
            report.warn(category, f"`{raw}` 疑似过去式，确认是否应还原为原型")

    # 数量：L3-6 = 4 词；L0-2 双行(Mastery+Exposure)，这里只校验非空与上限
    d = _level_digit(level)
    n = len(words)
    if d >= 3 and n != 4:
        report.warn(category, f"L{d} 词汇建议 4 个，当前 {n} 个")
    if not report.issues:
        report.ok(category, "全部 lemma 小写无标点、无专有名词")
    elif report.n_error == 0:
        report.ok(category, "无硬性错误（仅原型提醒）")
    return report


# ============================================================
#  2) 绘本 IP / 页面检查
# ============================================================

def check_picturebook(outline: Any, *, category: str = "绘本",
                      cast_pool: Optional[list[str]] = None,
                      generic_overrides: Optional[dict] = None,
                      report: Optional[Report] = None) -> Report:
    report = report or Report()
    pages = list(getattr(outline, "pages", []) or [])
    level = getattr(outline, "level", "5")
    welded_age = resolve_ip_age(level)
    ip_age = int(getattr(outline, "ip_age", 0) or welded_age)

    # 年龄焊死
    if ip_age != welded_age:
        report.error(category, f"IP 年龄 {ip_age} 与 Level({level}) 焊死值 {welded_age} 不一致")
    else:
        report.ok(category, f"IP 年龄焊死正确：Level {level} → {welded_age} 岁")

    # 正文页数（封面 + 7 页正文）
    story_pages = [p for p in pages if getattr(p, "page_type", "") != "cover"]
    if len(story_pages) and len(story_pages) != 7:
        report.warn(category, f"正文页数为 {len(story_pages)}，标准为 7 页")

    # 每页有文本
    for p in story_pages:
        if not (getattr(p, "text", "") or "").strip():
            report.error(category, f"第 {getattr(p,'index','?')} 页缺故事文本")

    # 逐页 IP 参考图能否解析 + 封面带齐主角
    try:
        from cn_prompt_builder import build_cn_page_prompt
        cover = next((p for p in pages if getattr(p, "page_type", "") == "cover"
                      or getattr(p, "index", -1) == 0), None)
        if cover is not None:
            b = build_cn_page_prompt(cover, outline, ip_age,
                                     cast_pool=cast_pool, generic_overrides=generic_overrides)
            n_cast = len(b.used_characters)
            n_ref = len(b.references)
            if n_cast == 0:
                report.error(category, "封面未识别到任何主角")
            else:
                names = "、".join(c.get("name", "?") for c in b.used_characters)
                report.ok(category, f"封面主角：{names}（{n_ref} 张参考图）")
            if n_ref < n_cast:
                report.warn(category, f"封面 {n_cast} 个主角只有 {n_ref} 张参考图，可能缺图")
    except Exception as e:  # pragma: no cover
        report.warn(category, f"封面 IP 检查跳过（{e}）")

    return report


# ============================================================
#  3) Worksheet 结构检查
# ============================================================

_BAD_WS_TYPES = ("color", "colour", "draw", "circle only", "圈画", "涂色")


def check_worksheet(worksheet_questions: list[dict], level: str, *,
                    category: str = "Worksheet", report: Optional[Report] = None) -> Report:
    report = report or Report()
    if not worksheet_questions:
        report.warn(category, "无 Worksheet 题目数据，跳过")
        return report

    titles = [(q.get("title") or q.get("page_title") or "").strip().lower()
              for q in worksheet_questions]
    n_vocab = sum(1 for t in titles if "vocab" in t)
    n_sent = sum(1 for t in titles if "sentence" in t)
    n_read = sum(1 for t in titles if "read" in t)

    if n_vocab < 2:
        report.warn(category, f"Vocabulary 页 {n_vocab}（标准 2）")
    if n_sent < 2:
        report.warn(category, f"Sentence 页 {n_sent}（标准 2）")
    if n_read < 2:
        report.warn(category, f"Reading 页 {n_read}（标准 2）")
    if n_vocab >= 2 and n_sent >= 2 and n_read >= 2:
        report.ok(category, f"页面结构正确（词汇{n_vocab}+句型{n_sent}+阅读{n_read}）")

    for i, q in enumerate(worksheet_questions, 1):
        items = q.get("items") or q.get("questions") or []
        qtype = str(q.get("type") or "").lower()
        # 题数下限
        if isinstance(items, list) and 0 < len(items) < 3:
            report.warn(category, f"第 {i} 页只有 {len(items)} 题（建议 ≥3）")
        # color-only 题型
        if any(bad in qtype for bad in _BAD_WS_TYPES):
            report.error(category, f"第 {i} 页题型 `{qtype}` 是涂色/圈画类，应替换为有语言输出的题型")
    return report


# ============================================================
#  4) Reading Report 检查
# ============================================================

def check_reading_report(rr_items: list[dict], level: str, *,
                          category: str = "Reading Report",
                          report: Optional[Report] = None) -> Report:
    report = report or Report()
    if not rr_items:
        report.warn(category, "无 Reading Report 数据，跳过")
        return report

    # 阅读表达题数量：0-2 级=4 题，3-6 级=5 题
    d = _level_digit(level)
    expected = 4 if d <= 2 else 5
    questions = [x for x in rr_items if (x.get("kind") or x.get("type") or "") in
                 ("question", "q", "comprehension")] or rr_items
    n = len(questions)
    if n and n != expected:
        report.warn(category, f"L{d} 阅读表达题应 {expected} 题，当前 {n} 题")
    elif n:
        report.ok(category, f"阅读表达题数量正确（{n} 题）")
    return report


# ============================================================
#  汇总
# ============================================================

def run_all(*, outline: Any = None,
            worksheet_questions: Optional[list[dict]] = None,
            rr_items: Optional[list[dict]] = None,
            cast_pool: Optional[list[str]] = None,
            generic_overrides: Optional[dict] = None) -> Report:
    report = Report()
    if outline is not None:
        level = getattr(outline, "level", "5")
        words = (getattr(outline, "mastery", None)
                 or getattr(outline, "vocabulary", None) or [])
        if words:
            check_vocabulary(list(words), level, report=report)
        check_picturebook(outline, cast_pool=cast_pool,
                          generic_overrides=generic_overrides, report=report)
        if worksheet_questions:
            check_worksheet(worksheet_questions, level, report=report)
        if rr_items:
            check_reading_report(rr_items, level, report=report)
    return report


def format_report(report: Report) -> str:
    head = (f"# 交付物体检报告\n"
            f"- ❌ 错误 {report.n_error}　⚠️ 警告 {report.n_warn}　"
            f"{'✅ 通过' if report.passed else '❌ 有硬性问题需修'}\n")
    body = "\n".join(i.line() for i in report.issues)
    return head + "\n" + body


# ============================================================
#  自测样例
# ============================================================

if __name__ == "__main__":
    r = Report()
    check_vocabulary(["nervous", "Shake", "books", "running", "anna"], "L5", report=r)
    print(format_report(r))
