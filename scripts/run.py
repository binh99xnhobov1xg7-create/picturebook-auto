#!/usr/bin/env python3
"""绘本自动化入口：outline.md → 9 张水彩图 + 9 页 PPT。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# 让本目录可以直接 import 同级模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import INPUTS_DIR, JIMENG_API_KEY, JIMENG_MODEL, MOCK_IMAGES, OUTPUTS_DIR, resolve_ip_age  # noqa: E402
from parser import parse_outline_file  # noqa: E402
from ppt_builder import build_picturebook_pptx, safe_filename  # noqa: E402
from prompt_builder import build_page_prompt  # noqa: E402
from seedream_client import generate_image  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="绘本流水线：解析大纲 → 即梦 4.6 生图 → 组装 9 页 PPT"
    )
    ap.add_argument("--outline", "-i", type=Path, required=True,
                    help="大纲 markdown 路径（如 inputs/L4_Book13_Visiting_Scotland.md）")
    ap.add_argument("--output", "-o", type=Path, default=None,
                    help="输出目录（默认 outputs/<slug>/）")
    ap.add_argument("--mock-images", action="store_true",
                    help="不调即梦 API，生成占位图（用于本地调试 PPT 版式）")
    ap.add_argument("--real-images", action="store_true",
                    help="强制调即梦 API（需 JIMENG_API_KEY / ARK_API_KEY）")
    ap.add_argument("--pages", default="",
                    help="仅重生指定页（逗号分隔，0=封面，1-7=故事）。其余页沿用已有 png。")
    ap.add_argument("--no-images", action="store_true",
                    help="完全跳过生图，仅用已有 png 重组 PPT（改字体/版式调整后用）")
    args = ap.parse_args()

    outline_path: Path = args.outline.resolve()
    if not outline_path.exists():
        # 兼容相对 inputs/ 的写法
        alt = (INPUTS_DIR / args.outline.name).resolve()
        if alt.exists():
            outline_path = alt
        else:
            print(f"[ERROR] 找不到大纲文件：{args.outline}")
            return 1

    print(f"[parse] {outline_path}")
    book = parse_outline_file(outline_path)
    ip_age = resolve_ip_age(book.level, book.ip_age)
    print(f"  书名：{book.title}")
    print(f"  级别：L{book.level or '?'} / CEFR {book.cefr or '?'}")
    print(f"  IP 年龄档：{ip_age} 岁")
    print(f"  页面：{len(book.pages)}（封面 + 7 故事，元信息页独立生成）")

    out_dir = args.output or (OUTPUTS_DIR / book.slug)
    img_dir = out_dir / "images"
    prompt_dir = out_dir / "prompts"
    img_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)

    mock = MOCK_IMAGES
    if args.mock_images:
        mock = True
    if args.real_images:
        mock = False
    if not mock and not JIMENG_API_KEY:
        print("[WARN] 未配置 JIMENG_API_KEY / ARK_API_KEY，自动降级到 mock 模式。")
        mock = True

    selected_pages: set[int] | None = None
    if args.no_images:
        selected_pages = set()  # 空集合 = 任何页都不重生
    elif args.pages.strip():
        try:
            selected_pages = {int(x) for x in args.pages.split(",") if x.strip()}
        except ValueError:
            print(f"[ERROR] --pages 参数无法解析为整数：{args.pages}")
            return 1

    if args.no_images:
        print("\n[generate] --no-images：完全跳过生图，仅重组 PPT")
    elif selected_pages is not None:
        print(f"\n[generate] 仅重生页：{sorted(selected_pages)}（其余页沿用现有 png）"
              + ("（mock 占位）" if mock else f"（模型 {JIMENG_MODEL}）"))
    else:
        print("\n[generate] 生成 8 张插画（封面 + 7 故事，4:3 水彩）"
              + ("（mock 占位）" if mock else f"（模型 {JIMENG_MODEL}）"))

    image_paths: list[Path] = []
    for page in book.pages:  # 共 8 个 PageSpec
        dest = img_dir / f"page_{page.index:02d}.png"
        if selected_pages is not None and page.index not in selected_pages:
            if dest.exists():
                print(f"  [skip] {dest.name}  ({dest.stat().st_size // 1024} KB, reused)")
                image_paths.append(dest)
                continue
            print(f"  [WARN] {dest.name} 不存在但被跳过，强制重生")

        built = build_page_prompt(page, book, ip_age)
        prompt_file = prompt_dir / f"page_{page.index:02d}_prompt.txt"
        prompt_file.write_text(built.prompt, encoding="utf-8")

        try:
            generate_image(
                prompt=built.prompt,
                dest=dest,
                references=built.references,
                mock=mock,
                label=page.label,
            )
            print(f"  [OK] {dest.name}  ({dest.stat().st_size // 1024} KB)")
        except Exception as e:
            print(f"  [FAIL] {dest.name}: {e}")
            raise
        image_paths.append(dest)

    print("\n[compose] 组装 9 页 PPT…")
    ppt_path = out_dir / safe_filename(book.title)
    build_picturebook_pptx(book, image_paths, ppt_path)

    summary = out_dir / "README.txt"
    summary.write_text(
        f"绘本：{book.title}\n"
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}\n"
        f"PPT：{ppt_path}\n"
        f"图片：{img_dir}\n"
        f"提示词：{prompt_dir}\n"
        f"IP 年龄档：{ip_age} 岁\n"
        f"模型：{JIMENG_MODEL if not mock else 'mock'}\n",
        encoding="utf-8",
    )

    print("\n完成。")
    print(f"  PPT  → {ppt_path}")
    print(f"  图片 → {img_dir}")
    print(f"  提示词 → {prompt_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
