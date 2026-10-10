"""Hero perched on the Porsche's front fender, hand-keyed procedurally (no Mixamo download), 250-frame loop:

    legs dangle and swing lazily (3 swings per loop, left/right out of phase),
    the right hand rests palm-up over the lap, then rises to eye level with the floating emerald
    (head turns to look at it), holds, and lowers again; the left hand leans on the fender,
    slow breathing, chest turned a little towards the camera.

    blender -b IN.blend -P sit_pose.py -- OUT.blend [SHOE_TEXTURE]

All poses are built analytically in "character space" (the rig's frame with the object's location and
Z turn removed: +X = character's left, -Y = facing, +Z = up) and written as quaternion keys.
"""
import math
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

OUT = sys.argv[sys.argv.index("--") + 1]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 250
LOOP = F1 - F0 + 1
P = "mixamorig:"
rig = D.objects["Hero_Rig"]
bones = rig.data.bones

# ---------------------------------------------------------------- seat on the front fender (camera side)
WHEEL = Vector((-56.98, -75.18))            # front wheel nearest the camera
FWD = Vector((-0.49, 0.87)).normalized()     # car's forward direction
OUTW = Vector((-0.87, -0.49)).normalized()   # car's left side, facing the street
SEAT = WHEEL + FWD * -0.1 + OUTW * -0.12      # on top of the arch, a hand's width in from the edge
SURFACE = 0.81                                # fender height there (ray-cast)
yaw_obj = math.atan2(OUTW.x, -OUTW.y)        # character faces out of the car side
rig.location = (SEAT.x, SEAT.y, 0)
rig.rotation_mode = "XYZ"
rig.rotation_euler = (math.radians(90), 0, yaw_obj)
bpy.context.view_layer.update()

K = (Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Scale(rig.scale[0], 4)).inverted()   # char -> armature
C2A = K.to_3x3().normalized()


def to_arm_pos(p):
    return K @ Vector(p)


def to_arm_dir(d):
    return (C2A @ Vector(d)).normalized()


cam_c = (Matrix.Rotation(yaw_obj, 4, "Z").inverted() @ (D.objects["Camera"].matrix_world.translation
                                                       - Vector((SEAT.x, SEAT.y, 0))))
cam_yaw = math.atan2(cam_c.x, -cam_c.y)      # how far the camera is from straight ahead


def rest(n):
    return bones[P + n].matrix_local.to_3x3().normalized()


def frame(a, b):
    a = a.normalized()
    b = (b - a * b.dot(a)).normalized()
    return Matrix((a, b, a.cross(b))).transposed()


def aim(n, d, ref_rest=None, ref_target=None, pre=None):
    """Armature-space rotation for bone n pointing along char-space direction d.
    With refs: a char-space vector that is ref_rest in the rest pose maps onto ref_target (sets the roll).
    Without: minimal rotation from the rest direction. pre: extra char-space rotation applied afterwards."""
    R0 = rest(n)
    a0 = R0.col[1]
    a1 = to_arm_dir(d)
    if ref_rest is None:
        R = a0.rotation_difference(a1).to_matrix()
    else:
        R = frame(a1, to_arm_dir(ref_target)) @ frame(a0, to_arm_dir(ref_rest)).inverted()
    M = R @ R0
    if pre is not None:
        M = C2A @ pre.to_3x3() @ C2A.inverted() @ M
    return M


def lerp_dir(a, b, w):
    return (Vector(a) * (1 - w) + Vector(b) * w).normalized()


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def lift(f):
    """0 = hand on the lap, 1 = emerald at eye level. Rises after the forklift has gone (140-180),
    holds with a small float, lowers 200-240; back on the lap well before the loop point."""
    return smooth((f - 140) / 40) - smooth((f - 200) / 40)


ORDER = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
         "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
         "RightShoulder", "RightArm", "RightForeArm", "RightHand",
         "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"]


