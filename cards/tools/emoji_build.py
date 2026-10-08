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


def paint(parts, color):
    out = []
    for n, part in enumerate(parts):
        sub = part.get("t")                      # optional per-part transform
        style = stroke(color, part["w"]) if part["kind"] == "stroke" else fill(color)
        items = part["paths"] + part["mods"] + [style]
        out.append(group(items, f"p{n}", **(sub or {})))
    return out


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
    front = outline([ellipse(44, 42, 13)] + path("M31,66 Q31,53 44,53 Q57,53 57,66"), 6)
    return [back, front], {}


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


# ---------------------------------------------------------------- owner: royal crown
def owner_layers():
    """Unique emoji for the project owners: a gold royal crown with pearl tips, an emerald on the
    centre point and a large emerald-cut stone (the brand gem from the cards) set in the front."""
    c = THEMES["emerald"]
    c1, c2, c3, c4, c5 = c
    g1, g2, g3, g4, g5 = THEMES["gold"]
    ease = (0.45, 0, 0.55, 1)

    body = ("M16,68 L11,35 Q17,51 22,53 Q28,51 30,27 Q37,47 41,49 Q46,47 50,15 "
            "Q54,47 59,49 Q63,47 70,27 Q72,51 78,53 Q83,51 89,35 L84,68 Z")
    band = "M13,66 Q50,74 87,66 L87,79 Q50,87 13,79 Z"

    def glint(t0, t1):   # white stripe sliding across, transparent elsewhere
        s_a = anim([(0, [-20, -10]), (t0, [-20, -10], (0.5, 0, 0.5, 1)), (t1, [90, 30])])
        e_a = anim([(0, [10, 20]), (t0, [10, 20], (0.5, 0, 0.5, 1)), (t1, [120, 60])])
        return gfill([(0, "#ffffff"), (1, "#ffffff")], s_a, e_a, alpha=[(0, 0), (0.4, 0), (0.5, 0.7), (0.6, 0), (1, 0)])

    gold = []
    # front: big emerald in a gold bezel, side stones, pearls on the band
    stone = group(gem_shapes(c, 110), "emerald", p=(50, 66), a=(50, 50), s=(27, 27))
    bezel = group([poly(OUTER), gfill([(0, g1), (0.5, g2), (1, g4)], (10, 0), (90, 100))], "bezel",
                  p=(50, 66), a=(50, 50), s=(34, 34))
    side = []
    for n, x in enumerate((27, 73)):
        y = 73.9
        tw = anim([(0, [100, 100]), (130 + n * 12, [100, 100], (0.4, 0, 0.3, 1.6)), (140 + n * 12, [130, 130]),
                   (156 + n * 12, [100, 100]), (OP, [100, 100])])
        side.append(group([ellipse(-1.2, -1.3, 2.2), fill("#ffffff", 85)], f"sg{n}", p=(x, y), s=tw))
        side.append(group([ellipse(0, 0, 7.5), gfill([(0, c1), (0.5, c2), (1, c4)], (-3, -3), (3, 3))], f"side{n}", p=(x, y), s=tw))
        side.append(group([ellipse(0, 0, 10), gfill([(0, g1), (1, g4)], (-4, -4), (4, 4))], f"sset{n}", p=(x, y)))
    pearls = []
    for x in (17, 37.5, 62.5, 83):
        y = 72.6 + (0.9 if x in (37.5, 62.5) else -0.6)
        pearls.append(group([ellipse(x - 0.6, y - 0.7, 1.2), fill("#ffffff")], "ph"))
        pearls.append(group([ellipse(x, y, 3.4), gfill([(0, "#ffffff"), (1, "#cfe9dc")], (x - 1.5, y - 1.5), (x + 1.5, y + 1.5))], "pearl"))
    gold += [stone, bezel] + side + pearls
    # band
    gold.append(group(path("M14,66.6 Q50,74.4 86,66.6") + [stroke("#ffffff", 1, 65)], "band-light"))
    gold.append(group(path(band) + [glint(40, 85)], "band-glint"))
    gold.append(group(path(band) + [gfill([(0, g1), (0.35, g2), (0.7, g3), (1, g4)], (50, 67), (50, 84))], "band"))
    # spike gems and the emerald on the centre point
    for n, (x, y) in enumerate(((30, 41), (70, 41))):
        gold.append(group([ellipse(x - 0.7, y - 1, 1.4), fill("#ffffff", 80)], f"kg{n}"))
        gold.append(group([ellipse(x, y, 4, 5.2), gfill([(0, c1), (1, c4)], (x - 2, y - 2.5), (x + 2, y + 2.5))], f"kgem{n}"))
    # body with glint, inner emboss and depth
    gold.append(group(path(body) + [glint(40, 85)], "body-glint"))
    gold.append(group(path(body) + [gfill([(0, g1), (0.35, g2), (0.75, g3), (1, g4)], (40, 15), (60, 70))], "body"))
    gold.append(group(path(body) + [fill(g5)], "body-depth", p=(0, 2.2)))
    gold.append(group(path(band) + [fill(g5)], "band-depth", p=(0, 2.2)))

    tips = []
    for n, (x, y) in enumerate(((11, 35), (30, 27), (70, 27), (89, 35))):
        tips.append(group([ellipse(x - 1, y - 1.3, 1.6), fill("#ffffff")], f"th{n}"))
        tips.append(group([ellipse(x, y - 1, 5.6), gfill([(0, "#ffffff"), (1, "#c9e6d8")], (x - 2.5, y - 3.5), (x + 2.5, y + 1.5))],
                          f"tip{n}"))
    crown_gem = group([poly(star_pts(0, 0, 6.4, 6.4 * 0.92, n=4, rot=-90)),
                       gfill([(0, c1), (0.5, c2), (1, c4)], (-5, -5), (5, 5))], "top-gem", p=(50, 12))
    top_hl = group([poly(star_pts(0, 0, 2.4, 2.4 * 0.92, n=4, rot=-90)), fill("#ffffff", 80)], "top-hl", p=(48.4, 10.4))
    top_set = group([ellipse(50, 12, 15), gfill([(0, g1), (1, g4)], (44, 6), (56, 18))], "top-set")
    tips = [top_hl, crown_gem, top_set] + tips

    float_p = anim([(0, [50, 51], ease), (OP / 2, [50, 48.5], ease), (OP, [50, 51])])
    tilt = anim([(0, 0, ease), (OP / 4, -2.5, ease), (OP * 3 / 4, 2.5, ease), (OP, 0)])
    size = anim([(0, [104, 104], ease), (OP / 2, [107, 107], ease), (OP, [104, 104])])

    halo = group([ellipse(0, 0, 96), gfill([(0, c2), (1, c3)], (0, 0), (48, 0), alpha=[(0, 0.4), (0.6, 0.12), (1, 0)], radial=True)],
                 "halo")
    shadow = group([ellipse(50, 93, 64, 7), gfill([(0, c3), (1, c5)], (50, 93), (82, 93), alpha=[(0, 0.6), (1, 0)], radial=True)],
                   "shadow")

    layers = []
    for n, (x, y, size_, t0) in enumerate([(62, 8, 7, 20), (90, 20, 5, 70), (8, 22, 5, 115), (60, 60, 6, 135)]):
        layers.append(sparkle(10 + n, x, y, size_, t0))
    layers.append(layer("tips", tips, 2, p=float_p, a=(50, 50), s=size, r=tilt))
    layers.append(layer("crown", gold, 3, p=float_p, a=(50, 50), s=size, r=tilt))
    layers.append(layer("shadow", [shadow], 5, s=anim([(0, [100, 100], ease), (OP / 2, [88, 88], ease), (OP, [100, 100])])))
    layers.append(layer("halo", [halo], 6, p=(50, 50), a=(0, 0),
                        s=anim([(0, [100, 100], ease), (OP / 2, [112, 112], ease), (OP, [100, 100])])))
    return layers


