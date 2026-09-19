#!/usr/bin/env python3
"""Generate the Cyberpunk-Neon Xcursor theme from the reference screenshot style.

Style derived from ~/Pictures/cursor-style-cyberpunk:
  - hard-edged neon outline strokes, no bloom, no casing
  - cyan  #00FFFF  primary / navigation
  - yellow #F9F002 position + precision markers

Crispness: stroke widths are snapped to whole device pixels at the target
size, and axis-aligned glyphs are centred on the pixel grid, so edges land
on pixel boundaries instead of straddling them.
"""
import argparse, math, os, shutil, subprocess, sys, tempfile
import cairo
from PIL import Image

THEME = "Cyberpunk-Neon"
REPO  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT   = os.path.join(REPO, THEME)      # overridden by --out / --install
WORK  = None                           # a temp dir, created in main()
SIZES = [24, 28, 32, 48, 64, 96]
SS    = 4                      # supersample factor

# ---------------------------------------------------------------- palette ---
CYAN    = (0.00, 1.00, 1.00, 1.00)   # #00FFFF  navigation
YEL     = (0.976, 0.941, 0.008, 1.0) # #F9F002  position / precision
MAG     = (1.00, 0.17, 0.84, 1.00)   # #FF2BD6  transform / resize
RED     = (1.00, 0.153, 0.251, 1.0)  # #FF2740  blocked
GRN     = (0.00, 1.00, 0.612, 1.00)  # #00FF9C  affirmative (copy / link)
DIM     = (0.00, 0.42, 0.46, 1.00)   # dim cyan for spinner track

FILLC   = (0.0, 0.0, 0.0, 0.0)         # interior body; alpha 0 = transparent
RIM     = 1                            # edge thickness, device pixels
RIM_A   = 0.85                         # edge opacity
# The edge takes each region's OWN colour, multiplied down to this fraction,
# rather than a flat black -- so cyan gets dark teal, yellow dark olive, and a
# two-colour glyph like `copy` gets the right shade on each part of itself.
DARKEN  = 0.25

# Every glyph is drawn inside a margin so the stroke, its miter overhang and
# the rim all fit on the canvas. Without this the ink runs off the edge and
# gets clipped -- which it silently did on 23 of 33 cursors.
# A fixed pixel cost, not a fraction: the overhead the margin has to cover
# (rim + miter overhang) barely grows with size, so a proportional margin
# wasted 5-9 px at the larger sizes while 24 px sat exactly at its limit.
PAD_PX   = 2
MITERLIM = 1.3                         # bounds spikes at very sharp corners

LW      = 0.072                        # nominal stroke, normalized units
BOLD    = 1.15                         # weight bump for everything but the dart
RC, RJ  = cairo.LINE_CAP_ROUND, cairo.LINE_JOIN_ROUND
BUTT    = cairo.LINE_CAP_BUTT
MITER   = cairo.LINE_JOIN_MITER


