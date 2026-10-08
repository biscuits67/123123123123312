"""Builds the animated Emerald custom emoji (Telegram .tgs = gzipped Lottie).

    python3 tools/emoji_build.py            -> bot/emerald_emoji/tgs/*.tgs + manifest.json
    python3 tools/emoji_build.py check star -> only the listed emoji

Telegram rules for animated custom emoji: 100x100 canvas, 60 fps, <= 3 s, <= 64 KB.
Everything is plain vector shapes (no masks, mattes, effects, images or text),
so it renders the same in rlottie (Telegram apps) and lottie-web.
"""
import gzip
import json
import math
import os
import re
import sys

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DIR, "bot", "emerald_emoji", "tgs")
FR, OP = 60, 180          # 60 fps, 3 s loop
WHITE = "#f2fff9"

THEMES = {  # c1 (light) .. c5 (deep) — same palette as card.html
    "emerald": ["#6ff2bd", "#19c48a", "#0b8a5e", "#05523a", "#032c20"],
    "ruby":    ["#ff9aa6", "#f0475d", "#b3203a", "#6e0f22", "#3a0712"],
    "gold":    ["#fff1b8", "#e8c66a", "#b8913a", "#6e5420", "#3a2c10"],
}


# ---------------------------------------------------------------- lottie bits
def rgb(h, a=1):
    h = h.lstrip("#")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [a]


def val(v):
    return {"a": 0, "k": v}


def anim(keys, hold=False):
    """keys: [(frame, value), ...] or [(frame, value, ease)]; ease = (ox, oy, ix, iy) or HOLD."""
    out = []
    for n, key in enumerate(keys):
        t, v = key[0], key[1]
        v = v if isinstance(v, list) else [v]
        k = {"t": t, "s": v}
        if n < len(keys) - 1:
            ease = key[2] if len(key) > 2 else (0.4, 0, 0.2, 1)
            if hold or ease == HOLD:
                k["h"] = 1
                ease = LINEAR
            ox, oy, ix, iy = ease
            d = len(v)
            k["o"] = {"x": [ox] * d, "y": [oy] * d}
            k["i"] = {"x": [ix] * d, "y": [iy] * d}
        out.append(k)
    return {"a": 1, "k": out}


def prop(v):
    return v if isinstance(v, dict) else val(v)


EASE_OUT_BACK = (0.3, 0, 0.2, 1.45)
LINEAR = (0, 0, 1, 1)
HOLD = "hold"


def tr(p=(0, 0), a=(0, 0), s=(100, 100), r=0, o=100):
    return {"ty": "tr", "p": prop(list(p) if not isinstance(p, dict) else p),
            "a": prop(list(a)), "s": prop(list(s) if not isinstance(s, dict) else s),
            "r": prop(r), "o": prop(o), "sk": val(0), "sa": val(0)}


def group(items, name="g", **t):
    return {"ty": "gr", "nm": name, "it": items + [tr(**t)]}


def fill(color, o=100):
    return {"ty": "fl", "c": val(rgb(color)), "o": prop(o), "r": 1}


def stroke(color, w, o=100):
    return {"ty": "st", "c": val(rgb(color)), "o": prop(o), "w": prop(w), "lc": 2, "lj": 2, "ml": 4}


def gfill(stops, s, e, o=100, alpha=None, radial=False):
    """stops: [(offset, color), ...]; alpha: optional [(offset, opacity 0..1)];
    s/e: start/end points (static or anim) — for a radial gradient: centre and a point on the edge."""
    k = []
    for off, c in stops:
        k += [off] + rgb(c)[:3]
    for off, a in alpha or []:
        k += [off, a]
    g = {"ty": "gf", "o": prop(o), "r": 1, "t": 2 if radial else 1,
         "s": prop(s if isinstance(s, dict) else list(s)),
         "e": prop(e if isinstance(e, dict) else list(e)),
         "g": {"p": len(stops), "k": val(k)}}
    if radial:
        g.update(h=val(0), a=val(0))
    return g


def trim(start=0, end=100, offset=0):
    return {"ty": "tm", "s": prop(start), "e": prop(end), "o": prop(offset), "m": 1}


def ellipse(cx, cy, w, h=None):
    return {"ty": "el", "p": prop([cx, cy]), "s": prop([w, w if h is None else h]), "d": 1}


def rect(cx, cy, w, h, r=0):
    return {"ty": "rc", "p": prop([cx, cy]), "s": prop([w, h]), "r": prop(r), "d": 1}


def shape(verts, closed=True, ins=None, outs=None):
    n = len(verts)
    return {"ty": "sh", "ks": val({"v": [list(v) for v in verts], "c": closed,
                                   "i": ins or [[0, 0]] * n, "o": outs or [[0, 0]] * n})}


def poly(points, closed=True):
    return shape(points, closed)


