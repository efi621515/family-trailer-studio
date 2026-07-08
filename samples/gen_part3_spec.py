# -*- coding: utf-8 -*-
"""Build the FULL Part-3 trailer spec programmatically and dump it to JSON.

This proves the engine reproduces the entire hand-built Part 3 from data alone —
and doubles as the reference for how the AI writer (phase 2) will emit a spec.
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = "C:/Users/shal1/OneDrive/Desktop/Operation Hair Transfer"
WHOOSH = "Impacts/04_Whoosh_Short.wav"
P3 = "01_Photos/חלק3/"
TAG = "צוות הדודות"

# (id, name, role, hair_file, bald_key, narration, music_offset)
CAST = [
    ("04_orna",    "ORNA",    "ראש המשפחה • The Boss",    "אורנה האמא.jpeg",     "orna",    "Orna. Roi's mother. The boss.",      4.0),
    ("05_eti",     "ETI",     "הלב החם • The Heart",      "אתי האימהית.jpeg",    "eti",     "Eti. The heart.",                    8.6),
    ("06_tali",    "TALI",    "הסטייל • The Diva",        "טלי הגנדרנית.jpeg",   "tali",    "Tali. The diva.",                    13.2),
    ("07_limor",   "LIMOR",   "החיוך הקטלני • The Smile", "לימור החייכנית.jpeg", "limor",   "Limor. The killer smile.",           17.8),
    ("08_simona",  "SIMONA",  "המתכננת • The Planner",    "סימונה הדאגנית.jpeg", "simona",  "Simona. The planner.",               22.4),
    ("09_ruchama", "RUCHAMA", "הסערה • The Storm",        "רוחמה העצבנית.jpeg",  "ruchama", "Ruchama. The storm.",                27.0),
    ("10_oriana",  "ORIANA",  "הזריזה • The Quick One",   "אוריאנה הקטנה.jpeg",  "oriana",  "Oriana. The quick one.",             31.6),
]


def cast_face(name, role, image):
    return {"type": "cast_card", "image": image, "name": name, "role": role, "tag": TAG}


scenes = [
    {"id": "00_logo", "type": "black_card", "duration": 4.2, "music": "01_Opening_Theme.mp3",
     "sfx": "Impacts/06_Logo_Whoosh.wav", "zoom_in": True, "narration": "Family Pictures... presents.",
     "lines": [
         {"t": "FAMILY PICTURES", "f": "IMP", "s": 118, "y": 470, "c": "WHITE", "tr": 16, "st": 2},
         {"t": "מציגה", "f": "HE", "s": 60, "y": 605, "c": "GOLD", "rtl": True, "st": 1}]},

    {"id": "01_recap", "type": "photo", "image": "01_Photos/כולם עם שיער.jpeg",
     "caption": "הגברים ניסו... פעמיים. ונכשלו", "duration": 5.2, "music": "03_Comedy_Theme.mp3",
     "sfx": "Transitions/09_Impact_Boom.wav", "zoom_in": True, "narration_delay": 0.4,
     "narration": "The men tried. Twice. And they failed."},

    {"id": "02_eilat", "type": "photo", "image": "01_Photos/חלק2/דוד gadi.jpg",
     "caption": "הפיאות עדיין שם... באילת", "caption_size": 64, "duration": 4.6, "music": "03_Comedy_Theme.mp3",
     "music_offset": 5.2, "sfx": "Impacts/05_Whoosh_Long.wav", "zoom_in": True, "narration_delay": 0.4,
     "narration": "The wigs were still out there... in Eilat."},

    {"id": "03_women", "type": "black_card", "duration": 4.4, "music": "04_Hero_Theme.mp3",
     "sfx": "Transitions/10_Boom_Swoosh.wav", "zoom_in": True, "narration": "So the family called in... the women.",
     "lines": [
         {"t": "אז המשפחה קראה...", "f": "HE", "s": 86, "y": 440, "c": "WHITE", "rtl": True, "st": 2},
         {"t": "לנשים", "f": "HE", "s": 120, "y": 600, "c": "PINK", "rtl": True, "st": 2}]},
]

# 7 aunt cast cards — hair -> bald fadewhite reveals
for sid, name, role, hair, key, narr, moff in CAST:
    scenes.append({
        "id": sid, "type": "reveal", "transition": "fadewhite", "duration": 4.6,
        "music": "04_Hero_Theme.mp3", "music_offset": moff, "sfx": WHOOSH, "narration": narr,
        "before": cast_face(name, role, P3 + hair),
        "after": cast_face(name, role, P3 + "bald/" + key + ".jpg"),
    })

scenes += [
    {"id": "11_efi", "type": "black_card", "duration": 5.0, "music": "04_Hero_Theme.mp3",
     "sfx": "Transitions/10_Boom_Swoosh.wav", "zoom_in": True,
     "narration": "And of course... Uncle Efi. The only man they trust.",
     "lines": [
         {"t": "EFI", "f": "BLACK", "s": 200, "y": 430, "c": "WHITE", "tr": 18, "st": 3},
         {"t": "היחיד שהן סומכות עליו • The Legend", "f": "HE", "s": 62, "y": 620, "c": "GOLD", "rtl": True, "st": 1}]},

    {"id": "11b_efi_video", "type": "video", "video": "02_Videos/דוד אפי.mp4", "duration": 8.0,
     "overlay_caption": "וכמובן... דוד אפי. היחיד שהן סומכות עליו"},

    {"id": "12_solidarity", "type": "black_card", "duration": 5.0, "music": "02_Family_Theme.mp3",
     "sfx": "Transitions/08_Cinematic_Boom.wav", "zoom_in": True, "narration_delay": 0.4,
     "narration": "To stand with Roi... the women did the unthinkable.",
     "lines": [
         {"t": "כדי להזדהות עם רועי...", "f": "HE", "s": 80, "y": 470, "c": "WHITE", "rtl": True, "st": 2},
         {"t": "הן עשו את הבלתי יאומן", "f": "HE", "s": 86, "y": 610, "c": "PINK", "rtl": True, "st": 2}]},

    # group bald reveal — SAME framing => smooth dissolve, hair vanishes on the whole group
    {"id": "13_group", "type": "reveal", "transition": "dissolve", "duration": 7.6,
     "music": "02_Family_Theme.mp3", "music_offset": 5.0, "sfx": "Transitions/09_Impact_Boom.wav",
     "narration": "Every single one of them... went bald.", "hold": 3.0, "xf": 1.3, "narration_delay": 3.2,
     "before": {"type": "photo", "image": P3 + "אפי והאחיות לפני.jpeg", "caption": "כל אחת ואחת... התגלחה", "caption_size": 72},
     "after":  {"type": "photo", "image": P3 + "אפי והדודות אחרי.jpeg", "caption": "כל אחת ואחת... התגלחה", "caption_size": 72}},

    {"id": "14_eilat_trip", "type": "photo", "image": "01_Photos/חלק2/דוד gadi.jpg",
     "caption": "ואז הן נסעו דרומה... לאילת", "caption_size": 62, "duration": 4.6, "music": "03_Comedy_Theme.mp3",
     "sfx": "Impacts/05_Whoosh_Long.wav", "zoom_in": True, "narration": "Then they drove south... to Eilat."},

    {"id": "15_men", "type": "black_card", "duration": 4.8, "music": "07_Trailer_Boom.mp3",
     "sfx": "Transitions/08_Cinematic_Boom.wav", "zoom_in": True,
     "narration": "And what two whole movies of men could not do...",
     "lines": [
         {"t": "מה ששני סרטים של גברים", "f": "HE", "s": 74, "y": 440, "c": "WHITE", "rtl": True, "st": 2},
         {"t": "לא הצליחו לעשות...", "f": "HE", "s": 80, "y": 580, "c": "GOLD", "rtl": True, "st": 2}]},

    {"id": "16_onecall", "type": "black_card", "duration": 4.8, "music": "03_Comedy_Theme.mp3",
     "sfx": "Transitions/09_Impact_Boom.wav", "zoom_in": True, "narration_delay": 0.3,
     "narration": "The women solved... with one phone call.",
     "lines": [
         {"t": "הנשים פתרו...", "f": "HE", "s": 86, "y": 450, "c": "WHITE", "rtl": True, "st": 2},
         {"t": "בטלפון אחד", "f": "HE", "s": 110, "y": 610, "c": "PINK", "rtl": True, "st": 2}]},

    {"id": "17_twist", "type": "photo", "image": P3 + "אורנה האמא.jpeg",
     "caption": "כי אורנה ידעה איפה הפיאות... כל הזמן", "caption_size": 58, "duration": 6.6,
     "music": "03_Comedy_Theme.mp3", "music_offset": 4.8, "sfx": "Transitions/09_Impact_Boom.wav",
     "zoom_in": True, "narration_delay": 0.4, "narration": "Because Orna knew where the wigs were... the entire time."},

    {"id": "18_mother", "type": "black_card", "duration": 5.8, "music": "02_Family_Theme.mp3",
     "sfx": "Transitions/08_Cinematic_Boom.wav", "zoom_in": True, "narration_delay": 0.4,
     "narration": "Behind every bald family... there stands a mother.",
     "lines": [
         {"t": "מאחורי כל משפחה קירחת...", "f": "HE", "s": 78, "y": 460, "c": "WHITE", "rtl": True, "st": 2},
         {"t": "עומדת אמא", "f": "HE", "s": 110, "y": 610, "c": "GOLD", "rtl": True, "st": 2}]},

    {"id": "19_title", "type": "black_card", "duration": 4.8, "music": "07_Trailer_Boom.mp3",
     "sfx": "Transitions/08_Cinematic_Boom.wav", "zoom_in": True, "narration": "Operation Hair Transfer. Three.",
     "lines": [
         {"t": "OPERATION HAIR TRANSFER", "f": "IMP", "s": 108, "y": 380, "c": "WHITE", "tr": 10, "st": 3},
         {"t": "3", "f": "IMP", "s": 190, "y": 560, "c": "GOLD", "st": 4},
         {"t": "הדודות נכנסות לפעולה", "f": "HE", "s": 66, "y": 730, "c": "WHITE", "rtl": True, "st": 1}]},

    {"id": "20_soon", "type": "coming_soon", "subtitle": "בקרוב — והפעם, הנשים בשליטה",
     "rating_letter": "W", "rating_word": "FOR WIG", "duration": 4.8, "music": "07_Trailer_Boom.mp3",
     "music_offset": 6, "sfx": "Transitions/09_Impact_Boom.wav", "zoom_in": True,
     "narration": "Coming soon... and this time, the women are in charge."},

    {"id": "21_end", "type": "black_card", "duration": 7.8, "music": "05_End_Credits.mp3",
     "zoom_in": True, "narration_delay": 0.4, "fadeout": 1.6,
     "narration": "That's how it is in a family... the women run the show.",
     "lines": [
         {"t": "ככה זה במשפחה...", "f": "HE", "s": 86, "y": 420, "c": "WHITE", "rtl": True, "st": 2},
         {"t": "הנשים", "f": "HE", "s": 100, "y": 560, "c": "PINK", "rtl": True, "st": 2},
         {"t": "מנהלות את ההצגה", "f": "HE", "s": 92, "y": 700, "c": "GOLD", "rtl": True, "st": 2}]},
]

spec = {
    "title": "Operation Hair Transfer 3 (from spec)",
    "assets_root": ASSETS,
    "music_dir": "03_Music/",
    "sfx_dir": "04_Sound FX/",
    "resolution": [1920, 1080],
    "fps": 30,
    "work_dir": ROOT.replace("\\", "/") + "/_work_part3",
    "output": ROOT.replace("\\", "/") + "/_work_part3/Operation_Hair_Transfer_3_from_spec.mp4",
    "narration": {"backend": "sapi"},
    "scenes": scenes,
}

out = os.path.join(ROOT, "part3_spec.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(spec, fh, ensure_ascii=False, indent=2)
print("wrote", out, "with", len(scenes), "scenes")