# ---------------------------------------------------------------- painter ---
class P:
    """Draws one glyph in two ordered passes onto a single surface:
    pass 'under' lays every interior body + black border, pass 'neon' lays
    every stroke on top, so no later border can bite into an earlier stroke."""

    def __init__(self, ctx, size, eff, pad):
        # size = cursor size in px (sets stroke weight, so weights are
        # unaffected by the margin); eff/pad = the inset drawing box, so
        # 1 normalized unit spans `eff` device px starting at `pad`.
        self.c, self.size, self.eff, self.pad = ctx, size, eff, pad
        self.sc, self.mode = 1.0, "under"
        self.bold = True          # cleared while drawing the dart

    # -- pixel-grid helpers ------------------------------------------------
    def dev(self, v):
        """Normalized coordinate -> device pixel."""
        return self.pad + v * self.eff

    def wpx(self, lw):
        """Stroke width snapped to a whole device pixel at the final size.
        Bold strokes gain at least one pixel so the bump shows at every size,
        not just where 1.35x happens to cross a rounding boundary."""
        base = lw * self.size
        if self.bold:
            base *= BOLD
        return max(1, math.floor(base + 0.5))  # not round(): avoid banker's

    def snap(self, lw):
        return self.wpx(lw) / self.eff

    def ctr(self, lw):
        """Canvas centre aligned so a stroke of this width has crisp edges."""
        w, half = self.wpx(lw), self.size / 2.0
        c = math.floor(half) + 0.5 if w % 2 else round(half)
        return (c - self.pad) / self.eff

    def sn(self, v):
        """Snap a coordinate to the device pixel grid."""
        return (round(self.dev(v)) - self.pad) / self.eff

    # -- transform ---------------------------------------------------------
    def push(self, tx=0.0, ty=0.0, s=1.0, rot=0.0):
        st = self.sc
        self.c.save(); self.c.translate(tx, ty); self.c.rotate(rot); self.c.scale(s, s)
        self.sc *= s
        return st

    def pop(self, st):
        self.c.restore(); self.sc = st

    # -- core stroke -------------------------------------------------------
    def stroke(self, build, color=CYAN, lw=LW, close=False, fill=False,
               cap=RC, join=RJ):
        c, lw_n = self.c, self.snap(lw)
        if self.mode == "under":
            if fill and FILLC[3] > 0:
                c.new_path(); build(c); c.close_path()
                c.set_source_rgba(*FILLC); c.fill()
            return
        # The rim is NOT stroked here. Doing it per primitive gave every
        # overlapping stroke its own edge, leaving black slivers in the gaps
        # between them. It is derived once from the finished glyph instead.
        c.new_path(); build(c)
        if close: c.close_path()
        c.set_line_cap(cap); c.set_line_join(join)
        c.set_miter_limit(MITERLIM)
        c.set_line_width(lw_n / self.sc)
        c.set_source_rgba(*color); c.stroke()

    # -- primitives --------------------------------------------------------
    def poly(self, pts, close=True, **kw):
        def b(c):
            c.move_to(*pts[0])
            for p in pts[1:]:
                c.line_to(*p)
        self.stroke(b, close=close, **kw)

    def line(self, a, b_, **kw):
        self.poly([a, b_], close=False, **kw)

    def circle(self, cx, cy, r, **kw):
        self.stroke(lambda c: c.arc(cx, cy, r, 0, 2 * math.pi), close=True, **kw)

    def arc(self, cx, cy, r, a0, a1, **kw):
        self.stroke(lambda c: c.arc(cx, cy, r, a0, a1), close=False, **kw)

    def dot(self, cx, cy, r, color=CYAN):
        rr, c = r * (BOLD if self.bold else 1.0), self.c
        if self.mode == "under":
            return
        c.new_path(); c.arc(cx, cy, rr, 0, 2 * math.pi)
        c.set_source_rgba(*color); c.fill()

    def head(self, x, y, ang, s, lw=None, spread=132.0, **kw):
        """Chevron arrowhead at (x,y) opening back from direction `ang`."""
        for sg in (1, -1):
            b = ang + sg * math.radians(spread)
            self.line((x, y), (x + s * math.cos(b), y + s * math.sin(b)),
                      lw=LW if lw is None else lw, **kw)

    def darrow(self, ang, half=0.40, hs=0.26, color=MAG,
               shaft=0.046, headlw=0.082):
        """Double-headed arrow: heads deliberately broader than the shaft."""
        axis = abs(math.sin(2 * ang)) < 1e-6          # horizontal or vertical
        c = self.ctr(shaft) if axis else 0.5
        dx, dy = math.cos(ang), math.sin(ang)
        a = (c - dx * half, c - dy * half)
        b = (c + dx * half, c + dy * half)
        self.line(a, b, color=color, lw=shaft, cap=BUTT)
        self.head(*b, ang, hs, lw=headlw, color=color, join=MITER)
        self.head(*a, ang + math.pi, hs, lw=headlw, color=color, join=MITER)