def path(d):
    """Absolute SVG path subset (M L H V Q C Z) -> list of Lottie 'sh' items."""
    toks = re.findall(r"[MLHVQCZ]|-?\d*\.?\d+", d.replace(",", " "))
    subs, cur, i, cmd = [], None, 0, None
    x = y = 0

    def num():
        nonlocal i
        i += 1
        return float(toks[i - 1])

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
        if cmd == "M":
            x, y = num(), num()
            cur = {"v": [[x, y]], "i": [[0, 0]], "o": [[0, 0]], "c": False}
            subs.append(cur)
            cmd = "L"
        elif cmd in "LHV":
            if cmd == "L":
                x, y = num(), num()
            elif cmd == "H":
                x = num()
            else:
                y = num()
            cur["v"].append([x, y]); cur["i"].append([0, 0]); cur["o"].append([0, 0])
        elif cmd in "QC":
            if cmd == "Q":
                qx, qy, ex, ey = num(), num(), num(), num()
                c1 = (x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y))
                c2 = (ex + 2 / 3 * (qx - ex), ey + 2 / 3 * (qy - ey))
            else:
                c1, c2, (ex, ey) = (num(), num()), (num(), num()), (num(), num())
            cur["o"][-1] = [c1[0] - x, c1[1] - y]
            cur["v"].append([ex, ey]); cur["i"].append([c2[0] - ex, c2[1] - ey]); cur["o"].append([0, 0])
            x, y = ex, ey
        elif cmd == "Z":
            if len(cur["v"]) > 1 and cur["v"][-1] == cur["v"][0]:   # closing point duplicates the start
                cur["i"][0] = cur["i"].pop(); cur["v"].pop(); cur["o"].pop()
            cur["c"] = True
            cmd = None
    return [shape(s["v"], s["c"], s["i"], s["o"]) for s in subs]


def star_pts(cx, cy, ro, ri, n=5, rot=-90):
    pts = []
    for k in range(n * 2):
        r = ro if k % 2 == 0 else ri
        a = math.radians(rot + k * 180 / n)
        pts.append((round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)))
    return pts


def layer(name, shapes, ind, p=(50, 50), a=(50, 50), s=(100, 100), r=0, o=100, parent=None):
    lay = {"ddd": 0, "ind": ind, "ty": 4, "nm": name, "sr": 1, "ao": 0, "bm": 0,
           "ks": {"o": prop(o), "r": prop(r),
                  "p": prop(p if isinstance(p, dict) else list(p)),
                  "a": prop(list(a)),
                  "s": prop(s if isinstance(s, dict) else list(s))},
           "shapes": shapes, "ip": 0, "op": OP, "st": 0}
    if parent:
        lay["parent"] = parent
    return lay


# ---------------------------------------------------------------- the gem
# emerald (step) cut, front view — the same stone as on the cards, simplified for 100x100
OUTER = [(28, 3), (72, 3), (92, 23), (92, 77), (72, 97), (28, 97), (8, 77), (8, 23)]
TABLE = [(34, 13.5), (66, 13.5), (82, 29.5), (82, 70.5), (66, 86.5), (34, 86.5), (18, 70.5), (18, 29.5)]


def gem_shapes(c, shine_at=110):
    c1, c2, c3, c4, c5 = c
    tones = [c1, c2, c3, c4, c5, c4, c3, c1]          # top, top-right, right, ... top-left (light from top-left)
    out = []
    # edges on top
    edges = [poly(OUTER), poly(TABLE)] + [poly([OUTER[k], TABLE[k]], False) for k in range(8)]
    out.append(group(edges + [stroke("#ffffff", 0.9, 26)], "edges"))
    # static gloss on the table + top facets
    out.append(group([poly([(34, 13.5), (58, 13.5), (18, 54), (18, 29.5)])] + [fill("#ffffff", 12)], "gloss"))
    out.append(group([poly([(28, 3), (72, 3), (66, 13.5), (34, 13.5), (18, 29.5), (8, 23)])] +
                     [gfill([(0, "#ffffff"), (1, c1)], (30, 0), (50, 20), 45)], "top-gloss"))
    # moving shine band across the table: a white gradient that is transparent except
    # for a narrow stripe, slid diagonally by animating its start/end points (no masks)
    t0 = shine_at
    band = [(0, "#ffffff"), (1, "#ffffff")]
    alpha = [(0, 0), (0.34, 0), (0.5, 0.75), (0.66, 0), (1, 0)]
    s_anim = anim([(0, [-60, -60]), (t0, [-60, -60], (0.5, 0, 0.5, 1)), (t0 + 40, [60, 60])], hold=False)
    e_anim = anim([(0, [-10, -10]), (t0, [-10, -10], (0.5, 0, 0.5, 1)), (t0 + 40, [110, 110])], hold=False)
    out.append(group([poly(TABLE), gfill(band, s_anim, e_anim, alpha=alpha)], "shine"))
    # base table gradient (shows when the band is away)
    out.append(group([poly(TABLE), gfill([(0, c2), (0.55, c3), (1, c4)], (20, 14), (82, 86))], "table"))
    # ring facets
    for k in range(8):
        a, b = OUTER[k], OUTER[(k + 1) % 8]
        ta, tb = TABLE[k], TABLE[(k + 1) % 8]
        out.append(group([poly([a, b, tb, ta]), fill(tones[k])], f"facet{k}"))
    return out


