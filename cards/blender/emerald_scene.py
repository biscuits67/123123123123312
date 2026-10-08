"""Emerald — cinematic 3D scene for Blender (Cycles).

    python emerald_scene.py -- still 60          -> renders/still_0060.png (one frame)
    python emerald_scene.py -- anim [start end]  -> renders/frames/0001.png ...  (then post.py + ffmpeg)
    python emerald_scene.py -- save              -> emerald_scene.blend (open and tweak in Blender)

Runs with Blender's Python module (pip install bpy) or `blender -b -P emerald_scene.py -- ...`.
Square 1080x1080, 24 fps, 120 frames (5 s). Night yard behind the Emerald office: steel scaffolding
carrying the extruded EMERALD sign, brick wall, ATMs, a mountain of cash, a neon briefcase and the
brand emerald with its crown on a pedestal; green rim light, volumetric haze, wet concrete.
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FPS, FRAMES = 24, 120
EM = {"c1": (0.16, 0.89, 0.51), "c2": (0.01, 0.55, 0.25), "c3": (0.003, 0.25, 0.11), "neon": (0.12, 1.0, 0.55)}
rnd = random.Random(7)


# ---------------------------------------------------------------- helpers
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color=(0.5, 0.5, 0.5), metal=0.0, rough=0.5, emit=None, emit_k=0.0, transmission=0.0, ior=1.45, coat=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    p.inputs["Transmission Weight"].default_value = transmission
    p.inputs["IOR"].default_value = ior
    p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = emit_k
    return m


def emission(name, color, k):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = k
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def image_mat(name, path, rough=0.6, emit_k=0.0, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit_k:
        nt.links.new(tex.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = emit_k
    return m


def obj(name, mesh, material=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    o = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(o)
    o.location, o.rotation_euler, o.scale = loc, rot, scale
    if material:
        o.data.materials.append(material)
    return o


def box_mesh(name, sx, sy, sz):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new()
    return me


def cyl_between(name, a, b, r, material, verts=10):
    a, b = Vector(a), Vector(b)
    d = b - a
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=d.length)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = obj(name, me, material, loc=(a + b) / 2)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    return o


def bevel(o, w=0.02, seg=3):
    m = o.modifiers.new("bevel", "BEVEL")
    m.width, m.segments = w, seg
    m.limit_method = "ANGLE"


def key(o, path, frame, value, index=-1):
    setattr(o, path, value) if index < 0 else getattr(o, path).__setitem__(index, value)
    o.keyframe_insert(data_path=path, frame=frame, index=index)


# ---------------------------------------------------------------- textures (drawn with Pillow)
def make_textures():
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    os.makedirs(os.path.join(HERE, "tex"), exist_ok=True)
    f = lambda s: ImageFont.truetype(FONT, s)
    # banknote
    w, h = 1024, 440
    im = Image.new("RGB", (w, h), (120, 205, 160))
    d = ImageDraw.Draw(im)
    for i in range(h):
        d.line([(0, i), (w, i)], fill=(110 + i // 12, 196 + i // 30, 150 + i // 20))
    d.rectangle([18, 18, w - 18, h - 18], outline=(12, 92, 62), width=14)
    d.rectangle([44, 44, w - 44, h - 44], outline=(12, 92, 62), width=4)
    for r in range(30, 230, 9):
        d.ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], outline=(70, 150, 112), width=2)
    d.ellipse([w / 2 - 110, h / 2 - 110, w / 2 + 110, h / 2 + 110], fill=(11, 138, 94))
    d.text((w / 2, h / 2 + 6), "$", font=f(170), fill=(234, 255, 246), anchor="mm")
    for (x, y, a) in ((120, 100, "lm"), (w - 120, h - 100, "rm")):
        d.text((x, y), "100", font=f(80), fill=(12, 92, 62), anchor=a)
    d.text((w - 70, 96), "EMERALD", font=f(44), fill=(12, 92, 62), anchor="rm")
    d.text((70, h - 96), "EMERALD", font=f(44), fill=(12, 92, 62), anchor="lm")
    im.save(os.path.join(HERE, "tex", "bill.png"))
    # band around a cash stack
    band = Image.new("RGB", (256, 64), (216, 196, 138))
    ImageDraw.Draw(band).text((128, 34), "$10 000", font=f(30), fill=(70, 55, 20), anchor="mm")
    band.save(os.path.join(HERE, "tex", "band.png"))
    # ATM screen
    sc = Image.new("RGB", (600, 460), (2, 22, 14))
    d = ImageDraw.Draw(sc)
    for y in range(460):
        d.line([(0, y), (600, y)], fill=(2, 22 + y // 18, 14 + y // 30))
    d.text((300, 160), "EMERALD", font=f(92), fill=(150, 255, 210), anchor="mm")
    d.rectangle([150, 250, 450, 256], fill=(25, 196, 138))
    d.text((300, 320), "WITHDRAW", font=f(40), fill=(110, 230, 180), anchor="mm")
    sc = sc.filter(ImageFilter.GaussianBlur(0.6))
    sc.save(os.path.join(HERE, "tex", "atm.png"))
    # brick wall
    bw, bh = 1024, 1024
    br = Image.new("RGB", (bw, bh), (22, 24, 22))
    d = ImageDraw.Draw(br)
    for row in range(0, bh, 48):
        off = 0 if (row // 48) % 2 == 0 else 60
        for col in range(-120, bw, 120):
            c = rnd.randint(34, 58)
            d.rectangle([col + off + 4, row + 4, col + off + 116, row + 44], fill=(c + 6, c - 4, c - 8))
    br = br.filter(ImageFilter.GaussianBlur(1.2))
    br.save(os.path.join(HERE, "tex", "brick.png"))


# ---------------------------------------------------------------- the scene
def build():
    reset()
    make_textures()
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, FRAMES
    T = os.path.join(HERE, "tex")

    # materials
    steel = mat("steel", (0.06, 0.07, 0.07), metal=1.0, rough=0.38)
    steel_lit = mat("steel_lit", (0.25, 0.28, 0.27), metal=1.0, rough=0.3)
    neon = emission("neon", EM["neon"], 14.0)
    neon_soft = emission("neon_soft", EM["neon"], 5.0)
    white_led = emission("led", (0.75, 1.0, 0.9), 9.0)
    letters = mat("letters", (0.9, 0.97, 0.94), metal=0.1, rough=0.25, coat=1.0, emit=(0.8, 1.0, 0.92), emit_k=0.35)
    letters_side = mat("letters_side", (0.02, 0.18, 0.1), metal=0.6, rough=0.3, emit=EM["neon"], emit_k=0.6)
    concrete = bpy.data.materials.new("concrete")
    concrete.use_nodes = True
    nt = concrete.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.03, 0.035, 0.033, 1)
    p.inputs["Metallic"].default_value = 0.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 6
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.45, (0.02, 0.02, 0.02, 1)   # puddles: mirror
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.6, (0.75, 0.75, 0.75, 1)    # dry: rough
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 40
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    brick = image_mat("brick", os.path.join(T, "brick.png"), rough=0.85)
    bill = image_mat("bill", os.path.join(T, "bill.png"), rough=0.55)
    band = image_mat("band", os.path.join(T, "band.png"), rough=0.5)
    atm_screen = image_mat("atm_screen", os.path.join(T, "atm.png"), rough=0.2, emit_k=3.0)
    atm_body = mat("atm_body", (0.02, 0.025, 0.024), metal=0.8, rough=0.3, coat=0.6)
    leather = mat("leather", (0.015, 0.016, 0.016), metal=0.0, rough=0.45, coat=0.5)
    gold = mat("gold", (0.85, 0.62, 0.25), metal=1.0, rough=0.18)
    crown_m = mat("crown", (0.45, 0.95, 0.75), metal=0.9, rough=0.2, coat=1.0, emit=(0.1, 0.8, 0.45), emit_k=0.25)
    pedestal_m = mat("pedestal", (0.01, 0.012, 0.012), metal=0.9, rough=0.2, coat=1.0)
    gem_m = mat("emerald", (0.05, 0.8, 0.4), rough=0.0, transmission=1.0, ior=1.58, coat=1.0, emit=(0.02, 0.7, 0.3), emit_k=0.55)
    # emerald depth: green volume absorption inside the stone
    vol = gem_m.node_tree.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (0.05, 0.75, 0.38, 1)
    vol.inputs["Density"].default_value = 1.8
    gem_m.node_tree.links.new(vol.outputs[0], gem_m.node_tree.nodes["Material Output"].inputs["Volume"])

    # floor + wall
    floor = obj("floor", box_mesh("floor", 60, 60, 0.1), concrete, loc=(0, 4, -0.05))
    wall = obj("wall", box_mesh("wall", 34, 0.5, 9), brick, loc=(0, 11.5, 4.5))
    # wall UVs scaled so bricks keep their size
    for lp in wall.data.uv_layers[0].data:
        lp.uv = (lp.uv[0] * 4, lp.uv[1] * 1.1)

    # scaffolding: poles, rails, diagonals, decks
    xs = [-10.5 + i * 2.1 for i in range(11)]
    ys = (6.0, 7.6)
    levels = (0.0, 2.3, 4.6, 6.9, 9.2)
    for x in xs:
        for y in ys:
            cyl_between("pole", (x, y, 0), (x, y, 9.4), 0.05, steel)
    for z in levels[1:]:
        for y in ys:
            cyl_between("rail", (xs[0], y, z), (xs[-1], y, z), 0.04, steel_lit)
        for x in xs:
            cyl_between("tie", (x, ys[0], z), (x, ys[1], z), 0.035, steel)
        deck = obj("deck", box_mesh("deck", 21.5, 1.6, 0.05), steel, loc=(0, 6.8, z - 0.05))
    for i in range(len(xs) - 1):
        for li in range(len(levels) - 1):
            a, b = (xs[i], ys[0], levels[li]), (xs[i + 1], ys[0], levels[li + 1])
            if (i + li) % 2:
                a, b = (xs[i + 1], ys[0], levels[li]), (xs[i], ys[0], levels[li + 1])
            cyl_between("brace", a, b, 0.03, steel)
    # neon strips along the scaffold levels (the green rim light of the whole scene)
    for z in (2.32, 6.92):
        obj("neon_strip", box_mesh("ns", 21.4, 0.04, 0.04), neon_soft, loc=(0, ys[0] - 0.08, z))
    stairs = obj("stairs", box_mesh("st", 1.4, 0.8, 2.3), steel, loc=(0, 6.8, 8.05))

    # the sign: two lines of extruded letters standing on top of the scaffold
    def sign_text(body, size, z):
        cu = bpy.data.curves.new(body, "FONT")
        cu.body = body
        cu.font = bpy.data.fonts.load(FONT)
        cu.size = size
        cu.extrude = 0.22
        cu.bevel_depth = 0.035
        cu.bevel_resolution = 3
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        cu.space_character = 1.04
        o = bpy.data.objects.new(body, cu)
        sc.collection.objects.link(o)
        o.location = (0, 5.7, z)
        o.rotation_euler = (math.radians(90), 0, 0)
        o.data.materials.append(letters)
        o.data.materials.append(letters_side)
        return o
    sign_text("EMERALD", 2.6, 11.6)
    sign_text("TEAM", 1.6, 9.95)
    # neon tubes behind the letters -> green halo
    obj("sign_rail", box_mesh("sr", 15.6, 0.3, 0.12), steel_lit, loc=(0, 5.85, 9.25))
    obj("sign_led", box_mesh("sl", 15.4, 0.04, 0.04), neon, loc=(0, 5.68, 9.33))

    # ATMs left and right
    def atm(x, rz):
        g = []
        body = obj("atm", box_mesh("atm", 1.1, 0.8, 2.2), atm_body, loc=(x, 2.5, 1.1), rot=(0, 0, rz))
        bevel(body, 0.03)
        hood = obj("atm_hood", box_mesh("hood", 1.15, 0.35, 0.18), atm_body, loc=(0, -0.55, 0.85))
        hood.parent = body
        screen = obj("atm_screen", box_mesh("scr", 0.7, 0.02, 0.52), atm_screen, loc=(0, -0.41, 0.45))
        screen.parent = body
        led = obj("atm_led", box_mesh("led", 1.0, 0.02, 0.03), neon, loc=(0, -0.41, 0.98))
        led.parent = body
        pad = obj("atm_pad", box_mesh("pad", 0.6, 0.25, 0.04), steel_lit, loc=(0, -0.5, -0.05), rot=(math.radians(-25), 0, 0))
        pad.parent = body
        slot = obj("atm_slot", box_mesh("slot", 0.4, 0.02, 0.03), white_led, loc=(0, -0.41, -0.32))
        slot.parent = body
    atm(-5.4, math.radians(28))
    atm(5.4, math.radians(-28))

    # cash: one stack mesh, many linked copies
    stack_me = box_mesh("stack", 0.33, 0.156, 0.12)
    stack_me.materials.append(bill)
    for poly in stack_me.polygons:            # map the bill image onto top and bottom faces
        poly.material_index = 0
    def stack(loc, rz, tilt=(0, 0)):
        o = bpy.data.objects.new("cash", stack_me)
        sc.collection.objects.link(o)
        o.location, o.rotation_euler = loc, (tilt[0], tilt[1], rz)
        return o
    # mountain of cash on a pallet behind the stone
    for i in range(520):
        r = rnd.random() ** 0.6 * 2.6
        a = rnd.random() * math.tau
        x, y = math.cos(a) * r * 1.4, 4.3 + math.sin(a) * r * 0.5
        hgt = max(0.0, 1.9 - r * 0.72) * rnd.uniform(0.75, 1.0)
        stack((x, y, 0.06 + hgt * rnd.random()), rnd.random() * math.tau, (rnd.uniform(-.3, .3), rnd.uniform(-.3, .3)))
    obj("pallet", box_mesh("pal", 5.6, 2.2, 0.12), mat("wood", (0.09, 0.06, 0.035), rough=0.8), loc=(0, 4.3, 0.06))
    # scattered stacks on the floor
    for i in range(70):
        a = rnd.random() * math.tau
        r = 1.6 + rnd.random() * 5.5
        stack((math.cos(a) * r, -1 + math.sin(a) * r * 0.7, 0.06), rnd.random() * math.tau)
    # neat towers next to the pedestal
    for (x, y) in ((-1.6, -0.4), (1.7, -0.2), (1.45, 0.45)):
        for k in range(rnd.randint(5, 9)):
            stack((x + rnd.uniform(-.02, .02), y, 0.06 + k * 0.121), rnd.uniform(-.08, .08))

    # neon briefcase, foreground left
    case = obj("case", box_mesh("case", 1.5, 0.42, 1.05), leather, loc=(-3.3, -2.3, 0.53), rot=(0, 0, math.radians(24)))
    bevel(case, 0.05, 4)
    for z in (0.5, -0.5):
        e = obj("case_neon", box_mesh("cn", 1.56, 0.47, 0.028), neon, loc=(0, 0, z * 1.03))
        e.parent = case
    for x in (-0.3, 0.3):
        cl = obj("clasp", box_mesh("cl", 0.12, 0.46, 0.08), gold, loc=(x, 0, 0.42))
        cl.parent = case
    handle = bpy.data.meshes.new("handle")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, segments=24, radius=0.17)
    bm.to_mesh(handle)
    bm.free()
    ho = obj("handle", handle, leather, loc=(0, 0, 0.6), rot=(math.radians(90), 0, 0))
    ho.parent = case
    sk = ho.modifiers.new("skin", "SKIN")
    for v in ho.data.skin_vertices[0].data:
        v.radius = (0.035, 0.035)

    # pedestal + emerald + crown (the hero)
    ped = bpy.data.meshes.new("ped")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=0.95, radius2=0.85, depth=0.9)
    bm.to_mesh(ped)
    bm.free()
    po = obj("pedestal", ped, pedestal_m, loc=(0, 0.4, 0.45))
    for z in (0.46, -0.44):
        ring = bpy.data.meshes.new("ring")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, segments=96, radius=0.9 if z > 0 else 0.97)
        bm.to_mesh(ring)
        bm.free()
        ro = obj("ped_ring", ring, neon, loc=(0, 0, z))
        ro.parent = po
        m = ro.modifiers.new("skin", "SKIN")
        for v in ro.data.skin_vertices[0].data:
            v.radius = (0.018, 0.018)

    # emerald cut: octagonal girdle, stepped crown and pavilion, convex hull -> flat facets
    def octagon(w, h, ch, z):
        W2, H2 = w / 2, h / 2
        return [(-W2 + ch, H2, z), (W2 - ch, H2, z), (W2, H2 - ch, z), (W2, -H2 + ch, z),
                (W2 - ch, -H2, z), (-W2 + ch, -H2, z), (-W2, -H2 + ch, z), (-W2, H2 - ch, z)]
    pts = []
    for s, z, cs in ((1, 0, 1), (.86, .2, .86), (.66, .33, .6), (.9, -.3, .9), (.62, -.62, .5), (.25, -.86, .15)):
        pts += octagon(1.25 * s, 1.45 * s, 0.34 * cs, z)
    bm = bmesh.new()
    for p_ in pts:
        bm.verts.new(p_)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    gem_me = bpy.data.meshes.new("emerald")
    bm.to_mesh(gem_me)
    bm.free()
    gem = obj("emerald", gem_me, gem_m, loc=(0, 0.4, 1.68), rot=(math.radians(90), 0, 0))
    for poly in gem.data.polygons:
        poly.use_smooth = False
    # inner light so the stone glows from inside
    core = bpy.data.lights.new("gem_core", "POINT")
    core.energy, core.color, core.shadow_soft_size = 25, EM["neon"], 0.35
    co = bpy.data.objects.new("gem_core", core)
    sc.collection.objects.link(co)
    co.location = (0, 1.3, 1.7)

    # crown: band whose top edge rises into five points
    crown_me = bpy.data.meshes.new("crown")
    bm = bmesh.new()
    seg, rows = 160, 6
    R = 0.42
    grid = []
    for j in range(rows + 1):
        ring = []
        for i in range(seg):
            a = i / seg * math.tau
            tri = 1 - abs(((a / math.tau * 5) % 1) * 2 - 1)
            top = 0.16 + 0.34 * tri ** 1.6
            y = j / rows * top
            flare = 1 + 0.14 * (j / rows) * tri
            ring.append(bm.verts.new((math.cos(a) * R * flare, math.sin(a) * R * flare, y)))
        grid.append(ring)
    for j in range(rows):
        for i in range(seg):
            bm.faces.new((grid[j][i], grid[j][(i + 1) % seg], grid[j + 1][(i + 1) % seg], grid[j + 1][i]))
    bm.to_mesh(crown_me)
    bm.free()
    crown = obj("crown", crown_me, crown_m, loc=(0, 0.4, 2.36), rot=(math.radians(-8), 0, 0))
    crown.modifiers.new("solid", "SOLIDIFY").thickness = 0.025
    for poly in crown.data.polygons:
        poly.use_smooth = True
    for i in range(5):
        a = (i + .5) / 5 * math.tau
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.045)
        pm = bpy.data.meshes.new("pearl")
        bm.to_mesh(pm)
        bm.free()
        pe = obj("pearl", pm, mat("pearl", (0.9, 1, 0.95), rough=0.15, coat=1), loc=(math.cos(a) * R * 1.14, math.sin(a) * R * 1.14, 0.52))
        pe.parent = crown

    # falling bills (a few, animated)
    bill_me = box_mesh("bill1", 0.156, 0.066, 0.002)
    bill_me.materials.append(bill)
    flyers = []
    for i in range(26):
        o = bpy.data.objects.new("flybill", bill_me)
        sc.collection.objects.link(o)
        o.scale = (2.2, 2.2, 2.2)
        x, y = rnd.uniform(-6, 6), rnd.uniform(-3, 4)
        z0, z1 = rnd.uniform(6, 13), rnd.uniform(-1, 3)
        ph = rnd.uniform(0, 1)
        for f in range(1, FRAMES + 1, 6):
            p_ = ((f / FRAMES) + ph) % 1
            o.location = (x + 0.6 * math.sin(p_ * 9 + i), y + 0.3 * math.cos(p_ * 7), z0 - (z0 - z1) * ((f / FRAMES * 0.6 + ph * 0.4)))
            o.rotation_euler = (p_ * 7 + i, p_ * 5, p_ * 3 + i)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
        flyers.append(o)

    # ---------------------------------------------------------------- lights
    def area(name, loc, rot, size, color, energy):
        l = bpy.data.lights.new(name, "AREA")
        l.size, l.color, l.energy = size, color, energy
        o = bpy.data.objects.new(name, l)
        sc.collection.objects.link(o)
        o.location, o.rotation_euler = loc, rot
        return o
    def spot(name, loc, target, color, energy, angle=40, blend=0.4):
        l = bpy.data.lights.new(name, "SPOT")
        l.color, l.energy, l.spot_size, l.spot_blend, l.shadow_soft_size = color, energy, math.radians(angle), blend, 0.3
        o = bpy.data.objects.new(name, l)
        sc.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return o
    area("key", (0, -6, 13), (math.radians(35), 0, 0), 10, (0.9, 1.0, 0.97), 2200)          # soft front light on the sign
    area("rimL", (-8, 7, 4), (math.radians(90), 0, math.radians(-120)), 5, EM["neon"], 900) # green rims
    area("rimR", (8, 7, 4), (math.radians(90), 0, math.radians(120)), 5, EM["neon"], 900)
    area("top", (0, 2, 9), (0, 0, 0), 6, (0.3, 1.0, 0.6), 250)
    area("sign_back", (0, 7.0, 11.0), (math.radians(-90), 0, 0), 14, EM["neon"], 2500)     # green light spilling behind the letters
    spot("beamL", (-6, 9, 9.5), (-2, -2, 0), EM["neon"], 2600, 30)                          # god rays through the haze
    spot("beamR", (6, 9, 9.5), (2, -2, 0), EM["neon"], 2600, 30)
    spot("gemkey", (2.5, -4, 5), (0, 0.4, 2), (0.85, 1, 0.95), 350, 18, 0.6)                 # sparkle on the stone
    area("gemcardL", (-1.6, -2.2, 2.6), (math.radians(70), 0, math.radians(-35)), 0.6, (1, 1, 1), 60)   # crisp facet highlights
    area("gemcardR", (1.8, -1.8, 1.2), (math.radians(95), 0, math.radians(40)), 0.5, (0.8, 1, 0.9), 45)
    world = bpy.data.worlds.new("night")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.014, 0.009, 1)
    # volumetric haze in a big box around the set
    haze = obj("haze", box_mesh("haze", 40, 40, 8.5), None, loc=(0, 3, 4.2))
    hm = bpy.data.materials.new("haze")
    hm.use_nodes = True
    hm.node_tree.nodes.clear()
    pv = hm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (0.7, 1.0, 0.85, 1)
    pv.inputs["Density"].default_value = 0.0025
    pv.inputs["Anisotropy"].default_value = 0.35
    mo = hm.node_tree.nodes.new("ShaderNodeOutputMaterial")
    hm.node_tree.links.new(pv.outputs[0], mo.inputs["Volume"])
    haze.data.materials.append(hm)

    # ---------------------------------------------------------------- camera: slow push-in with a little drift
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 30
    cam_d.dof.use_dof = True
    cam_d.dof.aperture_fstop = 2.2
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    target = bpy.data.objects.new("target", None)
    sc.collection.objects.link(target)
    target.location = (0, 0.4, 1.8)
    cam_d.dof.focus_object = target
    look = bpy.data.objects.new("look", None)
    sc.collection.objects.link(look)
    tc = cam.constraints.new("TRACK_TO")
    tc.target, tc.track_axis, tc.up_axis = look, "TRACK_NEGATIVE_Z", "UP_Y"
    for f, (x, y, z), (lx, ly, lz) in ((1, (-1.0, -9.4, 1.7), (0, 2, 4.9)), (FRAMES, (0.8, -7.9, 1.9), (0, 2, 5.1))):
        cam.location = (x, y, z)
        cam.keyframe_insert("location", frame=f)
        look.location = (lx, ly, lz)
        look.keyframe_insert("location", frame=f)

    # ---------------------------------------------------------------- hero animation
    for f, rz in ((1, -0.35), (FRAMES, 0.55)):
        gem.rotation_euler = (math.radians(90), 0, rz)
        gem.keyframe_insert("rotation_euler", frame=f)
    for f, z in ((1, 2.36), (30, 2.4), (40, 2.7), (50, 2.36), (56, 2.4), (62, 2.36), (FRAMES, 2.38)):
        crown.location = (0, 0.4, z)
        crown.keyframe_insert("location", frame=f)
    for f, rz in ((1, 0), (FRAMES, math.radians(72))):
        crown.rotation_euler = (math.radians(-8), 0, rz)
        crown.keyframe_insert("rotation_euler", frame=f)
    # neon flicker on the sign glow
    em = neon.node_tree.nodes["Emission"].inputs["Strength"]
    for f, v in ((1, 14), (70, 14), (71, 3), (73, 14), (75, 4), (77, 14), (FRAMES, 14)):
        em.default_value = v
        em.keyframe_insert("default_value", frame=f)

    # ---------------------------------------------------------------- render settings
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x = r.resolution_y = 1080
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.film_transparent = False
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = 64
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.03
    cy.use_denoising = True
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 8, 2, 4
    cy.transmission_bounces, cy.volume_bounces = 10, 0
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.volume_step_rate = 4.0
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.4
    return sc


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode = argv[0] if argv else "still"
    sc = build()
    os.makedirs(OUT, exist_ok=True)
    if mode == "save":
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "emerald_scene.blend"))
    elif mode == "still":
        f = int(argv[1]) if len(argv) > 1 else 60
        if len(argv) > 2:
            sc.cycles.samples = int(argv[2])
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    elif mode == "anim":
        start = int(argv[1]) if len(argv) > 1 else 1
        end = int(argv[2]) if len(argv) > 2 else FRAMES
        sc.cycles.samples = int(os.environ.get("SAMPLES", 28))
        os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
        for f in range(start, end + 1):
            path = os.path.join(OUT, "frames", f"{f:04d}.png")
            if os.path.exists(path):
                continue                          # resume after an interruption
            sc.frame_set(f)
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print("frame", f, flush=True)


if __name__ == "__main__":
    main()
