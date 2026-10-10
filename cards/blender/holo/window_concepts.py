"""Three full-window concepts for the shop niche (replace the rates board).

    blender -b IN.blend -P window_concepts.py -- OUT.blend VARIANT [PHASE]

VARIANT: aquarium  - glass front, a huge emerald-cut stone turning inside, engraved text on the glass
         tiles     - kinetic wall of black gloss tiles flipping in a wave into a giant "75%"
         led       - LED wall (dot pixels, green waves) with chrome 3D "75%" bursting out of it
PHASE (0..1) is where the wave/fly-in is for a concept still.
"""
import math
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

args = sys.argv[sys.argv.index("--") + 1:]
OUT, VARIANT = args[0], args[1]
PHASE = float(args[2]) if len(args) > 2 else 0.6
D, scn = bpy.data, bpy.context.scene
# niche opening (world): front plane x, centre, size
FRONT_X, BACK_X = -52.62, -51.13
CY, CZ, WID, HGT = -73.49, 2.70, 6.9, 2.6
MINT = (0.08, 1.0, 0.5, 1)
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"

D.objects["rates_board"].hide_render = True
D.objects["rates_board"].hide_viewport = True
for ob in D.objects:          # the niche's own area light would show as a white panel through the new window
    if ob.type == "LIGHT" and ob.data.type == "AREA":
        ob.visible_camera = False
        ob.visible_glossy = False
        ob.visible_transmission = False


def mat(name, color=(0.02, 0.02, 0.02), metal=0.0, rough=0.3, emit=None, strength=0.0):
    m = D.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value = metal, rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def text(body, size, loc, extrude, m, name, face=(90, 0, -90), font=FONT):
    cu = D.curves.new(name, "FONT")
    cu.body, cu.align_x, cu.align_y, cu.size, cu.extrude = body, "CENTER", "CENTER", size, extrude
    cu.font = D.fonts.load(font, check_existing=True)
    ob = D.objects.new(name, cu)
    scn.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = tuple(math.radians(a) for a in face)
    ob.data.materials.append(m)
    return ob


def mask(textv, cols, rows, pad=0.08):
    """Boolean grid of where the text covers the tile wall."""
    W, H = cols * 20, rows * 20
    im = Image.new("L", (W, H))
    d = ImageDraw.Draw(im)
    size = H
    while True:
        f = ImageFont.truetype(FONT, size)
        l, t, r, b = d.textbbox((0, 0), textv, font=f)
        if r - l < W * (1 - 2 * pad) and b - t < H * (1 - 2 * pad):
            break
        size -= 4
    d.text(((W - (r - l)) / 2 - l, (H - (b - t)) / 2 - t), textv, font=f, fill=255)
    a = np.asarray(im.resize((cols, rows), Image.BOX)) > 90
    return a[::-1]                      # row 0 = bottom


