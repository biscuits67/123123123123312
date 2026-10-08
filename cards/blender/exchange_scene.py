"""EMERALD EXCHANGE — night street scene for Blender (Cycles).

    python exchange_scene.py -- still 60 [samples]   -> renders/exchange_still_0060.png
    python exchange_scene.py -- anim [start end]     -> renders/exchange/0001.png ...  (then post.py exchange)
    python exchange_scene.py -- save                 -> exchange_scene.blend

A busy night street. A small exchange store with a flickering neon EMERALD sign, a rates board and
cash on the shelves. Behind the counter stands the Emerald agent (Mixamo character), an emerald
levitating over his hand. A G63 and a 911 are parked out front, traffic streaks past, and the wind
blows banknotes off the counter and down the street.
Models live in models/ (not in git): agent/yelling.fbx, g63/source/car.fbx, porsche/porsche.usdz,
money-stacks-20-usd, cash-pile-and-money-stacks.
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emerald_scene import (EM, FONT, HERE, MODELS, mat, emission, image_mat, obj, box_mesh, cyl_between, bevel,
                           import_model, instance, place, reset)

FPS, FRAMES = 24, 120
OUT = os.path.join(HERE, "renders")
TEX = os.path.join(HERE, "tex")
rnd = random.Random(21)
P = lambda *a: os.path.join(MODELS, *a)


# ---------------------------------------------------------------- textures
def textures():
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    os.makedirs(TEX, exist_ok=True)
    f = lambda s: ImageFont.truetype(FONT, s)
    # rates board
    im = Image.new("RGB", (900, 1100), (2, 10, 7))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 900, 150], fill=(6, 40, 28))
    d.text((450, 78), "EMERALD  RATES", font=f(70), fill=(150, 255, 210), anchor="mm")
    d.text((330, 210), "BUY", font=f(46), fill=(110, 200, 165), anchor="mm")
    d.text((680, 210), "SELL", font=f(46), fill=(110, 200, 165), anchor="mm")
    rows = [("USD", "1.000", "1.012"), ("EUR", "1.081", "1.094"), ("USDT", "0.998", "1.009"),
            ("BTC", "64 210", "64 980"), ("TRX", "0.162", "0.168"), ("ETH", "3 120", "3 168")]
    for i, (c, b, s) in enumerate(rows):
        y = 320 + i * 125
        d.rectangle([30, y - 52, 870, y + 52], outline=(10, 70, 48), width=3)
        d.text((60, y), c, font=f(58), fill=(234, 255, 246), anchor="lm")
        d.text((330, y), b, font=f(56), fill=(60, 255, 170), anchor="mm")
        d.text((680, y), s, font=f(56), fill=(255, 210, 120), anchor="mm")
    im.filter(ImageFilter.GaussianBlur(0.8)).save(os.path.join(TEX, "rates.png"))
    # facade windows of the upper floors (some lit)
    w = Image.new("RGB", (1024, 1024), (8, 10, 10))
    d = ImageDraw.Draw(w)
    for r in range(4):
        for c in range(6):
            x, y = 40 + c * 165, 40 + r * 250
            lit = rnd.random()
            col = (255, 196, 120) if lit < .25 else (120, 255, 200) if lit < .38 else (14, 18, 18)
            d.rectangle([x, y, x + 120, y + 180], fill=col)
            d.rectangle([x, y, x + 120, y + 180], outline=(30, 34, 34), width=8)
            if lit < .38:
                d.rectangle([x + 10, y + 120, x + 110, y + 172], fill=tuple(int(v * .6) for v in col))
    w.save(os.path.join(TEX, "windows.png"))
    # road: asphalt with lane dashes
    r = Image.new("RGB", (512, 2048), (24, 26, 26))
    d = ImageDraw.Draw(r)
    for i in range(30000):
        g = rnd.randint(14, 40)
        d.point((rnd.randrange(512), rnd.randrange(2048)), fill=(g, g, g))
    for y in range(0, 2048, 256):
        d.rectangle([250, y, 262, y + 140], fill=(46, 47, 44))
    r.filter(ImageFilter.GaussianBlur(0.7)).save(os.path.join(TEX, "road.png"))
    # dark tiles for the store interior
    t = Image.new("RGB", (512, 512), (14, 15, 16))
    d = ImageDraw.Draw(t)
    for y in range(0, 512, 64):
        for x in range(0, 512, 128):
            g = rnd.randint(-6, 6)
            d.rectangle([x + 3, y + 3, x + 125, y + 61], fill=(26 + g, 27 + g, 29 + g))
    t.save(os.path.join(TEX, "tiles.png"))


def wet_asphalt(name, img, scale_uv=1.0):
    m = image_mat(name, img, rough=0.5)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 0.35
    n.inputs["Detail"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.52, (0.02, 0.02, 0.02, 1)  # puddles
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.6, (0.72, 0.72, 0.72, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Roughness"])
    return m


def neon_text(body, size, loc, material, tube=0.022, rot=(math.radians(90), 0, 0), align="CENTER"):
    """Real neon: tubes running along the letter outlines (no fill)."""
    cu = bpy.data.curves.new(body, "FONT")
    cu.body, cu.font, cu.size = body, bpy.data.fonts.load(FONT), size
    cu.fill_mode = "NONE"
    cu.bevel_depth, cu.bevel_resolution = tube, 3
    cu.align_x, cu.align_y = align, "CENTER"
    cu.space_character = 1.06
    o = bpy.data.objects.new(body, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location, o.rotation_euler = loc, rot
    o.data.materials.append(material)
    return o


def solid_text(body, size, loc, materials, extrude=0.04, rot=(math.radians(90), 0, 0), bevel=0.008,
               font=FONT, spacing=1.25):
    cu = bpy.data.curves.new(body, "FONT")
    cu.body, cu.font, cu.size = body, bpy.data.fonts.load(font, check_existing=True), size
    cu.extrude, cu.bevel_depth, cu.bevel_resolution = extrude, bevel, 2
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.space_character = spacing
    o = bpy.data.objects.new(body, cu)
    bpy.context.scene.collection.objects.link(o)
    o.location, o.rotation_euler = loc, rot
    for m in materials:
        o.data.materials.append(m)
    return o


def light(kind, name, loc, color, energy, size=0.5, target=None, rot=None, spot=40):
    l = bpy.data.lights.new(name, kind)
    l.color, l.energy = color, energy
    if kind == "AREA":
        l.size = size
    elif kind == "SPOT":
        l.spot_size, l.spot_blend, l.shadow_soft_size = math.radians(spot), 0.5, size
    else:
        l.shadow_soft_size = size
    o = bpy.data.objects.new(name, l)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    if kind == "AREA":
        o.visible_glossy = False          # studio panels must not show up as white slabs in the wet ground
    if target is not None:
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    elif rot is not None:
        o.rotation_euler = rot
    return o


def flicker(socket, frames_off, on, off, light_obj=None, light_on=0, light_off=0):
    """Constant-interpolated on/off pattern for an emission strength (and a matching light)."""
    def setkey(f, v, lv):
        socket.default_value = v
        socket.keyframe_insert("default_value", frame=f)
        if light_obj:
            light_obj.data.energy = lv
            light_obj.data.keyframe_insert("energy", frame=f)
    setkey(1, on, light_on)
    for a, b in frames_off:
        setkey(a, off, light_off)
        setkey(b, on, light_on)
    for owner in (socket.id_data, light_obj.data if light_obj else None):
        ad = owner.animation_data if owner else None
        if ad and ad.action:
            for layer in getattr(ad.action, "layers", []):
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for fc in bag.fcurves:
                            for k in fc.keyframe_points:
                                k.interpolation = "CONSTANT"
            for fc in getattr(ad.action, "fcurves", []):
                for k in fc.keyframe_points:
                    k.interpolation = "CONSTANT"


def facing_plane(name, w, h):
    """Vertical plane facing -y with an upright UV (for images that must read correctly)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for lp, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        lp.uv = co
    return me



