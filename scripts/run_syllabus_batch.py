"""按【级别 + 官方书号列表】批量跑多本（绘本+WS+RR+TG+ZIP），含抽取串行锁+出图并发+体检+日志。

用法：
  python scripts/run_syllabus_batch.py --level 3 --numbers 3,6,9,...
  python scripts/run_syllabus_batch.py --level 3 --numbers 3,6 --mock   # 不调 API 验流程

编号 = 官方 Book No.（syllabus.get_by_number），正文取自大纲 pure_text。
每完成一本打印一行状态（status/eval/review/用时/错误），便于后台监督。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from syllabus import get_by_number
from batch_runner import BatchItem, BatchResult, run_batch
from config import OUTPUTS_DIR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", required=True)
    ap.add_argument("--numbers", required=True, help="逗号分隔的官方书号，如 3,6,9")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--book-concurrency", type=int, default=2)
    ap.add_argument("--image-concurrency", type=int, default=4)
    args = ap.parse_args()

    nums = []
    for x in args.numbers.replace(" ", "").split(","):
        x = x.strip()
        if x:
            try:
                nums.append(int(x))
            except ValueError:
                pass

    items: list[BatchItem] = []
    missing: list[int] = []
    for n in nums:
        e = get_by_number(str(args.level), n)
        if e is None:
            missing.append(n)
            continue
        story = e.pure_text or e.text_7page or e.reader_text or ""
        ft = "non-fiction" if e.genre == "nonfiction" else ("fiction" if e.genre == "fiction" else "")
        items.append(BatchItem(title=e.title, level=str(args.level),
                               book_number=f"{n:02d}", story=story, fiction_type=ft))

    if missing:
        print(f"MISSING book numbers (skipped): {missing}", flush=True)
    if not items:
        raise SystemExit("没有可跑的本。")

    out_root = OUTPUTS_DIR / f"L{args.level}_batch_{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"=== BATCH L{args.level}: {len(items)} books "
          f"(book_conc={args.book_concurrency}, img_conc={args.image_concurrency})"
          f"{' [MOCK]' if args.mock else ''} -> {out_root} ===", flush=True)
    for it in items:
        print(f"  queued: #{it.book_number} {it.title} ({it.fiction_type or 'auto'})", flush=True)

    def cb(done: int, total: int, r: BatchResult) -> None:
        msg = (f"[{done}/{total}] DONE #{r.item.book_number} {r.item.title} | "
               f"status={r.status} eval={r.eval_level or '-'} review={r.needs_human_review} "
               f"{r.elapsed_s:.0f}s")
        if r.eval_msgs:
            msg += " | " + " ; ".join(r.eval_msgs[:4])
        if r.error:
            msg += " | ERR " + r.error[:160].replace("\n", " ")
        print(msg, flush=True)

    summary = run_batch(
        items, out_root=out_root,
        concurrency=args.book_concurrency, image_concurrency=args.image_concurrency,
        mock=args.mock, progress_cb=cb,
    )
    print(f"=== SUMMARY ok={summary['ok']} failed={summary['failed']} "
          f"need_review={summary.get('need_review', 0)} clean={summary.get('clean_pass', 0)} ===",
          flush=True)
    print(f"LOG: {summary.get('log_path')}", flush=True)
    print(f"ALL_BOOKS_ZIP: {summary.get('master_zip')}", flush=True)
    print("=== BATCH DONE ===", flush=True)


if __name__ == "__main__":
    main()