# ================================================================== 1. emerald aquarium
def aquarium():
    # dark velvet back + soft spot from the top
    back = mat("Aq_Back", (0.006, 0.02, 0.014), rough=0.8)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(BACK_X - 0.01, CY, CZ), rotation=(0, math.radians(90), 0))
    p = bpy.context.object
    p.scale = (HGT, WID, 1)
    p.data.materials.append(back)
    # emerald-cut stone (same cut as the hand gem), 2.2 m tall, standing on a plinth
    def ring(sc, z, a=1.0, b=0.72, c=0.26):
        cc, A, B = c * sc, a * sc, b * sc
        return [(A - cc, B, z), (-(A - cc), B, z), (-A, B - cc, z), (-A, -(B - cc), z),
                (-(A - cc), -B, z), (A - cc, -B, z), (A, -(B - cc), z), (A, B - cc, z)]
    prof = [(0.70, 0.21), (0.82, 0.17), (0.91, 0.11), (0.97, 0.05), (1.0, 0.0), (1.0, -0.035),
            (0.84, -0.22), (0.6, -0.42), (0.34, -0.58), (0.1, -0.68)]
    v, f = [], []
    for sc, z in prof:
        v += ring(sc, z)
    for i in range(len(prof) - 1):
        for k in range(8):
            a_, b_ = i * 8 + k, i * 8 + (k + 1) % 8
            f.append((a_, b_, b_ + 8, a_ + 8))
    f.append(tuple(range(7, -1, -1)))
    f.append(tuple(range((len(prof) - 1) * 8, len(prof) * 8)))
    me = D.meshes.new("aq_gem")
    me.from_pydata([(x * 1.05, y * 1.05, z * 1.05) for x, y, z in v], [], f)
    gem = D.objects.new("Aquarium_Emerald", me)
    scn.collection.objects.link(gem)
    gem.location = (BACK_X - 0.7, CY, CZ + 0.05)
    face = Matrix(((0, 0, -1), (0, 1, 0), (1, 0, 0)))      # columns: local X->up, Y->Y, Z(table)->street (-X)
    gem.rotation_euler = (Matrix.Rotation(math.radians(-25 + 50 * PHASE), 3, "Z") @ face).to_euler()
    gm = D.materials.new("Aq_Emerald")
    nt = gm.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.0, 0.5, 0.15, 1)
    b.inputs["Transmission Weight"].default_value, b.inputs["IOR"].default_value = 1.0, 1.577
    b.inputs["Roughness"].default_value = 0.01
    ab = nt.nodes.new("ShaderNodeVolumeAbsorption")
    ab.inputs["Color"].default_value, ab.inputs["Density"].default_value = (0.03, 0.62, 0.22, 1), 7.0
    nt.links.new(ab.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    me.materials.append(gm)
    # inner glow and key lights that make the facets sparkle and throw green onto the street
    core = D.objects.new("Aq_Core", D.lights.new("Aq_Core", "POINT"))
    core.data.energy, core.data.color, core.data.shadow_soft_size = 900, (0.15, 1.0, 0.5), 0.4
    core.location = gem.location
    core.visible_camera = False
    core.visible_transmission = False
    scn.collection.objects.link(core)
    for dy, e in ((-2.4, 1500), (2.4, 1200)):
        k = D.objects.new("Aq_Key", D.lights.new("Aq_Key", "SPOT"))
        k.data.energy, k.data.spot_size, k.data.spot_blend = e, math.radians(30), 0.5
        k.data.color = (0.85, 1.0, 0.92)
        k.location = (FRONT_X + 0.15, CY + dy, CZ + 1.2)
        k.rotation_euler = (gem.location - k.location).to_track_quat("-Z", "Y").to_euler()
        k.visible_camera = False
        scn.collection.objects.link(k)
    # plinth
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.55, depth=0.12, location=(BACK_X - 0.7, CY, 1.375 + 0.06))
    pl = bpy.context.object
    pl.data.materials.append(mat("Aq_Plinth", (0.01, 0.01, 0.01), metal=1.0, rough=0.15))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.01, location=(BACK_X - 0.7, CY, 1.375 + 0.125))
    bpy.context.object.data.materials.append(mat("Aq_Ring", emit=(0.15, 1.0, 0.5), strength=30))
    # glass front with engraved lines
    gl = D.materials.new("Aq_Glass")
    gb = gl.node_tree.nodes["Principled BSDF"]
    gb.inputs["Transmission Weight"].default_value, gb.inputs["Roughness"].default_value = 1.0, 0.0
    gb.inputs["IOR"].default_value = 1.45
    bpy.ops.mesh.primitive_plane_add(size=1, location=(FRONT_X + 0.05, CY, CZ), rotation=(0, math.radians(90), 0))
    g = bpy.context.object
    g.scale = (HGT, WID, 1)
    g.data.materials.append(gl)
    engr = mat("Aq_Engraving", (0.9, 0.95, 0.92), rough=0.4, emit=(0.85, 1.0, 0.92), strength=2.5)
    text("75%", 1.25, Vector((FRONT_X + 0.03, CY - 2.2, CZ + 0.3)), 0.0, engr, "Aq_Value",
         font="/usr/share/fonts/opentype/inter/InterDisplay-Light.otf" if False else "/usr/share/fonts/opentype/inter/Inter-Thin.otf")
    text("ЛУЧШИЙ ПРОЦЕНТ", 0.22, Vector((FRONT_X + 0.03, CY - 2.2, CZ - 0.5)), 0.0, engr, "Aq_Label",
         font="/usr/share/fonts/opentype/inter/Inter-Light.otf")
    text("EMERALD  ·  JEWEL OF EXCHANGE", 0.09, Vector((FRONT_X + 0.03, CY + 2.35, CZ - 1.05)), 0.0, engr, "Aq_Small",
         font="/usr/share/fonts/opentype/inter/Inter-Light.otf")


