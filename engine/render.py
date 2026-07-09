# -*- coding: utf-8 -*-
"""Top-level orchestrator: a trailer spec (dict or JSON path) -> finished MP4.

    from engine.render import build_trailer
    build_trailer("samples/demo_spec.json")

The spec is the single source of truth. See samples/demo_spec.json for the shape.
This is the reusable core the AI writer (phase 2) and web app (phase 3) sit on top of.
"""
import json
import os

from .scenes import SceneRenderer
from .assemble import Assembler
from .tts import get_narrator


def _resolve_dir(assets_root, d):
    """A media dir may be absolute (a shared library) or relative to assets_root."""
    d = d.replace("\\", "/")
    if os.path.isabs(d):
        return d.rstrip("/") + "/"
    return assets_root.replace("\\", "/").rstrip("/") + "/" + d.rstrip("/") + "/"


def load_spec(spec):
    if isinstance(spec, dict):
        return spec, os.getcwd()
    with open(spec, "r", encoding="utf-8") as fh:
        return json.load(fh), os.path.dirname(os.path.abspath(spec))


def build_trailer(spec, work_dir=None, out_path=None, verbose=True):
    data, base = load_spec(spec)

    assets_root = data["assets_root"]
    size = tuple(data.get("resolution", [1920, 1080]))
    fps = data.get("fps", 30)
    work = work_dir or data.get("work_dir") or os.path.join(base, "_work")
    work = work.replace("\\", "/").rstrip("/")
    scenes_dir = work + "/scenes/"
    vo_dir = work + "/vo/"          # ASCII path — SAPI writes here
    seg_dir = work + "/seg/"
    out = out_path or data.get("output") or (work + "/trailer.mp4")

    fonts_dir = data.get("fonts_dir") or os.environ.get("FTS_FONTS_DIR") or "C:/Windows/Fonts/"
    renderer = SceneRenderer(assets_root, scenes_dir,
                             fonts_dir=fonts_dir,
                             fonts=data.get("fonts"), palette=data.get("palette"), size=size)
    assembler = Assembler(assets_root, _resolve_dir(assets_root, data.get("music_dir", "03_Music/")),
                          _resolve_dir(assets_root, data.get("sfx_dir", "04_Sound FX/")),
                          scenes_dir, vo_dir, seg_dir, fps=fps, size=size)

    scenes = data["scenes"]

    # 1) narration — collect every scene's line, synthesize in one batch
    narr = data.get("narration", {})
    backend = os.environ.get("FTS_TTS_BACKEND") or narr.get("backend") or "sapi"
    narrator = get_narrator(backend, **narr.get("options", {}))
    items = [(sc["id"], sc["narration"]) for sc in scenes if sc.get("narration")]
    vo_map = narrator.synth_all(items, vo_dir) if items else {}
    if verbose:
        print(f"narration: {len(vo_map)} lines")

    # 2) frames — render each scene's still(s) + attach vo path. A photo flagged
    #    "d3" gets a depth-based 3D parallax clip (raw photo warped) + a separate
    #    transparent caption overlaid on top, instead of the usual Ken Burns still.
    threed_dir = work + "/threed/"
    a_root = assets_root.replace("\\", "/").rstrip("/") + "/"
    for sc in scenes:
        if sc.get("type") == "photo" and sc.get("d3"):
            os.makedirs(threed_dir, exist_ok=True)
            frames = {}
            cap = sc.get("caption", "")
            if cap:
                frames["overlay"] = renderer.transparent_caption(
                    sc["id"] + "_cap.png", cap,
                    sc.get("caption_size", 74), sc.get("caption_color", "GOLD"))
            from .depth3d import render_3d_clip
            clip = threed_dir + sc["id"] + "_3d.mp4"
            # The parallax warp is the render's heaviest step (per-frame numpy over
            # the whole frame). seg_3d upscales the clip to full res anyway and the
            # background is blurred, so we warp at reduced res for a big speedup.
            # FTS_3D_SCALE trades speed vs foreground sharpness (0.5 ~= 4x faster).
            sc3 = float(os.environ.get("FTS_3D_SCALE", "0.5"))
            d3_size = (max(2, int(size[0] * sc3) // 2 * 2), max(2, int(size[1] * sc3) // 2 * 2))
            amp = sc.get("amp", 64.0) * (d3_size[1] / max(1, size[1]))   # keep motion ~constant
            render_3d_clip(a_root + sc["image"], clip,
                           dur=sc.get("duration", 4.0), fps=fps,
                           amp=amp, size=d3_size, verbose=verbose)
            sc["_3d_clip"] = clip
            sc["_frames"] = frames
        else:
            sc["_frames"] = renderer.render(sc)
        sc["_vo"] = vo_map.get(sc["id"])
        if verbose:
            print("frame", sc["id"])

    # 3) assemble
    result = assembler.build(scenes, out)
    if verbose:
        print("\nDONE ->", result)
    return result


if __name__ == "__main__":
    import sys
    build_trailer(sys.argv[1] if len(sys.argv) > 1 else "samples/demo_spec.json")
