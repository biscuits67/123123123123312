"""Telegram video avatar: the hero on the green 911 in the dark loft, 240-frame (10 s) seamless loop.

    blender -b qwiz.blend -P build_ava.py -- HERO.blend PROPS_DIR AVA_DIR OUT.blend

* hero (from the main scene file) sits on the front fender on the camera side; iPhone in the right hand,
  thumb flicks the EMERALD wallet screen, screen light on the balaclava; eyes glow emerald, blink twice
* money rain: bills flutter down and settle in a strip on the floor in front of the car
* a robot vacuum drives along the strip and swallows the bills (each hops before it vanishes)
* the hero looks up from the phone and follows the vacuum, eyes flare, then goes back to the phone
* camera: slow 12 deg orbit there and back, push-in while the hero watches, focus pulled to the vacuum,
  light handheld sway; every motion has a whole number of periods (or is zero at both ends)
"""
import math
import os
import random
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Vector

HERO_SRC, PROPS, AVA, OUT = sys.argv[sys.argv.index("--") + 1:]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 240
LOOP = F1 - F0 + 1
scn.frame_start, scn.frame_end = F0, F1
scn.frame_set(F0)
rnd = random.Random(11)
P = "mixamorig:"


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def window(f, a, b, ramp):
    """0 before a, 1 between a+ramp and b-ramp, 0 after b."""
    return smooth((f - a) / ramp) - smooth((f - (b - ramp)) / ramp)


def linear_keys(idblock):
    ad = idblock.animation_data
    for layer in ad.action.layers:
        for strip in layer.strips:
            for fc in strip.channelbag(ad.action_slot).fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"


dg = bpy.context.evaluated_depsgraph_get()
car = D.objects["Sketchfab_model.001"]
car_set = set(car.children_recursive)


def ray_down(x, y, z=3.0, only=None):
    o = Vector((x, y, z))
    for _ in range(30):
        hit, loc, nrm, _, ob, _ = scn.ray_cast(dg, o, Vector((0, 0, -1)))
        if not hit:
            return None
        if only is None or ob in only:
            return loc
        o = loc - Vector((0, 0, 0.001))
    return None


# ---------------------------------------------------------------- car frame from its tyres
tire = D.objects["AO_tire_main_tires_0"]
tv = [tire.matrix_world @ v.co for v in tire.data.vertices]
cen = sum(tv, Vector()) / len(tv)
sxx = sum((p.x - cen.x) ** 2 for p in tv)
syy = sum((p.y - cen.y) ** 2 for p in tv)
sxy = sum((p.x - cen.x) * (p.y - cen.y) for p in tv)
ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
AX = Vector((math.cos(ang), math.sin(ang), 0))                       # long axis
hl = D.objects["headlights_flash_lights_0"]
hl_c = sum((hl.matrix_world @ Vector(c) for c in hl.bound_box), Vector()) / 8
FWD = AX if (hl_c - cen).dot(AX) > 0 else -AX
RIGHT = FWD.cross(Vector((0, 0, 1)))
cam = D.objects["Camera"]
cam_pos0 = cam.matrix_world.translation.copy()
OUTW = RIGHT if (cam_pos0 - cen).dot(RIGHT) > 0 else -RIGHT        # car side facing the camera
wheels = {}
for p in tv:
    key = ((p - cen).dot(FWD) > 0, (p - cen).dot(OUTW) > 0)
    wheels.setdefault(key, []).append(p)
WHEEL = {k: (sum(v, Vector()) / len(v)) for k, v in wheels.items()}
front_out = WHEEL[(True, True)]
print("car fwd", tuple(round(c, 3) for c in FWD), "front wheel (camera side)", tuple(round(c, 3) for c in front_out))
FLOOR_Z = ray_down(cen.x + OUTW.x * 2, cen.y + OUTW.y * 2).z

# ---------------------------------------------------------------- hero from the main scene
keep = ("Hero_Rig", "Hero_Balaclava", "Hero_Eye_L", "Hero_Eye_R", "Hero_Face", "Hero_Hands_Head",
        "Hero_Hoodie", "Hero_Joints", "Hero_Pants", "Hero_Shoe_Left", "Hero_Shoe_Right")
with D.libraries.load(HERO_SRC, link=False) as (src, dst):
    dst.objects = [n for n in keep if n in src.objects]
    dst.objects.append("Bill_00")
hero_coll = D.collections.new("Hero")
scn.collection.children.link(hero_coll)
for o in dst.objects:
    if o.name.startswith("Bill"):
        continue
    hero_coll.objects.link(o)
bill_src = D.objects["Bill_00"]
rig = D.objects["Hero_Rig"]
bones = rig.data.bones
exec(open(os.path.join(AVA, "hero_eyes.py")).read())

# seat: on top of the front arch, a hand's width in from the edge
SEAT = front_out - FWD * 0.1 - OUTW * 0.12
dg = bpy.context.evaluated_depsgraph_get()
SURFACE = ray_down(SEAT.x, SEAT.y, only=car_set).z
yaw_obj = math.atan2(OUTW.x, -OUTW.y)                                  # character faces out of the side
rig.parent = None
rig.location = (SEAT.x, SEAT.y, 0)
rig.rotation_mode = "XYZ"
rig.rotation_euler = (math.radians(90), 0, yaw_obj)
bpy.context.view_layer.update()
print("seat", tuple(round(c, 3) for c in SEAT), "surface", round(SURFACE, 3), "floor", round(FLOOR_Z, 3))