def sparkle(ind, x, y, size, t0, dur=40):
    """4-point twinkle that pops in and out at frame t0."""
    pts = star_pts(0, 0, size, size * 0.22, n=4, rot=-90)
    sc = anim([(0, [0, 0]), (t0, [0, 0]), (t0 + dur * 0.45, [100, 100]), (t0 + dur, [0, 0]), (OP, [0, 0])])
    rot = anim([(0, 0), (t0, 0, LINEAR), (t0 + dur, 90), (OP, 90)])
    return layer(f"sparkle{ind}", [group([poly(pts), fill("#ffffff")], "s")], ind,
                 p=(x, y), a=(0, 0), s=sc, r=rot)


# ---------------------------------------------------------------- icons
# Each icon is a function returning (shapes, layer_kwargs); shapes are drawn twice —
# once as a dark drop shadow and once in white. Icon area ~ 30..70 around the centre.
SW = 6.5   # icon stroke width


def ln(d, w=SW, extra=()):
    """stroke-only group from an SVG path (colour filled in later)."""
    return {"paths": path(d), "w": w, "mods": list(extra), "kind": "stroke"}


def outline(items, w=SW, extra=()):
    """stroke-only group from ready shape items (ellipses, rects...)."""
    return {"paths": items, "w": w, "mods": list(extra), "kind": "stroke"}


def solid(items, extra=()):
    return {"paths": items, "mods": list(extra), "kind": "fill"}


def paint(parts, style):
    """style(part) -> fill/stroke item; a plain colour string means a flat colour."""
    if isinstance(style, str):
        color = style
        style = lambda part: stroke(color, part["w"]) if part["kind"] == "stroke" else fill(color)
    out = []
    for n, part in enumerate(parts):
        sub = part.get("t")                      # optional per-part transform
        items = part["paths"] + part["mods"] + [style(part)]
        out.append(group(items, f"p{n}", **(sub or {})))
    return out


def gstroke(stops, s, e, w, alpha=None):
    g = gfill(stops, s, e, alpha=alpha)
    g.update(ty="gs", w=prop(w), lc=2, lj=2, ml=4)
    del g["r"]
    return g


def with_t(part, **t):
    part["t"] = t
    return part


def draw_on(start, end, wipe=(96, 116)):
    """trim: the line is fully drawn on frame 0 (that frame is the still image when animations
    are off), gets wiped away and is drawn in again between `start` and `end`."""
    w0, w1 = wipe
    return trim(start=anim([(0, 0), (w0, 0, (0.5, 0, 0.6, 1)), (w1, 100, HOLD), (start - 1, 0), (OP, 0)]),
                end=anim([(0, 100), (start - 1, 100, HOLD), (start, 0, (0.3, 0, 0.1, 1)), (end, 100), (OP, 100)]))


def icon_check():
    return [ln("M36,51 L46,61 L65,40", 8, [draw_on(124, 152)])], {}


def icon_cross():
    return [ln("M39,39 L61,61", 8, [draw_on(124, 142)]), ln("M61,39 L39,61", 8, [draw_on(136, 154)])], \
        {"r": anim([(0, 0), (20, 0), (26, -8), (32, 7), (38, -4), (44, 0), (OP, 0)])}


def icon_stop():
    return [solid([rect(50, 50, 32, 9, 4.5)])], \
        {"r": anim([(0, 0), (20, 0), (26, -10), (32, 9), (38, -6), (44, 4), (50, 0), (OP, 0)]),
         "s": anim([(0, [100, 100]), (16, [100, 100]), (22, [112, 112]), (52, [100, 100]), (OP, [100, 100])])}


def icon_gem():
    # brand emoji: a small table glint instead of a pictogram
    pts = star_pts(50, 50, 13, 3.2, n=4)
    sc = anim([(0, [100, 100]), (40, [100, 100]), (60, [130, 130]), (90, [100, 100]), (OP, [100, 100])])
    return [with_t(solid([poly(pts)]), p=(50, 50), a=(50, 50), s=sc,
                   r=anim([(0, 0), (40, 0), (90, 90), (OP, 90)]))], {}


def icon_wallet():
    body = ln("M37,40 H63 Q67,40 67,44 V61 Q67,65 63,65 H37 Q33,65 33,61 V44 Q33,40 37,40 Z", 5.5)
    flap = ln("M36,40 L58,33 Q61,32 62,35 L63,40", 5)
    tab = with_t(solid([rect(64, 52.5, 14, 9, 3)]),
                 p=anim([(0, [0, 0]), (24, [0, 0], (0.4, 0, 0.2, 1.4)), (44, [6, 0]), (110, [6, 0]), (135, [0, 0]), (OP, [0, 0])]))
    return [body, flap, tab], {}


def icon_star():
    pts = star_pts(50, 51, 18, 8, 5)
    return [solid([poly(pts)], [])], {
        "r": anim([(0, 0), (10, 0, (0.5, 0, 0.2, 1)), (70, 144), (OP, 144)]),
        "s": anim([(0, [100, 100]), (10, [100, 100]), (40, [118, 118]), (70, [100, 100]), (OP, [100, 100])])}