# ------------------------------------------------------------- the glyphs ---
# Dart traced from the reference, then mirrored about its own 45-degree axis
# so wing and tail are exactly equal: wing = tip+(k,m), tail = tip+(m,k), and
# the notch sits on the axis at tip+(n,n).
# Length along the pointing axis vs. span across it is now 1.17 (was 1.33),
# so it reads less stretched while keeping the same overall footprint.
_T, _S = (0.06, 0.05), 0.80          # tip, and overall extent
# _N sets how deep the notch between the two tails cuts back toward the tip:
# lower = deeper. 0.603 was shallow, 0.540 pulls the waist further in.
_K, _M, _N = 1.000, 0.400, 0.540
ARROW = [
    _T,
    (_T[0] + _S * _K, _T[1] + _S * _M),   # wing
    (_T[0] + _S * _N, _T[1] + _S * _N),   # notch, on the axis
    (_T[0] + _S * _M, _T[1] + _S * _K),   # tail, mirror of the wing
]
TIP = _T


def arrow(p, color=CYAN):
    # the dart alone keeps the nominal weight; everything else is bolder.
    # fill=True gives the interior a translucent black body.
    was, p.bold = p.bold, False
    p.poly(ARROW, close=True, fill=True, color=color, join=MITER)
    p.bold = was


def dart_scaled(p, s):
    """Scale the dart about its own TIP. Scaling about the origin instead
    dragged the tip toward (0,0), off the canvas at small sizes, and left the
    declared hotspot sitting away from the drawn point."""
    return p.push(_T[0] * (1 - s), _T[1] * (1 - s), s)


def badged(p, draw_badge):
    """Small dart in the upper-left, badge in the lower-right quadrant."""
    st = dart_scaled(p, 0.60); arrow(p); p.pop(st)
    st = p.push(0.44, 0.44, 0.515); draw_badge(p); p.pop(st)


def c_default(p, f):
    arrow(p)


def c_pointer(p, f):
    """The yellow neon cross, waisted where the four arms meet.

    Tapered arms rather than two crossing bars, so the junction pinches
    in instead of piling up into a solid block. Traced as ONE closed
    12-point outline rather than four overlapping quads, so the black
    border wraps the silhouette instead of drawing lines across the
    junction where the arms meet."""
    a  = p.sn(0.38)               # arm length from centre
    w1 = p.snap(0.108) / 2.0      # half-width at the tip
    w0 = p.snap(0.026) / 2.0      # half-width at the waist
    c  = p.ctr(0.108)
    # Where two neighbouring arms' flanks cross, on the 45-degree diagonal.
    v = a * w0 / (a + w0 - w1)

    pts = []
    for k in range(4):
        ca, sa = math.cos(k * math.pi / 2), math.sin(k * math.pi / 2)
        for x, y in ((a, -w1), (a, w1), (v, v)):
            pts.append((c + ca * x - sa * y, c + sa * x + ca * y))

    def build(ctx):
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)

    if p.mode == "under":
        return
    ctx = p.c
    ctx.new_path(); build(ctx); ctx.close_path()
    ctx.set_source_rgba(*YEL); ctx.fill()


def c_crosshair(p, f):
    lw, a, g = 0.062, 0.44, 0.11
    c = p.ctr(lw)
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p.line((c + sx * g, c + sy * g), (c + sx * a, c + sy * a),
               color=YEL, lw=lw, cap=BUTT)


def c_cell(p, f):
    lw, a = 0.05, 0.425
    c = p.ctr(lw)
    p.line((c - a, c), (c + a, c), color=YEL, lw=lw, cap=BUTT)
    p.line((c, c - a), (c, c + a), color=YEL, lw=lw, cap=BUTT)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy, s = c + sx * a, c + sy * a, 0.11
        p.poly([(cx - sx * s, cy), (cx, cy), (cx, cy - sy * s)],
               close=False, color=YEL, lw=lw, join=MITER)


def c_text(p, f):
    """Wide-serif I-beam: long horizontal bars, shorter stem."""
    lw, h, w = 0.062, 0.29, 0.22
    c = p.ctr(lw)
    p.line((c, c - h), (c, c + h), color=YEL, lw=lw, cap=BUTT)
    for sy in (-1, 1):
        p.line((c - w, c + sy * h), (c + w, c + sy * h), color=YEL, lw=lw, cap=BUTT)


def c_vtext(p, f):
    lw, h, w = 0.062, 0.29, 0.22
    c = p.ctr(lw)
    p.line((c - h, c), (c + h, c), color=YEL, lw=lw, cap=BUTT)
    for sx in (-1, 1):
        p.line((c + sx * h, c - w), (c + sx * h, c + w), color=YEL, lw=lw, cap=BUTT)


