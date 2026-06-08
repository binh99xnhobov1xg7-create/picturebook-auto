"""IP 锁定验证：朋友书 cast=Mia12/Tommy12/Anna12，按新「定妆表」逻辑出封面+P1。
对比之前跑帧的封面，验证 Mia/Tommy/Anna 是否贴合官方定妆图。"""
from pathlib import Path
import pickle, hashlib
from parser import PageSpec, BookOutline
from ai_extractor import extract_all, apply_extracted_to_outline
from batch_runner import resolve_ip_age, _story_lines
from cn_prompt_builder import build_cn_page_prompt
from seedream_client import crop_character_portrait, build_reference_sheet, generate_image
from ip_library import load_library

TITLE, LEVEL = "What Makes a Good Friend", "5"
STORY = """Page 1: Anna felt nervous on her first day in the new class. Her hands shook as she sat down at a small wooden desk.
Page 2: At recess she saw a girl drop a pile of books on the floor. Anna helped pick up the books and smiled at the girl.
Page 3: Later she shared pencils and glue with a quiet boy at his table. The boy looked up and said thank you to her softly.
Page 4: A class hamster grabbed Anna's eraser and ran under a chair. The hamster looked like a tiny thief and everyone laughed together.
Page 5: Anna listened when classmates told stories about pets and games. She said, 'Tell me more,' and asked each person kind questions.
Page 6: Her classmates all liked her because she cared about them and helped them. Anna felt glad she had been kind from the very first day.
Page 7: By the week's end Anna had many new friends and a plan. The next week she would bake cookies and bring them for everyone in the class."""
CAST_POOL = ["mia_12", "tommy_12", "anna_12"]
OVERRIDES = {"girl": "mia_12", "boy": "tommy_12"}
OUT = Path(r"D:\picturebook_outputs\_ip_check")
PAGES = [0, 1]   # 封面 + P1


def _ip_name(ref):
    rp = str(Path(ref)).lower()
    for e in load_library():
        if str(e.image_path).lower() == rp:
            return e.name_base
    return ""


def main():
    ip_age = resolve_ip_age(LEVEL)
    ck = hashlib.md5((TITLE + LEVEL + STORY).encode()).hexdigest()[:10]
    cache = Path(__file__).parent / f"_ec_cache_{ck}.pkl"
    ec = pickle.loads(cache.read_bytes()) if cache.exists() else \
        extract_all(STORY, TITLE, LEVEL, theme="friendship", mock=False)
    if not cache.exists():
        cache.write_bytes(pickle.dumps(ec))

    pages = [PageSpec(index=0, page_type="cover", text="")]
    for i, line in enumerate(_story_lines(STORY), start=1):
        pages.append(PageSpec(index=i, page_type="story", text=line))
    while len(pages) < 8:
        pages.append(PageSpec(index=len(pages), page_type="story", text=""))
    outline = BookOutline(title=TITLE, pages=pages, level=LEVEL, book_number="1",
                          theme="friendship", ip_age=ip_age)
    apply_extracted_to_outline(outline, ec)
    outline.fiction_type = "fiction"

    OUT.mkdir(parents=True, exist_ok=True)
    sheet_dir = OUT / "_refsheets"
    for idx in PAGES:
        page = outline.pages[idx]
        built = build_cn_page_prompt(page, outline, ip_age,
                                     cast_pool=CAST_POOL, generic_overrides=OVERRIDES)
        local = [Path(r) for r in built.references if r and Path(r).exists()]
        names = [_ip_name(r) for r in local]
        print(f"\nP{idx} cast refs: {[(n, Path(r).name) for n, r in zip(names, local)]}", flush=True)
        note = ""
        anchor = None
        if len(local) >= 2:
            sheet = build_reference_sheet(local, sheet_dir / f"sheet_p{idx:02d}.png", labels=names)
            if sheet:
                anchor = sheet
                disp = "、".join(n for n in names if n)
                note = ("【参考图＝角色定妆表（连续性绘本·形象永久锁定）】所附唯一参考图是白底「角色定妆表」，"
                        f"并排展示本页所有出场角色（{disp}，面板上方有英文名标签）。请把每个角色的脸型、五官、"
                        "发型、发色、肤色、服装款式与配色 1:1 精确还原，与定妆表完全一致、与往期绘本同一个人。"
                        "【唯一允许改变：姿势/动作 与 面部表情】，形象其余一律不得改动；"
                        "严禁照搬定妆表的白底/并排站姿/多视图排版，只取‘谁长什么样’，把他们放进本页真实场景。")
        if anchor is None and local:
            anchor = crop_character_portrait(local[0], OUT / f"anchor_p{idx:02d}.png") or local[0]
        prompt = built.prompt + ("\n\n" + note if note else "")
        dest = OUT / f"page_{idx:02d}_new.png"
        print(f"生成 P{idx} → {dest}", flush=True)
        generate_image(prompt=prompt, dest=dest, references=[anchor] if anchor else [],
                       label=f"IPCHK P{idx}", mock=False)
        print(f"OK P{idx}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
