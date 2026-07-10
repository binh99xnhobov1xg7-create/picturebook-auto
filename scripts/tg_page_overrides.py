"""Verified official story page text overrides.

Use only when the official S&S source provides one continuous story string but
the book's printed page breaks are known. This prevents sentence averaging from
creating incorrect page text for TG/RR/Worksheet evidence.
"""
from __future__ import annotations

import re
from typing import Any


OFFICIAL_PAGE_TEXT_OVERRIDES: dict[tuple[str, str, str], list[str]] = {
    (
        "3",
        "1",
        "mia and the seven-day plan",
    ): [
        "Mia has many things to do this week.",
        "She has homework to finish. Her room is messy.",
        "The piano show is on Sunday. Mia wants to play well.",
        "Mia feels worried. She makes a seven-day plan.",
        "She will do homework first. She will clean her room on Tuesday.",
        "She will practice the piano every day. She will play for one hour a day.",
        "Mia is happy and proud of her plan.",
    ],
}


def official_page_text_override(outline: Any) -> list[str] | None:
    level = "".join(ch for ch in str(getattr(outline, "level", "") or "") if ch.isdigit())
    book = str(getattr(outline, "book_number", "") or "").lstrip("0") or str(getattr(outline, "book_number", "") or "")
    title = re.sub(r"\s+", " ", (getattr(outline, "title", "") or "").strip().lower())
    return OFFICIAL_PAGE_TEXT_OVERRIDES.get((level, book, title))