K = (Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Scale(rig.scale[0], 4)).inverted()   # char -> armature
C2A = K.to_3x3().normalized()
CH = Matrix.Translation((SEAT.x, SEAT.y, 0)) @ Matrix.Rotation(yaw_obj, 4, "Z")              # char -> world


def to_arm_pos(p):
    return K @ Vector(p)


def to_arm_dir(d):
    return (C2A @ Vector(d)).normalized()


def to_char(p_arm):
    return K.inverted() @ p_arm


def world_to_char(p):
    return CH.inverted() @ Vector(p)


def rest(n):
    return bones[P + n].matrix_local.to_3x3().normalized()


def frame3(a, b):
    a = a.normalized()
    b = (b - a * b.dot(a)).normalized()
    return Matrix((a, b, a.cross(b))).transposed()


def aim(n, d, ref_rest=None, ref_target=None, pre=None):
    R0 = rest(n)
    a0 = R0.col[1]
    a1 = to_arm_dir(d)
    if ref_rest is None:
        R = a0.rotation_difference(a1).to_matrix()
    else:
        R = frame3(a1, to_arm_dir(ref_target)) @ frame3(a0, to_arm_dir(ref_rest)).inverted()
    M = R @ R0
    if pre is not None:
        M = C2A @ pre.to_3x3() @ C2A.inverted() @ M
    return M


cam_c = world_to_char(cam_pos0)
cam_yaw = math.atan2(cam_c.x, -cam_c.y)
CAM_DIR_C = (cam_c - Vector((0, 0, SURFACE + 0.6))).normalized()

# ---------------------------------------------------------------- vacuum path + timing (the hero reacts to it)
# a line on the floor parallel to the car, in front of the camera-side flank; keep the visible stretch
LINE0 = cen + OUTW * 1.8
LINE0.z = FLOOR_Z
DIRV = None
vis = []
for i in range(-60, 61):
    p = LINE0 + FWD * (i * 0.1)
    v = world_to_camera_view(scn, cam, p)
    vis.append((i * 0.1, v.x, v.y))
inside = [(s, x) for s, x, y in vis if 0.0 < x < 1.0 and 0.0 < y < 1.0]
s_lo, s_hi = min(s for s, _ in inside), max(s for s, _ in inside)
x_at_lo = [x for s, x in inside if s == s_lo][0]
x_at_hi = [x for s, x in inside if s == s_hi][0]
if x_at_lo < x_at_hi:          # enter from the left of the frame
    S_START, S_END = s_lo - 0.6, s_hi + 0.6
else:
    S_START, S_END = s_hi + 0.6, s_lo - 0.6
V_IN, V_OUT = 86, 218           # frames: just off-screen left -> just off-screen right
print("vacuum along s", round(S_START, 2), "->", round(S_END, 2), "visible", round(s_lo, 2), round(s_hi, 2))


def vac_s(f):
    u = (f - V_IN) / (V_OUT - V_IN)
    u = min(1.0, max(0.0, u))
    return S_START + (S_END - S_START) * u


def vac_pos(f):
    return LINE0 + FWD * vac_s(f)


def vac_time(s):
    return V_IN + (s - S_START) / (S_END - S_START) * (V_OUT - V_IN)


LOOK0, LOOK1 = 100, 206          # hero watches the vacuum


def look(f):
    return window(f, LOOK0, LOOK1, 14)


# ---------------------------------------------------------------- hero pose
ORDER = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
         "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
         "RightShoulder", "RightArm", "RightForeArm", "RightHand",
         "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"]
HIPS_C = Vector((0, 0.03, SURFACE + 0.165))
THUMB_FLICKS = (30, 62, 150 + 60, 228)        # thumb swipes up the screen (screen scrolls with them)


def flick(f):
    """0..1 thumb travel during a swipe (8 frames), else 0."""
    for t in THUMB_FLICKS:
        if t <= f < t + 8:
            return math.sin(math.pi * (f - t) / 8)
    return 0.0


def pose_for(f):
    t = (f - F0) / LOOP
    tau = 2 * math.pi * t
    w = look(f)
    breathe = math.sin(tau * 4)
    rot = {}
    rot["Hips"] = (C2A @ Euler((math.radians(-4 + 0.6 * breathe), 0, math.radians(1.5 * math.sin(tau))))
                   .to_matrix() @ C2A.inverted()) @ rest("Hips")
    # chest: hunched over the phone, straightens and turns a little towards the vacuum
    tw = cam_yaw * 0.25 + math.radians(10) * w
    for i, n in enumerate(("Spine", "Spine1", "Spine2")):
        lean = (0.10, 0.16, 0.18)[i] * (1 - 0.45 * w) + 0.012 * breathe
        rot[n] = aim(n, (0, -lean, 1), pre=Matrix.Rotation(tw * (i + 1) / 3, 4, "Z"))
    rot["Neck"] = aim("Neck", (0, -0.16 * (1 - 0.4 * w), 1), pre=Matrix.Rotation(tw, 4, "Z"))
    # right arm: solved per frame from where the phone is (see grip below)
    # left arm: leaning on the fender beside the hip
    rot["LeftArm"] = aim("LeftArm", (0.24, 0.28, -0.93), (0, 0, -1), (0.0, 0.9, 0.2))
    rot["LeftForeArm"] = aim("LeftForeArm", (0.14, 0.18, -0.97), (0, 0, -1), (0.0, 0.9, 0.2))
    rot["LeftHand"] = aim("LeftHand", (0.1, -0.35, -0.93), (0, 0, -1), (0, 0.4, -0.9))
    # legs: the outer one swings lazily, the inner one hangs and taps
    for side, sx, amp, ph, sp in (("Left", 1, 6, 0.0, 4), ("Right", -1, 17, 1.3, 3)):
        rot[side + "UpLeg"] = aim(side + "UpLeg", (0.08 * sx, -0.96, -0.24))
        a = math.radians(16 + amp * math.sin(tau * sp + ph))
        rot[side + "Leg"] = aim(side + "Leg", (0.02 * sx, -math.sin(a), -math.cos(a)))
        b = a + math.radians(62)
        rot[side + "Foot"] = aim(side + "Foot", (0.03 * sx, -math.sin(b), -math.cos(b)))
    return rot, w