def icon_payout():
    tray = ln("M35,55 V61 Q35,66 40,66 H60 Q65,66 65,61 V55", 6)
    arrow = with_t(ln("M50,55 V33 M41,42 L50,33 L59,42", 6),
                   p=anim([(0, [0, 0]), (10, [0, 0], (0.5, 0, 0.3, 1)), (40, [0, -5]), (70, [0, 0]),
                           (100, [0, -5]), (130, [0, 0]), (OP, [0, 0])]))
    return [tray, arrow], {}


def icon_bolt():
    return [solid(path("M54,31 L36,54 H49 L45,70 L64,45 H51 Z"))], {
        "o": anim([(0, 100), (30, 100, LINEAR), (34, 35, LINEAR), (38, 100, LINEAR), (42, 45, LINEAR), (46, 100), (OP, 100)]),
        "s": anim([(0, [100, 100]), (30, [100, 100]), (36, [114, 114]), (60, [100, 100]), (OP, [100, 100])])}


def icon_users():
    back = with_t(outline([ellipse(60, 41, 10)] + path("M52,62 Q52,52 60,52 Q68,52 68,62"), 5),
                  p=anim([(0, [0, 0]), (20, [0, 0], (0.4, 0, 0.2, 1.4)), (40, [4, 0]), (120, [4, 0]), (145, [0, 0]), (OP, [0, 0])]))
    back["dim"] = True
    front = outline([ellipse(44, 42, 13)] + path("M31,66 Q31,53 44,53 Q57,53 57,66"), 6)
    return [front, back], {}          # first part is drawn on top


def icon_coin():
    ring = outline([ellipse(50, 50, 34)], 5.5)
    dollar = ln("M56,42 Q54,38 50,38 Q44,38 44,43.5 Q44,48 50,49.5 Q56,51 56,56.5 Q56,62 50,62 Q45,62 43.5,58 M50,33 V67", 4.5)
    flip = anim([(0, [100, 100]), (20, [100, 100], (0.5, 0, 0.5, 1)), (38, [8, 100], (0.5, 0, 0.5, 1)), (56, [100, 100]),
                 (OP, [100, 100])])
    return [ring, dollar], {"s": flip}


def icon_chart():
    parts = []
    for n, (x, h) in enumerate([(37, 16), (50, 28), (63, 21)]):
        grow = anim([(0, [100, 100]), (96, [100, 100], (0.5, 0, 0.8, 0)), (112, [100, 0]),
                     (122 + n * 8, [100, 0], EASE_OUT_BACK), (146 + n * 8, [100, 100]), (OP, [100, 100])])
        parts.append(with_t(solid([rect(x, 66 - h / 2, 8, h, 3)]), p=(x, 66), a=(x, 66), s=grow))
    parts.append(ln("M31,70 H69", 3.5))
    return parts, {}


def icon_like():
    hand = ln("M42,51 L49,35 Q51,31 54.5,32.5 Q57.5,34 56.5,39 L55,46 H64 Q69,46 68,51.5 L66,62 Q65,66 61,66 H42 Z", 5.5)
    cuff = solid([rect(35, 57.5, 7, 19, 2.5)])
    return [hand, cuff], {
        "r": anim([(0, 0), (14, 0, (0.4, 0, 0.3, 1.6)), (30, -14), (50, 0), (OP, 0)]),
        "p": anim([(0, [50, 50]), (14, [50, 50]), (30, [50, 47]), (50, [50, 50]), (OP, [50, 50])])}


def icon_plane():
    plane = solid(path("M31,49 L68,33 L60,67 L50,57 Z"))
    fold = ln("M68,33 L50,57 L49,66", 3.5)
    fly = anim([(0, [50, 50], (0.45, 0, 0.55, 1)), (45, [53, 47], (0.45, 0, 0.55, 1)), (90, [50, 50], (0.45, 0, 0.55, 1)),
                (135, [53, 47], (0.45, 0, 0.55, 1)), (OP, [50, 50])])
    return [plane, fold], {"p": fly, "r": anim([(0, 0, (0.45, 0, 0.55, 1)), (45, -5, (0.45, 0, 0.55, 1)), (90, 0, (0.45, 0, 0.55, 1)),
                                                 (135, -5, (0.45, 0, 0.55, 1)), (OP, 0)])}


def icon_chat():
    bubble = ln("M38,36 H62 Q68,36 68,42 V55 Q68,61 62,61 H47 L38,68 V61 Q32,61 32,55 V42 Q32,36 38,36 Z", 5)
    dots = []
    for n, x in enumerate((42, 50, 58)):
        t = 10 + n * 10
        hop = anim([(0, [0, 0]), (t, [0, 0], (0.4, 0, 0.6, 1)), (t + 12, [0, -4], (0.4, 0, 0.6, 1)), (t + 24, [0, 0]),
                    (t + 70, [0, 0], (0.4, 0, 0.6, 1)), (t + 82, [0, -4], (0.4, 0, 0.6, 1)), (t + 94, [0, 0]), (OP, [0, 0])])
        dots.append(with_t(solid([ellipse(x, 48.5, 5.5)]), p=hop))
    return [bubble] + dots, {}


