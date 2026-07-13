"""Teacher's Guide structured context and quality gates.

The TG generator is deterministic. This module keeps factual source data and
validation rules outside the DOCX layout code so page text, vocabulary,
worksheet answer keys, and internal-only wording can be checked before a final
Teacher's Guide is saved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any

from parser import BookOutline


class TGQualityError(ValueError):
    """Raised when a Teacher's Guide must not be emitted."""


@dataclass
class TGValidationIssue:
    severity: str
    code: str
    message: str


@dataclass
class TGBookPage:
    printed_page: int
    text: str
    image_summary: str = ""
    characters: list[str] = field(default_factory=list)
    visible_clues: list[str] = field(default_factory=list)


@dataclass
class TGWorksheetSection:
    section_number: int
    title: str
    instructions: str
    word_bank: list[str] = field(default_factory=list)
    answer_key: list[str] = field(default_factory=list)
    open_response: bool = False


@dataclass
class TGContext:
    book_metadata: dict[str, Any]
    instructional_focus: dict[str, Any]
    book_pages: list[TGBookPage]
    story_analysis: dict[str, Any]
    worksheet_sections: list[TGWorksheetSection]
    validation_results: dict[str, Any] = field(default_factory=dict)


_FORBIDDEN_OUTPUT_PATTERNS = [
    "Quality Checklist",
    "AI-generated",
    "AI generation",
    "placeholder",
    "TODO",
    "internal review",
    "copied exactly from",
    "SOP internal",
]

_L3_MIA_EXPECTED_PAGES = {
    2: "Mia has many things to do this week.",
    3: "She has homework to finish. Her room is messy.",
    4: "The piano show is on Sunday. Mia wants to play well.",
    5: "Mia feels worried. She makes a seven-day plan.",
    6: "She will do homework first. She will clean her room on Tuesday.",
    7: "She will practice the piano every day. She will play for one hour a day.",
    8: "Mia is happy and proud of her plan.",
}

_L3_MIA_FORBIDDEN_CLAIMS = [
    "Mia follows her plan",
    "Mia completes all her tasks",
    "Mia succeeds at the piano show",
    "excited at the start",
]

_BEHAVIOR_VERBS = {
    "identify", "match", "sequence", "use", "answer", "retell", "compare",
    "predict", "confirm", "write", "organize", "describe", "explain", "practice",
}


def normalize_text(text: str) -> str:
    text = (text or "").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def printed_story_pages(outline: BookOutline) -> list[TGBookPage]:
    pages: list[TGBookPage] = []
    for page in outline.pages:
        if page.page_type == "story" and (page.text or "").strip():
            pages.append(
                TGBookPage(
                    printed_page=page.index + 1,
                    text=normalize_text(page.text),
                    image_summary=getattr(page, "scene", "") or getattr(page, "scene_cn", ""),
                    characters=[],
                    visible_clues=[x for x in (getattr(page, "hook", ""), getattr(page, "focus", "")) if x],
                )
            )
    return pages


def build_tg_context(outline: BookOutline, worksheet_sections: list[dict] | None = None) -> TGContext:
    pages = printed_story_pages(outline)
    words = _core_vocab(outline)
    worksheet = _worksheet_sections_from_dicts(worksheet_sections or [])
    return TGContext(
        book_metadata={
            "title": outline.title,
            "level": _level_label(outline.level),
            "book_number": getattr(outline, "book_number", "") or "",
            "cefr": outline.cefr or "",
            "lexile": outline.lexile or "",
            "word_count": sum(len(re.findall(r"\b\w+\b", p.text)) for p in pages),
            "genre": "Nonfiction" if _is_nonfiction(outline) else "Fiction",
            "theme": outline.theme or "",
        },
        instructional_focus={
            "core_vocabulary": words,
            "language_focus": _language_focus(outline),
            "reading_strategy": _english_name(getattr(outline, "reading_strategy", "")) or "Predicting",
            "reading_skill": _english_name(getattr(outline, "reading_skill", "")) or "Sequence Events",
            "phonics_focus": {
                "raw": outline.phonics or "",
                "book_words": _phonics_book_words(outline),
            },
        },
        book_pages=pages,
        story_analysis=_story_analysis(outline),
        worksheet_sections=worksheet,
    )


def validate_tg_preflight(ctx: TGContext) -> list[TGValidationIssue]:
    issues: list[TGValidationIssue] = []
    issues.extend(_validate_l3_mia_pages(ctx))
    if not ctx.instructional_focus["core_vocabulary"]:
        issues.append(TGValidationIssue("BLOCKER", "core_vocab_missing", "Core Vocabulary is missing."))
    if not ctx.book_pages:
        issues.append(TGValidationIssue("BLOCKER", "book_pages_missing", "Book page text is missing."))
    for word in ctx.instructional_focus["phonics_focus"].get("book_words", []):
        if word.lower() not in " ".join(p.text.lower() for p in ctx.book_pages):
            issues.append(TGValidationIssue("BLOCKER", "phonics_word_not_in_book", f"Phonics word not found in book text: {word}"))
    _raise_blockers(issues)
    return issues