def _spinner(p, f, cx, cy, r, lw=LW):
    p.circle(cx, cy, r, color=DIM, lw=lw * 0.8)
    a0 = (f / 12.0) * 2 * math.pi
    p.arc(cx, cy, r, a0, a0 + math.radians(105), color=CYAN, lw=lw)


def c_wait(p, f):
    _spinner(p, f, 0.5, 0.5, 0.30, lw=0.085)


def c_progress(p, f):
    st = dart_scaled(p, 0.58); arrow(p); p.pop(st)
    _spinner(p, f, 0.675, 0.675, 0.215, lw=0.075)


def _qmark(p):
    p.arc(0.5, 0.36, 0.20, math.radians(160), math.radians(20), color=CYAN)
    p.line((0.5, 0.56), (0.5, 0.70), color=CYAN)
    p.dot(0.5, 0.88, 0.055, CYAN)


def c_help(p, f):
    badged(p, _qmark)


def _menu(p):
    p.poly([(0.12, 0.10), (0.88, 0.10), (0.88, 0.90), (0.12, 0.90)],
           close=True, color=CYAN, fill=True, join=MITER)
    for y in (0.32, 0.50, 0.68):
        p.line((0.30, y), (0.70, y), color=CYAN, lw=0.055)


def c_context_menu(p, f):
    badged(p, _menu)


def _ban(p, color=RED):
    p.circle(0.5, 0.5, 0.40, color=color, fill=True)
    d = 0.40 * math.sin(math.radians(45))
    p.line((0.5 - d, 0.5 + d), (0.5 + d, 0.5 - d), color=color)


def c_not_allowed(p, f):
    _ban(p)


def c_no_drop(p, f):
    badged(p, _ban)


def _plusbox(p, color=GRN):
    p.poly([(0.10, 0.10), (0.90, 0.10), (0.90, 0.90), (0.10, 0.90)],
           close=True, color=color, fill=True, join=MITER)
    p.line((0.30, 0.50), (0.70, 0.50), color=color, lw=0.06)
    p.line((0.50, 0.30), (0.50, 0.70), color=color, lw=0.06)


def c_copy(p, f):
    badged(p, _plusbox)


def _linkbox(p, color=GRN):
    p.poly([(0.10, 0.10), (0.90, 0.10), (0.90, 0.90), (0.10, 0.90)],
           close=True, color=color, fill=True, join=MITER)
    p.line((0.32, 0.68), (0.68, 0.32), color=color, lw=0.06)
    p.head(0.68, 0.32, math.radians(-45), 0.22, lw=0.06, color=color, join=MITER)


def c_alias(p, f):
    badged(p, _linkbox)


def c_move(p, f):
    # heads kept clear of each other so this reads as four arrows, not a diamond
    for k in range(4):
        p.darrow(k * math.pi / 2, half=0.408, hs=0.160, color=MAG)


def c_all_scroll(p, f):
    p.circle(0.5, 0.5, 0.13, color=MAG, lw=0.055)
    for k in range(4):
        a = k * math.pi / 2
        dx, dy = math.cos(a), math.sin(a)
        tip = (0.5 + dx * 0.423, 0.5 + dy * 0.423)
        p.line((0.5 + dx * 0.22, 0.5 + dy * 0.22), tip,
               color=MAG, lw=0.046, cap=BUTT)
        p.head(*tip, a, 0.22, lw=0.082, color=MAG, join=MITER)


def _reticle(p, o):
    """Four corner brackets; `o` is how far they sit from centre."""
    s = 0.15
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy = 0.5 + sx * o, 0.5 + sy * o
        p.poly([(cx - sx * s, cy), (cx, cy), (cx, cy - sy * s)],
               close=False, color=CYAN, join=MITER)


def c_grab(p, f):
    _reticle(p, 0.38); p.dot(0.5, 0.5, 0.045, CYAN)


def c_grabbing(p, f):
    _reticle(p, 0.24); p.dot(0.5, 0.5, 0.065, CYAN)