def icon_link():
    move = lambda d: anim([(0, [0, 0]), (20, [0, 0], (0.5, 0, 0.5, 1)), (40, [d, -d]), (60, [0, 0]), (OP, [0, 0])])
    a = with_t(ln("M47,44 L41,50 Q35,56 41,62 Q47,68 53,62 L56,59", 5.5), p=move(-2.5))
    b = with_t(ln("M53,56 L59,50 Q65,44 59,38 Q53,32 47,38 L44,41", 5.5), p=move(2.5))
    mid = ln("M45,55 L55,45", 5.5)
    return [a, b, mid], {}


def icon_book():
    cover = ln("M50,40 Q42,34 32,35 V63 Q42,62 50,68 Q58,62 68,63 V35 Q58,34 50,40 Z", 5)
    spine = ln("M50,40 V66", 4)
    page = with_t(ln("M50,40 Q57,35 64,36", 3.5), p=(50, 40), a=(50, 40),
                  s=anim([(0, [100, 100]), (30, [100, 100], (0.5, 0, 0.5, 1)), (55, [-100, 100]), (110, [-100, 100], (0.5, 0, 0.5, 1)),
                          (135, [100, 100]), (OP, [100, 100])]))
    return [cover, spine, page], {}


def icon_info():
    dot = with_t(solid([ellipse(50, 35, 9)]),
                 p=anim([(0, [0, 0]), (14, [0, 0], (0.3, 0, 0.7, 1)), (26, [0, -6], (0.3, 0, 0.7, 1)), (38, [0, 0]),
                         (46, [0, -2], (0.3, 0, 0.7, 1)), (54, [0, 0]), (OP, [0, 0])]))
    stem = ln("M50,46 V65", 8.5)
    return [dot, stem], {}


def icon_medal():
    ribbon = ln("M39,30 L46,45 M61,30 L54,45", 5)
    disk = outline([ellipse(50, 56, 25)], 5)
    num = ln("M47,53 L51,50 V62", 4)
    return [ribbon, disk, num], {"r": anim([(0, 0, (0.45, 0, 0.55, 1)), (30, 10, (0.45, 0, 0.55, 1)), (60, -7, (0.45, 0, 0.55, 1)),
                                             (90, 4, (0.45, 0, 0.55, 1)), (115, 0), (OP, 0)]),
                                 "a": (50, 30), "p": (50, 30)}


def icon_crown():
    crown = solid(path("M33,64 L30,39 L42,49 L50,34 L58,49 L70,39 L67,64 Z"))
    base = solid([rect(50, 69, 34, 4.5, 2.2)])
    return [crown, base], {"s": anim([(0, [100, 100]), (20, [100, 100], (0.4, 0, 0.3, 1.6)), (34, [112, 92]), (50, [96, 106]),
                                     (66, [100, 100]), (OP, [100, 100])]), "a": (50, 70), "p": (50, 70)}


def icon_calendar():
    body = ln("M36,37 H64 Q68,37 68,41 V63 Q68,67 64,67 H36 Q32,67 32,63 V41 Q32,37 36,37 Z", 5)
    rings = ln("M41,32 V40 M59,32 V40", 5)
    bar = ln("M33,46 H67", 4)
    pos = [(41, 54), (50, 54), (59, 54), (41, 61), (50, 61), (59, 61)]
    ks = []
    for n, (x, y) in enumerate(pos):
        ks.append((n * 30, [x - 50, y - 57.5], (0.4, 0, 0.2, 1)))
    ks.append((OP, [pos[0][0] - 50, pos[0][1] - 57.5]))
    day = with_t(solid([rect(50, 57.5, 6, 5, 1.5)]), p=anim(ks))
    return [body, rings, bar, day], {}


def icon_globe():
    ring = outline([ellipse(50, 50, 38)], 5)
    lat = ln("M32,50 H68 M35,40 H65 M35,60 H65", 3.5)
    spin = anim([(0, [16, 38], LINEAR), (90, [-16, 38], LINEAR), (OP, [16, 38])])
    mer = outline([{"ty": "el", "p": val([50, 50]), "s": spin, "d": 1}], 4)
    return [ring, lat, mer], {}


def icon_hourglass():
    glass = ln("M37,33 H63 M37,67 H63 M40,33 Q40,46 50,50 Q60,54 60,67 M60,33 Q60,46 50,50 Q40,54 40,67", 4.5)
    top = with_t(solid(path("M43,38 H57 Q56,45 50,47 Q44,45 43,38 Z")), p=(50, 38), a=(50, 38),
                 s=anim([(0, [100, 100], LINEAR), (90, [100, 0]), (OP, [100, 0])]))
    bot = with_t(solid(path("M43,63 H57 Q56,58 50,56 Q44,58 43,63 Z")), p=(50, 63), a=(50, 63),
                 s=anim([(0, [100, 0], LINEAR), (90, [100, 100]), (OP, [100, 100])]))
    return [glass, top, bot], {"r": anim([(0, 0), (110, 0, (0.5, 0, 0.3, 1.2)), (150, 180), (OP, 180)])}


