"""L3 批量编排器（单一长驻进程）：用进程池并发跑多本，每本 = 一个独立 py 子进程。

设计目标：
- 防交叉污染：每本书都 spawn 一个全新的 `py scripts/_rerun_one_fresh.py <bn>` 子进程，
  book_cast / scene / cast 等状态绝不跨书共享（与逐本独立进程等价）。
- 只占用 1 个 Cursor 后台 shell（编排器自己），子进程是普通 OS 进程，规避后台 shell 数量上限。
- 并发 2（默认），跑完一本补下一本，直到全部完成。
- 每本输出到独立日志；编排器持续写 _orch_status.json，便于外部轮询。
- 断点续跑：已生成完整 4 件套 + 8 张真实页图的书自动跳过（除非 FORCE=1）。

用法：
  py scripts/_orchestrate_l3.py 48 54 57 60 63 66 69 72
  # 可选环境变量： ORCH_CONCURRENCY=2  ORCH_FORCE=1
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
from config import OUTPUTS_DIR  # noqa: E402

OUT_ROOT = OUTPUTS_DIR / "L3_batch"
OUT_ROOT.mkdir(parents=True, exist_ok=True)
STATUS_PATH = OUT_ROOT / "_orch_status.json"

CONCURRENCY = int(os.getenv("ORCH_CONCURRENCY", "2"))
FORCE = os.getenv("ORCH_FORCE", "0") in ("1", "true", "yes")
PLACEHOLDER_MAX_BYTES = 60 * 1024  # < 60KB 视为失败占位（真实页图通常 2-5MB）

# 书号 -> 输出文件夹名片段（用于续跑判定）。运行时再用 xlsx 真标题校正。
PY = sys.executable or "py"


def _book_dirs():
    return {d.name: d for d in OUT_ROOT.iterdir() if d.is_dir()} if OUT_ROOT.exists() else {}


def _find_book_dir(bn: int):
    prefix = f"Level 3_Book{bn}_"
    for name, d in _book_dirs().items():
        if name.startswith(prefix):
            return d
    return None


def _is_complete(bn: int) -> bool:
    d = _find_book_dir(bn)
    if not d:
        return False
    imgs = d / "images"
    pages = sorted(imgs.glob("page_0*.png")) if imgs.exists() else []
    if len(pages) < 8:
        return False
    if any(p.stat().st_size < PLACEHOLDER_MAX_BYTES for p in pages):
        return False
    need_suffix = ["_Reader.pptx", "_Worksheet.pptx", "_Reading_Report.docx", "_Teachers_Guide.docx"]
    files = {f.name for f in d.glob("*")}
    for suf in need_suffix:
        if not any(n.endswith(suf) for n in files):
            return False
    return True


def _write_status(state: dict):
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    STATUS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    books = [int(x) for x in sys.argv[1:]]
    if not books:
        raise SystemExit("用法: py scripts/_orchestrate_l3.py 48 54 ...")

    state = {
        "concurrency": CONCURRENCY, "force": FORCE,
        "books": {str(b): {"status": "queued"} for b in books},
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    queue = list(books)
    # 续跑：跳过已完整的本
    if not FORCE:
        for b in list(queue):
            if _is_complete(b):
                state["books"][str(b)] = {"status": "skipped_complete"}
                print(f"[ORCH] book {b} 已完整，跳过（FORCE=1 可强制重跑）", flush=True)
                queue.remove(b)
    _write_status(state)

    running = {}  # bn -> (Popen, logfile_handle, start_ts)

    def _launch(bn: int):
        log_path = OUT_ROOT / f"_run_{bn}.log"
        fh = open(log_path, "w", encoding="utf-8", errors="replace")
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            [PY, "-u", "scripts/_rerun_one_fresh.py", str(bn)],
            stdout=fh, stderr=subprocess.STDOUT, env=env,
            cwd=str(Path.cwd()),
        )
        running[bn] = (proc, fh, time.time())
        state["books"][str(bn)] = {"status": "running", "pid": proc.pid,
                                   "log": str(log_path), "start": time.strftime("%H:%M:%S")}
        _write_status(state)
        print(f"[ORCH] launched book {bn} pid={proc.pid} -> {log_path}", flush=True)

    # 先填满并发槽
    while queue and len(running) < CONCURRENCY:
        _launch(queue.pop(0))

    while running:
        time.sleep(5)
        done_bns = []
        for bn, (proc, fh, t0) in running.items():
            rc = proc.poll()
            if rc is not None:
                done_bns.append((bn, rc, time.time() - t0))
        for bn, rc, elapsed in done_bns:
            proc, fh, t0 = running.pop(bn)
            try:
                fh.flush(); fh.close()
            except Exception:
                pass
            complete = _is_complete(bn)
            ok = (rc == 0) and complete
            d = _find_book_dir(bn)
            state["books"][str(bn)] = {
                "status": "done" if ok else "failed",
                "returncode": rc, "elapsed_s": round(elapsed, 1),
                "complete_deliverables": complete,
                "out_dir": str(d) if d else "",
            }
            _write_status(state)
            tag = "DONE" if ok else "FAILED"
            print(f"[ORCH] book {bn} {tag} rc={rc} complete={complete} elapsed={elapsed:.0f}s", flush=True)
            # 补下一本
            if queue:
                _launch(queue.pop(0))

    state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    n_ok = sum(1 for v in state["books"].values() if v.get("status") in ("done", "skipped_complete"))
    n_fail = sum(1 for v in state["books"].values() if v.get("status") == "failed")
    state["summary"] = {"ok": n_ok, "failed": n_fail, "total": len(books)}
    _write_status(state)
    print(f"\n[ORCH] ALL FINISHED ok={n_ok} failed={n_fail} total={len(books)}", flush=True)
    print("ORCH_ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
