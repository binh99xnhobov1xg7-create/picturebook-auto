"""平滑提示词新旧对比：对 L4《Bodies of Water》第 1、4 页用新提示词重出图。
旧图 = images/page_0X.png（上次生成）；新图 = images/_smooth_cmp/page_0X_new.png。"""
from pathlib import Path
import pickle, hashlib
from parser import PageSpec, BookOutline
from ai_extractor import extract_all, apply_extracted_to_outline
from reading_report_builder import attach_rr_questions
from worksheet_builder import attach_worksheet_questions
from batch_runner import resolve_ip_age, _story_lines
from cn_prompt_builder import build_cn_page_prompt, book_primary_anchor_ref, book_style_anchor_ref
from seedream_client import crop_character_portrait, generate_image

TITLE, LEVEL = "Bodies of Water", "4"
STORY = """Page 1 Water covers most of our planet. We call large water areas bodies of water.
Page 2 An ocean is a very large sea. Oceans cover about seventy percent of Earth.
Page 3 A river is a long, flowing stream. Rivers bring water to lakes and oceans.
Page 4 A lake is water surrounded by land. Some lakes are very deep and old.
Page 5 A coastline is where the land meets the sea.
Page 6 A delta is where the river meets the sea. Deltas make rich soil for plants.
Page 7 All bodies of water help people and life. We must protect them for the future."""
BDIR = Path(r"D:\picturebook_outputs\Bodies_of_Water_20260606_185133\Level 4_Book2_Bodies_of_Water")
PAGES_TO_REDO = [1, 4]


def main():
    ip_age = resolve_ip_age(LEVEL)
    ck = hashlib.md5((TITLE + LEVEL + STORY).encode()).hexdigest()[:10]
    cache = Path(__file__).parent / f"_ec_cache_{ck}.pkl"
    if cache.exists():
        ec = pickle.loads(cache.read_bytes())
        print("(用缓存抽取)", flush=True)
    else:
        ec = extract_all(STORY, TITLE, LEVEL, theme="bodies of water / geography", mock=False)
        cache.write_bytes(pickle.dumps(ec))

    pages = [PageSpec(index=0, page_type="cover", text="")]
    for i, line in enumerate(_story_lines(STORY), start=1):
        pages.append(PageSpec(index=i, page_type="story", text=line))
    while len(pages) < 8:
        pages.append(PageSpec(index=len(pages), page_type="story", text=""))
    outline = BookOutline(title=TITLE, pages=pages, level=LEVEL, book_number="2",
                          theme="bodies of water / geography", ip_age=ip_age)
    apply_extracted_to_outline(outline, ec)
    outline.fiction_type = "non-fiction"
    attach_rr_questions(outline, ec.rr_questions)
    attach_worksheet_questions(outline, ec.worksheet_questions, reading_q_count=4)

    img_dir = BDIR / "images"
    out_dir = img_dir / "_smooth_cmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    anchor_dir = out_dir / "_anchors"
    prot_ref = book_primary_anchor_ref(outline, ip_age)
    style_anchor = book_style_anchor_ref()

    for idx in PAGES_TO_REDO:
        page = outline.pages[idx]
        built = build_cn_page_prompt(page, outline, ip_age)
        refs = [Path(r) for r in built.references if r]
        if prot_ref and Path(prot_ref) in refs:
            refs.remove(Path(prot_ref)); refs.insert(0, Path(prot_ref))
        anchor = None
        if refs:
            anchor = crop_character_portrait(refs[0], anchor_dir / f"anchor_p{idx:02d}.png") or refs[0]
        elif style_anchor:
            anchor = style_anchor
        dest = out_dir / f"page_{idx:02d}_new.png"
        print(f"\n生成 P{idx} (新提示词) → {dest}", flush=True)
        generate_image(prompt=built.prompt, dest=dest,
                       references=[anchor] if anchor else [],
                       label=f"SMOOTH P{idx}", mock=False)
        print(f"OK P{idx}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
