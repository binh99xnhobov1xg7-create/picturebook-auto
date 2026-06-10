# -*- coding: utf-8 -*-
"""临时脚本：重画 Mia 定妆图为【枕骨上方·中高马尾 + 辫尾过肩胛】发型。

用现有定妆图做图生图参考（锁住治愈水彩画风/服装/三视图+表情版式/左上角姓名年龄标签/白底），
唯一改动＝把所有视图（正/侧/背/表情）的发型从旧版改成【中高马尾 mid-high ponytail】：
  · 发髻在【后脑枕骨上方、耳上沿稍上】，绝不在头顶正中/颅顶；
  · 马尾辫自然垂落、发尾至少到【肩胛骨下缘/上背中部】，长度明显可见、不是短穗；
  · 全部头发收拢束起、不留大片披散，前面可留极少量碎发框脸。

用法：
  py scripts/_mia_ponytail_regen.py 10 2     # 为 10 岁出 2 张候选
候选写到 D:\\picturebook_outputs\\_mia_ref_new\\mia_{age}_pony_candK.png（1536x1024，不裁切/不印刷放大）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seedream_client import generate_image, host_image_to_url  # noqa: E402

REF = {
    8: Path(r"C:\Users\Jered\picturebook-auto\assets\ip_library\mia_8.png"),
    10: Path(r"C:\Users\Jered\picturebook-auto\assets\ip_library\mia_10.png"),
    12: Path(r"C:\Users\Jered\picturebook-auto\assets\ip_library\mia_12.png"),
}

OUTFIT = {
    8:  "short-sleeve light purple/lavender T-shirt, blue denim jeans, white low-top sneakers",
    10: "long-sleeve light purple/lavender crew-neck sweatshirt, light gray sweatpants, white low-top sneakers",
    12: "long-sleeve light purple/lavender collared pullover, cream wide-leg trousers, white low-top sneakers",
}

OUT_DIR = Path(r"D:\picturebook_outputs\_mia_ref_new")


def build_prompt(age: int) -> str:
    outfit = OUTFIT[age]
    return f"""Image-to-image edit of the attached character turnaround / model sheet.
KEEP EVERYTHING from the reference EXACTLY THE SAME — the same soft low-saturation healing watercolor children's storybook art style, the same clean pure-white background, the same layout (four full-body views on the left: front, 3/4 front, side profile, back view; plus a grid of small head expression thumbnails on the right), the same top-left name label "Mia" with "Age{age}" under it, the same girl identity, the same ~{age}-year-old round soft cute face, the same brown hair color, and the same outfit ({outfit}).

THE ONLY THING YOU MUST CHANGE IS THE HAIRSTYLE, in EVERY single view and EVERY expression thumbnail.

Redraw the hair as a single MID-HIGH PONYTAIL, drawn consistently in all views:
- ALL of the hair is gathered and tied into ONE single ponytail. No loose hanging sections, no half-up.
- The tie / base of the ponytail sits at the OCCIPITAL region — the BACK OF THE HEAD, slightly above ear level (mid-high). It is clearly LOWER than the very top of the head.
- The ponytail TAIL hangs down naturally and is LONG: the hair tail clearly reaches DOWN to the SHOULDER BLADES / mid-upper back. It is obviously long, NOT a short little stub.
- A few soft loose strands may frame the face at the front; everything else is gathered up cleanly.

ABSOLUTELY NOT (these are the bugs to fix):
- NO bun / top-knot / half-up.
- NO super-high ponytail tied at the crown or top center of the head; the tie must be on the BACK of the head (occipital), NOT on top.
- NO short stubby ponytail (the tail must reach the shoulder blades).
- NO hair left completely loose/down; NO low nape ponytail; NO side ponytail; NO twin tails / pigtails; NO braids.

Per view, the ponytail must read clearly:
- Front & 3/4 view: hair pulled back cleanly from the face, a few face-framing strands, no loose hair on the shoulders; the gathered tie is at the back of the head.
- Side / profile view: the tie sits at the occipital (back of head, slightly above the ear), and a long ponytail tail hangs down the back reaching the shoulder blade — clearly mid-high, not on the crown.
- Back view: one single ponytail starting at the back of the head, the long tail hanging down and covering the upper back down to the shoulder blades.

Keep the name label text exactly "Mia / Age{age}" and do not add, remove or alter any other text. Keep the watercolor style, soft brown/sepia thin outlines, clean cheeks, gentle smile, and white background identical to the reference."""


def main() -> None:
    age = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    ref = REF[age]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[mia mid-high ponytail] age={age} n={n} ref={ref.name}", flush=True)
    ref_url = host_image_to_url(ref)
    print(f"  ref hosted: {ref_url}", flush=True)
    prompt = build_prompt(age)

    for k in range(1, n + 1):
        dest = OUT_DIR / f"mia_{age}_pony_cand{k}.png"
        print(f"  -> generating cand{k} : {dest}", flush=True)
        try:
            generate_image(
                prompt=prompt, dest=dest,
                reference_url=ref_url, size="1536x1024",
                label=f"Mia{age} pony c{k}", deliver_print=False,
            )
            print(f"     OK {dest}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"     FAIL cand{k}: {e}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