# ---------------------------------------------------------------- owner variants (pick one)
CROWN = ("M16,68 L11,35 Q17,51 22,53 Q28,51 30,27 Q37,47 41,49 Q46,47 50,15 "
         "Q54,47 59,49 Q63,47 70,27 Q72,51 78,53 Q83,51 89,35 L84,68 Z")
EASE = (0.45, 0, 0.55, 1)


def _glint(t0, t1, a0=(-20, -10), a1=(90, 30), span=30, peak=0.7):
    s_a = anim([(0, list(a0)), (t0, list(a0), (0.5, 0, 0.5, 1)), (t1, list(a1))])
    e_a = anim([(0, [a0[0] + span, a0[1] + span]), (t0, [a0[0] + span, a0[1] + span], (0.5, 0, 0.5, 1)),
                (t1, [a1[0] + span, a1[1] + span])])
    return gfill([(0, "#ffffff"), (1, "#ffffff")], s_a, e_a, alpha=[(0, 0), (0.4, 0), (0.5, peak), (0.6, 0), (1, 0)])


def _gstroke(stops, s, e, w, alpha=None):
    g = gfill(stops, s, e, alpha=alpha)
    g.update(ty="gs", w=prop(w), lc=2, lj=2, ml=4)
    del g["r"]
    return g