def validate_tg_output(ctx: TGContext, text: str, picture_walk_rows: list[dict] | None = None) -> list[TGValidationIssue]:
    norm = normalize_text(text)
    issues: list[TGValidationIssue] = []
    issues.extend(_validate_forbidden_output(norm))
    issues.extend(_validate_page_quotes(ctx, norm))
    issues.extend(_validate_l3_mia_output(ctx, norm))
    issues.extend(_validate_strategy_coverage(ctx, norm))
    issues.extend(_validate_picture_walk_repetition(picture_walk_rows or []))
    _raise_blockers(issues)
    return issues


def assert_behavior_objectives(objectives: list[str]) -> None:
    bad = []
    for obj in objectives:
        low = obj.lower()
        if not any(re.search(rf"\b{verb}\b", low) for verb in _BEHAVIOR_VERBS):
            bad.append(obj)
    if bad:
        raise TGQualityError("TG objective lacks observable behavior verb: " + "; ".join(bad))


def tg_doc_text(doc) -> str:
    parts: list[str] = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _validate_l3_mia_pages(ctx: TGContext) -> list[TGValidationIssue]:
    if not _is_l3_mia(ctx):
        return []
    issues: list[TGValidationIssue] = []
    actual = {p.printed_page: normalize_text(p.text) for p in ctx.book_pages}
    for page, expected in _L3_MIA_EXPECTED_PAGES.items():
        got = actual.get(page, "")
        if normalize_text(got) != normalize_text(expected):
            issues.append(TGValidationIssue(
                "BLOCKER",
                "l3_mia_page_text_mismatch",
                f"L3-1 page {page} text mismatch. Expected: {expected} Got: {got}",
            ))
    return issues


def _validate_forbidden_output(text: str) -> list[TGValidationIssue]:
    issues = []
    low = text.lower()
    for pattern in _FORBIDDEN_OUTPUT_PATTERNS:
        if pattern.lower() in low:
            issues.append(TGValidationIssue("BLOCKER", "forbidden_output_text", f"Forbidden TG output text found: {pattern}"))
    return issues


def _validate_page_quotes(ctx: TGContext, text: str) -> list[TGValidationIssue]:
    issues: list[TGValidationIssue] = []
    actual = {p.printed_page: normalize_text(p.text) for p in ctx.book_pages}
    labels = list(re.finditer(r"Page\s+(\d+):\s*Teacher reads:\s*", text))
    seen_pages: set[int] = set()
    for i, match in enumerate(labels):
        page = int(match.group(1))
        seen_pages.add(page)
        expected = actual.get(page)
        if expected is None:
            issues.append(TGValidationIssue("BLOCKER", "quote_page_missing", f"TG quotes missing book page {page}."))
            continue
        end = labels[i + 1].start() if i + 1 < len(labels) else len(text)
        segment = text[match.end():end]
        # Page text can itself contain dialogue quotes, so do not capture by the
        # next quote mark. Instead, verify the full normalized book text appears
        # inside the page's own Teacher reads segment.
        if expected not in segment:
            issues.append(TGValidationIssue("BLOCKER", "quote_text_mismatch", f"TG quote for Page {page} does not match book text."))
    for page in actual:
        if page not in seen_pages:
            issues.append(TGValidationIssue("BLOCKER", "quote_page_missing", f"TG quote for Page {page} is missing."))
    return issues


def _validate_l3_mia_output(ctx: TGContext, text: str) -> list[TGValidationIssue]:
    if not _is_l3_mia(ctx):
        return []
    issues: list[TGValidationIssue] = []
    low = text.lower()
    for claim in _L3_MIA_FORBIDDEN_CLAIMS:
        if claim.lower() in low:
            issues.append(TGValidationIssue("BLOCKER", "unsupported_l3_mia_claim", f"Unsupported L3-1 claim found: {claim}"))
    bad_bank = re.search(r"word bank(?:\s*\(max\s*8\s*words\))?:\s*week,\s*homework,\s*plan,\s*practice", low)
    if bad_bank:
        issues.append(TGValidationIssue("BLOCKER", "plan_chart_word_bank_core_vocab", "Plan Chart Word Bank must not be core vocabulary."))
    return issues


def _validate_strategy_coverage(ctx: TGContext, text: str) -> list[TGValidationIssue]:
    strategy = (ctx.instructional_focus.get("reading_strategy") or "").lower()
    if "predict" not in strategy:
        return []
    low = text.lower()
    checks = {
        "pre_or_picture_walk": ("predict" in low and "picture walk" in low),
        "during_reading": ("prediction" in low or "predict" in low) and ("detailed reading" in low or "pause" in low),
        "lesson_close": ("lesson close" in low and ("prediction" in low or "predict" in low)),
    }
    if all(checks.values()):
        return []
    return [TGValidationIssue("HIGH", "reading_strategy_coverage", f"Predicting coverage incomplete: {checks}")]


