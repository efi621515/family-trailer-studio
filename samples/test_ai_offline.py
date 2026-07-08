# -*- coding: utf-8 -*-
"""Offline proof of the AI-writer machinery (no API key needed).

A stub Claude client returns a canned scenes JSON. The FIRST response contains a
bad music filename, so validate_spec() flags it and the writer fires its repair
round-trip; the SECOND response is corrected. The resulting spec is then rendered
by the real engine — proving catalog + validate + repair + finalize + render all
wire together. Swap the stub for a real Anthropic() client + API key to go live.
"""
import json
import os
from types import SimpleNamespace

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.writer import TrailerWriter
from engine.render import build_trailer

ROOT = os.path.dirname(os.path.abspath(__file__))
P3 = "01_Photos/חלק3/"

SCENES = [
    {"id": "00_logo", "type": "black_card", "duration": 4.2, "music": "01_Opening_Theme.mp3",
     "sfx": "Impacts/06_Logo_Whoosh.wav", "zoom_in": True, "narration": "Family Pictures... presents.",
     "lines": [{"t": "FAMILY PICTURES", "f": "IMP", "s": 118, "y": 470, "c": "WHITE", "tr": 16, "st": 2},
               {"t": "מציגה", "f": "HE", "s": 60, "y": 605, "c": "GOLD", "rtl": True, "st": 1}]},
    {"id": "01_recap", "type": "photo", "image": "01_Photos/כולם עם שיער.jpeg",
     "caption": "הגברים ניסו... ונכשלו", "duration": 5.0, "music": "03_Comedy_Theme.mp3",
     "sfx": "Transitions/09_Impact_Boom.wav", "zoom_in": True, "narration_delay": 0.4,
     "narration": "The men tried. And they failed."},
    {"id": "04_orna", "type": "reveal", "transition": "fadewhite", "duration": 4.6,
     "music": "04_Hero_Theme.mp3", "music_offset": 4.0, "sfx": "Impacts/04_Whoosh_Short.wav",
     "narration": "Orna. Roi's mother. The boss.",
     "before": {"type": "cast_card", "image": P3 + "אורנה האמא.jpeg", "name": "ORNA",
                "role": "ראש המשפחה • The Boss", "tag": "צוות הדודות"},
     "after": {"type": "cast_card", "image": P3 + "bald/orna.jpg", "name": "ORNA",
               "role": "ראש המשפחה • The Boss", "tag": "צוות הדודות"}},
    {"id": "21_end", "type": "black_card", "duration": 6.0, "music": "05_End_Credits.mp3",
     "zoom_in": True, "narration_delay": 0.4, "fadeout": 1.6,
     "narration": "That's how it is in a family... the women run the show.",
     "lines": [{"t": "ככה זה במשפחה...", "f": "HE", "s": 86, "y": 440, "c": "WHITE", "rtl": True, "st": 2},
               {"t": "הנשים מנהלות את ההצגה", "f": "HE", "s": 82, "y": 610, "c": "GOLD", "rtl": True, "st": 2}]},
]


def _resp(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class StubMessages:
    def __init__(self, texts):
        self.texts = texts
        self.i = 0

    def create(self, **kw):
        t = self.texts[min(self.i, len(self.texts) - 1)]
        self.i += 1
        return _resp(t)


class StubClient:
    def __init__(self, texts):
        self.messages = StubMessages(texts)


# first response: WRONG music name on scene 0 -> validator flags it -> repair fires
bad = json.loads(json.dumps({"title": "The Aunts Strike Back", "scenes": SCENES}, ensure_ascii=False))
bad["scenes"][0]["music"] = "NONEXISTENT_Theme.mp3"
good = {"title": "The Aunts Strike Back", "scenes": SCENES}

with open(os.path.join(ROOT, "brief_example.json"), "r", encoding="utf-8") as fh:
    brief = json.load(fh)
brief["work_dir"] = ROOT.replace("\\", "/") + "/_work_ai_test"
brief["output"] = ROOT.replace("\\", "/") + "/_work_ai_test/ai_trailer_offline.mp4"

writer = TrailerWriter(brief["assets_root"], client=StubClient(
    [json.dumps(bad, ensure_ascii=False), json.dumps(good, ensure_ascii=False)]))

spec = writer.write(brief)
print("catalog music:", len(writer.catalog["music"]), "sfx:", len(writer.catalog["sfx"]))
print("final scenes:", [s["id"] for s in spec["scenes"]])
build_trailer(spec)
