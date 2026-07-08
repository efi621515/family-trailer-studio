# -*- coding: utf-8 -*-
"""The AI writer — Layer 2.

Turns a plain-language family brief + a labelled photo list into a full trailer
spec (the JSON the engine renders). Uses Claude (claude-opus-4-8, adaptive
thinking). The model output is validated against the engine's contract and the
real assets; on failure it does one repair round-trip.

    from ai.writer import TrailerWriter
    spec = TrailerWriter(assets_root).write(brief)          # -> spec dict
    # then: from engine.render import build_trailer; build_trailer(spec)
"""
import json
import os
import re

from anthropic import Anthropic

from .catalog import build_catalog
from .validate import validate_spec

MODEL = "claude-opus-4-8"

SYSTEM = """You are the story writer for "Family Trailer Studio" — a tool that turns family
photos into a Hollywood-style movie trailer. You output a TRAILER SPEC as JSON: a
rendering engine turns each scene into 1920x1080 video with Ken Burns motion,
music, sound effects, and voiceover.

# House style (ALWAYS follow)
- The spoken VOICEOVER narration is in ENGLISH. Every on-screen CAPTION is the
  HEBREW translation. This bilingual style is the signature of the product.
- Trailer arc: studio-logo intro -> hook -> rising action / cast introductions ->
  a twist or turn -> the big title card -> "coming soon" -> a closing line.
- Keep it playful and cinematic. 12-22 scenes, ~90-130 seconds total.
- Use the family's own names and the funny premise the user describes.

# Scene types (each scene is a JSON object)
- "black_card": text-only card. Field: "lines" = array of {t, f, s, y, c, rtl, tr, st}.
    f = font key ("IMP" Impact for English titles, "BLACK" Arial-Black, "HE" Hebrew bold).
    s = pixel size; y = vertical center (canvas is 1080 tall); c = color name
    ("WHITE","GOLD","PINK","RED"); rtl = true for Hebrew; tr = letter tracking; st = stroke width.
    English title lines: f="IMP" or "BLACK", rtl omitted. Hebrew lines: f="HE", rtl=true.
- "photo": a family photo with a Hebrew caption. Fields: "image" (path from the photo list),
    "caption" (Hebrew), optional "caption_size", "caption_color".
- "cast_card": introduce one person. Fields: "image", "name" (LATIN caps, e.g. "ORNA"),
    "role" (e.g. "The Boss • ראש המשפחה"), optional "tag" (small pill label), "tag_color".
- "coming_soon": fields "subtitle" (Hebrew), "rating_letter" (one letter), "rating_word".
- "reveal": a two-photo transition (e.g. before -> after). Fields "before" and "after"
    are each a face object (a photo or cast_card as above) plus "transition":
    "dissolve" when both photos share identical framing (hair melts away smoothly),
    "fadewhite" when framing differs (a white flash hides the jump).
- "video": overlays a Hebrew caption on a supplied video clip. Fields "video" (path),
    optional "overlay_caption" (Hebrew). No music/narration (uses the clip's own audio).

# Every scene also needs
- "id": short unique snake_case id (e.g. "00_logo", "04_orna").
- "narration": one short English line (the voiceover). Omit only on "video" scenes.
- "duration": seconds (cards ~4.5-6, photos ~4.5-6, title ~5, closing ~7).
- "music": EXACT filename chosen from the music catalog you are given.
- "sfx": OPTIONAL exact filename from the sfx catalog (a whoosh/boom on impactful cuts).
- optional "music_offset" (start N seconds into the track), "zoom_in" (bool),
  "narration_delay" (seconds before the VO starts), "fadeout".

# Rules
- Only use "image"/"video" paths that appear in the PHOTOS list, verbatim.
- Only use "music"/"sfx" names that appear in the catalogs, verbatim.
- Pick images by their labels so the right person/photo lands in the right scene.
- Output ONLY a single JSON object: {"title": "...", "scenes": [ ... ]}. No prose, no code fences.
"""