def _validate_picture_walk_repetition(rows: list[dict]) -> list[TGValidationIssue]:
    issues: list[TGValidationIssue] = []
    for prev, cur in zip(rows, rows[1:]):
        for key in ("teacher_action", "teacher_asks"):
            a = normalize_text(prev.get(key, ""))
            b = normalize_text(cur.get(key, ""))
            if a and b and SequenceMatcher(None, a, b).ratio() > 0.82:
                issues.append(TGValidationIssue("HIGH", "picture_walk_repetition", f"Picture Walk {key} is overly repetitive on adjacent pages."))
    return issues


def _raise_blockers(issues: list[TGValidationIssue]) -> None:
    blockers = [x for x in issues if x.severity == "BLOCKER"]
    if blockers:
        msg = "\n".join(f"[{x.code}] {x.message}" for x in blockers)
        raise TGQualityError(msg)


def _worksheet_sections_from_dicts(rows: list[dict]) -> list[TGWorksheetSection]:
    out = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        bank = row.get("word_bank") or row.get("words") or []
        if isinstance(bank, str):
            bank = [x.strip() for x in re.split(r"[,;/]", bank) if x.strip()]
        answers = row.get("answer_key") or []
        if isinstance(answers, str):
            answers = [x.strip() for x in re.split(r";|\n", answers) if x.strip()]
        out.append(TGWorksheetSection(
            section_number=i,
            title=str(row.get("title") or ""),
            instructions=str(row.get("instruction") or row.get("instructions") or ""),
            word_bank=[str(x) for x in bank],
            answer_key=[str(x) for x in answers],
            open_response=bool(row.get("open_response")),
        ))
    return out


def _story_analysis(outline: BookOutline) -> dict[str, Any]:
    text = " ".join(p.text for p in printed_story_pages(outline)).lower()
    if "seven-day plan" in text and "homework" in text:
        return {
            "story_structure": "Problem - Plan - Result",
            "problem": "Mia has many things to do and feels worried.",
            "plan_or_events": ["Mia makes a seven-day plan.", "Mia organizes tasks by time and order."],
            "result": "Mia feels happy and proud of her plan.",
            "explicit_facts": [p.text for p in printed_story_pages(outline)],
            "safe_inferences": ["Mia uses a plan to organize her tasks."],
            "emotion_arc": [
                {"pages": "2-4", "emotion": "concerned / worried", "evidence": "Many things to do; messy room; piano show on Sunday."},
                {"pages": "5-7", "emotion": "worried, then organized", "evidence": "Mia feels worried and makes a seven-day plan."},
                {"pages": "8", "emotion": "happy and proud", "evidence": "Mia is happy and proud of her plan."},
            ],
        }
    return {
        "story_structure": "Before - Event - After",
        "explicit_facts": [p.text for p in printed_story_pages(outline)],
        "safe_inferences": [],
        "emotion_arc": [],
    }


def _is_l3_mia(ctx: TGContext) -> bool:
    meta = ctx.book_metadata
    return str(meta.get("level")) == "3" and "mia and the seven-day plan" in str(meta.get("title", "")).lower()


def _core_vocab(outline: BookOutline) -> list[str]:
    if getattr(outline, "vocabulary_simple", None):
        return list(outline.vocabulary_simple)
    return list(getattr(outline, "vocabulary_mastery", []) or [])


def _language_focus(outline: BookOutline) -> list[str]:
    raw = outline.grammar_focus or ""
    if "[subject]" in raw.lower() and "will" in raw.lower():
        return ["Subject + will + base verb"]
    return [normalize_text(raw)] if raw else []


def _phonics_book_words(outline: BookOutline) -> list[str]:
    raw = (outline.phonics or "").lower()
    keys = [k for k in ("ay", "ee", "ai", "oa", "igh", "sh", "ch", "th") if k in raw]
    words: list[str] = []
    seen = set()
    for page in printed_story_pages(outline):
        for word in re.findall(r"[A-Za-z][A-Za-z'-]*", page.text):
            clean = word.strip("'")
            lw = clean.lower()
            if any(k in lw for k in keys) and lw not in seen:
                seen.add(lw)
                words.append(clean)
    return words[:6]


def _english_name(text: str) -> str:
    text = normalize_text(text)
    if not text:
        return ""
    match = re.search(r"\(([^()]+)\)", text)
    if match and re.search(r"[A-Za-z]", match.group(1)):
        return match.group(1).strip()
    return re.sub(r"[\u4e00-\u9fff]+", "", text).strip(" -/")


def _level_label(level: str) -> str:
    digits = "".join(ch for ch in str(level or "") if ch.isdigit())
    return digits or str(level or "").strip()


def _is_nonfiction(outline: BookOutline) -> bool:
    ft = (getattr(outline, "fiction_type", "") or "").lower()
    rt = (getattr(outline, "reader_type", "") or "").lower()
    return ft.startswith("non") or "nonfiction" in rt or "non-fiction" in rt
