#!/usr/bin/env python3
"""Render the preview images used in README.md.

Imports generate.py directly, so the previews always show the current
geometry rather than a stale export.
"""
import importlib.util, os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUTD = os.path.join(REPO, "preview")

spec = importlib.util.spec_from_file_location("gen", os.path.join(HERE, "generate.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

DARK, LIGHT = "#0d0d16", "#f2f2f4"
INK_D, INK_L = "#6f7392", "#8a8a99"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLDF = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(sz, bold=False):
    try:
        return ImageFont.truetype(BOLDF if bold else FONT, sz)
    except OSError:
        return ImageFont.load_default()


def glyph(name, size):
    fn, _hot, _fr = gen.CURSORS[name]
    return gen.render(fn, 0, size)


def sheet(names, size, cols, bg, ink, label=True, cell=None, pad=18, title=None):
    cell = cell or size + 34
    rows = (len(names) + cols - 1) // cols
    head = 46 if title else 0
    lblh = 16 if label else 0
    W, H = cols * cell + pad * 2, rows * (cell + lblh) + pad * 2 + head
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    if title:
        d.text((pad, pad + 2), title, font=font(19, True),
               fill="#00e5e5" if bg == DARK else "#0d7a7a")
    f = font(10)
    for i, n in enumerate(names):
        cx = pad + (i % cols) * cell
        cy = pad + head + (i // cols) * (cell + lblh)
        g = glyph(n, size)
        im.paste(g, (cx + (cell - size) // 2, cy + (cell - size) // 2), g)
        if label:
            w = d.textlength(n, font=f)
            d.text((cx + (cell - w) / 2, cy + cell - 4), n, font=f, fill=ink)
    return im


ALL = ["default", "pointer", "text", "vertical-text", "crosshair", "cell",
       "wait", "progress", "help", "context-menu", "not-allowed", "no-drop",
       "copy", "alias", "move", "all-scroll", "grab", "grabbing",
       "ns-resize", "ew-resize", "nesw-resize", "nwse-resize",
       "col-resize", "row-resize", "zoom-in", "zoom-out",
       "up-arrow", "down-arrow", "left-arrow", "right-arrow",
       "pencil", "X_cursor", "dotbox"]

HERO = ["default", "pointer", "text", "move", "ew-resize", "copy",
        "not-allowed", "wait"]


def banner():
    size, cell, pad = 64, 96, 30
    W, H = len(HERO) * cell + pad * 2, 200
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    d.text((pad, 26), "Cyberpunk-Neon", font=font(38, True), fill="#00ffff")
    d.text((pad + 3, 72), "a neon outline cursor theme for GNOME / X11 / Wayland",
           font=font(14), fill="#6f7392")
    for i, n in enumerate(HERO):
        g = glyph(n, size)
        im.paste(g, (pad + i * cell + (cell - size) // 2, 112), g)
    return im


# Six cursors for the product logo: one from each colour family, plus the
# two most recognisable shapes.
LOGO = ["default", "pointer", "move", "copy", "not-allowed", "wait"]


def logo(side=512, size=96, cols=3):
    im = Image.new("RGB", (side, side), DARK)
    rows = (len(LOGO) + cols - 1) // cols
    pad = 56
    cw = (side - pad * 2) / cols
    ch = cw
    top = (side - rows * ch) / 2
    for i, n in enumerate(LOGO):
        g = glyph(n, size)
        x = pad + (i % cols) * cw + (cw - size) / 2
        y = top + (i // cols) * ch + (ch - size) / 2
        im.paste(g, (int(round(x)), int(round(y))), g)
    return im


def sizes_strip():
    sizes = gen.SIZES
    cell, pad = 110, 26
    W, H = len(sizes) * cell + pad * 2, 150
    im = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(im)
    d.text((pad, 18), "Native sizes — every one is hand-snapped to the pixel grid,"
           " not a resample", font=font(13), fill="#6f7392")
    for i, s in enumerate(sizes):
        g = glyph("default", s)
        x = pad + i * cell
        im.paste(g, (x + (cell - s) // 2, 58 + (96 - s) // 2), g)
        t = f"{s}px"
        d.text((x + (cell - d.textlength(t, font=font(12))) / 2, 126),
               t, font=font(12), fill="#8a8ea8")
    return im


def main():
    os.makedirs(OUTD, exist_ok=True)
    jobs = [
        ("logo.png", logo()),
        ("banner.png", banner()),
        ("all-cursors-dark.png",
         sheet(ALL, 48, 7, DARK, INK_D, title="All 33 cursors")),
        ("all-cursors-light.png",
         sheet(ALL, 48, 7, LIGHT, INK_L,
               title="The same set on a light background")),
        ("sizes.png", sizes_strip()),
    ]
    for name, im in jobs:
        p = os.path.join(OUTD, name)
        im.save(p, optimize=True)
        print(f"  {name:24s} {im.size[0]}x{im.size[1]}")
    print(f"\npreviews written to {OUTD}")


if __name__ == "__main__":
    main()