def icon_bell():
    bell = ln("M36,61 Q39,57 39,49 Q39,37 50,36 Q61,37 61,49 Q61,57 64,61 Z", 5)
    clapper = with_t(solid([ellipse(50, 66, 7)]),
                     p=anim([(0, [0, 0]), (10, [0, 0], (0.45, 0, 0.55, 1)), (22, [3, 0], (0.45, 0, 0.55, 1)),
                             (34, [-3, 0], (0.45, 0, 0.55, 1)), (46, [2, 0], (0.45, 0, 0.55, 1)), (58, [0, 0]), (OP, [0, 0])]))
    knob = ln("M50,31 V35", 4.5)
    return [bell, clapper, knob], {"r": anim([(0, 0), (10, 0, (0.45, 0, 0.55, 1)), (22, -14, (0.45, 0, 0.55, 1)),
                                               (34, 12, (0.45, 0, 0.55, 1)), (46, -7, (0.45, 0, 0.55, 1)), (58, 3, (0.45, 0, 0.55, 1)),
                                               (68, 0), (OP, 0)]), "a": (50, 31), "p": (50, 31)}


# ---------------------------------------------------------------- owner: crown cut from emerald
def owner_layers():
    """Unique emoji for the project owners: an emerald-cut crown on a gold band, turning
    a soft halo behind it, a glint across the stone and twinkling gold tips."""
    c1, c2, c3, c4, c5 = THEMES["emerald"]
    g1, g2, g3, g4, _ = THEMES["gold"]
    A, B, C, D, E = (11, 37), (31, 54), (50, 14), (69, 54), (89, 37)
    G, H, Mb = (19, 75), (81, 75), (50, 75)
    L, Q, R, S = (29, 65), (42, 59), (58, 59), (71, 65)
    outline = [A, B, C, D, E, H, G]
    facets = [([A, B, L, G], c2), ([B, Q, L], c3), ([B, C, Q], c1), ([C, Mb, Q], c2), ([C, R, Mb], c3),
              ([C, D, R], c2), ([D, S, R], c4), ([D, E, H, S], c3), ([G, L, Q, Mb], c4), ([Mb, R, S, H], c5)]
    float_p = anim([(0, [50, 52], (0.45, 0, 0.55, 1)), (OP / 2, [50, 49.5], (0.45, 0, 0.55, 1)), (OP, [50, 52])])
    big = (112, 112)
    tilt = anim([(0, 0, (0.45, 0, 0.55, 1)), (OP / 4, -3, (0.45, 0, 0.55, 1)), (OP * 3 / 4, 3, (0.45, 0, 0.55, 1)), (OP, 0)])

    crown = []
    # edges
    lines = [poly(outline)] + [poly([a, b], False) for a, b in
                               [(B, L), (B, Q), (Q, L), (C, Q), (C, Mb), (C, R), (R, D), (R, S), (S, D), (Q, Mb), (R, Mb), (L, G), (S, H)]]
    crown.append(group(lines + [stroke("#ffffff", 0.9, 30)], "edges"))
    # glint sweeping across the stone (frames 40-85 and a softer one at 120-160)
    sweep = lambda a0, a1: anim([(0, a0), (40, a0, (0.5, 0, 0.5, 1)), (85, a1, HOLD), (86, a0), (120, a0, (0.5, 0, 0.5, 1)),
                                 (160, a1), (OP, a1)])
    crown.append(group([poly(outline), gfill([(0, "#ffffff"), (1, "#ffffff")], sweep([-50, -10], [80, 40]),
                                             sweep([0, 30], [130, 80]),
                                             alpha=[(0, 0), (0.36, 0), (0.5, 0.7), (0.64, 0), (1, 0)])], "shine"))
    crown.append(group([poly([A, B, L, G])] + [fill("#ffffff", 10)], "gloss"))
    for n, (pts, col) in enumerate(facets):
        crown.append(group([poly(pts), fill(col)], f"facet{n}"))

    # gold band with three small emeralds
    band = []
    for n, x in enumerate((30, 50, 70)):
        tw = anim([(0, [100, 100]), (30 + n * 14, [100, 100], (0.4, 0, 0.3, 1.6)), (40 + n * 14, [135, 135]),
                   (56 + n * 14, [100, 100]), (OP, [100, 100])])
        k = 1.45 if n == 1 else 0.9                                     # big centre stone, two small ones
        gem = star_pts(0, 0, 5.2 * k, 5.2 * k * 0.92, n=4, rot=-90)  # octagon-ish stone
        band.append(group([poly(star_pts(0, 0, 2 * k, 2 * k * 0.92, n=4, rot=-90)), fill("#ffffff", 75)], f"glint{n}",
                          p=(x - 1.5 * k, 79.6 - 0.4 * k), s=tw))
        band.append(group([poly(gem), gfill([(0, c1), (0.5, c2), (1, c4)], (-4 * k, -4 * k), (4 * k, 4 * k))], f"stone{n}",
                          p=(x, 81), s=tw))
        band.append(group([ellipse(x, 81, 12 * k)] + [gfill([(0, g1), (1, g4)], (x - 5 * k, 76), (x + 5 * k, 86))], f"set{n}"))
    band.append(group([poly([(19, 76.5), (81, 76.5)], False)] + [stroke("#ffffff", 1.2, 70)], "band-light"))
    band.append(group([rect(50, 81, 66, 12, 4)] + [stroke(g4, 1, 60)], "band-edge"))
    band.append(group([rect(50, 81, 66, 12, 4), gfill([(0, g1), (0.4, g2), (0.75, g3), (1, g4)], (50, 75), (50, 87))], "band"))
    band.append(group([rect(50, 83.5, 66, 12, 4), fill(g4)], "band-depth"))

    # gold balls on the tips
    tips = []
    for n, (x, y) in enumerate((A, C, E)):
        r = 8.5 if n == 1 else 6.5
        glow = anim([(0, [100, 100]), (60 + n * 10, [100, 100], (0.4, 0, 0.3, 1.6)), (70 + n * 10, [125, 125]),
                     (90 + n * 10, [100, 100]), (OP, [100, 100])])
        tips.append(group([ellipse(0, 0, r * 0.38), fill("#ffffff", 85)], f"hl{n}", p=(x - r * 0.18, y - r * 0.2 - 1)))
        tips.append(group([ellipse(0, 0, r), gfill([(0, g1), (1, g3)], (-r / 2, -r / 2), (r / 2, r / 2))],
                          f"tip{n}", p=(x, y - 1), s=glow))

    halo = group([ellipse(0, 0, 92), gfill([(0, c2), (1, c3)], (0, 0), (46, 0), alpha=[(0, 0.45), (1, 0)], radial=True)], "halo")
    shadow = group([ellipse(50, 92, 60, 8), gfill([(0, c2), (1, c4)], (50, 92), (80, 92), alpha=[(0, 0.5), (1, 0)], radial=True)],
                   "shadow")

    layers = []
    for n, (x, y, size, t0) in enumerate([(88, 12, 8, 10), (8, 20, 6, 60), (94, 62, 5, 110), (6, 64, 5, 135)]):
        layers.append(sparkle(10 + n, x, y, size, t0))
    layers.append(layer("tips", tips, 2, p=float_p, a=(50, 50), s=big, r=tilt))
    layers.append(layer("band", band, 3, p=float_p, a=(50, 50), s=big, r=tilt))
    layers.append(layer("crown", crown, 4, p=float_p, a=(50, 50), s=big, r=tilt))
    layers.append(layer("shadow", [shadow], 5,
                        s=anim([(0, [100, 100], (0.45, 0, 0.55, 1)), (OP / 2, [86, 86], (0.45, 0, 0.55, 1)), (OP, [100, 100])])))
    layers.append(layer("halo", [halo], 7, p=(50, 48), a=(0, 0),
                        s=anim([(0, [100, 100], (0.45, 0, 0.55, 1)), (OP / 2, [112, 112], (0.45, 0, 0.55, 1)), (OP, [100, 100])])))
    return layers