class TrailerWriter:
    def __init__(self, assets_root, music_dir="03_Music/", sfx_dir="04_Sound FX/",
                 model=MODEL, client=None):
        self.assets_root = assets_root.replace("\\", "/").rstrip("/")
        self.music_dir = music_dir
        self.sfx_dir = sfx_dir
        self.model = model
        self.client = client or Anthropic()
        self.catalog = build_catalog(self.assets_root, music_dir, sfx_dir)

    # ---- prompt plumbing ---------------------------------------------------
    def _user_msg(self, brief):
        photos = brief.get("photos", [])
        photo_lines = "\n".join(f'- "{p["file"]}"  —  {p.get("label", "")}' for p in photos)
        parts = [
            f"FAMILY / STORY BRIEF:\n{brief.get('story', '').strip()}",
            "",
            f"PHOTOS (use these exact paths):\n{photo_lines or '(none provided)'}",
            "",
            f"MUSIC CATALOG (pick exact names):\n{json.dumps(self.catalog['music'], ensure_ascii=False)}",
            "",
            f"SFX CATALOG (pick exact names):\n{json.dumps(self.catalog['sfx'], ensure_ascii=False)}",
        ]
        videos = list(brief.get("videos", []))
        if brief.get("video"):
            videos.append({"file": brief["video"], "label": brief.get("video_caption", "")})
        if videos:
            vlines = "\n".join(f'- "{v["file"]}"  —  {v.get("label", "")}' for v in videos)
            parts += ["", "VIDEO CLIPS (use these exact paths in \"video\" scenes, where a real "
                          "moving clip fits better than a still):\n" + vlines]
        if brief.get("notes"):
            parts += ["", f"EXTRA NOTES: {brief['notes']}"]
        parts += ["", "Write the trailer spec now as a single JSON object."]
        return "\n".join(parts)

    def _call(self, messages):
        resp = self.client.messages.create(
            model=self.model, max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},   # structured task — faster, less over-thinking
            system=[{"type": "text", "text": SYSTEM}],
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text, resp

    @staticmethod
    def _parse_json(text):
        t = text.strip()
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.MULTILINE).strip()
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object in model output")
        return json.loads(t[start:end + 1])

    def _finalize(self, data, brief):
        spec = {
            "title": data.get("title", brief.get("title", "Family Trailer")),
            "assets_root": self.assets_root,
            "music_dir": self.music_dir,
            "sfx_dir": self.sfx_dir,
            "resolution": [1920, 1080],
            "fps": 30,
            "narration": {"backend": brief.get("tts_backend", "sapi")},
            "scenes": data["scenes"],
        }
        if brief.get("work_dir"):
            spec["work_dir"] = brief["work_dir"]
        if brief.get("output"):
            spec["output"] = brief["output"]
        return spec

    # ---- public ------------------------------------------------------------
    def write(self, brief, max_repairs=2, verbose=True):
        messages = [{"role": "user", "content": self._user_msg(brief)}]
        text, _ = self._call(messages)
        data = self._parse_json(text)
        spec = self._finalize(data, brief)

        for attempt in range(max_repairs):
            errs = validate_spec(spec, self.catalog)
            if not errs:
                if verbose:
                    print(f"AI writer: valid spec, {len(spec['scenes'])} scenes")
                return spec
            if verbose:
                print(f"AI writer: repair {attempt + 1} — {len(errs)} issue(s)")
            messages += [
                {"role": "assistant", "content": json.dumps(data, ensure_ascii=False)},
                {"role": "user", "content": "The spec has these problems — fix them and "
                    "re-output the FULL corrected JSON object only:\n- " + "\n- ".join(errs)},
            ]
            text, _ = self._call(messages)
            data = self._parse_json(text)
            spec = self._finalize(data, brief)

        errs = validate_spec(spec, self.catalog)
        if errs:
            raise ValueError("spec still invalid after repairs:\n- " + "\n- ".join(errs))
        return spec

    def write_and_render(self, brief, **kw):
        from engine.render import build_trailer
        spec = self.write(brief, **kw)
        return spec, build_trailer(spec)


if __name__ == "__main__":
    import sys
    brief_path = sys.argv[1] if len(sys.argv) > 1 else "samples/brief_example.json"
    with open(brief_path, "r", encoding="utf-8") as fh:
        brief = json.load(fh)
    w = TrailerWriter(brief["assets_root"])
    spec = w.write(brief)
    out = os.path.splitext(brief_path)[0] + "_spec.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=2)
    print("wrote", out)