def head_rot(f, target_c, w_target, phone_c):
    head_c = to_char(pose["Head"].translation)

    def yp(v):
        return math.atan2(v.x, -v.y), math.atan2(-v.z, v.xy.length)
    y1, p1 = yp(phone_c - head_c)
    y2, p2 = yp(target_c - head_c)
    yaw = y1 + (y2 - y1) * w_target
    pitch = p1 + (p2 - p1) * w_target
    yaw = max(-math.radians(55), min(math.radians(55), yaw))          # a neck, not an owl
    pitch = max(-math.radians(12), min(math.radians(42), pitch))
    yaw += math.radians(1.5) * math.sin(2 * math.pi * (f - F0) / LOOP * 3)
    return C2A @ (Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(pitch, 3, "X")) @ C2A.inverted() @ rest("Head")


def chain(rot, f):
    out = {}
    fl = flick(f)
    for n in ORDER + [b.name[len(P):] for b in bones if b.name[len(P):] not in ORDER]:
        b = bones[P + n]
        if n == "Hips":
            M = Matrix.Translation(to_arm_pos(HIPS_C)) @ rot["Hips"].to_4x4()
        else:
            par = out.get(b.parent.name[len(P):])
            if par is None:
                continue
            rel = b.parent.matrix_local.inverted() @ b.matrix_local
            head = par @ rel.translation
            R = rot.get(n)
            if R is None:
                R = par.to_3x3().normalized() @ rel.to_3x3().normalized()
                if n.startswith("RightHandThumb"):
                    if n == "RightHandThumb1":
                        R = R @ Matrix.Rotation(math.radians(-28 + 14 * fl), 3, "X")
                    else:
                        R = R @ Matrix.Rotation(math.radians(10 - 25 * fl), 3, "X")
                elif n.startswith("RightHand"):
                    R = R @ Matrix.Rotation(math.radians(66), 3, "X")       # fingers wrap the phone edge
                elif n.startswith("LeftHand"):
                    R = R @ Matrix.Rotation(math.radians(14), 3, "X")
            M = Matrix.Translation(head) @ R.to_4x4()
        out[n] = M
    return out


# ---------------------------------------------------------------- grip: phone first, then the hand around it, then the arm (IK)
SC = rig.scale[0]
L_hand = bones[P + "RightHand"].length
R0_hand = rest("RightHand")
Y0_hand = R0_hand.col[1]
W0 = bones[P + "RightHandIndex1"].head_local - bones[P + "RightHandPinky1"].head_local
W0 = (W0 - Y0_hand * W0.dot(Y0_hand)).normalized()          # across the knuckles, towards the thumb
N0_PALM = W0.cross(Y0_hand).normalized()                     # right hand: out of the palm
phone_h = 0.163


def frame_rot(name, d_char, n_char):
    """Bone along char-space d_char, with the (rest) palm-side vector turned to n_char: no hidden twist."""
    R0 = rest(name)
    y0 = R0.col[1]
    n0 = (N0_PALM - y0 * N0_PALM.dot(y0)).normalized()
    R = frame3(to_arm_dir(d_char), to_arm_dir(n_char)) @ frame3(y0, n0).inverted()
    return R @ R0


def two_bone(S, T, a, b, pole):
    d = T - S
    L = min(d.length, (a + b) * 0.998)
    ax = d.normalized()
    cos_a = (a * a + L * L - b * b) / (2 * a * L)
    sin_a = math.sqrt(max(0.0, 1 - cos_a * cos_a))
    perp = (pole - ax * pole.dot(ax)).normalized()
    return S + ax * (a * cos_a) + perp * (a * sin_a)