# name: (fallback emoji, theme, icon, shine frame)
EMOJI = {
    "gem":       ("💎", "emerald", icon_gem, 40),
    "check":     ("✅", "emerald", icon_check, 60),
    "cross":     ("❌", "ruby", icon_cross, 70),
    "stop":      ("⛔", "ruby", icon_stop, 80),
    "wallet":    ("💳", "emerald", icon_wallet, 70),
    "star":      ("⭐", "gold", icon_star, 90),
    "payout":    ("💸", "emerald", icon_payout, 120),
    "bolt":      ("⚡", "gold", icon_bolt, 60),
    "users":     ("👥", "emerald", icon_users, 70),
    "coin":      ("💰", "gold", icon_coin, 80),
    "chart":     ("📊", "emerald", icon_chart, 60),
    "like":      ("👍", "emerald", icon_like, 70),
    "plane":     ("✈️", "emerald", icon_plane, 100),
    "chat":      ("💬", "emerald", icon_chat, 120),
    "link":      ("🔗", "emerald", icon_link, 80),
    "book":      ("📕", "emerald", icon_book, 70),
    "info":      ("ℹ️", "emerald", icon_info, 80),
    "medal":     ("🥇", "gold", icon_medal, 80),
    "crown":     ("👑", "gold", icon_crown, 80),
    "calendar":  ("📅", "emerald", icon_calendar, 100),
    "globe":     ("🌐", "emerald", icon_globe, 100),
    "hourglass": ("⏳", "emerald", icon_hourglass, 60),
    "bell":      ("🔔", "emerald", icon_bell, 90),
    "owner":     ("👑", "emerald", None, 0),     # unique: crown cut from emerald, for the project owners
}

SPARKLES = [(84, 12, 7, 0), (12, 26, 5, 50), (90, 74, 4.5, 100), (14, 84, 4, 140)]


ICON_SCALE = 175   # icons are drawn in a 40x40 box around the centre; no badge, so they fill the emoji