def _boxy_pts(a, hl, hh, sh):
    """Double-headed arrow as one closed outline: a rectangular shaft box
    between two triangular heads. Stroked only, so it stays hollow."""
    m = a - hl
    return [(a, 0), (m, -hh), (m, -sh), (-m, -sh), (-m, -hh), (-a, 0),
            (-m, hh), (-m, sh), (m, sh), (m, hh)]


# Outline weight for the hollow arrows: deliberately lighter than BOLD-ed
# strokes elsewhere, otherwise the two sides of the shaft merge and the
# shape fills in solid instead of reading as an outline.
BOXLW = 0.055


def _boxy(ang, a=0.437, hl=0.222, hh=0.200, sh=0.085, bar=False):
    def g(p, f):
        axis = abs(math.sin(2 * ang)) < 1e-6
        # Drawn unbolded: at the BOLD weight the two sides of the shaft box
        # nearly meet and the connector reads as a solid slab, so it cannot be
        # slimmed by narrowing the box alone.
        was, p.bold = p.bold, False
        c = p.ctr(BOXLW) if axis else 0.5
        st = p.push(c, c, 1.0, ang)
        p.poly(_boxy_pts(a, hl, hh, sh), close=True, fill=True,
               color=MAG, lw=BOXLW, join=MITER)
        if bar:                                  # splitter handle
            p.line((0, -0.27), (0, 0.27), color=MAG, lw=BOXLW, cap=BUTT)
        p.pop(st)
        p.bold = was
    return g


def _zoom(sign):
    def g(p, f):
        p.circle(0.42, 0.42, 0.28, color=CYAN, fill=True)
        p.line((0.62, 0.62), (0.88, 0.88), color=CYAN, lw=0.085)
        p.line((0.28, 0.42), (0.56, 0.42), color=CYAN, lw=0.055)
        if sign > 0:
            p.line((0.42, 0.28), (0.42, 0.56), color=CYAN, lw=0.055)
    return g


def c_up_arrow(p, f):
    c = p.ctr(LW)
    p.line((c, 0.12), (c, 0.88), color=CYAN, cap=BUTT)
    p.head(c, 0.12, math.radians(-90), 0.26, lw=0.082, color=CYAN, join=MITER)


def _dir_arrow(ang):
    def g(p, f):
        axis = abs(math.sin(2 * ang)) < 1e-6
        c = p.ctr(LW) if axis else 0.5
        dx, dy = math.cos(ang), math.sin(ang)
        tip = (c + dx * 0.38, c + dy * 0.38)
        p.line((c - dx * 0.38, c - dy * 0.38), tip, color=CYAN, cap=BUTT)
        p.head(*tip, ang, 0.26, lw=0.082, color=CYAN, join=MITER)
    return g


def c_pencil(p, f):
    p.poly([(0.10, 0.90), (0.24, 0.60), (0.72, 0.12), (0.88, 0.28), (0.40, 0.76)],
           close=True, color=CYAN, fill=True, join=MITER)
    p.line((0.24, 0.60), (0.40, 0.76), color=CYAN, lw=0.05)


def c_xcursor(p, f):
    d = 0.34
    p.line((0.5 - d, 0.5 - d), (0.5 + d, 0.5 + d), color=RED, lw=0.095, cap=BUTT)
    p.line((0.5 + d, 0.5 - d), (0.5 - d, 0.5 + d), color=RED, lw=0.095, cap=BUTT)


def c_dotbox(p, f):
    lw = 0.05
    c = p.ctr(lw)
    p.poly([(c - 0.36, c - 0.36), (c + 0.36, c - 0.36),
            (c + 0.36, c + 0.36), (c - 0.36, c + 0.36)],
           close=True, fill=True, color=YEL, lw=lw, join=MITER)
    p.dot(c, c, 0.07, YEL)