def grip(rot, pose, f, w):
    """Phone held up in front of the face, screen to the eyes, back (camera island) to the lens;
    lowered a little while the hero watches the vacuum. Returns the phone matrix in char space."""
    head_c = to_char(pose["Head"].translation)
    eye_c = head_c + Vector((0, -0.07, 0.09))
    C = eye_c + Vector((-0.04, -0.31 - 0.04 * w, -0.24 - 0.12 * w))
    n = (eye_c - C).normalized()                             # screen normal
    up = Vector((0, 0, 1))
    zp = (up - n * up.dot(n)).normalized()
    yp = -n
    xp = yp.cross(zp)
    # palm on the lower back of the phone, fingers round its left edge, thumb over the screen
    F = Vector((1, 0, 0))
    F = (F - n * F.dot(n)).normalized()
    palm_c = C - n * 0.022 - zp * 0.012
    T = palm_c - F * (L_hand * SC * 0.55)                   # wrist
    S = to_char(pose["RightArm"].translation)
    a = bones[P + "RightArm"].length * SC
    b = bones[P + "RightForeArm"].length * SC
    El = two_bone(S, T, a, b, Vector((-0.55, 0.2, -1.0)))
    n_up = (n * 0.5 + Vector((0, -0.4, -1)).normalized() * 0.5).normalized()
    rot["RightArm"] = frame_rot("RightArm", El - S, n_up)
    rot["RightForeArm"] = frame_rot("RightForeArm", T - El, n)
    rot["RightHand"] = frame_rot("RightHand", F, n)
    return Matrix.Translation(C) @ Matrix((xp, yp, zp)).transposed().to_4x4()


act = D.actions.new("Hero_Ava")
rig.animation_data_create()
rig.animation_data.action = act
for pb in rig.pose.bones:
    pb.rotation_mode = "QUATERNION"
head_world = {}
phone_world = {}
for f in range(F0, F1 + 1):
    rot, w = pose_for(f)
    pose = chain(rot, f)
    ph_c = grip(rot, pose, f, w)
    tgt_c = world_to_char(vac_pos(f) + Vector((0, 0, 0.05)))
    rot["Head"] = head_rot(f, tgt_c, w, ph_c.translation)
    pose = chain(rot, f)
    head_world[f] = CH @ to_char(pose["Head"].translation)
    phone_world[f] = CH @ ph_c
    for n, M in pose.items():
        b = bones[P + n]
        pb = rig.pose.bones[P + n]
        if b.parent is None:
            basis = b.matrix_local.inverted() @ M
        else:
            rel = b.parent.matrix_local.inverted() @ b.matrix_local
            basis = rel.inverted() @ pose[b.parent.name[len(P):]].inverted() @ M
        loc, q, _ = basis.decompose()
        pb.rotation_quaternion = q
        pb.keyframe_insert("rotation_quaternion", frame=f)
        if b.parent is None:
            pb.location = loc
            pb.keyframe_insert("location", frame=f)
linear_keys(rig)

# ---------------------------------------------------------------- eyes: blinks and a flare while watching
eyes_mat = D.materials["Hero_Eyes_Glow"]
nt = eyes_mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
ramp = next(n for n in nt.nodes if n.type == "VALTORGB")
gain = nt.nodes.new("ShaderNodeValue")
gain.name = "EyeGain"
mul = nt.nodes.new("ShaderNodeMath")
mul.operation = "MULTIPLY"
nt.links.new(ramp.outputs["Color"], mul.inputs[0])
nt.links.new(gain.outputs[0], mul.inputs[1])
nt.links.new(mul.outputs[0], bsdf.inputs["Emission Strength"])
BLINKS = (44, 168)
for f in range(F0, F1 + 1):
    g = 1.0 + 0.9 * look(f) * (0.85 + 0.15 * math.sin(f * 0.7))
    for bl in BLINKS:
        if bl <= f < bl + 5:
            g *= abs(f - bl - 2) / 2.5
    gain.outputs[0].default_value = g
    gain.outputs[0].keyframe_insert("default_value", frame=f)
linear_keys(nt)

# ---------------------------------------------------------------- iPhone in the right hand
before = set(D.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(PROPS, "iphone", "source", "apple_iphone_18_pro_max_burgundy.glb"))
new = [o for o in D.objects if o not in before]
meshes = [o for o in new if o.type == "MESH"]
empty_names = [o.name for o in new if o.type != "MESH"]
for o in meshes:
    o.data = o.data.copy()
    o.data.transform(o.matrix_world)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
with bpy.context.temp_override(active_object=meshes[0], selected_editable_objects=meshes):
    bpy.ops.object.join()
phone = meshes[0]
phone.name = "Hero_Phone"
for n in empty_names:
    D.objects.remove(D.objects[n])
for c in list(phone.users_collection):
    c.objects.unlink(phone)
hero_coll.objects.link(phone)
phone.data.transform(Matrix.Translation((0, 0, -phone_h / 2)))            # origin at the centre
# keyed per frame from the grip (the hand was solved around it)
for f in range(F0, F1 + 1):
    phone.matrix_world = phone_world[f]
    phone.keyframe_insert("location", frame=f)
    phone.keyframe_insert("rotation_euler", frame=f)
linear_keys(phone)
for m in D.materials:                                            # black gloves instead of mannequin hands
    if m.name.startswith("Gloves"):
        g = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        for l in list(g.inputs["Base Color"].links):
            m.node_tree.links.remove(l)
        g.inputs["Base Color"].default_value = (0.008, 0.008, 0.009, 1)
        g.inputs["Roughness"].default_value = 0.38
        g.inputs["Specular IOR Level"].default_value = 0.6
        g.inputs["Coat Weight"].default_value = 0.12
        g.inputs["Coat Roughness"].default_value = 0.3
        gn = m.node_tree
        wn = gn.nodes.new("ShaderNodeTexNoise")
        wn.inputs["Scale"].default_value = 180
        wn.inputs["Detail"].default_value = 6
        wb = gn.nodes.new("ShaderNodeBump")
        wb.inputs["Strength"].default_value = 0.25
        wb.inputs["Distance"].default_value = 0.001
        gn.links.new(wn.outputs["Fac"], wb.inputs["Height"])
        gn.links.new(wb.outputs["Normal"], g.inputs["Normal"])
