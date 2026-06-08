"""仅重建两本 worksheet（标准化阅读页：字号梯度 + 行对齐等距平铺 + 同题型），
复用最新生图目录的 page 图，覆盖 worksheet，并渲染阅读页(5)到 PNG 核对。"""
from pathlib import Path
import pickle, hashlib
from parser import PageSpec, BookOutline
from ai_extractor import extract_all, apply_extracted_to_outline
from reading_report_builder import attach_rr_questions
from worksheet_builder import attach_worksheet_questions, build_worksheet
from batch_runner import resolve_ip_age, _story_lines

BODIES = """Page 1 Water covers most of our planet. We call large water areas bodies of water.
Page 2 An ocean is a very large sea. Oceans cover about seventy percent of Earth.
Page 3 A river is a long, flowing stream. Rivers bring water to lakes and oceans.
Page 4 A lake is water surrounded by land. Some lakes are very deep and old.
Page 5 A coastline is where the land meets the sea.
Page 6 A delta is where the river meets the sea. Deltas make rich soil for plants.
Page 7 All bodies of water help people and life. We must protect them for the future."""

FRIENDS = """Page 1: Anna felt nervous on her first day in the new class. Her hands shook as she sat down at a small wooden desk.
Page 2: At recess she saw a girl drop a pile of books on the floor. Anna helped pick up the books and smiled at the girl.
Page 3: Later she shared pencils and glue with a quiet boy at his table. The boy looked up and said thank you to her softly.
Page 4: A class hamster grabbed Anna's eraser and ran under a chair. The hamster looked like a tiny thief and everyone laughed together.
Page 5: Anna listened when classmates told stories about pets and games. She said, 'Tell me more,' and asked each person kind questions.
Page 6: Her classmates all liked her because she cared about them and helped them. Anna felt glad she had been kind from the very first day.
Page 7: By the week's end Anna had many new friends and a plan. The next week she would bake cookies and bring them for everyone in the class."""

BOOKS = [
    dict(title="Bodies of Water", level="4", book_no="2", story=BODIES,
         theme="bodies of water / geography", fiction="non-fiction",
         dir=r"D:\picturebook_outputs\Bodies_of_Water_20260606_185133\Level 4_Book2_Bodies_of_Water",
         pre="Level 4_Book2_Bodies_of_Water"),
    dict(title="What Makes a Good Friend", level="5", book_no="1", story=FRIENDS,
         theme="friendship", fiction="fiction",
         dir=r"D:\picturebook_outputs\What_Makes_a_Good_Friend_20260606_190037\Level 5_Book1_What_Makes_a_Good_Friend",
         pre="Level 5_Book1_What_Makes_a_Good_Friend"),
]


def _close_open(paths):
    try:
        import win32com.client as win32
        pp = win32.GetActiveObject("PowerPoint.Application")
        for pr in list(pp.Presentations):
            if any(Path(pr.FullName).name == Path(p).name for p in paths):
                pr.Close()
    except Exception:
        pass


def main():
    rendered = []
    for bk in BOOKS:
        bdir = Path(bk["dir"])
        imgs = [bdir / "images" / f"page_{i:02d}.png" for i in range(8)]
        imgs = [p for p in imgs if p.exists()]
        print(f"\n== {bk['title']} (L{bk['level']}) imgs={len(imgs)} ==", flush=True)

        ck = hashlib.md5((bk["title"] + bk["level"] + bk["story"]).encode()).hexdigest()[:10]
        cache = Path(__file__).parent / f"_ec_cache_{ck}.pkl"
        if cache.exists():
            ec = pickle.loads(cache.read_bytes())
            print("  (用缓存抽取)", flush=True)
        else:
            ec = extract_all(bk["story"], bk["title"], bk["level"], theme=bk["theme"], mock=False)
            cache.write_bytes(pickle.dumps(ec))

        pages = [PageSpec(index=0, page_type="cover", text="")]
        for i, line in enumerate(_story_lines(bk["story"]), start=1):
            pages.append(PageSpec(index=i, page_type="story", text=line))
        while len(pages) < 8:
            pages.append(PageSpec(index=len(pages), page_type="story", text=""))
        outline = BookOutline(title=bk["title"], pages=pages, level=bk["level"],
                              book_number=bk["book_no"], theme=bk["theme"],
                              ip_age=resolve_ip_age(bk["level"]))
        apply_extracted_to_outline(outline, ec)
        outline.fiction_type = bk["fiction"]
        attach_rr_questions(outline, ec.rr_questions)
        attach_worksheet_questions(outline, ec.worksheet_questions, reading_q_count=4)

        ws = bdir / f"{bk['pre']}_Worksheet.pptx"
        _close_open([ws])
        build_worksheet(outline, ws, image_paths=imgs)
        print("WS SAVED:", ws, flush=True)
        rendered.append(str(ws))

    import win32com.client as win32
    pp = win32.Dispatch("PowerPoint.Application")
    for ws in rendered:
        pres = pp.Presentations.Open(ws, WithWindow=False)
        outdir = Path(ws).with_suffix("")
        outdir.mkdir(exist_ok=True)
        for i, sl in enumerate(pres.Slides, 1):
            if i in (5, 6):
                sl.Export(str(outdir / f"ws_slide_{i:02d}.png"), "PNG", 1400, 1050)
        pres.Close()
        print("RENDERED:", outdir, flush=True)
    pp.Quit()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