def _float_layers(items_top, items, sparkles, scale=104, glow=True):
    float_p = anim([(0, [50, 51], EASE), (OP / 2, [50, 48.5], EASE), (OP, [50, 51])])
    tilt = anim([(0, 0, EASE), (OP / 4, -2.5, EASE), (OP * 3 / 4, 2.5, EASE), (OP, 0)])
    size = anim([(0, [scale, scale], EASE), (OP / 2, [scale + 3, scale + 3], EASE), (OP, [scale, scale])])
    c = THEMES["emerald"]
    layers = [sparkle(10 + n, x, y, sz, t0) for n, (x, y, sz, t0) in enumerate(sparkles)]
    if items_top:
        layers.append(layer("top", items_top, 2, p=float_p, a=(50, 50), s=size, r=tilt))
    layers.append(layer("main", items, 3, p=float_p, a=(50, 50), s=size, r=tilt))
    layers.append(layer("shadow", [group([ellipse(50, 93, 64, 7), gfill([(0, c[2]), (1, c[4])], (50, 93), (82, 93),
                                                                       alpha=[(0, 0.6), (1, 0)], radial=True)], "sh")], 5,
                        s=anim([(0, [100, 100], EASE), (OP / 2, [88, 88], EASE), (OP, [100, 100])])))
    if glow:
        layers.append(layer("halo", [group([ellipse(0, 0, 96), gfill([(0, c[1]), (1, c[2])], (0, 0), (48, 0),
                                                                   alpha=[(0, 0.4), (0.6, 0.12), (1, 0)], radial=True)], "h")], 6,
                            p=(50, 50), a=(0, 0), s=anim([(0, [100, 100], EASE), (OP / 2, [112, 112], EASE), (OP, [100, 100])])))
    return layers