def pose_for(f):
    t = (f - F0) / LOOP
    tau = 2 * math.pi * t
    w = lift(f)
    breathe = math.sin(tau * 4)
    rot = {}                                   # armature-space rotations (3x3) for ORDER bones
    # pelvis upright, slight sway
    rot["Hips"] = (C2A @ Euler((math.radians(-4 + 0.6 * breathe), 0, math.radians(2 * math.sin(tau))))
                   .to_matrix() @ C2A.inverted()) @ rest("Hips")
    tw = cam_yaw * 0.3 * (1 - 0.6 * w)          # chest turns towards the camera, less while admiring the gem
    for i, n in enumerate(("Spine", "Spine1", "Spine2")):
        lean = (0.06, 0.12, 0.14)[i] + 0.012 * breathe
        rot[n] = aim(n, (0, -lean, 1), pre=Matrix.Rotation(tw * (i + 1) / 3, 4, "Z"))
    rot["Neck"] = aim("Neck", (0, -0.12, 1), pre=Matrix.Rotation(tw, 4, "Z"))
    # right arm: lap -> eye level, palm up all the way
    u = lerp_dir((-0.2, -0.28, -0.94), (-0.3, -0.72, -0.12), w)
    fa = lerp_dir((0.3, -0.95, 0.08), (0.28, -0.55, 0.78), w)
    hd = lerp_dir((0.12, -0.99, 0.05), (0.2, -0.97, 0.1), w)
    hover = 0.15 * w * math.sin(tau * 5)       # tiny float while it is up
    rot["RightArm"] = aim("RightArm", u, (0, 0, -1), lerp_dir((0.0, -0.3, -0.9), (0, -0.9, 0.3), w))
    rot["RightForeArm"] = aim("RightForeArm", (fa.x, fa.y, fa.z + hover), (0, 0, -1), (0.2, 0.0, 1))
    rot["RightHand"] = aim("RightHand", hd, (0, 0, -1), (0, 0, 1))
    # left arm: straight down beside the hip, hand on the fender
    rot["LeftArm"] = aim("LeftArm", (0.24, 0.28, -0.93), (0, 0, -1), (0.0, 0.9, 0.2))
    rot["LeftForeArm"] = aim("LeftForeArm", (0.14, 0.18, -0.97), (0, 0, -1), (0.0, 0.9, 0.2))
    rot["LeftHand"] = aim("LeftHand", (0.1, -0.35, -0.93), (0, 0, -1), (0, 0.4, -0.9))
    # legs over the edge, shins swinging
    for side, sx, ph in (("Left", 1, 0.0), ("Right", -1, 2.4)):
        rot[side + "UpLeg"] = aim(side + "UpLeg", (0.07 * sx, -0.97, -0.2))
        a = math.radians(14 + 16 * math.sin(tau * 3 + ph))
        rot[side + "Leg"] = aim(side + "Leg", (0.02 * sx, -math.sin(a), -math.cos(a)))
        b = a + math.radians(62)
        rot[side + "Foot"] = aim(side + "Foot", (0.03 * sx, -math.sin(b), -math.cos(b)))
    return rot, w


def head_pose(f, gem_c, w):
    """Look from the camera-ish direction towards the emerald as it rises."""
    head_c = to_char(pose["Head"].translation)
    to_gem = gem_c - head_c
    yaw_g, pitch_g = math.atan2(to_gem.x, -to_gem.y), math.atan2(-to_gem.z, to_gem.xy.length)
    yaw_c, pitch_c = cam_yaw * 0.55, math.radians(4)
    k = smooth(w * 1.4)
    yaw, pitch = yaw_c + (yaw_g - yaw_c) * k, pitch_c + (pitch_g - pitch_c) * k
    yaw += math.radians(3) * math.sin(2 * math.pi * (f - F0) / LOOP * 2)
    return C2A @ (Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(pitch, 3, "X")) @ C2A.inverted() @ rest("Head")


def to_char(p_arm):
    return K.inverted() @ p_arm


