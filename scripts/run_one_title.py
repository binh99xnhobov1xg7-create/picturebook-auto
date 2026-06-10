"""按【级别 + 书名】真跑单本（即梦出图 + GPT 视觉自审定向修图），用于单本验证/复跑。

用法：
  python scripts/run_one_title.py --level 0 --title "My Family"
  python scripts/run_one_title.py --level 0 --title "My Family" --mock

L0-2 没有官方 Book No.，按标题精确匹配大纲取正文；出图走即梦双段（IMAGE_SELF_REVIEW 开则自审）。
每页的 [即梦出图]/[review] 日志会实时打印，便于盯 IP/六指/图文匹配/分身/比例 问题。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from syllabus import list_level
from batch_runner import BatchItem, run_one
from config import OUTPUTS_DIR, IMAGE_SELF_REVIEW, resolve_image_backend


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower().strip() if ch.isalnum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--number", default="", help="仅用于输出文件名前缀，可留空")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--image-workers", type=int, default=4)
    args = ap.parse_args()

    rows = list_level(str(args.level))
    want = _norm(args.title)
    exact = [r for r in rows if _norm(r.title) == want]
    cand = exact or [r for r in rows if want in _norm(r.title)]
    if not cand:
        raise SystemExit(f"L{args.level} 未找到书名包含「{args.title}」的大纲条目。")
    if len(cand) > 1:
        print("匹配到多本，取第 1 本；其余：", [r.title for r in cand[1:]], flush=True)
    e = cand[0]
    story = e.pure_text or e.text_7page or e.reader_text or ""
    ft = "non-fiction" if e.genre == "nonfiction" else ("fiction" if e.genre == "fiction" else "")

    item = BatchItem(title=e.title, level=str(args.level),
                     book_number=(args.number or "00"), story=story, fiction_type=ft)
    out_root = OUTPUTS_DIR / f"L{args.level}_single_{_norm(e.title)[:20]}_{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"=== RUN L{args.level} 「{e.title}」 genre={e.genre} backend={resolve_image_backend(str(args.level))} "
          f"self_review={IMAGE_SELF_REVIEW}{' [MOCK]' if args.mock else ''} -> {out_root} ===", flush=True)
    print(f"STORY: {story[:300]}", flush=True)

    t0 = time.time()
    r = run_one(item, out_root=out_root, mock=args.mock, image_workers=args.image_workers)
    print(f"=== DONE status={r.status} eval={r.eval_level or '-'} review={r.needs_human_review} "
          f"{time.time() - t0:.0f}s ===", flush=True)
    if r.eval_msgs:
        for m in r.eval_msgs:
            print("  EVAL:", m, flush=True)
    if r.error:
        print("  ERR:", r.error[:300], flush=True)
    print(f"OUT: {out_root}", flush=True)
    print("=== SINGLE DONE ===", flush=True)


if __name__ == "__main__":
    main()