def owner_emerald():
    """B: the crown itself is cut from emerald, trimmed with gold: gold band, gold tips."""
    c1, c2, c3, c4, c5 = THEMES["emerald"]
    g1, g2, g3, g4, g5 = THEMES["gold"]
    band = "M13,66 Q50,74 87,66 L87,79 Q50,87 13,79 Z"
    facets = ("M30,27 L33,62 M50,15 L50,66 M70,27 L67,62 M11,35 L20,64 M89,35 L80,64 "
              "M22,53 L33,62 M41,49 L50,66 M59,49 L50,66 M78,53 L67,62")
    it = []
    for n, x in enumerate((30, 50, 70)):
        y = 75.2 if x == 50 else 73.6
        k = 1.25 if x == 50 else 0.95
        it.append(group([ellipse(x - 1.1 * k, y - 1.2 * k, 2 * k), fill("#ffffff", 85)], f"gh{n}"))
        it.append(group([poly(star_pts(x, y, 4.2 * k, 4.2 * k * 0.92, n=4)), gfill([(0, c1), (0.5, c2), (1, c4)],
                                                                                 (x - 3, y - 3), (x + 3, y + 3))], f"g{n}"))
        it.append(group([ellipse(x, y, 11 * k), gfill([(0, g1), (1, g4)], (x - 4, y - 4), (x + 4, y + 4))], f"set{n}"))
    it.append(group(path("M14,66.6 Q50,74.4 86,66.6") + [stroke("#ffffff", 1, 65)], "band-light"))
    it.append(group(path(band) + [_glint(40, 85)], "band-glint"))
    it.append(group(path(band) + [gfill([(0, g1), (0.35, g2), (0.7, g3), (1, g4)], (50, 67), (50, 84))], "band"))
    it.append(group(path(CROWN) + [_glint(100, 150, peak=0.8)], "glint"))
    it.append(group(path(facets) + [stroke("#ffffff", 0.9, 30)], "facets"))
    it.append(group(path(CROWN) + [stroke(g2, 2.2)], "rim"))
    it.append(group(path("M50,15 L41,49 Q46,47 50,15 Z M30,27 L22,53 Q28,51 30,27 Z") + [fill("#ffffff", 22)], "light"))
    it.append(group(path(CROWN) + [gfill([(0, c1), (0.4, c2), (0.8, c3), (1, c4)], (35, 15), (65, 70))], "body"))
    it.append(group(path(CROWN) + [fill(c5)], "depth", p=(0, 2.2)))
    it.append(group(path(band) + [fill(g5)], "band-depth", p=(0, 2.2)))
    top = []
    for n, (x, y) in enumerate(((11, 35), (30, 27), (50, 15), (70, 27), (89, 35))):
        r = 7 if x == 50 else 5.6
        top.append(group([ellipse(x - 1, y - 1.4, r * 0.3), fill("#ffffff", 90)], f"th{n}"))
        top.append(group([ellipse(x, y - 1, r), gfill([(0, g1), (1, g3)], (x - 2.5, y - 3.5), (x + 2.5, y + 1.5))], f"tip{n}"))
    return _float_layers(top, it, [(62, 8, 7, 20), (90, 20, 5, 70), (8, 22, 5, 115), (40, 58, 6, 140)])


def owner_crowned_gem():
    """C: the brand emerald with a small gold crown resting on top of it."""
    c = THEMES["emerald"]
    g1, g2, g3, g4, g5 = THEMES["gold"]
    stone = group(gem_shapes(c, 100), "stone", p=(50, 66), a=(50, 50), s=(60, 60))
    crown = []
    for n, (x, y) in enumerate(((11, 35), (30, 27), (50, 15), (70, 27), (89, 35))):
        crown.append(group([ellipse(x, y - 1, 6.5), gfill([(0, "#ffffff"), (1, "#cfe9dc")], (x - 2, y - 3), (x + 2, y + 1))], f"p{n}"))
    crown.append(group(path(CROWN) + [_glint(30, 70)], "glint"))
    crown.append(group(path(CROWN) + [gfill([(0, g1), (0.35, g2), (0.75, g3), (1, g4)], (40, 15), (60, 70))], "body"))
    crown.append(group(path(CROWN) + [fill(g5)], "depth", p=(0, 3)))
    hop = anim([(0, [53, 35], EASE), (18, [53, 35], (0.3, 0, 0.7, 1)), (32, [53, 28], (0.5, 0, 0.6, 1)), (46, [53, 35]),
                (54, [53, 33.5], EASE), (62, [53, 35]), (OP, [53, 35])])
    rot = anim([(0, -10, EASE), (18, -10, (0.3, 0, 0.7, 1)), (32, 4, (0.5, 0, 0.6, 1)), (46, -12, EASE), (62, -10), (OP, -10)])
    layers = [sparkle(10 + n, x, y, sz, t0) for n, (x, y, sz, t0) in
              enumerate([(86, 34, 7, 40), (14, 50, 5, 90), (84, 88, 5, 130), (20, 14, 5, 10)])]
    layers.append(layer("crown", [group(crown, "crown", a=(50, 68), s=(56, 56))], 2, p=hop, a=(0, 0), r=rot))
    layers.append(layer("stone", [stone], 3, s=anim([(0, [100, 100], EASE), (OP / 2, [97, 97], EASE), (OP, [100, 100])])))
    return layers


