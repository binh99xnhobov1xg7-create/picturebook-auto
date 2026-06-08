# -*- coding: utf-8 -*-
"""通读 0-6 全部 336 本故事，揪出"文字理解/指代判断"的坑。

对每本书逐页比对：官方 prompt 标注的【在场 IP】 vs 故事文字里的【指代/角色线索】，
标记三类风险：
  A) 童话/动物/物体主角（he/she ≠ Tommy/Mia）
  B) 有 he/she 但本页官方没点 Mia/Tommy（主体是大人/动物/物体）
  C) 大人视角（he=爸爸/爷爷、she=妈妈/奶奶）
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cn_prompt_builder import _official_positive, _cast_from_official

data = json.loads(Path("references/syllabus/image_prompts.json").read_text(encoding="utf-8"))

# 非 IP 寓言/动物/物体主角线索（出现在官方正向里 = 本页主角不是人类小孩）
NONIP = re.compile(
    r"\b(gingerbread man|fox|wolf|wolves|bear|bears|pig|pigs|goat|goats|"
    r"mouse|mice|rat|rabbit|bunny|hare|tortoise|turtle|duck|duckling|hen|"
    r"rooster|chick|lion|tiger|monkey|elephant|frog|snake|owl|crow|"
    r"troll|giant|ogre|dragon|fairy|elf|elves|gnome|goblin|witch|"
    r"snowman|robot|toy|teddy|doll|gingerbread|billy goat|"
    r"goldilocks|cinderella|rapunzel|pinocchio|thumbelina)\b", re.I)
# 经典童话标题线索
TALE = re.compile(
    r"gingerbread|goldilocks|three (little )?(pigs|bears|goats)|red riding hood|"
    r"billy goat|tortoise|hare|ugly duckling|little mermaid|beanstalk|"
    r"town mouse|country mouse|grasshopper|lion and the mouse|cried wolf|"
    r"stone soup|elves|shoemaker|emperor|princess and the pea|"
    r"jack|cinderella|rapunzel|pinocchio|thumbelina|snow white|"
    r"chicken little|henny penny|musicians of bremen|fisherman", re.I)
ADULT = re.compile(r"\b(mom|mommy|mother|dad|daddy|father|grandma|granny|grandmother|"
                   r"grandpa|grandfather)\b", re.I)
PRON = re.compile(r"\b(he|she|him|her|his|hers)\b", re.I)


def page_text(p):
    m = re.search(r"\*\*Text:\*\*\s*(.+?)(?:\*\*Prompt|$)", p.get("text", ""), re.S)
    return (m.group(1).strip() if m else "").replace("\n", " ")


def is_story_page(p):
    return bool(re.match(r"(?i)\s*page\s*\d+", p.get("marker") or ""))


report = {}
counts = {"fable": 0, "pron_nolead": 0, "adult": 0, "total": 0}

for e in data:
    lv = str(e.get("level"))
    title = e.get("title", "")
    pages = [p for p in e.get("pages", []) if is_story_page(p)]
    if not pages:
        continue
    counts["total"] += 1

    nonip_pages = 0
    pron_nolead = []      # 页：有he/she但官方没点Mia/Tommy
    adult_pages = []
    for p in pages:
        txt = page_text(p)
        pos = _official_positive(p.get("text", ""))
        cast = {c["key"] for c in _cast_from_official(p.get("text", ""), 10)}
        has_lead = bool(cast & {"mia", "tommy"})
        if NONIP.search(pos) and not has_lead:
            nonip_pages += 1
        if PRON.search(txt) and not has_lead:
            # 本页有代词，官方却没点主角 → 旧逻辑会误塞 Mia/Tommy
            subj = "动物/物体/寓言" if NONIP.search(pos) else (
                   "大人" if ADULT.search(txt) or ADULT.search(pos) else "?")
            pron_nolead.append((p.get("marker"), subj, txt[:70]))
        if ADULT.search(txt) and PRON.search(txt) and not has_lead:
            adult_pages.append(p.get("marker"))

    is_tale = bool(TALE.search(title)) or nonip_pages >= max(2, len(pages) // 2)
    flag = []
    if is_tale:
        flag.append("童话/非人类主角")
        counts["fable"] += 1
    if pron_nolead:
        flag.append(f"{len(pron_nolead)}页代词无主角")
        counts["pron_nolead"] += 1
    if adult_pages:
        flag.append("大人视角")
        counts["adult"] += 1

    if flag:
        report.setdefault(lv, []).append((title, e.get("book_label"), flag, pron_nolead))

print(f"扫描完成：共 {counts['total']} 本")
print(f"  童话/非人类主角: {counts['fable']} 本")
print(f"  含'代词但本页无主角'页: {counts['pron_nolead']} 本")
print(f"  含大人视角页: {counts['adult']} 本\n")

for lv in sorted(report):
    print(f"\n========== Level {lv}  （{len(report[lv])} 本需留意） ==========")
    for title, label, flag, pron in sorted(report[lv]):
        print(f"  · [{label}] {title}  —— {'、'.join(flag)}")
        for mk, subj, sample in pron[:3]:
            print(f"        {mk}（{subj}）: {sample}")
