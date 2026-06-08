# -*- coding: utf-8 -*-
"""L3-4 文本易错度打分器：按"角色识别/指代/选角"风险维度给每本书打分并排序。

风险维度（每项加权）：
  F 寓言/非人类主角（he/she≠Tommy/Mia）         —— 最易把寓言角色画成男孩
  O 一次性反复出场角色数（书内角色册）            —— 跨页漂移风险
  S 凶相反派（fox/wolf/giant/troll/witch/ogre）  —— 儿童向柔化风险
  D 同类多角色（three bears/pigs/goats…）        —— 分身/混淆风险
  N 否定句（"not in the frame"/background<10%）  —— 选角误纳风险
  A 大人视角代词（he=爸爸/she=妈妈）             —— 指代误判风险
  M 多角色同框页（≥3 named）                     —— 拼定妆表/超员风险
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from parser import BookOutline, PageSpec
from image_prompts import match
from cn_prompt_builder import _official_positive, _cast_from_official
from book_cast import build_book_cast

data = json.loads(Path("references/syllabus/image_prompts.json").read_text(encoding="utf-8"))

NONIP = re.compile(
    r"\b(gingerbread man|fox|wolf|wolves|bear|bears|pig|pigs|goat|goats|"
    r"mouse|mice|rat|rabbit|bunny|hare|tortoise|turtle|duck|duckling|hen|"
    r"rooster|chick|lion|tiger|monkey|elephant|frog|snake|owl|crow|goose|"
    r"troll|giant|ogre|dragon|fairy|elf|elves|gnome|goblin|witch|crane|"
    r"snowman|robot|goldilocks|cinderella|rapunzel|pinocchio|thumbelina)\b", re.I)
SCARY = re.compile(r"\b(fox|wolf|wolves|giant|troll|ogre|dragon|witch|goblin|monster|snake|bear|bears)\b", re.I)
DUP = re.compile(r"\b(three (little )?(pigs|bears|goats)|two bears|both bears|brothers|sisters|twins)\b", re.I)
NEG = re.compile(r"not in the frame|background[^.]{0,20}<\s*10|visual share\s*<", re.I)
ADULT = re.compile(r"\b(mom|mommy|mother|dad|daddy|father|grandma|granny|grandmother|grandpa|grandfather)\b", re.I)
PRON = re.compile(r"\b(he|she|him|her|his|hers)\b", re.I)
LEAD = re.compile(r"\b(mia|tommy)\b", re.I)


def page_text(p):
    m = re.search(r"\*\*Text:\*\*\s*(.+?)(?:\*\*Prompt|$)", p.get("text", ""), re.S)
    return (m.group(1).strip() if m else "").replace("\n", " ")


def is_story_page(p):
    return bool(re.match(r"(?i)\s*page\s*\d+", p.get("marker") or ""))


def score_book(e):
    lv = str(e.get("level"))
    title = e.get("title", "")
    pages = [p for p in e.get("pages", []) if is_story_page(p)]
    if not pages:
        return None
    F = O = S = D = N = A = M = 0
    dims = []
    for p in pages:
        raw = p.get("text", "")
        pos = _official_positive(raw)
        txt = page_text(p)
        cast = {c["key"] for c in _cast_from_official(raw, 10)}
        has_lead = bool(cast & {"mia", "tommy"})
        if NONIP.search(pos) and not has_lead:
            F += 1
        if SCARY.search(pos):
            S += 1
        if DUP.search(pos) or DUP.search(txt):
            D += 1
        if NEG.search(raw):
            N += 1
        if ADULT.search(txt) and PRON.search(txt) and not has_lead:
            A += 1
        named = len([c for c in _cast_from_official(raw, 10)])
        if named >= 3:
            M += 1

    # 书内角色册：反复出场一次性角色数
    tx = [page_text(p) for p in e.get("pages", []) if is_story_page(p)]
    oip = match(lv, title)
    ps = [PageSpec(index=0, page_type="cover", text="")] + \
         [PageSpec(index=i, page_type="story", text=t) for i, t in enumerate(tx[1:], 1)]
    o = BookOutline(title=title, level=f"Level {lv}", pages=ps, ip_age=10)
    o.official_image_prompt = oip
    bc = build_book_cast(o)
    O = sum(1 for r in bc.values() if r.needs_anchor)

    score = F * 3 + O * 2 + S * 2 + D * 2 + N * 1 + A * 2 + M * 1
    parts = []
    if F: parts.append(f"寓言主角×{F}")
    if O: parts.append(f"反复一次性角色×{O}")
    if S: parts.append(f"凶相反派×{S}")
    if D: parts.append(f"同类多角色×{D}")
    if N: parts.append(f"否定句×{N}")
    if A: parts.append(f"大人代词×{A}")
    if M: parts.append(f"多角色同框×{M}")
    roles = "、".join(r.display for r in bc.values() if r.needs_anchor)
    return dict(lv=lv, title=title, label=e.get("book_label"), score=score,
               parts=parts, roles=roles)


levels = sys.argv[1:] or ["3", "4"]
rows = []
for e in data:
    if str(e.get("level")) not in levels:
        continue
    r = score_book(e)
    if r and r["score"] > 0:
        rows.append(r)

rows.sort(key=lambda x: -x["score"])
print(f"=== L{'/'.join(levels)} 文本易错度排序（共 {len(rows)} 本有风险信号）===\n")
for r in rows[:25]:
    print(f"[{r['score']:>2}] L{r['lv']} [{r['label']}] {r['title']}")
    print(f"      {'、'.join(r['parts'])}")
    if r["roles"]:
        print(f"      锁定角色: {r['roles']}")
