# -*- coding: utf-8 -*-
"""Validate an AI-produced trailer spec against the engine's contract + the real
assets. Returns a list of human-readable errors (empty = valid). Used both to
gate a spec before rendering and to feed a repair round-trip back to the model.
"""
import os

SCENE_TYPES = {"black_card", "logo", "photo", "cast_card", "coming_soon", "reveal", "video"}
FACE_TYPES = {"black_card", "logo", "photo", "cast_card", "coming_soon"}
NUM_FIELDS = ("duration", "fadeout", "music_offset", "narration_delay", "hold", "xf", "caption_size")


def _num_errs(sc, where):
    errs = []
    for k in NUM_FIELDS:
        if k in sc and (isinstance(sc[k], bool) or not isinstance(sc[k], (int, float))):
            errs.append(f"{where}: '{k}' must be a number, got {sc[k]!r}")
    return errs


def _exists(assets_root, rel):
    return os.path.isfile(assets_root.rstrip("/") + "/" + rel)


def _check_face(f, where, assets_root, errs):
    t = f.get("type")
    if t not in FACE_TYPES:
        errs.append(f"{where}: face type '{t}' invalid (allowed: {sorted(FACE_TYPES)})")
        return
    if t in ("black_card", "logo"):
        if not f.get("lines"):
            errs.append(f"{where}: {t} needs non-empty 'lines'")
    elif t == "photo":
        img = f.get("image")
        if not img:
            errs.append(f"{where}: photo needs 'image'")
        elif not _exists(assets_root, img):
            errs.append(f"{where}: image not found: {img}")
    elif t == "cast_card":
        if not f.get("image"):
            errs.append(f"{where}: cast_card needs 'image'")
        elif not _exists(assets_root, f["image"]):
            errs.append(f"{where}: image not found: {f['image']}")
        if not f.get("name"):
            errs.append(f"{where}: cast_card needs 'name'")


def validate_spec(spec, catalog=None):
    errs = []
    assets_root = spec.get("assets_root")
    if not assets_root:
        errs.append("spec missing 'assets_root'")
        return errs
    assets_root = assets_root.replace("\\", "/")
    music = set((catalog or {}).get("music", []))
    sfx = set((catalog or {}).get("sfx", []))

    scenes = spec.get("scenes")
    if not scenes:
        errs.append("spec has no scenes")
        return errs

    ids = set()
    for i, sc in enumerate(scenes):
        w = f"scene[{i}] id={sc.get('id', '?')}"
        sid = sc.get("id")
        if not sid:
            errs.append(f"{w}: missing 'id'")
        elif sid in ids:
            errs.append(f"{w}: duplicate id '{sid}'")
        else:
            ids.add(sid)

        t = sc.get("type")
        if t not in SCENE_TYPES:
            errs.append(f"{w}: type '{t}' invalid (allowed: {sorted(SCENE_TYPES)})")
            continue

        if t == "reveal":
            for side in ("before", "after"):
                if side not in sc:
                    errs.append(f"{w}: reveal needs '{side}'")
                else:
                    _check_face(sc[side], f"{w}.{side}", assets_root, errs)
        elif t == "video":
            if not sc.get("video"):
                errs.append(f"{w}: video needs 'video'")
            elif not _exists(assets_root, sc["video"]):
                errs.append(f"{w}: video not found: {sc['video']}")
        else:
            _check_face(sc, w, assets_root, errs)

        # timing / audio (video scene carries its own audio, so music optional there)
        if t != "video":
            m = sc.get("music")
            if not m:
                errs.append(f"{w}: missing 'music'")
            elif music and m not in music and not os.path.isabs(m) and not _exists(assets_root, m):
                errs.append(f"{w}: music '{m}' not in catalog")
            if not sc.get("duration"):
                errs.append(f"{w}: missing 'duration'")
        s = sc.get("sfx")
        if s and sfx and s not in sfx:
            errs.append(f"{w}: sfx '{s}' not in catalog")

        errs += _num_errs(sc, w)

    return errs
