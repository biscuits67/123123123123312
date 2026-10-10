"""Kinetic flip-tile wall in the shop window, 250-frame loop (replaces the rates board).

    blender -b IN.blend -P kinetic_wall.py -- OUT.blend

84 x 28 black tiles (green glowing back face, green-lit edges) flip in a wave from left to right:
    75%  ->  bolt + ВЫПЛАТЫ  ->  1+ ГОД  ->  75% (loop)
Tiles that change flip 180 deg with an overshoot; the rest twitch as the wave passes, so the whole wall
moves like an airport board. A caption on the frame under the window switches with each message.
Every tile makes an even number of half turns per loop, so frame 251 == frame 1.
"""
import math
import sys

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[sys.argv.index("--") + 1]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 250
FRONT_X, BACK_X = -52.62, -51.13
CY, CZ, WID, HGT = -73.49, 2.70, 6.9, 2.6
COLS, ROWS = 84, 28
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
FONT_UI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
WAVE = 26          # frames for the wave to cross the wall
FLIP = 9           # frames for one tile flip
STARTS = (56, 132, 206)   # transition starts: msg0->1, 1->2, 2->0 (last flip settles by ~248)

D.objects["rates_board"].hide_render = True
D.objects["rates_board"].hide_viewport = True
for ob in D.objects:            # the niche's own area light would read as a white panel between the tiles
    if ob.type == "LIGHT" and ob.data.type == "AREA" and (ob.location - Vector((-52.0, CY, 3.5))).length < 2.5:
        ob.visible_camera = ob.visible_glossy = ob.visible_transmission = False


# ---------------------------------------------------------------- messages -> tile masks
# Hand-drawn pixel glyphs (11-row body, 2-tile stems) so every letter lands cleanly on the tile grid;
# a scaled-down font smears into broken letters at this resolution.
GLYPHS = {
    "7": ["#######", "#######", ".....##", "....##.", "....##.", "...##..", "...##..", "..##...", "..##...", "..##...", "..##..."],
    "5": ["#######", "#######", "##.....", "##.....", "######.", "#######", ".....##", ".....##", "##...##", "#######", ".#####."],
    "%": [".##....##", "####..##.", "####..##.", ".##..##..", "....##...", "...##....", "..##.....", ".##..##..",
          ".##.####.", "##..####.", "##...##.."],
    "1": ["..##.", ".###.", "####.", "..##.", "..##.", "..##.", "..##.", "..##.", "..##.", "#####", "#####"],
    "+": ["......", "......", "......", "..##..", "..##..", "######", "######", "..##..", "..##..", "......", "......"],
    " ": ["..", "..", "..", "..", "..", "..", "..", "..", "..", "..", ".."],
    "Г": ["######", "######", "##....", "##....", "##....", "##....", "##....", "##....", "##....", "##....", "##...."],
    "О": [".#####.", "#######", "##...##", "##...##", "##...##", "##...##", "##...##", "##...##", "##...##", "#######", ".#####."],
    "Д": ["..#####..", ".######..", ".##..##..", ".##..##..", ".##..##..", ".##..##..", ".##..##..", ".##..##..", ".##..##..",
          "#########", "#########", "##.....##", "##.....##"],
    "В": ["######.", "#######", "##...##", "##...##", "##..##.", "######.", "#######", "##...##", "##...##", "#######", "######."],
    "Ы": ["##.....##", "##.....##", "##.....##", "##.....##", "#####..##", "######.##", "##..##.##", "##..##.##", "##..##.##",
          "######.##", "#####..##"],
    "П": ["#######", "#######"] + ["##...##"] * 9,
    "Л": ["..#####", ".######", ".##..##", ".##..##", ".##..##", ".##..##", ".##..##", ".##..##", ".##..##", "##...##", "##...##"],
    "А": ["..###..", ".#####.", "##...##", "##...##", "##...##", "#######", "#######", "##...##", "##...##", "##...##", "##...##"],
    "Т": ["########", "########"] + ["...##..."] * 9,
}


BOLT = [".......####.", "......####..", "......###...", ".....####...", ".....###....", "....####....", "....###.....",
        "...####.....", "...###......", "..##########", ".##########.", "##########..", "......###...", ".....####...",
        ".....###....", "....####....", "....###.....", "...####.....", "...###......", "..####......", "..###.......",
        ".###........"]


def bolt():
    a = np.array([[c == "#" for c in r] for r in BOLT], dtype=bool)
    return np.vstack([a, np.zeros((4, a.shape[1]), dtype=bool)])     # pad like a glyph with descender room


def line(text, scale):
    """Rasterise a word: list of rows (top first) of 0/1, 11*scale tall (+descender)."""
    cols, h = [], 13
    for i, ch in enumerate(text):
        g = GLYPHS[ch] + ["." * len(GLYPHS[ch][0])] * (13 - len(GLYPHS[ch]))
        w = len(g[0])
        for x in range(w):
            cols.append([g[y][x] == "#" for y in range(h)])
        if i < len(text) - 1:
            cols.append([False] * h)
    a = np.array(cols, dtype=bool).T                 # rows x cols, row 0 = top
    return np.kron(a, np.ones((scale, scale), dtype=bool))


