# -*- coding: utf-8 -*-
"""Depth-based 3D parallax ("3D photo") from a single still.

A monocular depth model (Depth-Anything V2) estimates what's near vs far, then we
displace pixels by their depth while a virtual camera orbits — near pixels move
more than far ones, so the subject genuinely separates from the background.

Default "contain" mode keeps the whole photo (aspect-fit) over a blurred cover
background and applies the depth warp to the photo — so portraits aren't cropped.

    python -m engine.depth3d <photo> <out.mp4> [dur] [fps] [amp]

The depth model loads lazily and is cached; the first call downloads it (~100MB).
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

_PIPE = None


def _pipe():
    global _PIPE
    if _PIPE is None:
        from transformers import pipeline
        _PIPE = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")
    return _PIPE


def depth_map(pil_img, blur=4):
    """float32 depth normalized to [0,1] (1 = nearest), lightly smoothed."""
    out = _pipe()(pil_img)
    d = np.asarray(out["depth"], dtype=np.float32)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)     # Depth-Anything: bright = near
    dimg = Image.fromarray((d * 255).astype(np.uint8)).resize(pil_img.size)
    return np.asarray(dimg.filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255.0


def _bilinear(img, sx, sy):
    H, W = img.shape[:2]
    x0 = np.floor(sx).astype(np.int32); y0 = np.floor(sy).astype(np.int32)
    x1 = x0 + 1; y1 = y0 + 1
    wx = (sx - x0)[..., None]; wy = (sy - y0)[..., None]
    x0 = np.clip(x0, 0, W - 1); x1 = np.clip(x1, 0, W - 1)
    y0 = np.clip(y0, 0, H - 1); y1 = np.clip(y1, 0, H - 1)
    Ia = img[y0, x0]; Ib = img[y0, x1]; Ic = img[y1, x0]; Id = img[y1, x1]
    return Ia * (1 - wx) * (1 - wy) + Ib * wx * (1 - wy) + Ic * (1 - wx) * wy + Id * wx * wy


def _cover(pil_img, W, H):
    r = max(W / pil_img.width, H / pil_img.height)
    im = pil_img.resize((int(pil_img.width * r) + 1, int(pil_img.height * r) + 1))
    x = (im.width - W) // 2; y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def _blur_cover(pil_img, W, H, bright=0.5, blur=26):
    b = _cover(pil_img, W, H).filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(Image.eval(b, lambda p: int(p * bright)), dtype=np.float32)


def render_3d_clip(photo_path, out_mp4, dur=4.0, fps=30, amp=70.0, size=(1920, 1080),
                   mode="contain", fg_frac=0.92, depth_zoom=0.16, verbose=True):
    W, H = size
    src = Image.open(photo_path).convert("RGB")

    if mode == "cover":
        fg = np.asarray(_cover(src, W, H), dtype=np.float32)
        depth = depth_map(_cover(src, W, H))
        bg = None
        fw, fh = W, H
    else:  # contain — keep the whole photo, warp it over a blurred bg
        r = min(W * fg_frac / src.width, H * fg_frac / src.height)
        fw, fh = max(2, int(src.width * r)), max(2, int(src.height * r))
        fg_pil = src.resize((fw, fh))
        fg = np.asarray(fg_pil, dtype=np.float32)
        if verbose:
            print("estimating depth...")
        depth = depth_map(fg_pil)
        bg = _blur_cover(src, W, H)

    pivot = float(np.median(depth))
    disp = depth - pivot                                   # near>0, far<0
    Xf, Yf = np.meshgrid(np.arange(fw, dtype=np.float32), np.arange(fh, dtype=np.float32))
    cxf, cyf = fw / 2.0, fh / 2.0
    if bg is not None:
        Xb, Yb = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        cxb, cyb = W / 2.0, H / 2.0
    ox0, oy0 = (W - fw) // 2, (H - fh) // 2                 # fg paste offset

    n = max(1, int(round(dur * fps)))
    preset = os.environ.get("FTS_FFMPEG_PRESET", "medium")   # cloud sets "veryfast"
    crf = os.environ.get("FTS_FFMPEG_CRF", "19")
    args = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
            "-r", str(fps), "-i", "-", "-an", "-t", f"{dur}", "-r", str(fps),
            "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", out_mp4]
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    two_pi = 2.0 * np.pi
    for i in range(n):
        t = i / max(1, n - 1)
        zf = 1.06 + 0.03 * t
        ox = amp * np.sin(two_pi * t)
        oy = amp * 0.5 * np.cos(two_pi * t)
        breath = 0.5 - 0.5 * np.cos(two_pi * t)            # 0->1->0 smooth push-in
        rf = 1.0 + depth_zoom * disp * breath              # near grows more than far (volumetric)
        sx = cxf + (Xf - cxf) / (zf * rf) + disp * ox
        sy = cyf + (Yf - cyf) / (zf * rf) + disp * oy
        fgf = _bilinear(fg, sx, sy)
        if bg is None:
            frame = fgf
        else:
            zb = 1.04 + 0.05 * t
            bx = cxb + (Xb - cxb) / zb
            by = cyb + (Yb - cyb) / zb
            frame = _bilinear(bg, bx, by)
            frame[oy0:oy0 + fh, ox0:ox0 + fw] = fgf
        p.stdin.write(frame.clip(0, 255).astype(np.uint8).tobytes())
        if verbose and (i % 20 == 0):
            print(f"  frame {i+1}/{n}")
    p.stdin.close(); p.wait()
    if verbose:
        print("DONE ->", out_mp4)
    return out_mp4


if __name__ == "__main__":
    a = sys.argv
    render_3d_clip(a[1], a[2],
                   dur=float(a[3]) if len(a) > 3 else 4.0,
                   fps=int(a[4]) if len(a) > 4 else 30,
                   amp=float(a[5]) if len(a) > 5 else 42.0)
