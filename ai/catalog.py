# -*- coding: utf-8 -*-
"""Asset catalog — enumerate the real music / sfx files so the AI writer can only
reference filenames that actually exist on disk."""
import os

MUSIC_EXT = (".mp3", ".wav", ".m4a")
SFX_EXT = (".wav", ".mp3")


def _rel_files(root, exts, recurse=False):
    root = root.replace("\\", "/").rstrip("/")
    if not os.path.isdir(root):
        return []
    out = []
    if recurse:
        for dp, _dn, fns in os.walk(root):
            for fn in fns:
                if fn.lower().endswith(exts):
                    rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
                    out.append(rel)
    else:
        for fn in sorted(os.listdir(root)):
            if fn.lower().endswith(exts):
                out.append(fn)
    return sorted(out)


def resolve_dir(assets_root, d):
    """A media dir may be absolute (a shared library) or relative to assets_root."""
    d = d.replace("\\", "/")
    if os.path.isabs(d):
        return d.rstrip("/") + "/"
    return assets_root.replace("\\", "/").rstrip("/") + "/" + d.rstrip("/") + "/"


def build_catalog(assets_root, music_dir="03_Music/", sfx_dir="04_Sound FX/"):
    return {
        "music": _rel_files(resolve_dir(assets_root, music_dir), MUSIC_EXT, recurse=False),
        "sfx": _rel_files(resolve_dir(assets_root, sfx_dir), SFX_EXT, recurse=True),
    }