def place(parts):
    """parts: list of (bitmap, gap_after). Bitmaps are centred on the 11-row body line, the group is centred."""
    grid = np.zeros((ROWS, COLS), dtype=bool)
    total = sum(p.shape[1] + gap for p, gap in parts) - parts[-1][1]
    x = (COLS - total) // 2
    for p, gap in parts:
        body = p.shape[0] * 11 // 13                # rows above the descender
        y = min((ROWS - body) // 2, ROWS - p.shape[0])   # keep a descender (Д) inside the wall
        grid[y:y + p.shape[0], x:x + p.shape[1]] |= p[:ROWS - y]
        x += p.shape[1] + gap
    return grid[::-1]                                # row 0 = bottom


def draw_mask(kind):
    if kind == "percent":
        return place([(line("75%", 2), 0)])
    if kind == "payout":
        return place([(bolt(), 6), (line("ВЫПЛАТЫ", 1), 0)])
    return place([(line("1+", 2), 4), (line("ГОД", 2), 0)])


MASKS = [draw_mask(k) for k in ("percent", "payout", "year")]
CAPTIONS = ["ЛУЧШИЙ ПРОЦЕНТ НА РЫНКЕ", "МОМЕНТАЛЬНЫЕ ВЫПЛАТЫ", "РАБОТАЕМ БОЛЬШЕ ГОДА"]


# ---------------------------------------------------------------- materials + tile mesh
def mat(name, color, metal=0.0, rough=0.3, emit=None, strength=0.0):
    m = D.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value = metal, rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


black = mat("KW_Black", (0.006, 0.007, 0.007), metal=0.0, rough=0.42)
black.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.25
green = mat("KW_Green", (0.02, 0.45, 0.22), rough=0.25, emit=(0.08, 1.0, 0.5), strength=4.5)
edge = mat("KW_Edge", (0.012, 0.014, 0.014), metal=0.6, rough=0.35)          # dark anodised sides
# LED modules are never perfectly even: +-6% brightness per tile from Object Info > Random
gnt = green.node_tree
oi = gnt.nodes.new("ShaderNodeObjectInfo")
mr = gnt.nodes.new("ShaderNodeMapRange")
mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 4.2, 4.8
gnt.links.new(oi.outputs["Random"], mr.inputs["Value"])
gnt.links.new(mr.outputs["Result"], gnt.nodes["Principled BSDF"].inputs["Emission Strength"])
pitch_y, pitch_z = WID / COLS, HGT / ROWS
x, y, z = 0.025, pitch_y * 0.47, pitch_z * 0.47
me = D.meshes.new("kw_tile")
vs = [(-x, -y, -z), (-x, y, -z), (-x, y, z), (-x, -y, z), (x, -y, -z), (x, y, -z), (x, y, z), (x, -y, z)]
fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
me.from_pydata(vs, [], fs)
for m_ in (green, black, edge):
    me.materials.append(m_)
for p, mi in zip(me.polygons, (0, 1, 2, 2, 2, 2)):      # -X face green, +X face black, sides lit
    p.material_index = mi

# dark back panel so the gaps read as depth
bpy.ops.mesh.primitive_plane_add(size=1, location=(BACK_X - 0.02, CY, CZ), rotation=(0, math.radians(90), 0))
back = bpy.context.object
back.name = "KW_Back"
back.scale = (HGT + 0.1, WID + 0.1, 1)
back.data.materials.append(mat("KW_BackMat", (0.002, 0.003, 0.003), rough=0.9))

col = D.collections.new("Kinetic_Wall")
scn.collection.children.link(col)

# bezel: black anodised frame around the wall with a thin mint light line on its inner edge, and cover glass
bez = mat("KW_Bezel", (0.01, 0.011, 0.011), metal=0.8, rough=0.28)
line_m = mat("KW_BezelLine", (0.05, 0.5, 0.3), emit=(0.08, 1.0, 0.5), strength=8)
B, DEP = 0.14, 0.12
fx = FRONT_X + 0.16
for (dy, dz, sy, sz) in ((0, HGT / 2 + B / 2, WID + 2 * B, B), (0, -HGT / 2 - B / 2, WID + 2 * B, B),
                         (WID / 2 + B / 2, 0, B, HGT), (-WID / 2 - B / 2, 0, B, HGT)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(fx, CY + dy, CZ + dz))
    f = bpy.context.object
    f.scale = (DEP, sy, sz)
    f.data.materials.append(bez)
    bv = f.modifiers.new("bevel", "BEVEL")
    bv.width, bv.segments = 0.012, 3
    for c in list(f.users_collection):
        c.objects.unlink(f)
    col.objects.link(f)
for (dy, dz, sy, sz) in ((0, HGT / 2 + 0.006, WID, 0.012), (0, -HGT / 2 - 0.006, WID, 0.012),
                         (WID / 2 + 0.006, 0, 0.012, HGT), (-WID / 2 - 0.006, 0, 0.012, HGT)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(fx - DEP / 2 - 0.002, CY + dy, CZ + dz))
    l_ = bpy.context.object
    l_.scale = (0.006, sy, sz)
    l_.data.materials.append(line_m)
    for c in list(l_.users_collection):
        c.objects.unlink(l_)
    col.objects.link(l_)
glass = D.materials.new("KW_Glass")
gb = glass.node_tree.nodes["Principled BSDF"]
gb.inputs["Transmission Weight"].default_value, gb.inputs["Roughness"].default_value = 1.0, 0.02
gb.inputs["Thin Wall"].default_value = True
bpy.ops.mesh.primitive_plane_add(size=1, location=(fx - DEP / 2 - 0.01, CY, CZ), rotation=(0, math.radians(90), 0))
gl = bpy.context.object
gl.name = "KW_Glass"
gl.scale = (HGT, WID, 1)
gl.data.materials.append(glass)
gl.visible_shadow = False
gb.inputs["Specular IOR Level"].default_value = 0.35
key = D.objects.get("Hero_Key")          # its soft box would show up as a grey card in the cover glass
if key:
    key.visible_glossy = False
for c in list(gl.users_collection):
    c.objects.unlink(gl)
col.objects.link(gl)


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def angle_track(r, c):
    """Per-frame Z rotation: pi = black side out, 0 (mod 2pi) = green side out."""
    states = [bool(m[r, c]) for m in MASKS]
    base = 0.0 if states[0] else math.pi
    events = []                                          # (start frame, delta angle)
    for i, s0 in enumerate(STARTS):
        cur, nxt = states[i], states[(i + 1) % 3]
        t = s0 + WAVE * c / (COLS - 1) + 2.5 * math.sin(r * 0.9 + c * 0.3)   # ragged wave front
        events.append((t, math.pi if cur != nxt else 0.0))
    vals = []
    for f in range(F0, F1 + 2):
        a = base
        for t, dlt in events:
            k = (f - t) / FLIP
            if dlt:
                e = ease(k)
                a += dlt * e + (0.12 * math.sin(math.pi * min(1.0, (k - 1) * 2)) if k > 1 else 0)   # small bounce
            else:
                a += 0.32 * math.sin(math.pi * min(1.0, max(0.0, k)))          # twitch as the wave passes
        vals.append(a)
    return vals


for r in range(ROWS):
    for c in range(COLS):
        ob = D.objects.new(f"KW_{r:02d}_{c:02d}", me)
        col.objects.link(ob)
        ob.location = (FRONT_X + 0.22, CY + WID / 2 - (c + 0.5) * pitch_y, CZ - HGT / 2 + (r + 0.5) * pitch_z)
        vals = angle_track(r, c)
        ad = ob.animation_data_create()
        act = D.actions.new(ob.name)
        ad.action = act
        fc = None
        ob.rotation_euler = (0, 0, vals[0])
        ob.keyframe_insert("rotation_euler", index=2, frame=F0)
        for slot_bag in act.layers[0].strips[0].channelbag(ad.action_slot).fcurves:
            fc = slot_bag
        prev = None
        keys = []
        for f, v in zip(range(F0, F1 + 2), vals):
            if prev is None or abs(v - prev) > 1e-5 or f in (F0, F1 + 1):
                keys.append((f, v))
            prev = v
        # keep only keys around motion (plus the holds' ends) for a light file
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(keys))
        for kp, (f, v) in zip(fc.keyframe_points, keys):
            kp.co = (f, v)
            kp.interpolation = "LINEAR"
        fc.update()