for gname in ("Hero_Hands_Head", "Hero_Joints"):
    go = D.objects[gname]
    rm = go.modifiers.new("Glove_Fuse", "REMESH")       # after the armature: segments melt into one skin
    rm.mode, rm.adaptivity = "VOXEL", 0.0
    rm.voxel_size = 0.003 / go.matrix_world.to_scale().x            # object units are rig units (cm)
    rm.use_smooth_shade = True
    sm = go.modifiers.new("Glove_Smooth", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 3
# the screen: our wallet app, emissive, scrolls a page with each thumb swipe
scr_img = D.images.load(os.path.join(AVA, "phone_screen.png"))
scr_img.pack()
scr = D.materials.new("Phone_Screen_App")
snt = scr.node_tree
sb = next(n for n in snt.nodes if n.type == "BSDF_PRINCIPLED")
tc = snt.nodes.new("ShaderNodeTexCoord")
mp = snt.nodes.new("ShaderNodeMapping")
tx = snt.nodes.new("ShaderNodeTexImage")
tx.image, tx.extension = scr_img, "REPEAT"
snt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
snt.links.new(mp.outputs["Vector"], tx.inputs["Vector"])
snt.links.new(tx.outputs["Color"], sb.inputs["Base Color"])
snt.links.new(tx.outputs["Color"], sb.inputs["Emission Color"])
sb.inputs["Emission Strength"].default_value = 3.5
sb.inputs["Roughness"].default_value = 0.08
for i, m in enumerate(phone.data.materials):
    if m and "Screen" in m.name:
        phone.data.materials[i] = scr
steps = {f: sum(math.sin(math.pi * (f - t) / 12) ** 2 for t in THUMB_FLICKS if t <= f < t + 12)
         for f in range(F0, F1 + 1)}
total = sum(steps.values())
scroll = 0.0
for f in range(F0, F1 + 1):
    scroll += steps[f] / total          # one whole page per loop: the tiled texture lines up again
    mp.inputs["Location"].default_value[1] = scroll
    mp.inputs["Location"].keyframe_insert("default_value", index=1, frame=f)
linear_keys(snt)
# screen light on the face
sl = D.objects.new("Phone_Screen_Light", D.lights.new("Phone_Screen_Light", "AREA"))
sl.data.shape, sl.data.size, sl.data.size_y = "RECTANGLE", 0.07, 0.15
sl.data.energy, sl.data.color = 2.5, (0.75, 1.0, 0.85)
hero_coll.objects.link(sl)
sl.parent = phone
sl.matrix_parent_inverse = Matrix.Identity(4)
sl.location = (0, -0.006, 0)
sl.rotation_euler = (math.radians(90), 0, 0)                 # light shoots out of the screen (-Y)
sl.visible_camera = sl.visible_glossy = False

# ---------------------------------------------------------------- robot vacuum
before = set(D.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(PROPS, "vacuum", "vacuum.glb"))
new = [o for o in D.objects if o not in before]
vm = [o for o in new if o.type == "MESH"][0]
vm.data = vm.data.copy()
vm.data.transform(vm.matrix_world)
vm.parent = None
vm.matrix_world = Matrix.Identity(4)
for o in new:
    if o is not vm:
        D.objects.remove(o)
vm.name = "Robot_Vacuum"
pz = min(v.co.z for v in vm.data.vertices)
vm.data.transform(Matrix.Translation((0, 0, -pz)))
# which way is its front: the camera bump sits at the far end of the long axis of the small parts...
# the model's front faces -Y in the glTF; drive along +FWD*sign
props = D.collections.new("Avatar_Props")
scn.collection.children.link(props)
for c in list(vm.users_collection):
    c.objects.unlink(vm)
props.objects.link(vm)
VSCALE = 1.15
dir_s = 1 if S_END > S_START else -1
travel = FWD * dir_s
vac_yaw = math.atan2(-travel.x, travel.y)                      # model -Y -> travel direction
for f in range(F0, F1 + 1):
    p = vac_pos(f)
    wob = math.radians(2.5) * math.sin(f * 0.35)
    vm.location = (p.x, p.y, FLOOR_Z + 0.0005)
    vm.rotation_euler = (0, 0, vac_yaw + math.pi + wob)
    vm.scale = (VSCALE,) * 3
    vm.keyframe_insert("location", frame=f)
    vm.keyframe_insert("rotation_euler", frame=f)
vm.keyframe_insert("scale", frame=F0)
linear_keys(vm)
# status LED
led = D.objects.new("Vacuum_LED", D.lights.new("Vacuum_LED", "POINT"))
led.data.energy, led.data.color, led.data.shadow_soft_size = 0.08, (0.2, 1.0, 0.5), 0.005
props.objects.link(led)
led.parent = vm
led.location = (0, 0.09, 0.09)
led.visible_camera = False

# ---------------------------------------------------------------- money rain into a strip, eaten by the vacuum
N_BILLS = 54
bills = D.collections.new("Money_Rain")
scn.collection.children.link(bills)
s_a, s_b = sorted((s_lo + 0.25, s_hi - 0.25))
side_v = OUTW
for i in range(N_BILLS):
    ob = D.objects.new(f"Rain_Bill_{i:02d}", bill_src.data)
    bills.objects.link(ob)
    BS = 1.7                                                    # a touch oversized so they read in the circle
    s = rnd.uniform(s_a, s_b)
    lat = rnd.gauss(0, 0.09)
    land = LINE0 + FWD * s + side_v * lat
    land.z = FLOOR_Z + 0.0008 + 0.0004 * (i % 6)
    t_eat = vac_time(s) - 3                                    # vacuum front reaches it
    fall = rnd.uniform(46, 64)
    t_land = min(max(rnd.uniform(14, 120), fall + 2), t_eat - 10)
    t_top = t_land - fall
    yaw_end = rnd.uniform(0, 2 * math.pi)
    spin = rnd.uniform(1.5, 3.5) * rnd.choice((-1, 1))
    ph = rnd.uniform(0, 6.28)
    drift = Vector((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35), 0))
    crumple = (math.radians(rnd.uniform(-14, 14)), math.radians(rnd.uniform(-10, 10)))   # not dead flat: catches light
    for f in range(F0, F1 + 1):
        if f < t_top:
            ob.scale = (0, 0, 0)
            ob.location = land + Vector((0, 0, 3))
            ob.rotation_euler = (0, 0, 0)
        elif f < t_land:
            u = (f - t_top) / fall                              # 0 top -> 1 floor
            h = 2.6 * (1 - u) ** 1.15
            sway = math.sin(u * 7 + ph) * 0.18 * (1 - u)
            ob.location = land + drift * (1 - u) + side_v * sway + Vector((0, 0, h))
            tilt = (1 - u) ** 0.7
            ob.rotation_euler = (math.radians(55) * tilt * math.sin(u * 9 + ph),
                                 math.radians(35) * tilt * math.cos(u * 6 + ph), yaw_end + spin * (1 - u))
            ob.scale = (BS, BS, BS)
        elif f < t_eat:
            ob.location = land + Vector((0, 0, 0.012))
            ob.rotation_euler = (crumple[0], crumple[1], yaw_end)
            ob.scale = (BS, BS, BS)
        elif f < t_eat + 4:                                     # sucked in: little hop, flips, shrinks
            u = (f - t_eat) / 4
            ob.location = land + Vector((0, 0, 0.05 * math.sin(math.pi * u))) + travel * 0.06 * u
            ob.rotation_euler = (math.radians(70) * u, 0, yaw_end)
            sc = BS * (1 - u)
            ob.scale = (sc, sc, sc)
        else:
            ob.scale = (0, 0, 0)
            ob.location = land
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
        ob.keyframe_insert("scale", frame=f)
    linear_keys(ob)

