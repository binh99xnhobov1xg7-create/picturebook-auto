"""按「级别 + 编号」从官方 S&S 大纲取本并跑整本流水线（绘本+WS+RR+TG+ZIP）。

用法：
  python scripts/run_syllabus_book.py --level 3 --number 64
  python scripts/run_syllabus_book.py --level 3 --number 69 --mock   # 不调 API 走占位（验流程）

编号口径：L{level} 第 N 本 = 该级别大纲里第 N 条（课程顺序，1 起）。
正文取自大纲 pure_text（命中大纲时词表/拼读/题目按大纲 verbatim）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from syllabus import get_by_number, list_level
from batch_runner import BatchItem, run_one
from config import OUTPUTS_DIR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", required=True)
    ap.add_argument("--number", type=int, required=True)
    ap.add_argument("--mock", action="store_true", help="不调用 API，用占位图（仅验流程）")
    ap.add_argument("--workers", type=int, default=4, help="本本内出图并发")
    args = ap.parse_args()

    e = get_by_number(str(args.level), args.number)
    if e is None:
        avail = list_level(str(args.level))
        nums = [x.book_number for x in avail if x.book_number]
        raise SystemExit(
            f"L{args.level} 第 {args.number} 本未找到（按官方 Book No.）。"
            f"该级别现有书号：{nums[:5]}…共{len(nums)}本。"
        )
    title = e.title or f"L{args.level} Book {args.number}"
    story = e.pure_text or e.text_7page or e.reader_text or ""
    genre = (e.genre or "").lower()
    fiction_type = "non-fiction" if genre == "nonfiction" else ("fiction" if genre == "fiction" else "")

    item = BatchItem(
        title=title, level=str(args.level), book_number=f"{args.number:02d}",
        story=story, fiction_type=fiction_type,
    )
    out_root = OUTPUTS_DIR / f"L{args.level}_book{args.number:02d}"
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"=== RUN L{args.level} #{args.number}: {title} "
          f"({genre or 'auto'}, {len(story.split())} words){' [MOCK]' if args.mock else ''} ===",
          flush=True)
    res = run_one(item, out_root, mock=args.mock, image_workers=args.workers)
    print(f"STATUS: {res.status}  elapsed: {res.elapsed_s:.1f}s", flush=True)
    print(f"EVAL: {res.eval_level or '—'}  needs_review: {res.needs_human_review}", flush=True)
    for m in (res.eval_msgs or []):
        print(f"  • {m}", flush=True)
    for o in (res.outputs or []):
        print(f"OUT: {o}", flush=True)
    print(f"ZIP: {res.zip_path}", flush=True)
    if res.error:
        print(f"ERR: {res.error[:800]}", flush=True)
    print("=== DONE ===", flush=True)


if __name__ == "__main__":
    main()