HIPS_C = Vector((0, 0.03, SURFACE + 0.165))     # pelvis bone head: sit bones ~16 cm below it


def chain(rot):
    """Pose matrices (armature space) from rotations, walking parent -> child from the rest offsets."""
    out = {}
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
            if R is None:          # keep the rest relation to the parent (shoulders, fingers, toes, ...)
                R = (par.to_3x3().normalized() @ rel.to_3x3().normalized())
                if n == "RightHandThumb1":
                    R = R @ Matrix.Rotation(math.radians(-32), 3, "X")    # lay the thumb along the palm
                elif "Thumb" in n:
                    pass                                                   # thumb keeps its rest spread
                elif "RightHand" in n and n != "RightHand":
                    R = R @ Matrix.Rotation(math.radians(9), 3, "X")      # relaxed open fingers
                if "LeftHand" in n and n != "LeftHand":
                    R = R @ Matrix.Rotation(math.radians(14), 3, "X")
            M = Matrix.Translation(head) @ R.to_4x4()
        out[n] = M
    return out


# ---------------------------------------------------------------- key every frame
act = D.actions.new("Hero_Sit")
rig.animation_data_create()
rig.animation_data.action = act
for pb in rig.pose.bones:
    pb.rotation_mode = "QUATERNION"
gem = D.objects["Hero_Emerald"]
for f in range(F0, F1 + 1):
    rot, w = pose_for(f)
    pose = chain(rot)
    # where the emerald will be (the palm, 0.6 along the hand bone, + its bob offset)
    hand = pose["RightHand"]
    palm = hand @ Vector((0, bones[P + "RightHand"].length * 0.6, 0))
    gem_c = to_char(palm) + Vector((0, 0, 0.09))
    rot["Head"] = head_pose(f, gem_c, w)
    pose = chain(rot)
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
for fc in act.layers[0].strips[0].channelbag(rig.animation_data.action_slot).fcurves:
    for k in fc.keyframe_points:
        k.interpolation = "LINEAR"

# softer emerald: the glow was clipping to a white blob
glow = D.objects.get("Hero_Emerald_Glow")
if glow:
    glow.data.energy = 4.0
em = gem.data.materials[0].node_tree.nodes["Principled BSDF"]
em.inputs["Emission Strength"].default_value = 0.12
# Defender sneakers: the scan's own colour texture (texgen_1), plus a light bump from its luminance
SHOE_TEX = sys.argv[sys.argv.index("--") + 2] if len(sys.argv) > sys.argv.index("--") + 2 else None
shoe_mat = D.objects["Hero_Shoe_Left"].data.materials[0] if "Hero_Shoe_Left" in D.objects else None
if shoe_mat and SHOE_TEX:
    nt = shoe_mat.node_tree
    for n in [n for n in nt.nodes if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL")]:
        nt.nodes.remove(n)
    b = nt.nodes["Principled BSDF"]
    img = D.images.load(SHOE_TEX)
    img.pack()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.62
    b.inputs["Sheen Weight"].default_value = 0.25

# point lights render as glowing spheres to the camera in Cycles: keep their light, hide the bulbs
for ob in D.objects:
    if ob.type == "LIGHT" and ob.data.type in ("POINT", "SPOT"):
        ob.visible_camera = False

# soft key light on the hero from camera left, so the hoodie and the pose read in the dark
key = D.objects.new("Hero_Key", D.lights.new("Hero_Key", "AREA"))
key.data.energy, key.data.size, key.data.color = 35, 1.2, (0.75, 0.88, 1.0)
scn.collection.objects.link(key)
seat3 = Vector((SEAT.x, SEAT.y, 1.25))
key.location = seat3 + Vector((-2.4, 1.6, 1.2))
key.rotation_euler = (seat3 - key.location).to_track_quat("-Z", "Y").to_euler()
scn.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT, "cam_yaw", round(math.degrees(cam_yaw), 1))
