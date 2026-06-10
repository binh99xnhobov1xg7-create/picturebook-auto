# -*- coding: utf-8 -*-
"""即梦4.6 画风落地 · 两条路对比（用户拍板 2026-06-08：compare_both）。

同一页（L5 P1·Anna 单人）出两张，公平对比"贴近即梦4.6 画风"的两条路：
  A 组 = 纯 GPT 出图（gpt-image-2）：保留人物定妆锚图 + 已按样书校准的画风提示词（首尾双置）。
  B 组 = GPT 打底 → 即梦4.6 图生图换皮：内容/IP/构图用 GPT 保真，最终像素由即梦渲染（100% 同款画风）。

两组均关闭"视觉自审/4K"，只看单次原始输出，公平对比。参考图锚定逻辑与线上一致。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import seedream_client as sc
from parser import parse_outline_file
from cn_prompt_builder import build_cn_page_prompt

sc.IMAGE_SELF_REVIEW = False  # 公平对比：只看单次原始输出

INPUT = ROOT.parent / "inputs" / "L5_Book01_What_Makes_a_Good_Friend.md"
OUT = ROOT.parent / "outputs" / "_test_gpt"
OUT.mkdir(parents=True, exist_ok=True)


def _ref_names(built):
    by = {}
    for c in (built.used_characters or []):
        if c.get("ref_path"):
            by[str(Path(c["ref_path"]))] = c.get("name") or ""
    return [by.get(str(Path(r)), "") for r in built.references]


def _anchor(built):
    """单角色 → 贴身裁切单锚图 + 锁形 note（与线上 _maybe_build_reference_sheet 等价的单人分支）。"""
    refs = built.references
    names = _ref_names(built)
    local = [Path(r) for r in refs if r and Path(str(r)).exists()]
    if not local:
        return list(refs), ""
    primary = local[0]
    dest = OUT / "_anchors" / "cmp_anchor_p01.png"
    a = sc.crop_character_portrait(primary, dest) or primary
    nm = (names[0] if names else "") or "主角"
    note = (
        f"【参考图＝{nm} 官方定妆图（连续性绘本·形象永久锁定）】所附唯一参考图是 {nm} 的单人定妆图"
        "（贴身裁切、干净背景）。请把其脸型、五官、发型、发色、肤色、服装款式与配色 1:1 精确还原，"
        "与定妆图完全一致；【唯一允许改变的是该角色的姿势/动作与表情】，不要照搬参考图的背景或姿势。"
    )
    return [a], note


def main() -> None:
    outline = parse_outline_file(INPUT)
    ip_age = outline.ip_age or 12
    page = next(p for p in outline.pages if p.index == 1)
    built = build_cn_page_prompt(page, outline, ip_age)
    anchored, note = _anchor(built)
    prompt = built.prompt + (("\n\n" + note) if note else "")
    print(f">> P1 cast={[c.get('name') for c in built.used_characters]} anchor={[Path(a).name for a in anchored]}")

    # A 组：纯 GPT（level 5 → 纯 gpt-image-2，画风指令已在函数内首尾双置）
    print(">> [A] 纯 GPT 出图 ...")
    t0 = time.time()
    destA = OUT / "CMP_A_pureGPT.png"
    sc.generate_image_for_level("5", prompt=prompt, dest=destA,
                                references=anchored, label="CMP-A-pureGPT", deliver_print=False)
    print(f"   [A] 完成 {destA} 用时 {time.time()-t0:.0f}s")

    # B 组：GPT 打底 → 即梦4.6 换皮
    print(">> [B] GPT 打底 → 即梦换皮 ...")
    t0 = time.time()
    destB = OUT / "CMP_B_gpt_then_jimeng.png"
    sc.generate_image_gpt_base_jimeng_style(prompt=prompt, dest=destB,
                                            references=anchored, label="CMP-B-jimeng", deliver_print=False)
    print(f"   [B] 完成 {destB} 用时 {time.time()-t0:.0f}s")

    print("\n对比完成：")
    print(f"  A 纯GPT          ：{destA}")
    print(f"  B GPT打底+即梦换皮：{destB}")


if __name__ == "__main__":
    main()