# --------------------------------------------------------------- registry ---
C = (0.5, 0.5)
CURSORS = {
    "default":       (c_default,      TIP, 1),
    "pointer":       (c_pointer,      C,   1),
    "crosshair":     (c_crosshair,    C,   1),
    "cell":          (c_cell,         C,   1),
    "text":          (c_text,         C,   1),
    "vertical-text": (c_vtext,        C,   1),
    "wait":          (c_wait,         C,   12),
    "progress":      (c_progress,     TIP, 12),
    "help":          (c_help,         TIP, 1),
    "context-menu":  (c_context_menu, TIP, 1),
    "not-allowed":   (c_not_allowed,  C,   1),
    "no-drop":       (c_no_drop,      TIP, 1),
    "copy":          (c_copy,         TIP, 1),
    "alias":         (c_alias,        TIP, 1),
    "move":          (c_move,         C,   1),
    "all-scroll":    (c_all_scroll,   C,   1),
    "grab":          (c_grab,         C,   1),
    "grabbing":      (c_grabbing,     C,   1),
    "ns-resize":     (_boxy(math.pi / 2),             C, 1),
    "ew-resize":     (_boxy(0),                       C, 1),
    "nesw-resize":   (_boxy(-math.pi / 4),            C, 1),
    "nwse-resize":   (_boxy(math.pi / 4),             C, 1),
    "row-resize":    (_boxy(math.pi / 2, bar=True),   C, 1),
    "col-resize":    (_boxy(0, bar=True),             C, 1),
    "zoom-in":       (_zoom(+1),      C,   1),
    "zoom-out":      (_zoom(-1),      C,   1),
    "up-arrow":      (c_up_arrow,     (0.5, 0.12), 1),
    "down-arrow":    (_dir_arrow(math.pi / 2),  (0.5, 0.88), 1),
    "left-arrow":    (_dir_arrow(math.pi),      (0.12, 0.5), 1),
    "right-arrow":   (_dir_arrow(0),            (0.88, 0.5), 1),
    "pencil":        (c_pencil,       (0.09, 0.91), 1),
    "X_cursor":      (c_xcursor,      C,   1),
    "dotbox":        (c_dotbox,       C,   1),
}

# Legacy X11 / GTK-hashed names -> rendered cursor
ALIASES = {
    "default": ["left_ptr", "arrow", "top_left_arrow"],
    "pointer": ["hand", "hand1", "hand2", "pointing_hand",
                "9d800788f1b08800ae810202380a0822",
                "e29285e634086352946a0e7090d73106"],
    "text": ["xterm", "ibeam"],
    "vertical-text": ["048008013003cff3c00c801001200000"],
    "crosshair": ["cross", "cross_reverse", "tcross", "diamond_cross"],
    "cell": ["plus"],
    "wait": ["watch"],
    "progress": ["left_ptr_watch", "half-busy",
                 "00000000000000020006000e7e9ffc3f",
                 "08e8e1c95fe2fc01f976f1e063a24ccd",
                 "3ecb610c1bf2410f44200f48c40d3599"],
    "help": ["question_arrow", "whats_this", "dnd-ask", "left_ptr_help",
             "5c6cd98b3f3ebcb1f9c7f1c204630408",
             "d9ce0ab605698f320427677b458ad60b"],
    "context-menu": ["08ffe1cb5fe6fc01f906f1c063814ccf"],
    "not-allowed": ["crossed_circle", "forbidden", "circle",
                    "03b6e0fcb3499374a867c041f52298f0"],
    "no-drop": ["dnd-no-drop", "dnd_no_drop"],
    "copy": ["dnd-copy", "dnd_copy",
             "1081e37283d90000800003c07f3ef6bf",
             "6407b0e94181790501fd1e167b474872",
             "b66166c04f8c3109214a4fbd64a50fc8"],
    "alias": ["link", "dnd-link", "dnd_link",
              "640fb0e74195791501fd1ed57b41487f",
              "a2a266d0498c3104214a47bd64ab0fc8"],
    "move": ["dnd-move", "dnd_move", "fleur", "size_all",
             "4498f0e0c1937ffe01fd06f973665830",
             "9081237383d90e509aa00f00170e968f",
             "fcf21c00b30f7e3f83fe0dfd12e71cff",
             "fcf1c3c7cd4491d801f1e1c78f100000"],
    "all-scroll": ["scroll-all"],
    "grab": ["openhand", "5aca4d189052212118709018842178c0"],
    "grabbing": ["closedhand", "dnd-none", "dnd_none", "grabbing_hand",
                 "208530c400c041818281048008011002"],
    "ns-resize": ["n-resize", "s-resize", "size_ver", "v_double_arrow",
                  "sb_v_double_arrow", "double_arrow", "top_side", "bottom_side",
                  "based_arrow_down", "based_arrow_up",
                  "00008160000006810000408080010102"],
    "ew-resize": ["e-resize", "w-resize", "size_hor", "h_double_arrow",
                  "sb_h_double_arrow", "left_side", "right_side",
                  "028006030e0e7ebffc7f7070c0600140"],
    "nesw-resize": ["ne-resize", "sw-resize", "size_bdiag",
                    "top_right_corner", "bottom_left_corner",
                    "ur_angle", "ll_angle", "fd_double_arrow",
                    "c7088f0f3e6c8088236ef8e1e3e70000"],
    "nwse-resize": ["nw-resize", "se-resize", "size_fdiag",
                    "top_left_corner", "bottom_right_corner",
                    "ul_angle", "lr_angle", "bd_double_arrow",
                    "14fef782d02440884392942c11205230"],
    "col-resize": ["split_h"],
    "row-resize": ["split_v"],
    "zoom-in": ["f41c0e382c94c0958e07017e42b00462"],
    "zoom-out": ["f41c0e382c97c0938e07017e42800402"],
    "up-arrow": ["center_ptr", "sb_up_arrow"],
    "down-arrow": ["sb_down_arrow"],
    "left-arrow": ["sb_left_arrow"],
    "right-arrow": ["sb_right_arrow"],
    "pencil": ["draft", "draft_large", "draft_small"],
    "X_cursor": ["X-cursor", "x-cursor", "pirate"],
    "dotbox": ["dot_box_mask", "draped_box", "icon", "target", "dotbox_mask"],
}