def owner_minimal():
    """D: clean monoline crown polished from emerald, with one emerald in the centre."""
    c1, c2, c3, c4, c5 = THEMES["emerald"]
    line = "M20,66 L15,32 L33,48 L50,22 L67,48 L85,32 L80,66 Z"
    base = "M20,78 H80"
    stops = [(0, "#a8ffd9"), (0.35, c1), (0.7, c2), (1, c3)]
    it = []
    gem = star_pts(50, 54, 7.5, 7.5 * 0.92, n=4)
    it.append(group([ellipse(47.6, 51.5, 3), fill("#ffffff", 90)], "gem-hl"))
    it.append(group([poly(gem), _glint(110, 150, (40, 44), (60, 64), 8, 0.9)], "gem-glint"))
    it.append(group([poly(gem), stroke(c5, 1.2, 60)], "gem-edge"))
    it.append(group([poly(gem), gfill([(0, c1), (0.4, c2), (1, c4)], (44, 48), (56, 60))], "gem"))
    for d in (line, base):
        it.append(group(path(d) + [_gstroke([(0, "#ffffff"), (1, "#ffffff")],
                                            anim([(0, [-30, -30]), (30, [-30, -30], (0.5, 0, 0.5, 1)), (75, [70, 70])]),
                                            anim([(0, [0, 0]), (30, [0, 0], (0.5, 0, 0.5, 1)), (75, [100, 100])]), 7,
                                            alpha=[(0, 0), (0.4, 0), (0.5, 0.85), (0.6, 0), (1, 0)])], "glint"))
        it.append(group(path(d) + [_gstroke(stops, (30, 20), (70, 80), 7)], "line"))
        it.append(group(path(d) + [stroke(c4, 7)], "depth", p=(0, 1.3)))
        it.append(group(path(d) + [stroke(c5, 7)], "depth2", p=(0, 2.6)))
    return _float_layers([], it, [(78, 12, 6, 30), (12, 60, 4.5, 90), (90, 70, 4.5, 140)], scale=100)


def owner_crystals():
    """E: a crown of three emerald crystals rising from a gold base."""
    c1, c2, c3, c4, c5 = THEMES["emerald"]
    g1, g2, g3, g4, g5 = THEMES["gold"]
    it = []
    for n, (x, top, w) in enumerate(((31, 30, 15), (50, 12, 19), (69, 30, 15))):
        h = w / 2
        bot = 68
        tip = [(x, top), (x - h, top + h * 1.2), (x, top + h * 1.9), (x + h, top + h * 1.2)]
        t0 = 40 + n * 14
        outline = [(x, top), (x - h, top + h * 1.2), (x - h, bot), (x, bot + 2), (x + h, bot), (x + h, top + h * 1.2)]
        it.append(group([poly(outline), _glint(t0, t0 + 30, (x - 30, top - 10), (x + 12, top + 40), 18, 0.75)], f"glint{n}"))
        it.append(group([poly([(x, top + h * 1.9), (x, bot + 2)], False), stroke("#ffffff", 0.8, 35)], f"ridge{n}"))
        it.append(group([poly(tip), gfill([(0, "#ffffff"), (1, c1)], (x - h, top), (x + h, top + h * 2))], f"tip{n}"))
        it.append(group([poly([(x, top + h * 1.9), (x - h, top + h * 1.2), (x - h, bot), (x, bot + 2)]),
                         gfill([(0, c1), (1, c3)], (x - h, top), (x, bot))], f"l{n}"))
        it.append(group([poly([(x, top + h * 1.9), (x + h, top + h * 1.2), (x + h, bot), (x, bot + 2)]),
                         gfill([(0, c2), (1, c5)], (x, top), (x + h, bot))], f"r{n}"))
    band = "M16,64 Q50,70 84,64 L84,78 Q50,85 16,78 Z"
    it = [group(path("M17,64.6 Q50,70.4 83,64.6") + [stroke("#ffffff", 1, 70)], "band-light"),
          group(path(band) + [_glint(90, 130)], "band-glint"),
          group([poly(star_pts(50, 73.5, 4.5, 4.5 * 0.92, n=4)), gfill([(0, c1), (1, c4)], (46, 70), (54, 77))], "stone"),
          group([ellipse(50, 73.5, 12), gfill([(0, g1), (1, g4)], (45, 68), (55, 79))], "set"),
          group(path(band) + [gfill([(0, g1), (0.35, g2), (0.7, g3), (1, g4)], (50, 64), (50, 82))], "band")] + it
    it.append(group(path(band) + [fill(g5)], "band-depth", p=(0, 2.2)))
    return _float_layers([], it, [(50, 4, 6, 40), (84, 30, 5, 80), (14, 34, 5, 120), (88, 70, 4, 150)])