# ---------------------------------------------------------------- caption under the window
cap_mat = mat("KW_Caption", (0.9, 1.0, 0.95), emit=(0.75, 1.0, 0.88), strength=3.0)
for i, text in enumerate(CAPTIONS):
    cu = D.curves.new(f"KW_Caption_{i}", "FONT")
    cu.body, cu.align_x, cu.align_y, cu.size = text, "CENTER", "CENTER", 0.16
    cu.space_character = 1.25
    cu.font = D.fonts.load(FONT_UI, check_existing=True)
    cu.materials.append(cap_mat)
    ob = D.objects.new(cu.name, cu)
    col.objects.link(ob)
    ob.location = (FRONT_X - 0.012, CY, 1.2)
    ob.rotation_euler = (math.radians(90), 0, math.radians(-90))
    shown = [(F0, i == 0)]
    for j, s0 in enumerate(STARTS):                      # swap captions halfway through each wave
        shown.append((int(s0 + WAVE / 2), i == (j + 1) % 3))
    for f, vis in shown:
        ob.hide_render = ob.hide_viewport = not vis
        ob.keyframe_insert("hide_render", frame=f)
        ob.keyframe_insert("hide_viewport", frame=f)

for font in D.fonts:
    if font.filepath.startswith("/usr/share/fonts") and not font.packed_file:
        font.pack()
scn.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