# ---------------------------------------------------------------- camera: orbit, push-in, rack focus, handheld
base = cam.matrix_world.copy()
fwd0 = (base.to_3x3() @ Vector((0, 0, -1))).normalized()
pivot = Vector((cen.x, cen.y, 0.75))
base_target = cam_pos0 + fwd0 * (pivot - cam_pos0).length          # what the user's framing looks at
cam.animation_data_clear()
cam.data.dof.use_dof = True
cam.data.dof.focus_object = None
cam.data.dof.aperture_fstop = 2.4
for f in range(F0, F1 + 1):
    t = 2 * math.pi * (f - F0) / LOOP
    orbit = math.radians(12) * math.sin(t)
    R = Matrix.Translation(pivot) @ Matrix.Rotation(orbit, 4, "Z") @ Matrix.Translation(-pivot)
    pos = R @ cam_pos0
    tgt0 = R @ base_target
    pw = window(f, 100, 220, 36)                                  # push-in while the hero watches the vacuum
    hero_t = head_world[f] - Vector((0, 0, 0.35))
    tgt = tgt0 + (hero_t - tgt0) * (0.75 * pw)
    pos = pos + (hero_t - pos).normalized() * (1.6 * pw)
    pos += Vector((0, 0, 0.006 * math.sin(3 * t + 0.4) + 0.004 * math.sin(7 * t)))
    look_q = (tgt - pos).to_track_quat("-Z", "Y")
    sway = Euler((math.radians(0.25 * math.sin(2 * t + 0.7) + 0.08 * math.sin(9 * t)),
                  math.radians(0.3 * math.sin(3 * t + 2.1)),
                  math.radians(0.15 * math.sin(5 * t + 0.3)))).to_matrix()
    cam.matrix_world = Matrix.Translation(pos) @ (look_q.to_matrix() @ sway).to_4x4()
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
    rf = window(f, 128, 182, 16)                                # focus pulled to the vacuum
    d_hero = (head_world[f] - pos).length
    d_vac = (vac_pos(f) - pos).length
    cam.data.dof.focus_distance = d_hero + (d_vac - d_hero) * rf
    cam.data.dof.keyframe_insert("focus_distance", frame=f)
linear_keys(cam)
linear_keys(cam.data)

