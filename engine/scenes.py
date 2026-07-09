# -*- coding: utf-8 -*-
"""Data-driven scene composition for Family Trailer Studio.

Ports the proven PIL primitives from the Operation Hair Transfer pipeline into a
parametrized SceneRenderer. Each scene in a trailer spec is a plain dict; the
renderer bakes it into one or more 1920x1080 PNG frames.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
try:
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover
    from bidi import get_display

# Force BASIC text layout so Pillow never applies its own bidi/shaping (raqm). We
# reorder RTL ourselves via python-bidi; without this, a raqm-enabled Pillow (as on
# Linux/cloud) would reverse Hebrew a SECOND time and it renders backwards.
try:
    _BASIC_LAYOUT = ImageFont.Layout.BASIC
except AttributeError:
    _BASIC_LAYOUT = ImageFont.LAYOUT_BASIC

DEFAULT_FONTS = {"HE": "arialbd.ttf", "BLACK": "ariblk.ttf", "IMP": "impact.ttf"}
DEFAULT_PALETTE = {
    "GOLD": [216, 178, 60], "WHITE": [244, 244, 244],
    "RED": [210, 45, 45], "PINK": [226, 110, 150], "BLACK_BG": [8, 8, 10],
}


class SceneRenderer:
    def __init__(self, assets_root, out_dir, fonts_dir="C:/Windows/Fonts/",
                 fonts=None, palette=None, size=(1920, 1080)):
        self.A = assets_root.replace("\\", "/").rstrip("/") + "/"
        self.OUT = out_dir.replace("\\", "/").rstrip("/") + "/"
        os.makedirs(self.OUT, exist_ok=True)
        self.FD = fonts_dir.replace("\\", "/").rstrip("/") + "/"
        self.fonts = {**DEFAULT_FONTS, **(fonts or {})}
        pal = {**DEFAULT_PALETTE, **(palette or {})}
        self.pal = {k: tuple(v) for k, v in pal.items()}
        self.W, self.H = size

    # ---- low-level helpers -------------------------------------------------
    def font(self, key, s):
        return ImageFont.truetype(self.FD + self.fonts.get(key, key), s, layout_engine=_BASIC_LAYOUT)

    def color(self, c):
        if c is None:
            return self.pal["WHITE"]
        if isinstance(c, str):
            return self.pal.get(c, self.pal["WHITE"])
        return tuple(c)

    def _shp(self, t, rtl):
        return get_display(t) if rtl else t

    def _fit_font(self, text, fkey, rtl, track):
        """Latin display fonts (Impact / Arial-Black) have no Hebrew glyphs, so
        Hebrew typed into such a line renders as tofu boxes. Detect Hebrew and
        fall back to the Hebrew bold font with RTL. Makes edits 'just work'."""
        if fkey in ("IMP", "BLACK") and any("֐" <= ch <= "׿" for ch in text or ""):
            return "HE", True, 0
        return fkey, rtl, track

    def cover_blur(self, im, bright=0.55, blur=28):
        W, H = self.W, self.H
        r = max(W / im.width, H / im.height)
        b = im.resize((int(im.width * r) + 2, int(im.height * r) + 2))
        x = (b.width - W) // 2
        y = (b.height - H) // 2
        b = b.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(blur))
        return Image.eval(b, lambda p: int(p * bright))

    def contain(self, im, mw, mh):
        r = min(mw / im.width, mh / im.height)
        return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))))

    def bottom_grad(self, c, h=360, strength=210):
        W, H = self.W, self.H
        g = Image.new("L", (1, h), 0)
        for i in range(h):
            g.putpixel((0, i), int(strength * (i / h) ** 1.5))
        g = g.resize((W, h))
        sh = Image.new("RGBA", (W, h), (0, 0, 0, 255))
        sh.putalpha(g)
        c.alpha_composite(sh, (0, H - h))

    def vignette(self, c, strength=160):
        W, H = self.W, self.H
        mask = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse([-W * 0.25, -H * 0.25, W * 1.25, H * 1.25], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(300))
        dark = Image.new("RGBA", (W, H), (0, 0, 0, strength))
        dark.putalpha(Image.eval(mask, lambda p: 255 - p))
        c.alpha_composite(dark)

    def ctext(self, d, cy, t, fnt, fill, rtl=False, track=0, soff=5, stroke=0, sfill=(0, 0, 0)):
        W = self.W
        s = self._shp(t, rtl)
        if track == 0:
            bb = d.textbbox((0, 0), s, font=fnt, stroke_width=stroke)
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            x = (W - w) // 2 - bb[0]
            y = cy - h // 2 - bb[1]
            d.text((x + soff, y + soff), s, font=fnt, fill=(0, 0, 0, 200))
            d.text((x, y), s, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=sfill)
        else:
            ws = [d.textlength(c, font=fnt) for c in s]
            tot = sum(ws) + track * (len(s) - 1)
            x = (W - tot) / 2
            asc, desc = fnt.getmetrics()
            y = cy - (asc + desc) / 2
            for c, cw in zip(s, ws):
                d.text((x + soff, y + soff), c, font=fnt, fill=(0, 0, 0, 200))
                d.text((x, y), c, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=sfill)
                x += cw + track

    def _save(self, c, n):
        c.convert("RGB").save(self.OUT + n, quality=95)
        return self.OUT + n

    # ---- scene builders ----------------------------------------------------
    def black_card(self, name, lines):
        W, H = self.W, self.H
        c = Image.new("RGBA", (W, H), self.color("BLACK_BG") + (255,))
        self.vignette(c, 200)
        d = ImageDraw.Draw(c)
        for ln in lines:
            fk, rtl, tr = self._fit_font(ln["t"], ln.get("f", "HE"),
                                         ln.get("rtl", False), ln.get("tr", 0))
            self.ctext(d, ln["y"], ln["t"], self.font(fk, ln["s"]),
                       self.color(ln.get("c", "WHITE")), rtl=rtl,
                       track=tr, stroke=ln.get("st", 0))
        return self._save(c, name)

    def photo_caption(self, name, image_rel, caption, csize=78, ccolor="GOLD"):
        W, H = self.W, self.H
        src = Image.open(self.A + image_rel).convert("RGB")
        c = self.cover_blur(src).convert("RGBA")
        fg = self.contain(src, W, H).convert("RGBA")
        c.alpha_composite(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
        self.vignette(c, 120)
        self.bottom_grad(c, 380, 220)
        if caption:
            self.ctext(ImageDraw.Draw(c), H - 150, caption, self.font("HE", csize),
                       self.color(ccolor), rtl=True, stroke=2)
        return self._save(c, name)

    def cast_card(self, name, image_rel, big, role, tag="", tag_color="PINK"):
        W, H = self.W, self.H
        src = Image.open(self.A + image_rel).convert("RGB")
        c = self.cover_blur(src, 0.4).convert("RGBA")
        fg = self.contain(src, 980, 790).convert("RGBA")
        c.alpha_composite(fg, ((W - fg.width) // 2, 95))
        self.vignette(c, 150)
        self.bottom_grad(c, 440, 235)
        d = ImageDraw.Draw(c)
        tcol = self.color(tag_color)
        if tag:
            s = self._shp(tag, True)
            tf = self.font("HE", 46)
            bb = d.textbbox((0, 0), s, font=tf)
            tw = bb[2] - bb[0]
            d.rounded_rectangle([(W - tw) // 2 - 30, 40, (W + tw) // 2 + 30, 110],
                                radius=20, fill=(0, 0, 0, 150), outline=tcol, width=3)
            self.ctext(d, 76, tag, tf, tcol, rtl=True, soff=0)
        nfk, nrtl, ntr = self._fit_font(big, "BLACK", False, 12)
        self.ctext(d, H - 238, big, self.font(nfk, 150), self.color("WHITE"),
                   rtl=nrtl, track=ntr, stroke=3, soff=8)
        d.rectangle([W // 2 - 170, H - 150, W // 2 + 170, H - 144], fill=self.color("GOLD"))
        self.ctext(d, H - 95, role, self.font("HE", 60), self.color("GOLD"), rtl=True, stroke=1)
        return self._save(c, name)

    def transparent_caption(self, name, caption, size=74, color="GOLD"):
        W, H = self.W, self.H
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.bottom_grad(c, 340, 205)
        self.ctext(ImageDraw.Draw(c), H - 135, caption, self.font("HE", size),
                   self.color(color), rtl=True, stroke=2)
        c.save(self.OUT + name)
        return self.OUT + name

    def coming_soon(self, name, subtitle="בקרוב", rating_letter="B", rating_word="FOR BALD"):
        W, H = self.W, self.H
        c = Image.new("RGBA", (W, H), self.color("BLACK_BG") + (255,))
        self.vignette(c, 200)
        d = ImageDraw.Draw(c)
        self.ctext(d, 360, "COMING SOON", self.font("IMP", 150), self.color("GOLD"),
                   track=14, stroke=3, soff=8)
        self.ctext(d, 510, subtitle, self.font("HE", 58), self.color("WHITE"), rtl=True, stroke=1)
        bx0, by0, bx1, by1 = W // 2 - 360, 660, W // 2 + 360, 850
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=14, fill=(235, 235, 235),
                            outline=(20, 20, 20), width=6)
        d.line([W // 2 - 150, by0 + 30, W // 2 - 150, by1 - 30], fill=(20, 20, 20), width=5)
        f1 = self.font("BLACK", 150)
        bb = d.textbbox((0, 0), rating_letter, font=f1)
        d.text((bx0 + 60 + (180 - (bb[2] - bb[0])) // 2 - bb[0],
                (by0 + by1) // 2 - (bb[3] - bb[1]) // 2 - bb[1]),
               rating_letter, font=f1, fill=(15, 15, 15))
        f2 = self.font("BLACK", 66)
        d.text((W // 2 - 120, (by0 + by1) // 2 - 33), rating_word, font=f2, fill=(15, 15, 15))
        return self._save(c, name)

    # ---- dispatch ----------------------------------------------------------
    def render(self, scene):
        """Render a scene dict to frame file(s). Returns dict of frame paths."""
        t = scene["type"]
        sid = scene["id"]
        if t == "reveal":
            b = self._render_face(scene["before"], sid + "_before.png")
            a = self._render_face(scene["after"], sid + "_after.png")
            return {"before": b, "after": a}
        frame = self._render_face(scene, sid + ".png")
        out = {"frame": frame}
        if scene.get("overlay_caption"):
            out["overlay"] = self.transparent_caption(
                sid + "_cap.png", scene["overlay_caption"],
                scene.get("overlay_size", 74), scene.get("overlay_color", "GOLD"))
        return out

    def _render_face(self, s, out_name):
        t = s["type"]
        if t in ("black_card", "logo"):
            return self.black_card(out_name, s["lines"])
        if t == "photo":
            return self.photo_caption(out_name, s["image"], s.get("caption", ""),
                                      s.get("caption_size", 78), s.get("caption_color", "GOLD"))
        if t == "cast_card":
            return self.cast_card(out_name, s["image"], s["name"], s["role"],
                                  s.get("tag", ""), s.get("tag_color", "PINK"))
        if t == "coming_soon":
            return self.coming_soon(out_name, s.get("subtitle", "בקרוב"),
                                    s.get("rating_letter", "B"), s.get("rating_word", "FOR BALD"))
        if t == "video":
            # video scenes carry no still frame; caption handled at overlay level
            return None
        raise ValueError(f"unknown scene face type: {t}")