OWNER_VARIANTS = {"a_royal": owner_layers, "b_emerald": owner_emerald, "c_crowned_gem": owner_crowned_gem,
                  "d_minimal": owner_minimal, "e_crystals": owner_crystals}


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
    "owner":     ("👑", "emerald", None, 0),     # unique: monoline emerald crown, for the project owners
}

SPARKLES = [(86, 10, 9, 0), (10, 30, 6, 50), (92, 70, 5.5, 100), (14, 88, 5, 140)]


def build(name):
    _, theme, icon, shine = EMOJI[name]
    if icon is None:
        return {"tgs": 1, "v": "5.5.2", "fr": FR, "ip": 0, "op": OP, "w": 100, "h": 100,
                "nm": f"emerald_{name}", "ddd": 0, "assets": [], "layers": owner_minimal()}
    c = THEMES[theme]
    parts, lk = icon()
    lk = dict(lk)
    a = lk.pop("a", (50, 50))
    p = lk.pop("p", a)
    layers = []
    for n, (x, y, size, t0) in enumerate(SPARKLES):
        layers.append(sparkle(10 + n, x, y, size, (t0 + shine) % (OP - 40)))
    icon_l = layer("icon", paint(parts, WHITE), 2, p=p, a=a, **lk)
    shadow = layer("icon-shadow", paint(parts, c[4]), 3, p=(a[0], a[1] + 2.4), a=a, o=55, parent=2)
    gem = layer("gem", gem_shapes(c, shine), 4,
                s=anim([(0, [100, 100], (0.45, 0, 0.55, 1)), (OP / 2, [97, 97], (0.45, 0, 0.55, 1)), (OP, [100, 100])]))
    layers += [icon_l, shadow, gem]
    return {"tgs": 1, "v": "5.5.2", "fr": FR, "ip": 0, "op": OP, "w": 100, "h": 100,
            "nm": f"emerald_{name}", "ddd": 0, "assets": [], "layers": layers}


def main():
    if sys.argv[1:] == ["--owner-variants"]:      # previews to choose the owner crown from
        out = os.path.join(DIR, "owner_variants")
        os.makedirs(out, exist_ok=True)
        for key, fn in OWNER_VARIANTS.items():
            data = {"tgs": 1, "v": "5.5.2", "fr": FR, "ip": 0, "op": OP, "w": 100, "h": 100, "nm": f"owner_{key}",
                    "ddd": 0, "assets": [], "layers": fn()}
            with open(os.path.join(out, f"owner_{key}.tgs"), "wb") as f:
                f.write(gzip.compress(json.dumps(data, separators=(",", ":")).encode(), 9, mtime=0))
            print(key)
        return
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
