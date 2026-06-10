"""临时脚本：重画 Mia 三档 IP 定妆图为正确的 half-up 半扎发型。

用现有定妆图做图生图参考（锁住治愈水彩画风/服装/三视图+表情版式/左上角姓名年龄标签/白底），
唯一改动＝把所有视图（正/侧/背/表情）的发型从「高马尾/全扎」改成「half-up 半扎」。

用法：
  py scripts/_mia_halfup_regen.py 10 2     # 为 10 岁出 2 张候选
候选写到 D:\\picturebook_outputs\\_mia_ref_new\\mia_{age}_candK.png（1536x1024，不做4:3裁切/印刷放大）。
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

# 各年龄档服装（来自 manifest，保持不变）
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

Redraw the hair as a SOFT HALF-UP (half updo) hairstyle, drawn consistently in all views:
- Hair is parted in the MIDDLE (center part).
- Only the UPPER layer of hair — the top section and the hair at both temples/sides — is gently swept back and tied into ONE small half-up section (a small tie / tiny half-bun) at the BACK OF THE CROWN / back of the head.
- The LOWER HALF of the hair stays DOWN: loose, free-flowing, hanging naturally down the back and resting on the shoulders. About half the hair remains loose and down.
- A few soft loose strands frame the face at the front.
- Overall soft and brushed-back, gentle and natural.

ABSOLUTELY NOT (this is the bug to fix): do NOT gather ALL the hair into a single ponytail; NO high ponytail; NO side ponytail; NO single long tail sticking out from the back of the head; do NOT leave all hair completely loose/undone either. It must be HALF-up: top tied, bottom loose.

Per view, the hair must read as half-up:
- Front & 3/4 view: you can see the small gathered section at the crown, plus loose hair falling over the shoulders on both sides; a center part with face-framing strands.
- Side / profile view: a small soft gathered bump/tie at the back of the crown, and the rest of the hair hanging LOOSE and DOWN along the back — NOT a long ponytail tail projecting out behind the head.
- Back view: the small top section gathered into a little tie at the crown, while the rest of the hair hangs loose and down, covering the upper back.

Keep the name label text exactly "Mia / Age{age}" and do not add, remove or alter any other text. Keep the watercolor style, soft brown/sepia thin outlines, clean cheeks, gentle smile, and white background identical to the reference."""


def main() -> None:
    age = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    ref = REF[age]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[mia half-up] age={age} n={n} ref={ref.name}", flush=True)
    ref_url = host_image_to_url(ref)
    print(f"  ref hosted: {ref_url}", flush=True)
    prompt = build_prompt(age)

    for k in range(1, n + 1):
        dest = OUT_DIR / f"mia_{age}_cand{k}.png"
        print(f"  -> generating cand{k} : {dest}", flush=True)
        try:
            generate_image(
                prompt=prompt, dest=dest,
                reference_url=ref_url, size="1536x1024",
                label=f"Mia{age} half-up c{k}", deliver_print=False,
            )
            print(f"     OK {dest}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"     FAIL cand{k}: {e}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