def jewel_layers(parts, lk, c, shine):
    """The icon itself is cut from the stone: a deep extrusion underneath, a light-to-deep
    gradient body, a bevel highlight on the upper-left edges and a glint that runs across."""
    c1, c2, c3, c4, c5 = c
    lk = dict(lk)
    a = lk.pop("a", (50, 50))
    p = lk.pop("p", a)
    body_s, body_e = (32, 26), (66, 76)

    def body(part):
        stops = [(0, c2), (0.5, c3), (1, c4)] if part.get("dim") else [(0, c1), (0.5, c2), (1, c3)]
        if part["kind"] == "stroke":
            return gstroke(stops, body_s, body_e, part["w"])
        return gfill(stops, body_s, body_e)

    def bevel(part):
        stops, al = [(0, "#ffffff"), (1, "#ffffff")], [(0, 0.95), (0.45, 0.25), (0.7, 0)]
        if part["kind"] == "stroke":
            return gstroke(stops, (34, 30), (62, 70), part["w"] * 0.3, alpha=al)
        return gfill(stops, (34, 30), (58, 64), alpha=[(0, 0.6), (0.5, 0.12), (0.8, 0)])

    t0 = shine
    s_anim = anim([(0, [-40, -40]), (t0, [-40, -40], (0.5, 0, 0.5, 1)), (t0 + 42, [70, 70])])
    e_anim = anim([(0, [0, 0]), (t0, [0, 0], (0.5, 0, 0.5, 1)), (t0 + 42, [110, 110])])
    band = [(0, "#ffffff"), (1, "#ffffff")]
    band_a = [(0, 0), (0.38, 0), (0.5, 0.85), (0.62, 0), (1, 0)]

    def glint(part):
        if part["kind"] == "stroke":
            return gstroke(band, s_anim, e_anim, part["w"], alpha=band_a)
        return gfill(band, s_anim, e_anim, alpha=band_a)

    def depth(color):
        return lambda part: stroke(color, part["w"]) if part["kind"] == "stroke" else fill(color)

    root = {"ddd": 0, "ind": 30, "ty": 3, "nm": "scale", "sr": 1, "ao": 0,
            "ks": {"o": val(0), "r": val(0), "p": val([50, 51]), "a": val([50, 50]),
                   "s": anim([(0, [ICON_SCALE] * 2, (0.45, 0, 0.55, 1)), (OP / 2, [ICON_SCALE * 1.025] * 2, (0.45, 0, 0.55, 1)),
                              (OP, [ICON_SCALE] * 2)])},
            "ip": 0, "op": OP, "st": 0}
    icon = layer("body", paint(parts, body), 21, p=p, a=a, parent=30, **lk)
    sub = lambda name, ind, style, dx=0, dy=0, o=100: layer(name, paint(parts, style), ind, p=(a[0] + dx, a[1] + dy), a=a,
                                                             o=o, parent=21)
    glow = layer("glow", [group([ellipse(50, 52, 92), gfill([(0, c2), (1, c3)], (50, 52), (96, 52),
                                                               alpha=[(0, 0.32), (0.55, 0.1), (1, 0)], radial=True)], "glow")], 26,
                 s=anim([(0, [100, 100], (0.45, 0, 0.55, 1)), (OP / 2, [110, 110], (0.45, 0, 0.55, 1)), (OP, [100, 100])]))
    return [sub("glint", 20, glint), sub("bevel", 22, bevel, -0.35, -0.45),
            icon,
            sub("depth", 23, depth(c4), 0, 1.3), sub("depth2", 24, depth(c5), 0, 2.5),
            sub("shadow", 25, depth("#000000"), 0, 4, o=28),
            glow, root]


def build(name):
    _, theme, icon, shine = EMOJI[name]
    if icon is None:
        layers = owner_layers()
    else:
        c = THEMES[theme]
        layers = []
        for n, (x, y, size, t0) in enumerate(SPARKLES):
            layers.append(sparkle(10 + n, x, y, size, (t0 + shine) % (OP - 40)))
        if name == "gem":            # the brand emoji is the stone itself
            layers.append(layer("gem", gem_shapes(c, shine), 2,
                                s=anim([(0, [100, 100], (0.45, 0, 0.55, 1)), (OP / 2, [96, 96], (0.45, 0, 0.55, 1)),
                                        (OP, [100, 100])])))
        else:
            layers += jewel_layers(*icon(), c, shine)
    return {"tgs": 1, "v": "5.5.2", "fr": FR, "ip": 0, "op": OP, "w": 100, "h": 100,
            "nm": f"emerald_{name}", "ddd": 0, "assets": [], "layers": layers}


def main():
    names = sys.argv[1:] or list(EMOJI)
    os.makedirs(OUT, exist_ok=True)
    # pack order + fallback emoji, read by upload_pack.py and emoji.py
    with open(os.path.join(os.path.dirname(OUT), "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({n: v[0] for n, v in EMOJI.items()}, f, ensure_ascii=False, indent=1)
    for name in names:
        data = json.dumps(build(name), separators=(",", ":"), ensure_ascii=False).encode()
        blob = gzip.compress(data, 9, mtime=0)
        assert len(blob) <= 64 * 1024, f"{name}: {len(blob)} bytes > 64 KB"
        with open(os.path.join(OUT, f"{name}.tgs"), "wb") as f:
            f.write(blob)
        print(f"{name:10} {EMOJI[name][0]}  {len(blob) / 1024:5.1f} KB")


if __name__ == "__main__":
    main()
