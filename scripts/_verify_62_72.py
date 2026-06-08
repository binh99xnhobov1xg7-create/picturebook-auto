# -*- coding: utf-8 -*-
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
from syllabus import match

TITLES = [
    "Folk Tales: Stories Passed from Voice to Voice",
    "Officer Buckle's Busy Day",
    "Goldilocks and the three bears",
    "The Ant and the Grasshopper",
    "Helping Hands in Our Neighborhood",
    "Mia and Her Spanish Friend",
    "Discovering Canada",
    "The Clean-Up Day",
    "The Llama Who Climbed to the Clouds",
    "Discovering New Zealand",
    "Why Do We Have Libraries and Museums?",
]
for t in TITLES:
    e = match("3", t)
    if not e:
        print("MISS", t)
        continue
    n_pages = len(re.findall(r"(?i)page\s*\d+\s*[:：]", e.text_7page or ""))
    print("HIT  | %-48s | genre=%-10s | vocab=%s | text7_pages=%d | strat=%s | GO=%s" % (
        t[:48], e.genre, e.vocab_words(), n_pages,
        (e.reading_strategy or "")[:18], (e.graphic_organizer or "")[:18]))