def rigged_agent(loc, rz, style="counter", tilt=0.0, phase=0.0):
    """Hazmat suit + a hand-built 17-bone skeleton. Weights come from distance to the bone segments
    (smooth falloff, three strongest bones per vertex). The rest pose has the arms out to the sides;
    the animation lowers them: left hand on the counter, right hand palm-up holding the emerald."""
    import numpy as np
    from mathutils import Matrix, Quaternion
    root, meshes, size = import_model(P("hazmat-suit", "source", "hazmat suit model unrigged.fbx"))
    body = meshes[0]
    white = monogram_suit() if style != "counter" else mat("suit_black", (0.012, 0.013, 0.014), rough=0.45, coat=0.2)
    glove_w = mat("glove_white", (0.85, 0.87, 0.86), rough=0.4, coat=0.3)
    white.node_tree.nodes["Principled BSDF"].inputs["Sheen Weight"].default_value = 0.4
    visor = mat("visor", (0.01, 0.05, 0.03), metal=0.3, rough=0.03, coat=1.0, emit=EM["neon"], emit_k=2.5)
    rubber = mat("rubber", (0.01, 0.01, 0.01), rough=0.3, coat=0.8)
    trim = mat("trim", (0.05, 0.06, 0.06), metal=1.0, rough=0.3)
    for i, m in enumerate(body.data.materials):
        n = (m.name if m else "").lower()
        body.data.materials[i] = visor if n == "faceplate" else trim if "trim" in n else glove_w if "glove" in n else rubber if "boot" in n else white
    # bake the import transform into the mesh so it sits at the origin, facing +x
    bpy.context.view_layer.update()
    mw = body.matrix_world.copy()
    body.parent = None
    body.data.transform(mw)
    body.matrix_world = Matrix.Identity(4)
    vs = np.array([v.co[:] for v in body.data.vertices])
    off = np.array([(vs[:, 0].min() + vs[:, 0].max()) / 2, (vs[:, 1].min() + vs[:, 1].max()) / 2, vs[:, 2].min()])
    body.data.transform(Matrix.Translation(Vector(-off)))
    vs = vs - off
    B = {   # name: (head, tail, parent) in model space, facing +x, arms along y
        "hips": ((0, 0, 0.92), (0, 0, 1.08), None), "spine": ((0, 0, 1.08), (0, 0, 1.28), "hips"),
        "chest": ((0, 0, 1.28), (0, 0, 1.47), "spine"), "neck": ((0, 0, 1.47), (0, 0, 1.62), "chest"),
        "head": ((0, 0, 1.62), (0, 0, 1.885), "neck"),
        "shoulder.L": ((0, -0.06, 1.44), (0, -0.2, 1.45), "chest"), "upper.L": ((0, -0.2, 1.45), (0.05, -0.45, 1.5), "shoulder.L"),
        "fore.L": ((0.05, -0.45, 1.5), (0.16, -0.66, 1.55), "upper.L"), "hand.L": ((0.16, -0.66, 1.55), (0.2, -0.75, 1.57), "fore.L"),
        "shoulder.R": ((0, 0.06, 1.43), (0, 0.2, 1.43), "chest"), "upper.R": ((0, 0.2, 1.43), (0.05, 0.45, 1.42), "shoulder.R"),
        "fore.R": ((0.05, 0.45, 1.42), (0.16, 0.66, 1.41), "upper.R"), "hand.R": ((0.16, 0.66, 1.41), (0.21, 0.75, 1.41), "fore.R"),
        "thigh.L": ((0, -0.1, 0.92), (0, -0.25, 0.5), "hips"), "shin.L": ((0, -0.25, 0.5), (0, -0.34, 0.08), "thigh.L"),
        "thigh.R": ((0, 0.1, 0.92), (0, 0.26, 0.5), "hips"), "shin.R": ((0, 0.26, 0.5), (0, 0.36, 0.08), "thigh.R"),
    }
    ad = bpy.data.armatures.new("agent_rig")
    arm = bpy.data.objects.new("agent_rig", ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for n, (h, t, par) in B.items():
        eb = ad.edit_bones.new(n)
        eb.head, eb.tail = h, t
    for n, (h, t, par) in B.items():
        if par:
            ad.edit_bones[n].parent = ad.edit_bones[par]
            ad.edit_bones[n].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    # weights: distance to each bone segment, sharp falloff, top 3
    names = list(B)
    d = np.zeros((len(vs), len(names)))
    for k, n in enumerate(names):
        a, b = np.array(B[n][0]), np.array(B[n][1])
        ab = b - a
        t = np.clip(((vs - a) @ ab) / (ab @ ab), 0, 1)
        d[:, k] = np.linalg.norm(vs - (a + t[:, None] * ab), axis=1)
    w = 1.0 / (d + 0.01) ** 6
    # keep the torso rigid when the arms move: arm bones only drive vertices outside the chest
    ay = np.abs(vs[:, 1])
    for k, n in enumerate(names):
        if n.startswith(("upper.", "fore.", "hand.")):
            w[:, k] *= np.clip((ay - 0.2) / 0.06, 0, 1)
        elif n.startswith("shoulder."):
            w[:, k] *= np.clip((ay - 0.12) / 0.05, 0, 1)
    keep = np.argsort(-w, axis=1)[:, :3]
    mask = np.zeros_like(w, dtype=bool)
    np.put_along_axis(mask, keep, True, axis=1)
    w = np.where(mask, w, 0)
    w /= w.sum(1, keepdims=True)
    for k, n in enumerate(names):
        g = body.vertex_groups.new(name=n)
        idx = np.nonzero(w[:, k] > 0.01)[0]
        for vi in idx:
            g.add([int(vi)], float(w[vi, k]), "REPLACE")
    body.parent = arm
    mod = body.modifiers.new("rig", "ARMATURE")
    mod.object = arm
    # place the rig in the scene
    arm.location, arm.rotation_euler = loc, (0, tilt, rz)
    bpy.data.objects.remove(root)

    # ---- pose helpers (armature space)
    pb = arm.pose.bones
    rest = {n: ad.bones[n].matrix_local.to_quaternion() for n in names}
    def aim(n, target_dir, parent_q=Quaternion()):
        v_rest = (ad.bones[n].tail_local - ad.bones[n].head_local).normalized()
        cur = parent_q @ v_rest
        q = cur.rotation_difference(Vector(target_dir).normalized())
        total = q @ parent_q
        local = rest[n].inverted() @ parent_q.inverted() @ q @ parent_q @ rest[n]
        pb[n].rotation_mode = "QUATERNION"
        pb[n].rotation_quaternion = local
        return total
    def twist(n, axis_arm, angle):
        local = rest[n].inverted() @ Quaternion(axis_arm, angle) @ rest[n]
        pb[n].rotation_mode = "QUATERNION"
        pb[n].rotation_quaternion = local
    for f in range(1, FRAMES + 1, 2):
        u = f / FRAMES * math.tau + phase * math.tau
        breathe = math.sin(u * 2)
        if style == "counter":
            twist("spine", (0, 1, 0), 0.04 + 0.015 * breathe)            # lean slightly over the counter
            twist("chest", (0, 0, 1), 0.06 * math.sin(u))                  # shoulders sway
            twist("head", (0, 0, 1), 0.22 * math.sin(u + 0.6))             # looks around the street
            lift = 0.04 * math.sin(u * 2 + 1)
            # right arm: forearm forward, palm up in front of the chest -> holds the emerald
            qs = aim("shoulder.R", (0.05, 1, -0.12))
            qu = aim("upper.R", (0.35, 0.45, -0.82), qs)
            qf = aim("fore.R", (1.0, -0.15, 0.32 + lift), qu)
            aim("hand.R", (1.0, -0.1, 0.12), qf)
            # left arm: hand resting on the counter
            qs = aim("shoulder.L", (0.05, -1, -0.12))
            qu = aim("upper.L", (0.3, -0.42, -0.86), qs)
            qf = aim("fore.L", (1.0, 0.25, -0.1 + 0.02 * breathe), qu)
            aim("hand.L", (1.0, 0.3, -0.25), qf)
        else:
            # leaning back on the car, right sole pressed against the door
            aim("thigh.L", (0.04, -0.12, -1.0))
            qt = aim("shin.L", (-0.02, -0.06, -1.0), aim("thigh.L", (0.04, -0.12, -1.0)))
            qt = aim("thigh.R", (0.5, 0.12, -0.86))
            aim("shin.R", (-0.62, 0.05, -0.78), qt)
            twist("chest", (0, 0, 1), 0.05 * math.sin(u))
            if style == "count":
                # head down at the money, left hand holds the stack, right thumb flicks the bills
                twist("head", (0, 1, 0), 0.32 + 0.03 * breathe)
                qs = aim("shoulder.L", (0.05, -1, -0.15))
                qu = aim("upper.L", (0.28, -0.3, -0.91), qs)
                qf = aim("fore.L", (0.82, 0.48, 0.32), qu)
                aim("hand.L", (0.9, 0.42, 0.1), qf)
                flick = math.sin(f / 4.0) * 0.16                            # quick counting motion
                qs = aim("shoulder.R", (0.05, 1, -0.15))
                qu = aim("upper.R", (0.25, 0.32, -0.91), qs)
                qf = aim("fore.R", (0.8, -0.42, 0.38 + flick), qu)
                aim("hand.R", (0.8, -0.5, 0.2 + flick), qf)
            else:  # catch
                # looks up and snatches the bills flying past; left hand holds the ones already caught
                twist("head", (0, 1, 0), -0.38 + 0.08 * math.sin(u * 2))
                twist("head", (0, 0, 1), 0.0)
                reach = math.sin(u * 2)
                qs = aim("shoulder.R", (0.0, 1, 0.2))
                qu = aim("upper.R", (0.22 + 0.12 * reach, 0.42, 0.88), qs)
                qf = aim("fore.R", (0.3 + 0.2 * reach, 0.1 - 0.15 * reach, 0.95), qu)
                aim("hand.R", (0.25, 0.0, 1.0), qf)
                qs = aim("shoulder.L", (0.05, -1, -0.15))
                qu = aim("upper.L", (0.2, -0.32, -0.93), qs)
                qf = aim("fore.L", (0.92, 0.25, 0.12), qu)
                aim("hand.L", (0.95, 0.2, -0.05), qf)
        for n in names:
            if pb[n].rotation_mode == "QUATERNION":
                pb[n].keyframe_insert("rotation_quaternion", frame=f)
    return arm, "hand.R"


def monogram_suit():
    """Luxury monogram canvas (beige/brown, interlocking E-E diamonds) mapped by box projection."""
    path = os.path.join(TEX, "monogram.png")
    if not os.path.exists(path):
        from PIL import Image, ImageDraw, ImageFont
        S = 512
        im = Image.new("RGB", (S, S), (6, 52, 32))
        d = ImageDraw.Draw(im)
        for y in range(0, S, 2):                                   # canvas weave
            d.line([(0, y), (S, y)], fill=(8, 58, 36) if (y // 2) % 2 else (5, 46, 28))
        f = ImageFont.truetype(FONT, 92)
        for cy in (S // 4, 3 * S // 4):
            for cx in (S // 4, 3 * S // 4):
                ox = 0 if cy == S // 4 else S // 4
                x = (cx + ox) % S
                for dx in (0, -S, S):
                    d.text((x + dx - 22, cy), "E", font=f, fill=(150, 214, 170), anchor="mm")
                    d.text((x + dx + 22, cy), "\u018e", font=f, fill=(150, 214, 170), anchor="mm")   # mirrored E
                    d.regular_polygon((x + dx, cy, 120), 4, rotation=45, outline=(60, 140, 96), width=3)
        im.save(path)
    m = bpy.data.materials.new("monogram_suit")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (11, 11, 11)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    tex.projection, tex.projection_blend = "BOX", 0.3
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.55
    p.inputs["Sheen Weight"].default_value = 0.5
    return m


def lean_spot(car_center, cam, back=0.32):
    """Point just in front of the car's side surface, seen from the camera (ray cast)."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    origin = Vector((cam[0], cam[1], 0.7))
    target = Vector((car_center[0], car_center[1], 0.7))
    hit, loc, *_ = sc.ray_cast(dg, origin, (target - origin).normalized())
    if not hit:
        loc = target
    toward = (origin - loc)
    toward.z = 0
    toward.normalize()
    p = loc + toward * back
    return (p.x, p.y, 0.0), math.atan2(toward.y, toward.x)

# ---------------------------------------------------------------- scene
def build():
    reset()
    textures()
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, FRAMES

    # materials
    concrete = mat("facade", (0.035, 0.035, 0.036), rough=0.6)
    dark_metal = mat("dark_metal", (0.02, 0.022, 0.022), metal=1.0, rough=0.35)
    steel = mat("steel", (0.3, 0.33, 0.32), metal=1.0, rough=0.25)
    marble = mat("counter", (0.01, 0.012, 0.012), rough=0.08, coat=1.0)
    neon = emission("sign_face", (0.05, 1.0, 0.45), 2.4)
    neon_led = emission("led", (1.0, 0.86, 0.7), 5.0)          # warm white strips: the store stays neutral
    white_box = emission("lightbox", (0.92, 1.0, 0.96), 6.0)
    warm = emission("warm", (1.0, 0.72, 0.45), 12.0)
    tiles = image_mat("tiles", os.path.join(TEX, "tiles.png"), rough=0.25)
    rates = image_mat("rates", os.path.join(TEX, "rates.png"), rough=0.2, emit_k=2.4)
    windows = image_mat("windows", os.path.join(TEX, "windows.png"), rough=0.3, emit_k=0.28)
    road = wet_asphalt("road", os.path.join(TEX, "road.png"))
    sidewalk = mat("sidewalk", (0.05, 0.05, 0.048), rough=0.35)
    bill = image_mat("bill", os.path.join(TEX, "bill.png"), rough=0.55)
    glass = mat("glass", (0.8, 0.95, 0.9), rough=0.02, transmission=1.0, ior=1.5)

    # ground: road (camera side) + kerb + sidewalk
    rd = obj("road", box_mesh("road", 80, 14, 0.1), road, loc=(0, -9.0, -0.05))
    for lp in rd.data.uv_layers[0].data:          # dashes run along x
        lp.uv = (lp.uv[1] * 1.0, lp.uv[0] * 10)
    obj("kerb", box_mesh("kerb", 80, 0.25, 0.16), mat("kerb", (0.12, 0.12, 0.115), rough=0.6), loc=(0, -2.0, 0.08))
    obj("sidewalk", box_mesh("sw", 80, 2.0, 0.15), sidewalk, loc=(0, -1.0, 0.075))

    # ---- the store: facade with a service window, interior, counter
    FX0, FX1 = -2.3, 2.3                    # window opening
    Z0, Z1 = 0.95, 2.95
    obj("pillarL", box_mesh("pl", 1.6, 0.5, 3.3), concrete, loc=(FX0 - 0.8, 0.25, 1.65))
    obj("pillarR", box_mesh("pr", 1.6, 0.5, 3.3), concrete, loc=(FX1 + 0.8, 0.25, 1.65))
    obj("under", box_mesh("un", FX1 - FX0, 0.5, Z0), dark_metal, loc=(0, 0.25, Z0 / 2))
    obj("lintel", box_mesh("li", FX1 - FX0, 0.5, 0.35), concrete, loc=(0, 0.25, Z1 + 0.175))
    # sign band + neon
    band = obj("signband", box_mesh("sb", 7.6, 0.4, 1.25), mat("signbox", (0.006, 0.006, 0.007), metal=0.5, rough=0.5, coat=0.2), loc=(0, 0.05, 3.95))
    bevel(band, 0.03)
    # channel letters in the brand typeface (Inter Display Bold, wide tracking like the logo on the cards):
    # dark metal returns, glowing emerald faces, and a soft halo washing the sign band behind them
    BRAND = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
    letter_metal = mat("letter_metal", (0.02, 0.022, 0.022), metal=1.0, rough=0.3)
    solid_text("EMERALD", 0.8, (0, -0.2, 4.12), [letter_metal], extrude=0.05, bevel=0.004, font=BRAND, spacing=1.32)
    solid_text("EMERALD", 0.8, (0, -0.257, 4.12), [neon], extrude=0.0, bevel=0.0, font=BRAND, spacing=1.32)
    halo = solid_text("EMERALD", 0.8, (0, -0.145, 4.12), [emission("halo", EM["neon"], 2.0)], extrude=0.0, bevel=0.0,
                      font=BRAND, spacing=1.32)
    halo.scale = (1.03, 1.03, 1.03)
    exch = solid_text("EXCHANGE", 0.24, (0, -0.2, 3.52), [white_box], bevel=0.0, font=BRAND, spacing=1.9)
    obj("sign_led", box_mesh("sl", 7.5, 0.03, 0.03), neon_led, loc=(0, -0.16, 3.33))
    # upper floors of the building
    # standalone pavilion: flat roof over the store, the city stands behind it
    obj("roof", box_mesh("roof", 8.0, 3.9, 0.25), concrete, loc=(0, 1.7, 4.7))
    obj("roof_led", box_mesh("rl", 8.2, 0.03, 0.03), neon_led, loc=(0, -0.22, 4.58))
    # rolling shutter, half up
    for i in range(10):
        cyl_between("shutter", (FX0, 0.05, Z1 - 0.04 - i * 0.045), (FX1, 0.05, Z1 - 0.04 - i * 0.045), 0.024, steel, 6)
    # rates board on the left pillar
    obj("rates", facing_plane("rt", 1.15, 1.42), rates, loc=(FX0 - 0.8, -0.035, 1.75))
    obj("rates_frame", box_mesh("rf", 1.25, 0.06, 1.52), dark_metal, loc=(FX0 - 0.8, 0.0, 1.75))
    # counter
    ctr = obj("counter", box_mesh("ct", FX1 - FX0 + 0.3, 0.9, 0.08), marble, loc=(0, -0.05, Z0 + 0.04))
    bevel(ctr, 0.015)
    obj("counter_led", box_mesh("cl", FX1 - FX0 + 0.3, 0.02, 0.02), neon_led, loc=(0, -0.5, Z0 - 0.01))
    # interior box
    obj("int_back", box_mesh("ib", 6.0, 0.2, 3.4), tiles, loc=(0, 3.4, 1.7))
    obj("int_l", box_mesh("il", 0.2, 3.4, 3.4), tiles, loc=(-3.0, 1.7, 1.7))
    obj("int_r", box_mesh("ir", 0.2, 3.4, 3.4), tiles, loc=(3.0, 1.7, 1.7))
    obj("int_floor", box_mesh("if", 6.0, 3.4, 0.1), marble, loc=(0, 1.7, 0.0))
    obj("int_ceil", box_mesh("ic", 6.0, 3.4, 0.1), concrete, loc=(0, 1.7, 3.35))
    for x in (-1.6, 0, 1.6):
        obj("ceil_panel", box_mesh("cp", 1.1, 0.5, 0.02), emission("panel", (1.0, 0.92, 0.82), 9.0), loc=(x, 1.8, 3.28))
    # shelves with cash on the back wall
    for z in (1.45, 2.15):
        obj("shelf", box_mesh("sh", 5.4, 0.45, 0.04), dark_metal, loc=(0, 3.05, z))
        obj("shelf_led", box_mesh("shl", 5.4, 0.02, 0.015), neon_led, loc=(0, 2.83, z - 0.03))
    stacks, meshes, size = import_model(P("money-stacks-20-usd", "source", "Money stackssss.glb"))
    place(stacks, size, 0.42, (-1.3, 3.05, 1.47))
    place(instance(stacks, "stacks2"), size, 0.42, (1.4, 3.05, 1.47), math.radians(180))
    place(instance(stacks, "stacks3"), size, 0.42, (0.2, 3.05, 2.17), math.radians(10))
    pile, pm, psize = import_model(P("cash-pile-and-money-stacks", "source", "inner", "cashpile 4.fbx"))
    place(pile, psize, 0.16, (1.25, -0.1, Z0 + 0.08), math.radians(30))       # cash on the counter
    place(instance(pile, "pile2"), psize, 0.2, (-4.2, -1.3, 0.15), math.radians(-20))  # blown onto the sidewalk

    # neighbouring shop fronts: darker, other signs, to make the street feel alive
    # the city block (downloaded model) behind the pavilion
    city, cmeshes, csize = import_model(P("city", "source", "\u0443\u043b\u0438\u0446\u0430 \u0441\u043a\u0435\u0442\u0447.fbx"))
    for im in bpy.data.images:                    # textures sit next to the fbx
        if not im.has_data and im.filepath:
            cand = P("city", "textures", os.path.basename(im.filepath))
            if os.path.exists(cand):
                im.filepath = cand
    place(city, csize, 70, (-4, 112, 0), 0.0)
    bpy.context.view_layer.update()
    for o in cmeshes:                             # drop the model's own ground: our wet street is the ground
        d = o.dimensions
        if d.z < 0.3 * max(d.x, d.y) * 0.1 or (d.z < 1.0 and max(d.x, d.y) > 4):
            o.hide_render = True
    for o in cmeshes:                             # night: photo facades glow faintly, as if lit by the city
        for m in o.data.materials:
            if not m or not m.use_nodes:
                continue
            nt = m.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
            if bsdf and tex:
                nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
                bsdf.inputs["Emission Strength"].default_value = 0.07
                bsdf.inputs["Roughness"].default_value = 0.8

    # street lamps
    for x in (-6.3, 6.3):
        cyl_between("lamp_pole", (x, -1.7, 0.15), (x, -1.7, 5.2), 0.06, dark_metal, 12)
        cyl_between("lamp_arm", (x, -1.7, 5.2), (x, -2.6, 5.35), 0.04, dark_metal, 8)
        obj("lamp_head", box_mesh("lh", 0.5, 0.25, 0.08), warm, loc=(x, -2.75, 5.32)).visible_glossy = False
        light("SPOT", "lamp", (x, -2.75, 5.25), (1.0, 0.75, 0.5), 900, size=0.25, target=(x, -3.5, 0), spot=75)

    # ---- the agent: hazmat suit with a hand-built skeleton, posed behind the counter
    arm, hand_bone = rigged_agent((0, 0.95, 0), math.radians(-90))

    # ---- levitating emerald over the agent's right hand
    pts = []
    def octa(w, h, ch, z):
        W2, H2 = w / 2, h / 2
        return [(-W2 + ch, H2, z), (W2 - ch, H2, z), (W2, H2 - ch, z), (W2, -H2 + ch, z),
                (W2 - ch, -H2, z), (-W2 + ch, -H2, z), (-W2, -H2 + ch, z), (-W2, H2 - ch, z)]
    # brilliant cut (the 💎 silhouette): flat table, crown, girdle and a pointed pavilion
    def ring(r, z, n=16, rot=0.0):
        return [(r * math.cos(rot + k / n * math.tau), r * math.sin(rot + k / n * math.tau), z) for k in range(n)]
    pts = ring(0.55, 0.42, 8, math.pi / 8) + ring(0.82, 0.3, 8) + ring(1.0, 0.1, 16, math.pi / 16) + ring(1.0, 0.04, 16, math.pi / 16) \
        + ring(0.55, -0.55, 8, math.pi / 8) + [(0, 0, -1.05)]
    bm = bmesh.new()
    for p_ in pts:
        bm.verts.new(p_)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    gme = bpy.data.meshes.new("gem")
    bm.to_mesh(gme)
    bm.free()
    gem_m = mat("emerald", (0.02, 0.55, 0.24), rough=0.0, transmission=0.6, ior=2.0, coat=1.0, emit=(0.0, 0.45, 0.17), emit_k=0.3)
    gem = obj("gem", gme, gem_m, scale=(0.13, 0.13, 0.13))
    c = gem.constraints.new("COPY_LOCATION")
    c.target, c.subtarget, c.use_offset = arm, hand_bone, True
    for f in range(1, FRAMES + 1, 4):
        gem.location = (0, -0.16, 0.24 + 0.035 * math.sin(f / FRAMES * math.tau * 2))
        gem.rotation_euler = (math.radians(-18) + 0.12 * math.sin(f / 20), 0, f / FRAMES * math.tau * 1.2)
        gem.keyframe_insert("location", frame=f)
        gem.keyframe_insert("rotation_euler", frame=f)
    glow = light("POINT", "gem_glow", (0, 0, 0), EM["neon"], 4, size=0.05)
    # crisp highlights on the facets + a levitation ring and sparks under the stone
    light("SPOT", "gem_spark", (1.0, -1.6, 2.4), (1, 1, 1), 14, size=0.05, target=(0.3, 0.6, 1.45), spot=6)
    ring_me = bpy.data.meshes.new("lev_ring")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, segments=64, radius=0.11)
    bm.to_mesh(ring_me)
    bm.free()
    ring = obj("lev_ring", ring_me, emission("lev_ring", EM["neon"], 9.0))
    ring.modifiers.new("skin", "SKIN")
    for v in ring.data.skin_vertices[0].data:
        v.radius = (0.006, 0.006)
    rc = ring.constraints.new("COPY_LOCATION")
    rc.target, rc.subtarget, rc.use_offset = arm, hand_bone, True
    for f in range(1, FRAMES + 1, 4):
        k = 1 + 0.25 * math.sin(f / FRAMES * math.tau * 3)
        ring.location, ring.scale = (0, -0.16, 0.07), (k, k, k)
        ring.keyframe_insert("location", frame=f)
        ring.keyframe_insert("scale", frame=f)
    for n in range(10):                                 # sparks orbiting the stone
        sp = obj("spark", box_mesh("sp", 0.012, 0.012, 0.012), emission("spark", (0.7, 1.0, 0.85), 30))
        spc = sp.constraints.new("COPY_LOCATION")
        spc.target, spc.subtarget, spc.use_offset = arm, hand_bone, True
        r0, ph = 0.13 + 0.05 * (n % 3), n / 10
        for f in range(1, FRAMES + 1, 3):
            a = math.tau * (ph + f / FRAMES * (1.5 + 0.3 * (n % 2)))
            sp.location = (math.cos(a) * r0, -0.16 + math.sin(a) * r0, 0.12 + 0.12 * ((f / FRAMES * 2 + ph) % 1))
            sp.keyframe_insert("location", frame=f)
    gc = glow.constraints.new("COPY_LOCATION")            # under the stone: lights the palm, not the gem
    gc.target, gc.subtarget, gc.use_offset = arm, hand_bone, True
    glow.location = (0, -0.16, 0.04)

    # ---- cars
    g63, gmeshes, gsize = import_model(P("g63", "source", "car.fbx"))
    paint = mat("g63_paint", (0.004, 0.13, 0.065), metal=0.7, rough=0.3, coat=0.8)        # deep emerald metallic
    chrome = mat("chrome", (0.9, 0.9, 0.9), metal=1.0, rough=0.06)
    tire = mat("tire", (0.012, 0.012, 0.012), rough=0.75)
    lamp = emission("headlamp", (0.9, 0.97, 1.0), 5)
    tail = emission("taillamp", (1.0, 0.05, 0.04), 12)
    tint = mat("tint", (0.02, 0.025, 0.025), rough=0.02, coat=1.0)
    black_plastic = mat("g63_trim", (0.012, 0.013, 0.013), rough=0.45, coat=0.2)
    wheel_metal = mat("g63_wheel", (0.03, 0.032, 0.033), metal=1.0, rough=0.25)
    signal = emission("g63_signal", (1.0, 0.45, 0.05), 3)
    car_glass_g = mat("g63_glass", (0.04, 0.05, 0.05), rough=0.0, transmission=1.0, ior=1.5, coat=1.0)
    def g63_material(n):
        n = n.lower()
        if "bodypaint" in n or "carpaint" in n:
            return paint                                              # only the real body panels get the emerald paint
        if "glass" in n or "win30" in n or "extwindows" in n or ("window" in n and "plastic" not in n):
            return car_glass_g
        if any(k in n for k in ("headlight", "lightled", "lights_lod0", "nlightsf", "highbeam", "foglight", "lightemissive", "lamp_alpha", "license_light")):
            return lamp
        if "taillight" in n or "chmsl" in n:
            return tail
        if "signal" in n:
            return signal
        if any(k in n for k in ("silver", "alum", "exhaust", "chrom", "wheels_secondcolor", "hood_logo", "side_logo", "setlogo")):
            return chrome
        if "wheels_color" in n:
            return wheel_metal
        if "tire" in n or "tyre" in n:
            return tire
        return black_plastic
    for o in gmeshes:
        for i, m in enumerate(o.data.materials):
            o.data.materials[i] = g63_material(m.name if m else "")
    place(g63, gsize, 1.95, (-2.7, -3.0, 0), math.radians(58))
    light("SPOT", "g63_head", (-1.9, -4.7, 0.9), (0.9, 0.97, 1.0), 500, size=0.15, target=(4, -6.5, 0), spot=50)
    porsche, pmeshes, psize2 = import_model(P("porsche", "porsche.usdz"))
    invisible = bpy.data.materials.new("invisible")
    invisible.use_nodes = True
    _nt = invisible.node_tree
    _nt.nodes.clear()
    _tr = _nt.nodes.new("ShaderNodeBsdfTransparent")
    _nt.links.new(_tr.outputs[0], _nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    car_glass = mat("car_glass", (0.05, 0.06, 0.06), rough=0.0, transmission=1.0, ior=1.5, coat=1.0)
    em_paint = mat("911_paint", (0.0, 0.36, 0.16), metal=0.75, rough=0.26, coat=0.7)        # bright emerald metallic
    for o in pmeshes:
        for i, m in enumerate(o.data.materials):
            if m and m.name == "body_main":
                o.data.materials[i] = em_paint
            if m and m.name in ("lights", "headlights_pattern"):
                o.data.materials[i] = lamp
            if m and m.name == "red_light_main":
                o.data.materials[i] = tail
            if m and m.name == "invisible_all":           # helper geometry of the model: hide it
                o.data.materials[i] = invisible
            if m and m.name in ("windows", "windows_dots"):   # imported glass comes in opaque -> real tinted glass
                o.data.materials[i] = car_glass
    place(porsche, psize2, 1.31, (3.3, -4.2, 0), math.radians(-136))
    light("SPOT", "911_head", (2.3, -6.2, 0.7), (0.9, 0.97, 1.0), 400, size=0.12, target=(-1, -11, 0), spot=55)

    # ---- two agents in monogram suits: one counts cash leaning on the 911, the other catches flying bills at the G63
    bpy.context.view_layer.update()
    CAM = (2.0, -11.0)
    for car_c, style, ph, side in (((3.3, -4.2), "count", 0.0, -0.2), ((-2.7, -3.0), "catch", 0.35, -0.5)):
        spot, face = lean_spot((car_c[0] - side, car_c[1]), CAM)
        a2, hb2 = rigged_agent(spot, face, style=style, tilt=-0.12, phase=ph)
        # balaclava eye slit: dark opening with two eyes catching the light
        slit = obj("eye_slit", box_mesh("es", 0.03, 0.05, 0.17), mat("slit", (0.004, 0.003, 0.003), rough=0.8))
        slit.parent, slit.parent_type, slit.parent_bone = a2, "BONE", "head"
        slit.location = (0.098, -0.165, 0.0)
        eye_m = mat("eye", (0.025, 0.018, 0.014), rough=0.03, coat=1.0)      # dark wet eyes, the light only makes a glint
        for ez in (-0.038, 0.038):
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.013)
            em_ = bpy.data.meshes.new("eye")
            bm.to_mesh(em_)
            bm.free()
            for pl in em_.polygons:
                pl.use_smooth = True
            eye = obj("eye", em_, eye_m)
            eye.parent, eye.parent_type, eye.parent_bone = a2, "BONE", "head"
            eye.location = (0.1, -0.165, ez)
        if style == "count":                                    # stack of bills in the left hand
            st = obj("count_stack", box_mesh("cs", 0.16, 0.07, 0.035), bill)
            st.parent, st.parent_type, st.parent_bone = a2, "BONE", "hand.L"
            st.location, st.rotation_euler = (0.0, 0.0, 0.0), (0, 0, math.radians(90))
            for n in range(4):                                  # bills flicking off the stack
                fb = obj("flick", box_mesh("fb", 0.156, 0.066, 0.0015), bill)
                fb.parent, fb.parent_type, fb.parent_bone = a2, "BONE", "hand.R"
                for f in range(1, FRAMES + 1, 2):
                    t = ((f / 12.0) + n / 4) % 1
                    fb.location = (0.05 * t, 0.12 * t, 0.06 * t)
                    fb.rotation_euler = (t * 3, t * 1.5, 0.4 + t)
                    fb.scale = (1.0 - t * 0.2,) * 3
                    fb.keyframe_insert("location", frame=f)
                    fb.keyframe_insert("rotation_euler", frame=f)
                    fb.keyframe_insert("scale", frame=f)
        else:                                                   # a fan of caught bills + one in the grabbing hand
            for n in range(3):
                cb = obj("caught", box_mesh("cb", 0.156, 0.066, 0.0015), bill)
                cb.parent, cb.parent_type, cb.parent_bone = a2, "BONE", "hand.L"
                cb.rotation_euler = (0, math.radians(-20 + n * 20), math.radians(90))
            gb = obj("grab", box_mesh("gb", 0.156, 0.066, 0.0015), bill)
            gb.parent, gb.parent_type, gb.parent_bone = a2, "BONE", "hand.R"
            gb.rotation_euler = (math.radians(30), 0, 0.3)
            # bills streaming past his raised hand
            hp = Vector((spot[0], spot[1], 2.1))
            for n in range(9):
                o = obj("pass_bill", box_mesh("pb", 0.156, 0.066, 0.0015), bill, scale=(1.6, 1.6, 1.6))
                st0 = n * 13
                for f in range(1, FRAMES + 1, 3):
                    t = ((f - st0) % FRAMES) / 40.0
                    o.location = (hp.x - 2.0 + 4.0 * t, hp.y + 0.3 * math.sin(n) - 0.6 * t, hp.z + 0.5 - 0.6 * t * t + 0.2 * math.sin(t * 6 + n))
                    o.rotation_euler = (t * 7 + n, t * 4, t * 3)
                    o.keyframe_insert("location", frame=f)
                    o.keyframe_insert("rotation_euler", frame=f)

    # ---- wind: banknotes blown off the counter and down the street
    bill_me = box_mesh("bill1", 0.156, 0.066, 0.0015)
    bill_me.materials.append(bill)
    for i in range(46):
        o = bpy.data.objects.new("bill", bill_me)
        sc.collection.objects.link(o)
        o.scale = (1.7, 1.7, 1.7)
        start = rnd.randint(-80, FRAMES - 10)
        x0, y0 = rnd.uniform(-1.8, 1.8), rnd.uniform(-0.4, 0.2)
        spin = (rnd.uniform(3, 8), rnd.uniform(2, 6), rnd.uniform(1, 4))
        for f in range(1, FRAMES + 1, 3):
            t = (f - start) / 24
            if t < 0:
                o.location, o.rotation_euler = (x0, y0, 1.0), (0, 0, rnd.uniform(0, 3))
            else:
                o.location = (x0 + 3.8 * t + 0.4 * math.sin(t * 3 + i), y0 - 1.6 * t - 0.25 * t * t,
                              max(0.18, 1.02 + 1.3 * math.sin(min(t, 1.2) * 1.3) - 0.55 * t * t + 0.25 * math.sin(t * 5 + i)))
                o.rotation_euler = (t * spin[0], t * spin[1], t * spin[2] + i)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)

    # ---- lights
    light("AREA", "store_fill", (0, 1.2, 3.1), (1.0, 0.88, 0.76), 420, size=4.0, rot=(0, 0, 0))
    neon_light = light("AREA", "sign_spill", (0, -0.6, 4.6), (1.0, 0.92, 0.82), 120, size=7.0, rot=(math.radians(150), 0, 0))
    # car lighting like a night car shoot: a long soft strip above (reads as a line on the paint) + cool rims behind
    light("AREA", "car_strip", (2.4, -4.4, 4.2), (0.92, 0.96, 1.0), 380, size=4.0, target=(2.7, -4.0, 0.6))
    light("AREA", "rim_911", (5.6, -1.8, 1.4), (0.75, 0.88, 1.0), 260, size=1.5, target=(2.7, -4.0, 0.7))
    light("AREA", "rim_g63", (-5.8, -1.0, 2.2), (0.75, 0.88, 1.0), 300, size=1.8, target=(-2.7, -3.0, 1.0))
    light("AREA", "rim_cool", (-6, -6, 6), (0.55, 0.7, 1.0), 450, size=5, target=(0, 0, 1.5))
    light("AREA", "agent_key", (1.2, -1.5, 2.6), (0.8, 1.0, 0.92), 50, size=1.0, target=(0, 0.85, 1.4))
    world = bpy.data.worlds.new("night")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.008, 1)
    haze = obj("haze", box_mesh("haze", 40, 30, 10), None, loc=(0, -4, 5))
    hm = bpy.data.materials.new("haze")
    hm.use_nodes = True
    hm.node_tree.nodes.clear()
    pv = hm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
    pv.inputs["Density"].default_value = 0.006
    pv.inputs["Anisotropy"].default_value = 0.3
    out = hm.node_tree.nodes.new("ShaderNodeOutputMaterial")
    hm.node_tree.links.new(pv.outputs[0], out.inputs["Volume"])
    haze.data.materials.append(hm)

    # neon EMERALD: burning, then sputtering like a faulty transformer
    em_sock = neon.node_tree.nodes["Emission"].inputs["Strength"]
    flicker(em_sock, [(18, 20), (22, 23), (24, 27), (61, 62), (64, 70), (72, 73), (98, 99), (101, 104)], 2.4, 0.15,
            neon_light, 200, 10)

    # ---- camera: low, slow push towards the store
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 36
    cam_d.dof.use_dof = True
    cam_d.dof.aperture_fstop = 5.6
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    focus = bpy.data.objects.new("focus", None)
    sc.collection.objects.link(focus)
    focus.location = (2.6, -5.6, 1.0)
    cam_d.dof.focus_object = focus
    look = bpy.data.objects.new("look", None)
    sc.collection.objects.link(look)
    tc = cam.constraints.new("TRACK_TO")
    tc.target, tc.track_axis, tc.up_axis = look, "TRACK_NEGATIVE_Z", "UP_Y"
    for f, cpos, lpos in ((1, (2.2, -11.4, 0.75), (0.3, -0.6, 1.65)), (FRAMES, (1.8, -10.6, 0.78), (0.25, -0.6, 1.62))):
        cam.location, look.location = cpos, lpos
        cam.keyframe_insert("location", frame=f)
        look.keyframe_insert("location", frame=f)

    # ---- render settings
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x = r.resolution_y = 1080
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.6
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = 48
    cy.use_adaptive_sampling, cy.adaptive_threshold = True, 0.03
    cy.use_denoising = True
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces, cy.volume_bounces = 8, 2, 4, 8, 0
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.volume_step_rate = 4.0
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    sc.view_settings.exposure = 0.3
    return sc


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode = argv[0] if argv else "still"
    sc = build()
    os.makedirs(OUT, exist_ok=True)
    if mode == "save":
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "exchange_scene.blend"))
    elif mode == "still":
        f = int(argv[1]) if len(argv) > 1 else 60
        if len(argv) > 2:
            sc.cycles.samples = int(argv[2])
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, f"exchange_still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    elif mode == "anim":
        start = int(argv[1]) if len(argv) > 1 else 1
        end = int(argv[2]) if len(argv) > 2 else FRAMES
        sc.cycles.samples = int(os.environ.get("SAMPLES", 48))
        os.makedirs(os.path.join(OUT, "exchange"), exist_ok=True)
        for f in range(start, end + 1):
            path = os.path.join(OUT, "exchange", f"{f:04d}.png")
            if os.path.exists(path):
                continue
            sc.frame_set(f)
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print("frame", f, flush=True)


if __name__ == "__main__":
    main()