# soft key on the hero from camera left, cool rim from behind, so the hoodie reads against the dark loft
seat3 = Vector((SEAT.x, SEAT.y, SURFACE + 0.55))
cam_side = (cam_pos0 - seat3)
cam_side.z = 0
cam_side.normalize()
left = Vector((0, 0, 1)).cross(cam_side)
for name, power, size, col, off in (("Hero_Key", 12, 1.0, (0.85, 0.95, 1.0), cam_side * 2.0 + left * 1.4 + Vector((0, 0, 1.0))),
                                    ("Hero_Rim", 28, 0.6, (0.5, 1.0, 0.75), -cam_side * 1.6 - left * 0.6 + Vector((0, 0, 1.2)))):
    L = D.objects.new(name, D.lights.new(name, "AREA"))
    L.data.energy, L.data.size, L.data.color = power, size, col
    hero_coll.objects.link(L)
    L.location = seat3 + off
    L.rotation_euler = (seat3 - L.location).to_track_quat("-Z", "Y").to_euler()
    L.visible_camera = L.visible_glossy = False

# ---------------------------------------------------------------- QWIZ: levitating neon letters above the car
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
cam_mw0 = base
right_c = (cam_mw0.to_3x3() @ Vector((1, 0, 0)))
right_c.z = 0
right_c.normalize()
to_cam = Vector((cam_pos0.x - cen.x, cam_pos0.y - cen.y, 0)).normalized()
# a spot in the upper half of the frame, behind the car
Q_C = Vector((cen.x, cen.y, 0)) - to_cam * 2.2 + right_c * 0.6
Q_C.z = 2.15
Q_H = 0.85                                                   # cap height, m
q_root = D.objects.new("QWIZ_Root", None)
props.objects.link(q_root)
q_root.matrix_world = Matrix.Translation(Q_C) @ Matrix((right_c, to_cam.cross(right_c), to_cam)).transposed().to_4x4()
# face: dark mirror metal with a scanner sweep; sides: emerald neon, one gain per letter
face = D.materials.new("QWIZ_Face")
fnt = face.node_tree
fb = next(n for n in fnt.nodes if n.type == "BSDF_PRINCIPLED")
fb.inputs["Base Color"].default_value = (0.02, 0.025, 0.024, 1)
fb.inputs["Metallic"].default_value = 1.0
fb.inputs["Roughness"].default_value = 0.12
fb.inputs["Emission Color"].default_value = (0.75, 1.0, 0.85, 1)
tco = fnt.nodes.new("ShaderNodeTexCoord")
tco.object = q_root
sep = fnt.nodes.new("ShaderNodeSeparateXYZ")
sweep = fnt.nodes.new("ShaderNodeValue")
sweep.name = "Sweep"
sub = fnt.nodes.new("ShaderNodeMath")
sub.operation = "SUBTRACT"
absn = fnt.nodes.new("ShaderNodeMath")
absn.operation = "ABSOLUTE"
band = fnt.nodes.new("ShaderNodeMapRange")
band.inputs["From Min"].default_value, band.inputs["From Max"].default_value = 0.0, 0.18
band.inputs["To Min"].default_value, band.inputs["To Max"].default_value = 9.0, 0.0
skew = fnt.nodes.new("ShaderNodeMath")
skew.operation = "MULTIPLY_ADD"                               # slanted band: x + 0.35 y
skew.inputs[1].default_value = 0.35
fnt.links.new(tco.outputs["Object"], sep.inputs["Vector"])
fnt.links.new(sep.outputs["Y"], skew.inputs[0])
fnt.links.new(sep.outputs["X"], skew.inputs[2])
fnt.links.new(skew.outputs[0], sub.inputs[0])
fnt.links.new(sweep.outputs[0], sub.inputs[1])
fnt.links.new(sub.outputs[0], absn.inputs[0])
fnt.links.new(absn.outputs[0], band.inputs["Value"])
fnt.links.new(band.outputs["Result"], fb.inputs["Emission Strength"])
SWEEPS = ((58, 92), (196, 226))                               # two passes per loop
for f in range(F0, F1 + 1):
    v = -9.0
    for a_, b_ in SWEEPS:
        if a_ <= f <= b_:
            v = -2.0 + 4.6 * smooth((f - a_) / (b_ - a_))
    sweep.outputs[0].default_value = v
    sweep.outputs[0].keyframe_insert("default_value", frame=f)
linear_keys(fnt)

x_cursor = 0.0
letters = []
for i, ch in enumerate("QWIZ"):
    cu = D.curves.new(f"QWIZ_{ch}", "FONT")
    cu.body = ch
    cu.font = D.fonts.load(FONT, check_existing=True)
    cu.size = Q_H / 0.73
    cu.extrude = 0.07
    cu.bevel_depth = 0.008
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    ob = D.objects.new(f"QWIZ_{ch}", cu)
    props.objects.link(ob)
    with bpy.context.temp_override(active_object=ob, selected_editable_objects=[ob], object=ob):
        bpy.ops.object.convert(target="MESH")
    ob = D.objects[f"QWIZ_{ch}"]
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    w_ = max(xs) - min(xs)
    neon = D.materials.new(f"QWIZ_Neon_{ch}")
    nn = neon.node_tree
    nb = next(n for n in nn.nodes if n.type == "BSDF_PRINCIPLED")
    nb.inputs["Base Color"].default_value = (0.0, 0.05, 0.02, 1)
    nb.inputs["Emission Color"].default_value = (0.05, 1.0, 0.35, 1)
    me.materials.clear()
    me.materials.append(face)
    me.materials.append(neon)
    for poly in me.polygons:
        poly.material_index = 0 if abs(poly.normal.z) > 0.9 else 1
    letters.append((ob, nb, w_))