# ================================================================== 2. kinetic tile wall
def tiles():
    cols, rows = 42, 16
    on = mask("75%", cols, rows)
    pitch_y, pitch_z = WID / cols, HGT / rows
    tw, th, td = pitch_y * 0.9, pitch_z * 0.9, 0.05
    black = mat("Tile_Black", (0.008, 0.008, 0.009), metal=0.3, rough=0.12)
    green = mat("Tile_Green", (0.02, 0.4, 0.2), rough=0.25, emit=(0.08, 1.0, 0.5), strength=6)
    edge = mat("Tile_Edge", (0.01, 0.05, 0.03), emit=(0.08, 1.0, 0.5), strength=1.5)
    me = D.meshes.new("tile")
    # box with a black face (+X: towards the street when flipped 180), green face (-X) and green-lit edges
    x, y, z = td / 2, tw / 2, th / 2
    vs = [(-x, -y, -z), (-x, y, -z), (-x, y, z), (-x, -y, z), (x, -y, -z), (x, y, -z), (x, y, z), (x, -y, z)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
    me.from_pydata(vs, [], fs)
    me.materials.append(green)   # 0: -X face
    me.materials.append(black)   # 1: +X face
    me.materials.append(edge)    # 2: sides
    for p, mi in zip(me.polygons, (0, 1, 2, 2, 2, 2)):
        p.material_index = mi
    me_black = me.copy()
    for p in me_black.polygons:          # tiles outside the digits are black on both sides
        if p.material_index == 0:
            p.material_index = 1
        elif p.material_index == 2:
            p.material_index = 1
    bpy.ops.mesh.primitive_plane_add(size=1, location=(BACK_X - 0.01, CY, CZ), rotation=(0, math.radians(90), 0))
    bk = bpy.context.object
    bk.scale = (HGT, WID, 1)
    bk.data.materials.append(mat("Tile_Back", (0.003, 0.004, 0.004), rough=0.9))
    wave = PHASE * (cols + 8) - 4
    for r in range(rows):
        for c in range(cols):
            yy = CY + WID / 2 - (c + 0.5) * pitch_y          # column 0 on the viewer's left
            zz = CZ - HGT / 2 + (r + 0.5) * pitch_z
            ob = D.objects.new(f"Tile_{r}_{c}", me if on[r, c] else me_black)
            scn.collection.objects.link(ob)
            ob.location = (FRONT_X + 0.25, yy, zz)
            k = min(1.0, max(0.0, (wave - c + 0.3 * math.sin(r)) / 3.0))   # wave sweeps left->right
            k = k * k * (3 - 2 * k)
            ob.rotation_euler = (0, 0, math.pi * (1 - k))                     # pi: black side to the street, 0: green
    key = D.objects.new("Tile_Key", D.lights.new("Tile_Key", "AREA"))
    key.data.energy, key.data.size, key.data.color = 400, 3, (0.8, 1.0, 0.9)
    key.location = (FRONT_X - 2.5, CY - 1.5, CZ + 2.5)
    key.rotation_euler = (Vector((FRONT_X, CY, CZ)) - key.location).to_track_quat("-Z", "Y").to_euler()
    key.visible_camera = False
    scn.collection.objects.link(key)


# ================================================================== 3. LED wall + chrome numbers
def led():
    W, H = 2760, 1040                    # 2.5 mm "pixels" at 6.9 x 2.6 m
    px = 6
    y = np.linspace(0, 1, H // px)[:, None]
    x = np.linspace(0, 1, W // px)[None, :]
    wave = 0.5 + 0.5 * np.sin(14 * x - 6 * y + 9 * PHASE) * np.cos(5 * y + 3 * x)
    glow = np.clip(wave ** 3 * 0.9 + 0.05, 0, 1)
    rgb = np.stack([glow * 0.05, glow * 0.95, glow * 0.5], -1)
    big = np.repeat(np.repeat(rgb, px, 0), px, 1)
    yy, xx = np.mgrid[0:big.shape[0], 0:big.shape[1]]
    dot = (((xx % px) - px / 2 + 0.5) ** 2 + ((yy % px) - px / 2 + 0.5) ** 2) < (px * 0.36) ** 2
    img = (big * dot[..., None] * 255).astype(np.uint8)
    path = bpy.path.abspath("//") or "/tmp/"
    im = Image.fromarray(img[::-1])
    p = "/tmp/led_wall.png"
    im.save(p)
    led_img = D.images.load(p)
    led_img.pack()
    m = D.materials.new("LED_Wall")
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image, t.interpolation = led_img, "Closest"
    nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 4
    b.inputs["Base Color"].default_value = (0.005, 0.005, 0.005, 1)
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Specular IOR Level"].default_value = 0.05
    bpy.ops.mesh.primitive_plane_add(size=1, location=(FRONT_X + 0.3, CY, CZ), rotation=(0, math.radians(90), 0))
    s = bpy.context.object
    s.scale = (HGT, WID, 1)
    s.rotation_euler = (math.radians(90), 0, math.radians(-90))
    s.scale = (WID, HGT, 1)
    s.data.materials.append(m)
    chrome = mat("Chrome", (0.9, 0.92, 0.92), metal=1.0, rough=0.06)
    tilt = 1 - PHASE
    v = text("75%", 1.75, Vector((FRONT_X - 0.25 - 0.8 * tilt, CY - 0.2, CZ + 0.05)), 0.22, chrome, "Chrome_Value",
             face=(90 + 8 * tilt, 6 * tilt, -90 - 14 * tilt))
    v.data.bevel_depth, v.data.bevel_resolution = 0.025, 3
    lbl = text("ЛУЧШИЙ ПРОЦЕНТ", 0.24, Vector((FRONT_X - 0.05, CY, CZ - 1.0)), 0.03, chrome, "Chrome_Label")
    lbl.data.bevel_depth = 0.006
    # studio reflections for the chrome: two big soft strips out of camera view
    for dz, e in ((2.2, 350), (-0.6, 120)):
        k = D.objects.new("Chrome_Strip", D.lights.new("Chrome_Strip", "AREA"))
        k.data.shape, k.data.size, k.data.size_y, k.data.energy = "RECTANGLE", 6, 0.4, e
        k.location = (FRONT_X - 2.2, CY, CZ + dz)
        k.rotation_euler = (Vector((FRONT_X, CY, CZ)) - k.location).to_track_quat("-Z", "Y").to_euler()
        k.visible_camera = False
        scn.collection.objects.link(k)


{"aquarium": aquarium, "tiles": tiles, "led": led}[VARIANT]()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