# ----------------------------------------------------------------- render ---
def geom(size):
    """Inset drawing box: (pad, eff) in device pixels."""
    return PAD_PX, size - 2 * PAD_PX


def render(fn, frame, size):
    """One surface, two ordered passes, one downsample. No bloom."""
    big = size * SS
    pad, eff = geom(size)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, big, big)
    ctx = cairo.Context(surf)
    ctx.scale(SS, SS)                  # 1 user unit == 1 device px
    ctx.translate(pad, pad)
    ctx.scale(eff, eff)                # 1 user unit == the inset box
    ctx.set_antialias(cairo.ANTIALIAS_BEST)

    p = P(ctx, size, eff, pad)
    for mode in ("under", "neon"):
        p.mode, p.sc, p.bold = mode, 1.0, True
        fn(p, frame)

    surf.flush()
    im = Image.frombuffer("RGBA", (big, big), bytes(surf.get_data()),
                          "raw", "BGRA", 0, 1)
    # downsample while still premultiplied (correct), then unpremultiply once
    im = im.resize((size, size), Image.LANCZOS)
    px = im.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = px[x, y]
            if a and a < 255:
                px[x, y] = (min(255, (r * 255 + a // 2) // a),
                            min(255, (g * 255 + a // 2) // a),
                            min(255, (b * 255 + a // 2) // a), a)
    if RIM <= 0 or RIM_A <= 0:
        return im
    # Rim derived ONCE from the finished glyph, by spreading a darkened copy of
    # it outward one pixel at a time. Because it comes from the union of
    # everything drawn, it hugs the outer silhouette only and can never appear
    # between two overlapping strokes the way a per-primitive rim did. Spreading
    # the colour (not just the alpha) is what lets each region keep its own hue.
    r, g, b, al = im.split()
    f = lambda v: int(v * DARKEN)
    src = Image.merge("RGBA", (r.point(f), g.point(f), b.point(f), al))
    for _ in range(int(RIM)):
        acc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                       (1, 0), (-1, 1), (0, 1), (1, 1)):
            sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            sh.paste(src, (dx, dy))
            acc.alpha_composite(sh)
        acc.alpha_composite(src)
        src = acc
    # The rim is kept on every face of the stroke, enclosed holes included, so
    # the hollow middle of the dart and the inside of the boxy resize arrows
    # each carry their own edge.
    src.putalpha(src.split()[3].point(lambda v: int(v * RIM_A)))
    src.alpha_composite(im)
    return src


def edge_ink(img):
    """Max alpha along the canvas border; non-zero means the glyph is cut off."""
    w, h = img.size
    px = img.load()
    m = 0
    for x in range(w):
        m = max(m, px[x, 0][3], px[x, h - 1][3])
    for y in range(h):
        m = max(m, px[0, y][3], px[w - 1, y][3])
    return m


def build(out_dir, work_dir, keep_frames=False):
    global OUT, WORK
    OUT, WORK = out_dir, work_dir
    os.makedirs(WORK, exist_ok=True)
    # Only the cursors/ tree is rebuilt. Wiping all of OUT also deleted
    # README.md and the reference screenshots kept alongside the theme.
    cdir = os.path.join(OUT, "cursors")
    shutil.rmtree(cdir, ignore_errors=True)
    os.makedirs(cdir, exist_ok=True)

    clipped = {}
    for name, (fn, (hx, hy), frames) in CURSORS.items():
        cfg = []
        for size in SIZES:
            pad, eff = geom(size)
            for fr in range(frames):
                png = os.path.join(WORK, f"{name}_{size}_{fr}.png")
                img = render(fn, fr, size)
                if edge_ink(img) > 20:          # ink running off the canvas
                    clipped.setdefault(name, set()).add(size)
                img.save(png)
                xh = max(0, min(size - 1, round(pad + hx * eff)))
                yh = max(0, min(size - 1, round(pad + hy * eff)))
                row = f"{size} {xh} {yh} {png}"
                if frames > 1:
                    row += " 60"
                cfg.append(row)
        cfgp = os.path.join(WORK, f"{name}.cursor")
        open(cfgp, "w").write("\n".join(cfg) + "\n")
        subprocess.run(["xcursorgen", cfgp, os.path.join(cdir, name)], check=True)
        print(f"  {name:16s} {frames:2d}fr")

    seen = set(CURSORS)
    for target, names in ALIASES.items():
        for a in names:
            if a in seen:
                print(f"  !! duplicate alias {a}", file=sys.stderr); continue
            seen.add(a)
            os.symlink(target, os.path.join(cdir, a))

    meta = ("[Icon Theme]\n"
            "Name=Cyberpunk-Neon\n"
            "Comment=Hard-edged neon outline cursors - cyan & yellow cyberpunk\n"
            "Inherits=Adwaita\n")
    open(os.path.join(OUT, "index.theme"), "w").write(meta)
    open(os.path.join(OUT, "cursor.theme"), "w").write(meta)
    print(f"\n{len(CURSORS)} cursors + {len(seen) - len(CURSORS)} aliases -> {OUT}")
    if clipped:
        print(f"\n!! CLIPPED -- ink runs off the canvas on {len(clipped)} cursor(s);"
              f" raise PAD_PX or pull the geometry in:", file=sys.stderr)
        for n, s in sorted(clipped.items()):
            print(f"     {n:15s} at {sorted(s)}", file=sys.stderr)
        return False
    print("edge check: clean, no glyph touches the canvas border")
    return True


def main():
    ap = argparse.ArgumentParser(
        description="Build the Cyberpunk-Neon Xcursor theme.")
    ap.add_argument("-o", "--out", metavar="DIR",
                    help=f"where to write the {THEME} theme directory "
                         f"(default: {OUT})")
    ap.add_argument("-i", "--install", action="store_true",
                    help="build straight into ~/.icons/" + THEME)
    ap.add_argument("--keep-frames", metavar="DIR",
                    help="also keep the rendered PNG frames in DIR")
    a = ap.parse_args()

    if a.install and a.out:
        ap.error("--install and --out are mutually exclusive")
    if a.install:
        out = os.path.expanduser(f"~/.icons/{THEME}")
    else:
        out = os.path.abspath(a.out) if a.out else OUT

    work = a.keep_frames and os.path.abspath(a.keep_frames)
    tmp = None if work else tempfile.mkdtemp(prefix="cyberpunk-neon-")
    try:
        ok = build(out, work or tmp)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\ntheme written to {out}")
    if a.install:
        print(f"  gsettings set org.gnome.desktop.interface cursor-theme {THEME}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