gap = 0.12
total_w = sum(w for _, _, w in letters) + gap * 3
x = -total_w / 2
for i, (ob, nb, w_) in enumerate(letters):
    home = Vector((x + w_ / 2, 0, 0))
    x += w_ + gap
    ob.parent = q_root
    ph = i * 1.37
    wake = 10 + i * 7                                         # neon wakes letter by letter
    for f in range(F0, F1 + 1):
        t = 2 * math.pi * (f - F0) / LOOP
        ob.location = home + Vector((0, 0.07 * math.sin(2 * t + ph), 0.04 * math.sin(3 * t + ph)))
        ob.rotation_euler = (math.radians(4) * math.sin(2 * t + ph + 1), math.radians(6) * math.sin(t + ph),
                             math.radians(2) * math.sin(3 * t + ph))
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
        g = 1.0
        if wake - 8 <= f < wake + 14:                         # flicker: off, stutter, on
            u = f - (wake - 8)
            g = (0.05, 0.05, 0.6, 0.05, 0.05, 0.9, 0.2, 0.05, 1.0, 0.4, 1.0, 1.0, 0.7, 1.0,
                 1.0, 0.85, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)[u]
        g *= 1.0 + 0.04 * math.sin(f * 1.9 + ph)              # neon hum
        nb.inputs["Emission Strength"].default_value = 7.0 * g
        nb.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    linear_keys(ob)
    linear_keys(nb.id_data)
# green spill on the car roof and the floor from the letters
spill = D.objects.new("QWIZ_Spill", D.lights.new("QWIZ_Spill", "AREA"))
spill.data.shape, spill.data.size, spill.data.size_y = "RECTANGLE", total_w, 0.5
spill.data.energy, spill.data.color = 90, (0.1, 1.0, 0.45)
props.objects.link(spill)
spill.parent = q_root
spill.location = (0, -Q_H * 0.6, 0.15)
spill.rotation_euler = (math.radians(-60), 0, 0)
spill.visible_camera = spill.visible_glossy = False
print("QWIZ at", tuple(round(c, 2) for c in Q_C), "width", round(total_w, 2))

# light haze so the lights read as beams
hz = D.meshes.new("Haze")
hz_ob = D.objects.new("Haze", hz)
props.objects.link(hz_ob)
import bmesh
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(hz)
bm.free()
hz_ob.location = (cen.x, cen.y, 2.0)
hz_ob.scale = (12, 12, 4)
hm = D.materials.new("Haze")
hnt = hm.node_tree
for n in list(hnt.nodes):
    if n.type == "BSDF_PRINCIPLED":
        hnt.nodes.remove(n)
vol = hnt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.012
vol.inputs["Anisotropy"].default_value = 0.4
hnt.links.new(vol.outputs[0], hnt.nodes["Material Output"].inputs["Volume"])
hz.materials.append(hm)
hz_ob.visible_shadow = False

# compositor: bloom, a little lens dispersion, vignette
tree = D.node_groups.new("QWIZ Grade", "CompositorNodeTree")
tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
N = tree.nodes
rl = N.new("CompositorNodeRLayers")
glare = N.new("CompositorNodeGlare")
glare.inputs["Type"].default_value = "Bloom"
glare.inputs["Quality"].default_value = "High"
glare.inputs["Threshold"].default_value = 0.9
glare.inputs["Strength"].default_value = 0.45
glare.inputs["Size"].default_value = 0.6
lens = N.new("CompositorNodeLensdist")
lens.inputs["Dispersion"].default_value = 0.01
lens.inputs["Fit"].default_value = True
mask = N.new("CompositorNodeEllipseMask")
mask.inputs["Mask"].default_value = 0.0
mask.inputs["Value"].default_value = 1.0
mask.inputs["Size"].default_value = (1.1, 1.1)
blur = N.new("CompositorNodeBlur")
blur.inputs["Size"].default_value = (180, 180)
blur.inputs["Extend Bounds"].default_value = False
lift = N.new("ShaderNodeMapRange")
lift.inputs["To Min"].default_value = 0.5
mixv = N.new("ShaderNodeMix")
mixv.data_type, mixv.blend_type = "RGBA", "MULTIPLY"
mixv.inputs[0].default_value = 1.0
outn = N.new("NodeGroupOutput")
Lk = tree.links
Lk.new(rl.outputs["Image"], glare.inputs["Image"])
Lk.new(glare.outputs["Image"], lens.inputs["Image"])
Lk.new(mask.outputs["Mask"], blur.inputs["Image"])
Lk.new(blur.outputs["Image"], lift.inputs["Value"])
Lk.new(lens.outputs["Image"], mixv.inputs[6])
Lk.new(lift.outputs["Result"], mixv.inputs[7])
Lk.new(mixv.outputs[2], outn.inputs[0])
scn.compositing_node_group = tree
scn.render.use_compositing = True

# ---------------------------------------------------------------- render: Telegram video avatar
r = scn.render
r.resolution_x = r.resolution_y = 800
r.resolution_percentage = 100
r.fps = 24
c = scn.cycles
c.samples, c.adaptive_threshold, c.use_adaptive_sampling = 384, 0.02, True
c.use_denoising = True
r.use_motion_blur = True
r.motion_blur_shutter = 0.4
r.filepath = "//ava_render/ava_"
im = r.image_settings
if hasattr(im, "media_type"):
    im.media_type = "IMAGE"
im.file_format = "PNG"
scn.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
